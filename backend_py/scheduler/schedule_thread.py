# 我们尽量不适用OOP来复杂化项目。在这里所有使用到的class都仅仅是为了声明结构体，而不是定义任何成员函数

from typing import Dict, Deque
import datetime
from collections import deque
import asyncio
import time
import threading

from scheduler.schedule_struct import (
    ScheduleItem,
    DBQueueItem,
    ScheduleTask
)

from server_config import bupt_hotel_config
from scheduler.schedule_cache import ScheduleCache
from sql_utils import DetailedRecord, User

from loguru import logger

# ============= 多线程都会访问的全局变量 ==============
schedule_task_queue: Deque[ScheduleTask] = deque([])
task_queue_lock = threading.Lock()
stop_event = threading.Event()
# ====================================================

# ============= 本线程内访问的变量 ================
# 我们在联调验收的时候，设置服务队列为3，等待队列为2。如果后续情况有变，可自行更改
serving_queue_size = int(bupt_hotel_config.room_per_layer * 0.6)
serving_queue: Deque[ScheduleItem] = deque([], maxlen=serving_queue_size)

waiting_queue_size = bupt_hotel_config.room_per_layer - serving_queue_size
waiting_queue: Deque[ScheduleItem] = deque([], maxlen=waiting_queue_size)

# 在step()的后面，决定要入库的消息都放到db_queue中
db_queue: Deque[DBQueueItem] = deque([])

schedule_cache = ScheduleCache()

# ====================================================

# wrapper function, 避免主线程直接操作schedule_task_queue
def add_task_to_queue(task: ScheduleTask):
    with task_queue_lock:  # 加锁
        schedule_task_queue.append(task)  # 添加任务到队列
        
def handle_task_queue():
    global schedule_task_queue, schedule_cache, db_queue, waiting_queue, serving_queue
    # 除了打开
    with task_queue_lock:  # 加锁
        while len(schedule_task_queue) > 0:
            task = schedule_task_queue.popleft()  # 取出任务
            
            room_number = task.room_number
            op_type = task.op_type
            op_value = task.op_value
            
            match op_type:
                case "temperature": # 这是最简单的一种情况，所以先写
                    # 1. 检查有没有开空调。如果没有就先开空调。
                    # 判断的依据就是有没有在ServedRooms里面
                    isInCache = schedule_cache.has_room(str(room_number))
                    if not isInCache:
                        waiting_queue.append(ScheduleItem(room_number=room_number, now_speed="medium")) # 还没开始serving，不能计时
                        schedule_cache.add_room(str(room_number))
                    
                    # 更新cache，并且直接更新数据库
                    schedule_cache.update_temperature(str(room_number), op_value)   
                    db_queue.append(DBQueueItem(room_number=room_number, op_type=op_type, op_value=op_value))
                case "speed":
                    # 检查有没有开空调，也就是在不在ServedRooms里面
                    isInCache = schedule_cache.has_room(str(room_number))
                    if not isInCache:
                        # 加入队列
                        waiting_queue.append(ScheduleItem(room_number=room_number, now_speed=op_value)) # 还没开始serving，不能计时
                        schedule_cache.add_room(str(room_number))
                        # 这种情况，因为仅仅是开空调，所以不需要更新数据库
                        continue
                    
                    # 对于持久化的逻辑，其实有一个关键点：任何一个ScheduleItem都会出队。而且它结算的时候，就是在出队的时候。
                    # 不管是因为优先级下降，被挤到waiting_queue中了，还是因为临时改变了风速。反正只有在出队的时候才被结算。
                    # 那么，我们的思路就是：先更新ServedRooms。然后在serving_queue队首的那个Item出队的时候，看看是否与ServedRooms
                    # 里面记录的风速一不一致。在这个时候做统一更改。
                    #
                    # 在这里已经属于是在cache里面了，两个队列里面也肯定有。按照上面的思路，在这里就是修改ServedRooms里面的状态就完事。
                    schedule_cache.update_speed(str(room_number), op_value)
                case "off":
                    pass
                case _:
                    logger.error(f"unknown op_type: {op_type}")

def need_step() -> bool:
    """判断是否需要step，因为step的依据其实并不是每隔一秒钟、两秒钟。那如果我一个step()函数里面的内容，一秒钟之内完不成呢？第二次step的指令
    又来了，那岂不是直接撞车。或者造成程序的堵塞了？所以我们需要判断到底是否需要step()的函数，一方面是为了让step()的执行更加顺畅、不至于阻塞
    另一方面是避免CPU过于繁忙，或者CPU过于空闲，如果需要step的话，上一次step完了继续step下一次就行，没必要非要等满一秒钟才继续执行。

    相当于，之前的程序模型是:
        1 - 1 - 1 - 1 - 1 - 1 
        每隔一秒钟迭代一次， 但是容易出问题。（比如step没法在一秒钟之内完成，下一次的step信号又来了）
    现在的程序模型是:
        0.52 - 0.96 - 1.3 - 0.2 - 1.01 - 0.45 - 0.63 
        不定时迭代，只要需要进行step，那就立即step，好处就是不会积压任务，因为只有上一次完成了下一次才会开始。坏处可能就是会导致送风不是那
        么规律，但是是可以接受的。
    """
    global serving_queue, waiting_queue, db_queue
    return True


def update_item_status(schedule_item: ScheduleItem) -> ScheduleItem:
    # 返回一个完备的ScheduleItem体，所有字段都不为空
    global schedule_cache
    schedule_item.end_time = datetime.datetime.now()
        
    current_speed = schedule_cache.get_room_speed(str(schedule_item.room_number))
    schedule_item.last_speed = schedule_item.now_speed
    if current_speed != schedule_item.now_speed:
        schedule_item.now_speed = current_speed
        
    return schedule_item

async def add_record(item: ScheduleItem):
    serving_speed = item.last_speed
    duration = item.end_time - item.start_time
    room_number = item.room_number
    
    bill_rate = {"low": 0.1, "medium": 0.2, "high": 0.3}
    
    user = await User.filter(room_number=room_number).first()
    if user:
        user_name = user.name
        await DetailedRecord.create(user_name=user_name, 
                                    room_numbe=room_number,
                                    serving_speed=serving_speed,
                                    start_time=item.start_time,
                                    end_time=item.end_time,
                                    bill=(duration.total_seconds() / 60) * bill_rate[serving_speed])  # 60秒钟为单位计算
    else:
        logger.error(f"room_number: {room_number} not found in User table.")

async def step_queue():
    # 注意，下面这一堆逻辑，只为了搞懂两个点：
    # 1. 加入serving_queue的是谁: 有可能是serving queue的队首，它出来了又进去；有可能是waiting queue的队首
    # 2. 离开serving_queue的是serving queue的第一个元素，它到达哪里去？
    
    leaving_item: ScheduleItem = None
    if len(serving_queue) == 0 and len(waiting_queue) == 0:
        return  # 没意义，不迭代
    
    if len(waiting_queue) == 0 and len(serving_queue) > 0:
        # 在serving_queue中迭代
        leaving_item = serving_queue.popleft()
        new_item = update_item_status(leaving_item)
            
        await add_record(new_item)
        
        # 更新元素时间，加入serving queue队尾
        new_item.start_time = datetime.datetime.now()
        new_item.end_time = None
        serving_queue.append(leaving_item)
    else:
        if len(serving_queue) < serving_queue_size:
            # 有空位，这种情况直接进来，从waiting_queue中取出一个元素，加入到serving_queue中
            # 这种情况就是：1 - 1, 3
            # 迭代之后就是：1 - 3 - 1, 1
            # 先让waiting_queue的元素进来，然后再把serving queue原来的队头，放到队尾
            
            leaving_item = serving_queue.popleft()
            new_item = update_item_status(leaving_item)
            
            # 结算离开的元素
            await add_record(new_item)
            
            # 先不慌，先把waiting queue里面的元素拿进来
            join_item = waiting_queue.popleft()
            join_item.start_time = datetime.datetime.now()
            serving_queue.append(join_item)
            
            
            # 更新元素时间，加入serving queue队尾
            new_item.start_time = datetime.datetime.now()
            new_item.end_time = None
            serving_queue.append(new_item)
            
        else:
            # 检查waiting queue，如果队首元素的优先级比serving queue的队首元素的优先级高或者相同，那么就允许入队
            # 比如：2 - 3 - 3, 3
            # 迭代之后就是：3 - 3 - 3, 2
            
            # 但是如果是：3 - 3 - 1, 2
            # 这个时候不能抢占式入队。因为1还处于刚刚加入serving queue的状态。要等到2轮过后，当1为队首的时候，才能把waiting queue的2加入进去
            # 两轮之后：
            # 1 - 3 - 3, 2
            # 再过一轮：
            # 3 - 3 - 2, 1
            # 这样的逻辑有什么好处呢：避免强行插队。你不能说风速优先级高，当场就插队了，这是不利于维护系统和谐性的。在一次step中，从一个数理完备的逻辑来讲
            # 最多同时只能有一个元素入队、出队。
            # 如果你强行挤占，那么就会一次性出入队很多元素，自己搞不清楚，把问题复杂化了。
            
            # 还需要额外注意的是，只有这个条件分支是会发生挤占的情况。其他分支都不会发生serving queue与waiting queue元素互相挤占的情况。
            # 其他两个条件分支，要么是waiting queue是空的，要么是serving queue有空位，都是直接加入就完事。
            leaving_item = serving_queue.popleft()  # 老规矩，先出队队首元素
            new_item = update_item_status(leaving_item) # 更新风速
            # 现在就要决定这个new_item，到底是降落回waiting queue，还是插入到serving queue的队尾
            speed_mapping = {
                "low": 1,
                "medium": 2,
                "high": 3
            }
            if speed_mapping[waiting_queue[0].now_speed] >= speed_mapping[new_item.now_speed]:
                # 这个时候，new_item要进入waiting_queue里面。waiting_queue的队首要进去serving_queue里面
                inserted_item = waiting_queue.popleft()
                inserted_item.start_time = datetime.datetime.now()
                serving_queue.append(inserted_item)
                
                # 结算离开的元素
                await add_record(new_item)
                
                # new_item重新, 加入waiting queue队尾
                new_item.start_time = None
                new_item.end_time = None
                waiting_queue.append(new_item)
            else:
                # 不能发生置换，重新加入队尾
                
                # 结算离开的元素
                await add_record(new_item)
                
                # 更新元素时间，加入serving queue队尾
                new_item.start_time = datetime.datetime.now()
                new_item.end_time = None
                serving_queue.append(new_item)

async def step():
    handle_task_queue()
    await step_queue()


def scheduler_thread_func():
    # set event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while not stop_event.is_set():
        signal = need_step()
        if signal:
            loop.run_until_complete(step())
        else:
            loop.run_until_complete(asyncio.sleep(0.1)) # 避免CPU过于繁忙

    loop.close()