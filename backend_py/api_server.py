from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn
import asyncio
import threading
from loguru import logger

# ==================== User Defined Modules ==================
from request_model import (
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
    close_db
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
    # checkin 并不一定要开空调
    return {"status": "OK"}

@app.post("/api/checkout")
async def checkout(request: CheckoutRequest):
    # checkout 一定要检查关空调
    return {"status": "OK"}

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