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

# ============= 多线程都会访问的全局变量 ==============
schedule_task_queue: Deque[ScheduleTask] = deque([])
task_queue_lock = threading.Lock()
stop_event = threading.Event()
# ====================================================

# ============= 本线程内访问的变量 ================
# 我们在联调验收的时候，设置服务队列为3，等待队列为2，所以在这里就先行设置队列长度了。如果后续情况有变，可自行更改
serving_queue: Deque[ScheduleItem] = deque([], maxlen=3)
waiting_queue: Deque[ScheduleItem] = deque([], maxlen=2)

# 在step()的后面，决定要入库的消息都放到db_queue中
db_queue: Deque[DBQueueItem] = deque([])

# 定义全局变量 RoomServe，key是房间号，value是一个字典，记录房间的风速、温度，这个value的长度只能为2.
RoomServe: Dict[str, Dict[str, str]] = {}

# ====================================================

def initialize_room_serve():
    global RoomServe
    # 此处我们联合验收的时候，假设一共有5层楼，每一层楼5个房间，也就是101-105, 501-505
    for i in range(1, 6):
        for j in range(1, 6):
            RoomServe[f"{i}0{j}"] = {}  # 先置为空

# wrapper function, 避免主线程直接操作schedule_task_queue
def add_task_to_queue(task: ScheduleTask):
    with task_queue_lock:  # 加锁
        schedule_task_queue.append(task)  # 添加任务到队列

def need_step() -> bool:
    """判断是否需要step，因为step的依据其实并不是每隔一秒钟、两秒钟。那如果我一个step()函数里面的内容，一秒钟之内完不成呢？第二次step的指令
    又来了，那岂不是直接撞车。或者造成程序的堵塞了？所以我们需要判断到底是否需要step()的函数，一方面是为了让step()的执行更加顺畅、不至于阻塞
    另一方面是避免CPU过于繁忙，或者CPU过于空闲，如果需要step的话，上一次step完了继续step下一次就行，没必要非要等满一秒钟才继续执行。

    相当于，之前的程序模型是:
    1 - 1 - 1 - 1 - 1 - 1 每隔一秒钟迭代一次， 但是容易出问题。（比如step没法在一秒钟之内完成，下一次的step信号又来了）
    现在的程序模型是：
    0.52 - 0.96 - 1.3 - 0.2 - 1.01 - 0.45 - 0.63 不定时迭代，只要需要进行step，那就立即step，好处就是不会积压任务，因为只有上一次完成了下一次
    才会开始。坏处可能就是会导致送风不是那么规律，但是是可以接受的。
    """
    global serving_queue, waiting_queue, db_queue
    return True

async def step():
    with task_queue_lock:  # 加锁
        while len(schedule_task_queue) > 0:
            task = schedule_task_queue.popleft()  # 取出任务
            pass

def scheduler_thread_func():
    initialize_room_serve()

    # set event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    while not stop_event.is_set():
        signal = need_step()
        if signal:
            loop.run_until_complete(step())
        else:
            loop.run_until_complete(asyncio.sleep(0.2)) # 避免CPU过于繁忙

    loop.close()