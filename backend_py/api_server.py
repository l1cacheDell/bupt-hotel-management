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
    Room,
    User
)

from scheduler import (
    ScheduleTask,
    scheduler_thread_func,
    add_task_to_queue,
    stop_event
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
    next_available_room_number = await Room.filter(status='available').first()
    if next_available_room_number is None:
        return {"status": 1024, "message": "No available room."}
    else:
        try:
            await User.create(name=client_name, identity_card=client_id, room_number=next_available_room_number)
            await Room.filter(id=next_available_room_number).update(status='occupied')
            return {"status": 200, "message": "Checkin success."}
        except Exception as e:
            logger.error(f"Checkin failed: {e}")
            return {"status": 500, "message": "Checkin failed."}

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
    # TODO: 检查ServedRooms的状态
    client_name = request.client_name
    try:
        now_time = datetime.datetime.now()
        await User.filter(name=client_name).update(check_out_time=now_time, bill=10086.0)   # TODO: 这里需要明算账
        usr = await User.filter(name=client_name).first()
        room_number = usr.room_number
        await Room.filter(room_number=room_number).update(status='available')
        return {"status": "OK"}
    except Exception as e:
        logger.error(f"Checkout failed: {e}")
        return {"status": 500, "message": "Checkout failed."}
    

@app.post("/api/turn_on")
async def turn_on(request: TurnOnRequest):
    # 开空调
    return {"status": "OK"}

@app.post("/api/turn_off")
async def turn_off(request: TurnOffRequest):
    # 关空调
    return {"status": "OK"}

@app.post("/api/set_temperature")
async def set_temperature(request: SetTemperatureRequest):
    # 设置温度
    return {"status": "OK"}

@app.post("/api/set_speed")
async def set_speed(request: SetSpeedRequest):
    # 设置空调速度
    return {"status": "OK"}

@app.get("/api/query_room_info")
async def query_room_info(request: QueryRoomInfoRequest):
    # 直接访问db
    return {"status": "OK"}

@app.get("/api/query_schedule")
async def query_schedule():
    # 直接访问RoomServe
    return {"status": "OK"}


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)