from tortoise import Tortoise

from server_config import bupt_hotel_config
from sql_utils.schema import (
    Room
)

DATABASE_URL = "sqlite://hotel_management.db"

async def init_db():
    await Tortoise.init(
        db_url=DATABASE_URL,
        modules={"models": ["sql_utils.schema"]}
    )
    await Tortoise.generate_schemas()

    # 初始化
    room_count = await Room.all().count()
    if room_count == 0:
        # 如果一条记录都没有，那么就要初始化所有房间
        for i in range(1, bupt_hotel_config.hotel_layers + 1):
            for j in range(1, bupt_hotel_config.room_per_layer + 1):
                room_number_int = i * 100 + j
                await Room.create(
                    room_number=room_number_int,   # int
                    status='available',            # 只有available和occupied两种状态 
                    speed='medium',                # 只有low, medium, high三种速度
                    temperature=26                 # 26摄氏度
                )

async def close_db():
    await Tortoise.close_connections()