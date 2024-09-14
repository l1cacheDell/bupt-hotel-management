import inspect
import threading
import pymysql
import json
import os
import time

class Base:
    def keys(self):
        return self.__dict__.keys()

    def __getitem__(self, item):
        """对[]运算符进行重载"""
        return getattr(self, item)

    def __setitem__(self, key, value):
        """对[]运算符进行重载"""
        return setattr(self, key, value)

    def __repr__(self):
        return str(self.__dict__)

    def jsonify(self):
        """序列化"""
        # 写成如下形式的理由如下:
        # 1. 使用json的理由:dict直接转字符串键由单引号包着,应该用双引号
        # 2. 使用str再用eval转成字典的理由: slave对象不能用json序列化,但是可以将其转换成字符串重建成dict对象再通过json序列化
        return json.dumps(eval(str(self.__dict__)))

class Slave(Base):
    def __init__(self, roomId, idCard):
        self.id = roomId
        self.idCard = idCard
        self.name = ''
        self.checkInDate = ''
        self.cost = 0
        self.expectTemp = 25
        self.speed = 'medium'
        self.temp = 30
        self.power = False
        self.haveCheckIn = False
        self._showDetails = False

        self.record = 'NULL'
        self.init_temper = 30

        # 调度模块
        self.is_blowing_in = False

    def set_temp(self, temp: int):
        self.expectTemp = temp

    def set_speed(self, speed: int):
        self.speed = speed