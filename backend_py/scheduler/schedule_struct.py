from pydantic import BaseModel
import datetime

class ScheduleItem(BaseModel):
    room_number: int
    now_speed: str  # high, medium, low
    last_speed: str=None  # high, medium, low, 因为第一次加入的时候，是没有last_speed的，所以可以为空
    start_time: datetime.datetime = None
    end_time: datetime.datetime = None

class DBQueueItem(BaseModel):
    room_number: int
    op_type: str    # temperature, speed
    op_value: str   # [new_temperatue] or [high, medium, low]
    start_time: datetime.datetime = None    # 可以为空
    end_time: datetime.datetime = None      # 可以为空

class ScheduleTask(BaseModel):
    room_number: int
    op_type: str    # temperature, speed, off
    op_value: str   # [new_temperatue] or [high, medium, low]