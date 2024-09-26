from pydantic import BaseModel
import datetime

class ScheduleItem(BaseModel):
    room_number: int
    start_time: datetime.datetime
    end_time: datetime.datetime
    speed: str  # high, medium, low

class DBQueueItem(BaseModel):
    room_number: int
    op_type: str    # temperature, speed
    op_value: str   # [new_temperatue] or [high, medium, low]
    start_time: datetime.datetime
    end_time: datetime.datetime

class ScheduleTask(BaseModel):
    room_number: int
    op_type: str    # temperature, speed, off
    op_value: str   # [new_temperatue] or [high, medium, low]