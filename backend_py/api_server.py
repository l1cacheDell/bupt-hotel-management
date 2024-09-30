from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn
import asyncio
import threading
from loguru import logger

import datetime

# ==================== User Defined Modules ==================
from server_utils import (
    CheckinRequest,
    CheckoutRequest,
    TurnOnRequest,
    TurnOffRequest,
    SetTemperatureRequest,
    SetSpeedRequest,
    QueryRoomInfoRequest
)

from sql_utils import (
    init_db,
    close_db,
    summarize_bill,
    Room,
    User
)

from scheduler import (
    ScheduleTask,
    scheduler_thread_func,
    add_task_to_queue,
    query_serving_queue,
    stop_event,
    schedule_cache
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    sche_thread = threading.Thread(target=scheduler_thread_func)
    sche_thread.start()
    logger.info("Scheduler thread started.")
    try:
        yield
    finally:
        stop_event.set()
        sche_thread.join()
        logger.info("Scheduler thread stopped.")

        await close_db()

        logger.info("DB connection closed.")
        logger.info("Server stopped gracefully.")

app = FastAPI(lifespan=lifespan)

# ==================== 联调测试-公用API接口 ===================

@app.post("/api/checkin")
async def checkin(request: CheckinRequest):
    """checkin: 入住的路由函数
        入住的路由函数可以直接对数据库进行操作。因为入住了之后不会自动打开空调，需要用户手动打开。
        
        需要对两个表格进行操作：
        
            1. 搜索`房间表`，查找第一个空闲的房间。如果没有找到空闲的房间，return 1024 code，message就是 No available room.
            2. 向`用户表`中添加信息：用户名字，用户身份证，房间id，剩下的三个字段不用管。
            3. 更新`房间表`，将该房间的状态设置为`occupied`。
    """
    client_name, client_id = request.client_name, request.client_id
    next_available_room = await Room.filter(status='available').first()
    if next_available_room is None:
        return {"status": 1024, "message": "No available room."}
    else:
        try:
            next_available_room_number = next_available_room.room_number
            await User.create(name=client_name, identity_card=client_id, room_number=next_available_room_number)
            await Room.filter(room_number=next_available_room_number).update(status='occupied')
            return {"status": "OK", "allocate_room": next_available_room_number}
        except Exception as e:
            logger.error(f"Checkin failed: {e}")
            return {"status": "OK", "message": "Checkin failed."}

@app.post("/api/checkout")
async def checkout(request: CheckoutRequest):
    """checkout: 退房的路由函数
    
        退房的路由函数可以直接对数据库进行操作。不需要检查空调是否关闭。
        
        这个问题的trick是：判断空调是否开启，就看它在不在ServedRooms里面就完事，如果在就是开着的；如果不在就没开。
        
        如果在，那就从ServedRooms里面踢出它，算账，就完事。
        
        如果不在就直接算账。

        对数据库的操作，有两个：
        
            - 第一个是`用户表`添加check_out_time，然后在`bill`里面写清数字。
            - 第二个是`房间表`更新状态为`available`。

    """
    client_name = request.client_name
    try:
        now_time = datetime.datetime.now()
        usr = await User.filter(name=client_name).first()
        if usr is not None:
            room_number = usr.room_number
            room_number_str = str(room_number)
            isInCache = schedule_cache.has_room(room_number_str)
            if isInCache:
                schedule_cache.remove_room(room_number_str)
            else:
                logger.error(f"Room {room_number_str} not in cache. This operation may trigger unexpected behavior.")
                
            # 还需要从ServedRooms里面踢出这个房间，因为有可能在退房的时候，顾客根本就没有关空调，空调在退房之前都还是在serving状态。
            # 这个off类型的任务，就会实现：移除ServedRooms、持久化到数据库
            add_task_to_queue(ScheduleTask(room_number=room_number, op_type='off', op_value='null'))
            await asyncio.sleep(1.5)
            
            # 这里需要明算账
            bill = await summarize_bill(room_number, client_name)
            if bill != -1.0:
                await User.filter(name=client_name).update(check_out_time=now_time, bill=bill)   

            # 需要检查房间的状态：speed和temperature必须去除，设置为空值
            await Room.filter(room_number=room_number).update(status='available', speed=None, temperature=None)
            
            # 要删除用户User表，以便下一次入住
            await User.filter(name=client_name).delete()
            return {"status": "OK", "bill": bill}
        else:
            return {"status": 404, "message": "Client not found, please contact admin."}
    except Exception as e:
        logger.error(f"Checkout failed: {e}")
        return {"status": 500, "message": "Checkout failed."}
    

@app.post("/api/turn_on")
async def turn_on(request: TurnOnRequest):
    """需要对数据库进行任何操作，因为在初始化的时候，房间的温度、风速都是没有设置的
        只需要把这个房间放入ServedRooms里面、放入waiting_queue里面就行。

        其中，持久化到数据库、放入waiting_queue的逻辑，通过传递一个ScheduleTask来实现

    Args:
        request (TurnOnRequest): 成员变量：room_number，是哪个房间打开了空调

    Returns:
        dict: status: OK
    """
    room_number = request.room_number
    room_number_str = str(room_number)
    isInCache = schedule_cache.has_room(room_number_str)
    if isInCache:
        schedule_cache.remove_room(room_number_str)
        schedule_cache.add_room(room_number_str)
        logger.error(f"Room {room_number_str} already in cache. We removed it and add it again. This operation may trigger unexpected behavior.")
    else:
        schedule_cache.add_room(room_number_str)
        logger.info(f"Room {room_number_str} added to cache.")

    schedule_task_speed = ScheduleTask(
        room_number=room_number,
        op_type='speed',
        op_value='medium'
    )
    schedule_task_temp = ScheduleTask(
        room_number=room_number,
        op_type='temperature',
        op_value='26'
    )

    add_task_to_queue(schedule_task_speed)
    add_task_to_queue(schedule_task_temp)

    return {"status": "OK"}

@app.post("/api/turn_off")
async def turn_off(request: TurnOffRequest):
    """不需要对数据库进行任何操作，只需要把这个房间从ServedRooms里面移除、从waiting_queue里面移除。
        并且要落到详单里面去，这个记录是怎么样一个情况。

    Args:
        request (TurnOnRequest): 成员变量：room_number，是哪个房间关闭了空调

    Returns:
        dict: status: OK
    """
    room_number = request.room_number
    room_number_str = str(room_number)
    isInCache = schedule_cache.has_room(room_number_str)
    if isInCache:
        schedule_cache.remove_room(room_number_str)
        logger.info(f"Room {room_number_str} removed from cache.")
    else:
        logger.error(f"Room {room_number_str} not in cache. This operation may trigger unexpected behavior.")
    
    schedule_task_off = ScheduleTask(
        room_number=room_number,
        op_type='off',
        op_value='null'
    )
    add_task_to_queue(schedule_task_off)

    return {"status": "OK"}

@app.post("/api/set_temperature")
async def set_temperature(request: SetTemperatureRequest):
    """发送一个Task给Scheduler，不需要进入详单，也不需要更新ServedRooms，注意，我们这里讨论的是空调温度。
        至于室温怎么变动，不是我们关心的事情。

        所以，比如说上一秒空调温度是26度，下一秒16度，也是可以办到的。

        **我们只关心空调温度，不关心室温怎么变化。**

    Args:
        request (SetTemperatureRequest): 
            + room_number: 房间号
            + temperature: 被设置的温度，这里仅仅允许整型。不允许浮点型。

    Returns:
        dict: status: OK
    """
    room_number = request.room_number
    target_temperature = request.temperature

    schedule_task_temp = ScheduleTask(
        room_number=room_number,
        op_type='temperature',
        op_value=str(target_temperature)
    )

    add_task_to_queue(schedule_task_temp)

    return {"status": "OK"}

@app.post("/api/set_speed")
async def set_speed(request: SetSpeedRequest):
    """封装一个task交给scheduler，让scheduler来处理。
        注意，在这个地方scheduler是会更新详单的。

    Args:
        request (SetTemperatureRequest): 
            + room_number: 房间号
            + speed: 被设置的风速。

    Returns:
        dict: status: OK
    """
    room_number = request.room_number
    target_speed = request.speed

    schedule_task_speed = ScheduleTask(
        room_number=room_number,
        op_type='speed',
        op_value=target_speed
    )

    add_task_to_queue(schedule_task_speed)

    return {"status": "OK"}

@app.get("/api/query_room_info")
async def query_room_info(request: QueryRoomInfoRequest):
    # 直接访问db
    room_number = request.room_number
    room = await Room.filter(room_number=room_number).first()
    if room is None:
        return {"status": 404, "message": "Room not found."}
    else:
        temperature = await Room.filter(room_number=room_number).values('temperature').first()
        speed = await Room.filter(room_number=room_number).values('speed').first()
        # TODO: 还要查询账单的信息，因此每生成一条详单，就要在bill上面加一笔账。
        user = await User.filter(room_number=room_number).first()
        if user:
            user_name = user.name
            bill = await summarize_bill(room_number, user_name)
            return {"status": "OK", 
                    "temperature": temperature['temperature'], 
                    "speed": speed['speed'],
                    "bill": bill}
        else:
            return {"status": 404, "message": "Client name not found."}


@app.get("/api/query_schedule")
async def query_schedule():
    # 直接访问ServedRooms
    serving_queue, waiting_queue = query_serving_queue(log_level="null")
    return {"status": "OK", "serving_queue": serving_queue, "waiting_queue": waiting_queue}


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8080)