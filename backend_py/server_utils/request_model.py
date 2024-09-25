from pydantic import BaseModel

class CheckinRequest(BaseModel):
    client_name: str
    client_id: str
    
class CheckoutRequest(BaseModel):
    client_name: str
    
class TurnOnRequest(BaseModel):
    room_number: int
    
class TurnOffRequest(BaseModel):   
    room_number: int
    
class SetTemperatureRequest(BaseModel):
    room_number: int
    temperature: int
    
class SetSpeedRequest(BaseModel):
    room_number: int
    speed: str
    
class QueryRoomInfoRequest(BaseModel):
    room_number: int
    