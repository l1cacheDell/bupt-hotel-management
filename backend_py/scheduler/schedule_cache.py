from typing import Dict
import threading

# def initialize_room_serve():
#     global ServedRooms
#     # 此处我们联合验收的时候，假设一共有5层楼，每一层楼5个房间，也就是101-105, 501-505
#     for i in range(1, bupt_hotel_config.hotel_layers + 1):
#         for j in range(1, bupt_hotel_config.room_per_layer + 1):
#             ServedRooms[f"{i}0{j}"] = {"temperature": 26, "speed": "medium"}  # 先置为初始默认状态

# 定义全局变量 ServedRooms，key是房间号，value是一个字典，记录房间的风速、温度，这个value字典的长度只能为2.
# 为了便于管理数据，cache里面的数据全部都转化为字符串格式。
# 
# 这个ServedRooms在这里扮演一种cache的角色，作为路由层与数据库持久化层之间的cache。因为有一些数据属于in-flight状态
# 暂时不能加入数据库，并且还需要迭代。所以这个时候就要做一层cache，作为调度的中间层。
# 同时，这个ServedRooms的意思是正在被serving的Rooms。不管是在哪个queue里面，都需要在这个字典中先进行注册。
# 因为如果后续有开关空调的操作，都先要经过这里，然后才是到下一层。

# 考虑到封装与外部获取、交互的必要性，这里还是写一个类。避免直接暴露字典。
class ScheduleCache:
    def __init__(self):
        self.ServedRooms: Dict[str, Dict[str, str]] = {}
        self.lock = threading.Lock()

    def has_room(self, room_number_str: str) -> bool:
        with self.lock:
            return room_number_str in self.ServedRooms
    
    def get_room_temperature(self, room_number_str: str) -> str:
        with self.lock:
            if room_number_str in self.ServedRooms:
                return self.ServedRooms[room_number_str]["temperature"]
            else:
                return "unknown"
        
    def get_room_speed(self, room_number_str: str) -> str:
        with self.lock:
            if room_number_str in self.ServedRooms:
                return self.ServedRooms[room_number_str]["speed"]
            else:
                return "unknown"
    
    def add_room(self, room_number_str: str) -> bool:
        with self.lock:
            if room_number_str not in self.ServedRooms:
                self.ServedRooms[room_number_str] = {"temperature": '26', "speed": "medium"}    # NOTE: 一定是字符串！不要写数字。
                return True
            else:
                return False
        
    def remove_room(self, room_number_str: str) -> bool:
        with self.lock:
            if room_number_str in self.ServedRooms:
                del self.ServedRooms[room_number_str]
                return True
            else:
                return False
        