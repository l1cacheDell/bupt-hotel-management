from pydantic import BaseModel

class Config(BaseModel):
    hotel_layers: int
    room_per_layer: int

bupt_hotel_config = Config(
    hotel_layers=5,
    room_per_layer=5
)