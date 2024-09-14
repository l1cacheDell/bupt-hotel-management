from fastapi import FastAPI
from contextlib import asynccontextmanager
import uvicorn
import asyncio

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    
    yield
    



app = FastAPI(lifespan=lifespan)

# ==================== 联调测试-公用API接口 ===================

@app.post("/api/checkin")
async def checkin(request: CheckinRequest):
    pass
    return {"status": "OK"}

@app.post("/api/checkout")
async def checkout(request: CheckoutRequest):
    pass
    return {"status": "OK"}

@app.post("/api/turn_on")
async def turn_on(request: TurnOnRequest):
    pass
    return {"status": "OK"}

@app.post("/api/turn_off")
async def turn_off(request: TurnOffRequest):
    pass
    return {"status": "OK"}

@app.post("/api/set_temperature")
async def set_temperature(request: SetTemperatureRequest):
    pass
    return {"status": "OK"}

@app.post("/api/set_speed")
async def set_speed(request: SetSpeedRequest):
    pass
    return {"status": "OK"}

@app.get("/api/query_room_info")
async def query_room_info(request: QueryRoomInfoRequest):
    pass
    return {"status": "OK"}

@app.get("/api/query_schedule")
async def query_schedule():
    pass
    return {"status": "OK"}


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)