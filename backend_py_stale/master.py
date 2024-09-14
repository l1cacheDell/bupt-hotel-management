from datetime import datetime
import inspect
import threading
import pymysql
import json
import os
import time
from queue import Queue
from slave import *
import copy
# import csv
from mysqlTable import *

NORMAL_TEMPERATURE = 25

DATABASE_USER_NAME = "root"
DATABASE_USER_PASSWORD = "1234"
# DATABASE_USER_PASSWORD = "dyz20020324"
DATABASE_SCHEMA = "backend"
DATABASE_USER_PORT = 3306
DATABASE_USER_HOST = "localhost"
lock = threading.Lock()
speed_rec = ['medium'] * 40  # 初始speed
serving_time = [0]*40
room_serial_dict = {
}

def trans_roomid_to_id(roomid):
    id = ((int(roomid) - 100) // 100) * 10 + (int(roomid) - 1) % 100
    return id
def trans_id_to_roomid(id):
    roomid = ((id//10)+1)*100 + id % 10 + 1
    return roomid

class Master(Base):
    def __init__(self):
        self.db = pymysql.connect(
            host=DATABASE_USER_HOST,  # 默认用主机名
            port=DATABASE_USER_PORT,
            user=DATABASE_USER_NAME,  # 默认用户名
            password=DATABASE_USER_PASSWORD,  # mysql密码
            database=DATABASE_SCHEMA,  # 库名
            charset='utf8'  # 编码方式
        )
        self.cursor = self.db.cursor()  # 使用 cursor() 方法创建一个游标对象 cursor

        # 建表
        self.cursor.execute(identity_drop)
        self.cursor.execute(identity_create)

        self.cursor.execute(slave_drop)
        self.cursor.execute(slave_create)

        self.cursor.execute(oprecord_drop)
        self.cursor.execute(oprecord_create)

        self.cursor.execute(checkrecord_drop)
        self.cursor.execute(checkrecord_create)

        self.cursor.execute(bill_drop)
        self.cursor.execute(bill_create)

        self.cursor.execute(detail_drop)
        self.cursor.execute(detail_create)
        self.db.commit()

        self.add_identity('admin', 'password', '0')
        self.add_identity('reception', 'password', '1')

        self.power = False
        self.state = 'Standby'
        self.mode = "Cold"
        self.temp = 25
        self.rate = 1   # 费率为一元一度

        self.frequence = 120  # 刷新频率120s
        self.opened_time = 0
        self.rec_no_detail = 1

        # 直接将各个slave抽象成为master的一个部件
        #self.SLAVE_NUM = 40
        self.SLAVE_NUM = 5

        self.slaves = []
        roomid=[101,102,103,104,105,106,107,108,109,110,201,202,203,204,205,206,207,208,209,210,
                301,302,303,304,305,306,307,308,309,310,401,402,403,404,405,406,407,408,409,410]
        for i in range(self.SLAVE_NUM):
            self.slaves.append(Slave(int(roomid[i]), ''))
            self.init_slave(self.slaves[i].__dict__)

        # 管理员列表
        # self.admins = []
        self.slave_init = copy.deepcopy(self.slaves)

        # HTTP请求队列
        self.signals = [threading.Condition() for i in range(self.SLAVE_NUM)]
        self.request_queue = Queue()

        # 调度队列
        self.blowing_list = []
        self.schedule_queue = []
        self.schedule_queue_medium = []  # 优先级调度
        self.schedule_queue_high = []
        self.schedule_queue_low = []

        self.socketio = None

    # center_page

    def center_data(self) -> dict:
        center = {}
        center['power'] = self.power
        center['state'] = self.state
        center['mode'] = self.mode
        center['temp'] = self.temp
        center['freq'] = self.frequence
        return center

    # def __del__(self):
    #     self.cursor.close()  # 关闭游标
    #     self.db.close()     # 关闭数据库连接

    # init_room

    def init_slave(self, d: dict):
        try:
            sql = 'insert into slave values(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)'
            self.cursor.execute(sql, (d['id'], d['name'], d['idCard'], d['checkInDate'],
                                      d['cost'], d['expectTemp'], d['speed'], d['temp'], False, '0', '0',False, False))
            self.db.commit()
            # print("insert slave", end=' ')
        except:  # 主键约束
            sql = 'update slave set name=%s, idCard=%s, checkInDate=%s, cost=%s, expectTemp=%s, speed=%s, temp=%s, \
                    power=%s, timer=%s, min=%s, haveCheckIn=%s, showDetails=%s where id = %s'
            self.cursor.execute(sql, (d['name'], d['idCard'], d['checkInDate'], d['cost'],
                                      d['expectTemp'], d['speed'], d['temp'], False, '0', '0',False, False, d['id']))
            self.db.commit()
            # print("update slave", end=' ')

    # /rooms/路由 all_rooms_info

    def get_all_room(self) -> list:
        rooms = []
        db = pymysql.connect(
            host=DATABASE_USER_HOST,  # 默认用主机名
            port=DATABASE_USER_PORT,
            user=DATABASE_USER_NAME,  # 默认用户名
            password=DATABASE_USER_PASSWORD,  # mysql密码
            database=DATABASE_SCHEMA,  # 库名
            charset='utf8'  # 编码方式
        )  # 打开数据库连接
        cursor = db.cursor()
        lock.acquire()
        cursor.execute("select * from slave")
        lock.release()
        db.commit()
        while 1:
            res = cursor.fetchone()
            if res is None:  # 表示已经取完结果集
                break
            id = trans_roomid_to_id(int(res[0]))
            d = {
                'id': res[0],
                'haveCheckIn': False if res[10] == '0' else True,
                'name': res[1],
                'idCard': res[2],
                'checkInDate': res[3],
                'cost': res[4],
                'expectTemp': res[5],
                'speed': res[6],
                'temp': res[7],
                'power': False if res[8] == '0' else True,
                '_showDetails': False if res[11] == '0' else True,
                'is_blowing_in': self.slaves[id].is_blowing_in
            }
            rooms.append(d)
        cursor.close()
        db.close()
        return rooms

    # 获取当前房间的记录号
    def get_CheckRecord_Record(self, roomId: str):
        # 对于当前房间号，获取其入住状态为1的记录，即入住中的记录
        sql = 'select Record from checkrecord where id = %s and state =%s'
        #lock.acquire()
        self.cursor.execute(sql, (roomId, '1'))
        #print(6)
        self.db.commit()
        #lock.release()
        rec_no = ''
        if self.cursor is not None:  # 注意这里: 单纯判断cursor是否为None是不够的
            row = self.cursor.fetchone()
            if row is not None:
                rec_no = row[0]

        return rec_no

    # 从控机获取当前房间的状态
    def get_slave_power(self, roomId: str):
        try:  # 如果开始数据库没有数据怎么办...
            sql = 'select power from slave where id = %s'
            lock.acquire()
            self.cursor.execute(sql, (roomId))
            power = self.cursor.fetchone()[0]
            self.db.commit()
            lock.release()
        except Exception as reason:
            power = '0'
            print(reason)
        return power  # 对于当前房间号，获取其从控机的开关机情况

    # 获取当前的入住记录数
    def get_CheckRecord_count(self):
        query = " select count(*) from checkrecord "
        db = pymysql.connect(
            host=DATABASE_USER_HOST,  # 默认用主机名
            port=DATABASE_USER_PORT,
            user=DATABASE_USER_NAME,  # 默认用户名
            password=DATABASE_USER_PASSWORD,  # mysql密码
            database=DATABASE_SCHEMA,  # 库名
            charset='utf8'  # 编码方式
        )  # 打开数据库连接
        cursor = db.cursor()
        cursor.execute(query)
        count = cursor.fetchone()[0]
        db.commit()
        cursor.close()
        db.close()
        return count

    # 获取操作记录记录数
    def get_OpRecord_count(self):
        query = " select count(*) from oprecord "
        lock.acquire()
        self.cursor.execute(query)
        count = self.cursor.fetchone()[0]
        self.db.commit()
        lock.release()
        return count

    # 获取送风时间,读出计时器的秒值
    def get_slave_timer(self, roomId: str):
        sql = 'select timer from slave where id = %s'
        db = pymysql.connect(
            host=DATABASE_USER_HOST,  # 默认用主机名
            port=DATABASE_USER_PORT,
            user=DATABASE_USER_NAME,  # 默认用户名
            password=DATABASE_USER_PASSWORD,  # mysql密码
            database=DATABASE_SCHEMA,  # 库名
            charset='utf8'  # 编码方式
        )  # 打开数据库连接
        cursor = db.cursor()
        cursor.execute(sql, (roomId))
        tim = cursor.fetchone()[0]
        db.commit()
        cursor.close()
        db.close()
        return tim
    # 获取送风时间,读出计时器的分值
    def get_slave_min(self, roomId: str):
        sql = 'select min from slave where id = %s'
        db = pymysql.connect(
            host=DATABASE_USER_HOST,  # 默认用主机名
            port=DATABASE_USER_PORT,
            user=DATABASE_USER_NAME,  # 默认用户名
            password=DATABASE_USER_PASSWORD,  # mysql密码
            database=DATABASE_SCHEMA,  # 库名
            charset='utf8'  # 编码方式
        )  # 打开数据库连接
        cursor = db.cursor()
        cursor.execute(sql, (roomId))
        min = cursor.fetchone()[0]
        db.commit()
        cursor.close()
        db.close()
        return min
    # 更新计时器的秒值
    def update_slave_timer(self, roomId: str, timer: str):
        sql = 'update slave set timer=%s where id = %s'
        lock.acquire()
        self.cursor.execute(sql, (timer, roomId))
        lock.release()
        self.db.commit()

    # 更新计时器的分值
    def update_slave_min(self, roomId: str, min: str):
        sql = 'update slave set min=%s where id = %s'
        lock.acquire()
        self.cursor.execute(sql, (min, roomId))
        lock.release()
        self.db.commit()

    # 获取风速
    def get_slave_speed(self, roomId: str):
        sql = 'select speed from slave where id = %s'
        db = pymysql.connect(
            host=DATABASE_USER_HOST,  # 默认用主机名
            port=DATABASE_USER_PORT,
            user=DATABASE_USER_NAME,  # 默认用户名
            password=DATABASE_USER_PASSWORD,  # mysql密码
            database=DATABASE_SCHEMA,  # 库名
            charset='utf8'  # 编码方式
        )  # 打开数据库连接
        cursor = db.cursor()
        cursor.execute(sql, (roomId))
        speed = cursor.fetchone()[0]
        db.commit()
        cursor.close()
        db.close()
        return speed

    # 获取新的阶段用电量 = 功率 * 时间
    def cal_power(self, roomId: str, speed: str):
        current_power = 0
        tim = self.get_slave_timer(roomId)
        if speed == 'high':
            current_power = 1 * float(tim) / 60
        if speed == 'medium':
            current_power = 0.5 * float(tim) / 60
        if speed == 'low':
            current_power = (1/3) * float(tim) / 60
        return current_power

    # 获取新的总费用 = 原花费 + 费率 * 用电量
    def cal_cost(self, roomId: str, current_power: float):
        # 获取原先费用
        sql = 'select cost from slave where id = %s'

        #lock.acquire()
        self.cursor.execute(sql, roomId)
        #lock.release()
        cost = self.cursor.fetchone()[0]
        # 获取价钱
        cost = round(float(cost), 2) + self.rate * round(float(current_power), 2)
        return cost

    # 更新某房间的送风量和费用，插入新记录
    # type初始为0；1，开关机；2，设定温度 temp1 -> temp2；3，设定风速 speed1 -> speed2;4，每一分钟的例行更新；5,是否送风
    def update_cost_and_wind(self, roomId: str, typ: str, old: str, new: str):  # time以秒为单位
        speed = ' '
        if typ =='1' and new == '1':
            query_time = time.strftime('%Y-%m-%d %H:%M:%S ', time.localtime(time.time()))
            rec_no_detail = self.rec_no_detail
            speed = old  # 如果是变更风速，把老风速保留，计算上一阶段的cost
            sql1 = 'insert into detail(record, room_id, query_time, speed, rate, have_done) values(%s, %s, %s, %s, %s, %s)'
            db = pymysql.connect(
                host=DATABASE_USER_HOST,  # 默认用主机名
                port=DATABASE_USER_PORT,
                user=DATABASE_USER_NAME,  # 默认用户名
                password=DATABASE_USER_PASSWORD,  # mysql密码
                database=DATABASE_SCHEMA,  # 库名
                charset='utf8'  # 编码方式
            )  # 打开数据库连接
            lock.acquire()
            cursor = db.cursor()
            cursor.execute(sql1, (rec_no_detail, roomId, query_time, 'medium', self.rate, "0"))
            lock.release()
            db.commit()
            cursor.close()
            room_serial_dict[str(roomId)] = self.rec_no_detail
            self.rec_no_detail = self.rec_no_detail + 1
            print(room_serial_dict)
            db.close()
        if typ != '3':
            speed = self.get_slave_speed(roomId)  # 如果不是变更风速就按从原来的风速变化
        else:
            self.serve_done(roomId)
            id = trans_roomid_to_id((roomId))
            self.slaves[id]['is_blowing_in'] = False
            query_time = time.strftime('%Y-%m-%d %H:%M:%S ', time.localtime(time.time()))
            rec_no_detail = self.rec_no_detail
            speed = old  # 如果是变更风速，把老风速保留，计算上一阶段的cost
            sql1 = 'insert into detail(record, room_id, query_time, speed, rate, have_done) values(%s, %s, %s, %s, %s, %s)'
            db = pymysql.connect(
                host=DATABASE_USER_HOST,  # 默认用主机名
                port=DATABASE_USER_PORT,
                user=DATABASE_USER_NAME,  # 默认用户名
                password=DATABASE_USER_PASSWORD,  # mysql密码
                database=DATABASE_SCHEMA,  # 库名
                charset='utf8'  # 编码方式
            )  # 打开数据库连接
            lock.acquire()
            cursor = db.cursor()
            cursor.execute(sql1, (rec_no_detail, roomId, query_time, new, self.rate, "0"))
            lock.release()
            db.commit()
            cursor.close()
            room_serial_dict[str(roomId)] = self.rec_no_detail
            self.rec_no_detail = self.rec_no_detail + 1
            print(room_serial_dict)
            db.close()
        current_power = self.cal_power(roomId, speed)
        print(61)
        cost = self.cal_cost(roomId, current_power)
        print(62)
        # 对于当前房间号，获取其入住状态为1的记录，即入住中的记录
        rec_no = self.get_CheckRecord_Record(roomId)
        #print(rec_no)
        #print("this op is oprated by rec_no = %s" % (rec_no))
        now_time = time.strftime('%Y-%m-%d %H:%M:%S ',time.localtime(time.time()))
        # 将slave和oprecord中的cost和wind更新
        # print("roomid = %s  wind=%s cost = %s timer = %s" %(roomId,wind, cost, run_time))
        sql = 'insert into oprecord(Record, roomid, time, type, old, new, wind, cost) values(%s, %s, %s, %s, %s, %s, %s, %s)'
        db = pymysql.connect(
            host=DATABASE_USER_HOST,  # 默认用主机名
            port=DATABASE_USER_PORT,
            user=DATABASE_USER_NAME,  # 默认用户名
            password=DATABASE_USER_PASSWORD,  # mysql密码
            database=DATABASE_SCHEMA,  # 库名
            charset='utf8'  # 编码方式
        )  # 打开数据库连接
        cursor = db.cursor()
        cursor.execute(sql, (rec_no, roomId, now_time, typ, old, new, str(round(current_power, 2)), str(round(cost, 2))))
        print(0)
        db.commit()
        cursor.execute("update slave set cost=%s where id=%s", (round(cost, 2), roomId))
        cursor.execute("update bill set cost=%s where roomid=%s", (round(cost, 2), roomId))
        db.commit()
        
        if typ == '1' and new == '0':
            sql2 = 'select timer,min,speed from slave where  id = %s '
            cursor.execute(sql2, roomId)
            res = cursor.fetchone()
            tim = int(res[0])
            min = int(res[1])
            serve_time = 60 * min + tim
            sql1 = 'update detail set serve_time=%s,cost=%s,have_done=%s  where room_id = %s and have_done = %s'
            cursor.execute(sql1, (serve_time, cost, '1', roomId, '0'))
            db.commit()
        
        cursor.close()
        db.close()
        print(7)
    def serve_start(self,roomId :str):
        sql1 = 'update detail set start_time=%s where room_id = %s and have_done = %s'
        start_time = time.strftime('%Y-%m-%d %H:%M:%S ', time.localtime(time.time()))
        db = pymysql.connect(
            host=DATABASE_USER_HOST,  # 默认用主机名
            port=DATABASE_USER_PORT,
            user=DATABASE_USER_NAME,  # 默认用户名
            password=DATABASE_USER_PASSWORD,  # mysql密码
            database=DATABASE_SCHEMA,  # 库名
            charset='utf8'  # 编码方式
        )  # 打开数据库连接
        cursor = db.cursor()
        cursor.execute(sql1,(start_time, roomId,'0'))
        db.commit()
        cursor.close()
        db.close()
    def serve_done(self,roomId :str):
        rec = room_serial_dict[str(roomId)]
        sql = 'select start_time from detail where  record = %s '
        db = pymysql.connect(
            host=DATABASE_USER_HOST,  # 默认用主机名
            port=DATABASE_USER_PORT,
            user=DATABASE_USER_NAME,  # 默认用户名
            password=DATABASE_USER_PASSWORD,  # mysql密码
            database=DATABASE_SCHEMA,  # 库名
            charset='utf8'  # 编码方式
        )  # 打开数据库连接
        cursor = db.cursor()
        lock.acquire()
        cursor.execute(sql, rec)
        lock.release()
        end_time = time.strftime('%Y-%m-%d %H:%M:%S ', time.localtime(time.time()))
        sql2 = 'select timer,min,speed from slave where  id = %s '
        lock.acquire()
        cursor = db.cursor()
        cursor.execute(sql2, roomId)
        lock.release()
        res = cursor.fetchone()
        tim = int(res[0])
        min = int(res[1])
        serve_time = 60 * min + tim
        speed = res[2]
        current_power = 0
        if speed == 'high':
            current_power = 1 * float(serve_time) / 60
        if speed == 'medium':
            current_power = 0.5 * float(serve_time) / 60
        if speed == 'low':
            current_power = (1 / 3) * float(serve_time) / 60
        cost = self.rate * round(float(current_power), 2)
        print("cost:",cost)
        sql0 = "SELECT cost FROM detail WHERE record = %s"
        sql1 = 'update detail set end_time=%s, serve_time=%s,cost=%s,have_done=%s  where record = %s'
        sql2 = 'update detail set end_time=%s,have_done=%s  where record = %s'
        lock.acquire()
        cursor.execute(sql0,rec)
        result = cursor.fetchone()[0]
        if result != None:
            cursor.execute(sql2, (end_time,  '1', rec))
        else:
            cursor.execute(sql1, (end_time, serve_time, cost, '1', rec))
        lock.release()
        db.commit()
        cursor.close()
        db.close()

    # room checkIn
    def checkIn(self, roomId: str, name: str, idCard: str, 
                date: str, show: bool):
        #print(7)
        db = pymysql.connect(
            host=DATABASE_USER_HOST,  # 默认用主机名
            port=DATABASE_USER_PORT,
            user=DATABASE_USER_NAME,  # 默认用户名
            password=DATABASE_USER_PASSWORD,  # mysql密码
            database=DATABASE_SCHEMA,  # 库名
            charset='utf8'  # 编码方式
        )  # 打开数据库连接
        #print(0)
        #print(roomId)
        cursor = db.cursor()
        #print(8)

        lock.acquire()
        sql = 'update slave set name=%s, idCard=%s, checkInDate=%s, timer=%s, haveCheckIn=%s, showDetails=%s where id = %s'
        cursor.execute(sql, (name, idCard, date, '0', True, show, roomId))
        #print(1)
        lock.release()
        db.commit()
        #print(7)
        # 入住，check in会增加一次开房记录
        sql = 'insert into checkrecord(Record,idcard, id, checkInDate, checkOutDate, state) values(%s, %s, %s, %s, %s, %s)'
        sql1 = 'insert into bill( record, roomid,checkInDate, checkOutDate, cost) values(%s, %s, %s, %s, %s)'
        sql2 = 'insert into identity( account,password,identity) values(%s, %s, %s)'
        rec_num = self.get_CheckRecord_count()
        #print(rec_num)
        lock.acquire()
        #print(1)
        cursor.execute(sql, (rec_num, idCard, roomId, date, 'NULL', '1'))
        #print(2)
        cursor.execute(sql1, (rec_num, roomId, date, 'NULL', 'NULL'))
        #print(3)

        cursor.execute(sql2, (roomId, idCard, '2'))
        #print(4)

        lock.release()
        cursor.close()
        db.commit()
        # 把开房编号赋值给从控机
        id=trans_roomid_to_id(int(roomId))
        self.slaves[id].record = rec_num
        db.close()

    # 离开，把这一次入住记录改为离开
    def checkOut(self, roomId: str, date: str):
        # 查看房间空调状态是否为关机，不是关机就计算费用，插入记录
        sql = 'select power from slave where id = %s'

        lock.acquire()
        self.cursor.execute(sql, roomId)
        lock.release()
        res = self.cursor.fetchone()[0]
        if res != '0':  # 数据库中状态变为关机就计算费用，同时清零原计时，后台运行的线程会停止计时
            self.update_cost_and_wind(roomId, '1', '1', '0')
            sql = 'update slave set power=(not power), showDetails=%s, haveCheckIn = %s where id = %s'
            lock.acquire()
            self.cursor.execute(sql, (False, '0', roomId))
            lock.release()
            self.db.commit()
            self.update_slave_timer(roomId, 0)
            self.update_slave_min(roomId, 0)
        # 对于当前房间号，获取其入住状态为1的记录，即入住中的记录
        id = trans_roomid_to_id(roomId)
        rec_no = self.get_CheckRecord_Record(roomId)
        # 将这个记录号的状态改为离开
        sql = 'update checkrecord set checkOutDate=%s, state=%s where Record=%s'
        sql1 = 'update bill set checkOutDate=%s where Record=%s'
        sql2 = 'DELETE FROM identity WHERE account = %s'
        lock.acquire()
        self.cursor.execute(sql, (date, '0', rec_no))
        self.cursor.execute(sql1, (date, rec_no))
        self.cursor.execute(sql2, str(roomId))
        lock.release()
        self.slave_init[id].temp = self.slaves[id].temp
        self.init_slave(self.slave_init[id])
        self.db.commit()

    # 添加人员
    def add_identity(self, account: str, password: str,identity: str) -> bool:
        try:
            sql = 'insert into identity values(%s, %s,%s )'
            lock.acquire()
            self.cursor.execute(sql, (account, password,identity))
            self.db.commit()  # 需要commit才可以提交插入
            lock.release()
        except Exception as reason:
            print("add_identity", reason)
            return False
        return True

    # 管理员登录
    def login(self, account: str, passowrd: str) -> bool:
        sql = "select * from identity where account = %s"
        lock.acquire()
        self.cursor.execute(sql, account)
        res = self.cursor.fetchone()
        lock.release()
        self.db.commit()
        if res == None or res[0] != account or res[1] != passowrd:
            return False
        else:
            return res[2]

    # 获取一个房间信息
    def get_one_room(self, roomId: str) -> dict:
        db = pymysql.connect(
            host=DATABASE_USER_HOST,  # 默认用主机名
            port=DATABASE_USER_PORT,
            user=DATABASE_USER_NAME,  # 默认用户名
            password=DATABASE_USER_PASSWORD,  # mysql密码
            database=DATABASE_SCHEMA,  # 库名
            charset='utf8'  # 编码方式
        ) # 打开数据库连接
        cursor = db.cursor()
        lock.acquire()
        cursor.execute("select * from slave where id = %s", roomId)
        lock.release()
        db.commit()
        res = cursor.fetchone()
        id = trans_roomid_to_id(int(res[0]))
        d = {
            'roomid': res[0],
            'name': res[1],
            'idCard': res[2],
            'checkInDate': res[3],
            'cost': res[4],
            'expectTemp': res[5],
            'speed': res[6],
            'temp': res[7],
            'power': False if res[8] == '0' else True,
            'haveCheckIn': False if res[11] == '0' else True,
            '_showDetails': False if res[12] == '0' else True,
            'init_temper': self.slaves[id].init_temper,
            'is_blowing_in': self.slaves[id].is_blowing_in
        }
        cursor.close()
        db.close()
        return d

    def get_room_bill(self, roomId: str) -> dict:
        db = pymysql.connect(
            host=DATABASE_USER_HOST,  # 默认用主机名
            port=DATABASE_USER_PORT,
            user=DATABASE_USER_NAME,  # 默认用户名
            password=DATABASE_USER_PASSWORD,  # mysql密码
            database=DATABASE_SCHEMA,  # 库名
            charset='utf8'  # 编码方式
        ) # 打开数据库连接
        cursor = db.cursor()
        lock.acquire()
        cursor.execute("select * from bill where roomid = %s", roomId)
        lock.release()
        db.commit()
        res = cursor.fetchone()
        d = {
            'record': res[0],
            'roomid': res[1],
            'checkInDate': res[2],
            'checkOutDate': res[3],
            'cost': res[4],
        }
        cursor.close()
        db.close()
        return d

    def get_room_detail(self, roomId: str) -> dict:
        data = []
        db = pymysql.connect(
            host=DATABASE_USER_HOST,  # 默认用主机名
            port=DATABASE_USER_PORT,
            user=DATABASE_USER_NAME,  # 默认用户名
            password=DATABASE_USER_PASSWORD,  # mysql密码
            database=DATABASE_SCHEMA,  # 库名
            charset='utf8'  # 编码方式
        )  # 打开数据库连接
        cursor = db.cursor()
        lock.acquire()
        cursor.execute("select * from detail where room_id = %s",roomId)
        lock.release()
        db.commit()
        while 1:
            res = cursor.fetchone()
            if res is None:  # 表示已经取完结果集
                break
            d = {
                'record': res[0],
                'room_id': res[1],
                'query_time': res[2],
                'start_time': res[3],
                'end_time': res[4],
                'serve_time': res[5],
                'speed': res[6],
                'cost': res[7],
                'rate': res[8],
            }
            data.append(d)
        cursor.close()
        db.close()
        return data

    # slave/flipPower
    def slaveFilpPower(self, roomId: str):
        db = pymysql.connect(
            host=DATABASE_USER_HOST,  # 默认用主机名
            port=DATABASE_USER_PORT,
            user=DATABASE_USER_NAME,  # 默认用户名
            password=DATABASE_USER_PASSWORD,  # mysql密码
            database=DATABASE_SCHEMA,  # 库名
            charset='utf8'  # 编码方式
        )  # 打开数据库连接
        sql = 'update slave set power=(not power), showDetails=%s where id = %s'
        cursor = db.cursor()
        cursor.execute(sql, (True, roomId))
        db.commit()

        sql = 'select power from slave where id = %s'
        lock.acquire()
        cursor.execute(sql, roomId)
        lock.release()
        res = cursor.fetchone()[0]
        print(res)
        if res == '0':
            # 数据库中状态变为关机就计算费用，同时清零原计时，后台运行的线程会停止计时
            lock.acquire()
            self.update_cost_and_wind(roomId, '1', '1', '0')
            lock.release()
            print(53)
            self.update_slave_timer(roomId, 0)
            self.update_slave_min(roomId, 0)
            print(54)
        else:
            # 数据库中状态变为开机开始计算费用，同时后台运行的线程会开始计时
            self.update_cost_and_wind(roomId, '1', '0', '1')
            print(55)

        cursor.close()
        db.close()

    # 设置预期温度
    def ExpectTemSet(self, roomId: str, temp: int):
        self.db.ping(reconnect=True)
        lock.acquire()
        self.cursor.execute("select expectTemp from slave where id=%s", roomId)
        res = self.cursor.fetchone()[0]
        exp_temp = temp
        self.cursor.execute(
            "update slave set expectTemp=%s, showDetails=%s where id=%s", (str(exp_temp), True, roomId))
        lock.release()
        
        self.update_cost_and_wind(roomId, '2', res, exp_temp)
        self.update_slave_timer(roomId, 0)
        self.update_slave_min(roomId, 0)
        self.db.commit()
        
    # 设置房间初始温度
    def InitTemSet(self, roomId: str, temp: int):
        self.db.ping(reconnect=True)
        lock.acquire()
        self.cursor.execute(
            "update slave set temp=%s, showDetails=%s where id=%s", (str(temp), True, roomId))
        lock.release()
        self.db.commit()
    # 速度变化，送风计时清零，计算上一阶段的费用
    def setSpeed(self, roomId: str, wind: str):
        res = self.get_slave_speed(roomId)
        lock.acquire()
        self.cursor.execute(
            "update slave set speed=%s, showDetails=%s where id=%s", (wind, True, roomId))
        lock.release()
        self.update_cost_and_wind(roomId, '3', res, wind)
        self.update_slave_timer(roomId, 0)
        self.update_slave_min(roomId, 0)
        self.db.commit()

    def get_OpRecord_id(self, Record: str):
        sql = 'select id from checkrecord where Record = {}'.format(Record)
        lock.acquire()
        self.cursor.execute(sql)
        lock.release()
        id = self.cursor.fetchone()[0]
        self.db.commit()
        return id

    def get_room_list(self):
        db = pymysql.connect(
        host=DATABASE_USER_HOST,  # 默认用主机名
            port=DATABASE_USER_PORT,
            user=DATABASE_USER_NAME,  # 默认用户名
            password=DATABASE_USER_PASSWORD,  # mysql密码
            database=DATABASE_SCHEMA,  # 库名
            charset='utf8'  # 编码方式
        )  # 打开数据库连接
        cursor = db.cursor()
        lock.acquire()
        cursor.execute("select * from slave")
        lock.release()
        db.commit()
        ret = []
        while 1:
            t = cursor.fetchone()
            temp = {}
            if t is None:
                break
            temp = {
                'id': t[0],
                'name': t[1],
                'idCard': t[2],
                'checkInDate': t[3],
                'cost': t[4],
                'expectTemp': t[5],
                'speed': t[6],
                'temp': t[7],
                'power': t[8],
                'timer': t[9],
                'haveCheckIn': t[10],
                'showDetails': t[11]
            }
            ret.append(temp)
        cursor.close()
        db.close()
        return ret

    # 获取表单staring date,ending date,starting room,ending room
    def get_form(self, sd, ed, sr, er):
        sql = "select * from oprecord where time between \"{}\" and \"{}\"".format(sd, ed)
        self.cursor.execute(sql)
        ret = []
        all_record = self.cursor.fetchall()
        count = 0
        if all_record is not None:
            count = len(all_record)

        i = 0
        while i < count:
            t = all_record[i]
            if t is None:
                break
            rid = self.get_OpRecord_id(t[0])
            if int(sr[0]) <= int(rid) and int(rid) <= int(er[0]):
                ret.append({
                    "id": rid,
                    "time": t[1],
                    "type": t[2],
                    "old": t[3],
                    "new": t[4],
                    "wind": t[5],
                    "cost": t[6]
                })
            i = i + 1
        self.db.commit()
        return ret

    def update_state(self):
        print(12)
        db = pymysql.connect(
            host=DATABASE_USER_HOST,  # 默认用主机名
            port=DATABASE_USER_PORT,
            user=DATABASE_USER_NAME,  # 默认用户名
            password=DATABASE_USER_PASSWORD,  # mysql密码
            database=DATABASE_SCHEMA,  # 库名
            charset='utf8'  # 编码方式
        )  # 打开数据库连接
        wind = {'low': 60, 'medium': 60, 'high': 60, 'Shutdown': 60} #不管开关机都是每分钟变化0.5度
        for idx, slave in enumerate(self.slaves):
            if slave['power']:
                # print(slave.speed)
                # print(speed_rec[idx])
                if slave.speed != speed_rec[idx]:  # 风速发生变化了
                    if slave.speed == 'medium':  # 现在风速是medium
                        if speed_rec[idx] == 'high':  # 以前风速是high
                            self.schedule_queue_high.remove(idx)
                            print("self.schedule_queue_high", self.schedule_queue_high)

                            self.schedule_queue = self.schedule_queue_high + self.schedule_queue_medium + self.schedule_queue_low
                        else :  # 以前风速是low
                            self.schedule_queue_low.remove(idx)
                            print("self.schedule_queue_low", self.schedule_queue_low)

                            self.schedule_queue = self.schedule_queue_high + self.schedule_queue_medium + self.schedule_queue_low
                    elif slave.speed == 'high':  # 现在是high
                        if speed_rec[idx] == 'medium':  # 以前是medium
                            self.schedule_queue_medium.remove(idx)
                            print("self.schedule_queue_medium", self.schedule_queue_medium)

                            self.schedule_queue = self.schedule_queue_high + self.schedule_queue_medium + self.schedule_queue_low

                        else:  # 以前是low
                            self.schedule_queue_low.remove(idx)
                            print("self.schedule_queue_low", self.schedule_queue_low)

                            self.schedule_queue = self.schedule_queue_high + self.schedule_queue_medium + self.schedule_queue_low
                    else:  # 现在是low
                        if speed_rec[idx] == 'high':  # 以前是high
                            self.schedule_queue_high.remove(idx)
                            print("self.schedule_queue_high", self.schedule_queue_high)
                            self.schedule_queue = self.schedule_queue_high + self.schedule_queue_medium + self.schedule_queue_low
                        else:  # 以前是medium
                            self.schedule_queue_medium.remove(idx)
                            print("self.schedule_queue_medium", self.schedule_queue_medium)

                            self.schedule_queue = self.schedule_queue_high + self.schedule_queue_medium + self.schedule_queue_low
                #if idx not in self.blowing_list and idx not in self.schedule_queue:
                if idx not in self.schedule_queue:
                    # 没有加入队列,那么将其加入到等待队列
                    speed_rec[idx] = slave.speed
                    print(speed_rec[idx])
                    if speed_rec[idx] == 'medium':
                        self.schedule_queue_medium.append(idx)
                        print("self.schedule_queue_medium", self.schedule_queue_medium)
                        self.schedule_queue = self.schedule_queue_high + self.schedule_queue_medium + self.schedule_queue_low
                    elif speed_rec[idx] == 'high':
                        self.schedule_queue_high.append(idx)
                        print("self.schedule_queue_high", self.schedule_queue_high)
                        self.schedule_queue = self.schedule_queue_high + self.schedule_queue_medium + self.schedule_queue_low
                    else:
                        self.schedule_queue_low.append(idx)
                        print("self.schedule_queue_low", self.schedule_queue_low)
                        self.schedule_queue = self.schedule_queue_high + self.schedule_queue_medium + self.schedule_queue_low
                #else:
                if idx in self.blowing_list:  # 在送风队列
                    # 该机器被调度到送风队列了,开启送风
                    if slave['is_blowing_in'] == False:
                        roomid = trans_id_to_roomid(idx)
                        self.update_cost_and_wind(roomid, '5', '0', '1')
                        print("update_cost_and_wind")
                        slave['is_blowing_in'] = True
                        self.serve_start(roomid)
                    else:
                        if len(self.schedule_queue)>= 4:
                            serving_time[idx] = serving_time[idx]+1
                            print(idx,serving_time)
                            print("self.schedule_queue_medium",self.schedule_queue_medium)
                            if serving_time[idx] == 20:    # MODIFIED
                                roomid = trans_id_to_roomid(idx)
                                speed = slave['speed']
                                print(speed)
                                self.update_cost_and_wind(roomid, '3', speed, speed)
                                print(123)
                                slave['is_blowing_in'] = False
                                if speed == "high":
                                    print("self.schedule_queue_high",self.schedule_queue_high)
                                    serving_time[idx] = 0
                                    #self.schedule_queue = self.schedule_queue_high + self.schedule_queue_medium + self.schedule_queue_low
                                elif speed == "medium":
                                    print(1)
                                    self.schedule_queue_medium.remove(idx)
                                    self.schedule_queue_medium.append(idx)
                                    # temp = self.schedule_queue_medium.pop(0)
                                    # self.schedule_queue_medium.append(temp)

                                    serving_time[idx] = 0
                                    print("self.schedule_queue_medium", self.schedule_queue_medium)
                                    self.schedule_queue = self.schedule_queue_high + self.schedule_queue_medium + self.schedule_queue_low
                                else:
                                    self.schedule_queue_low.remove(idx)
                                    self.schedule_queue_low.append(idx)
                                    # temp = self.schedule_queue_low.pop(0)
                                    # self.schedule_queue_low.append(temp)

                                    serving_time[idx] = 0
                                    print("self.schedule_queue_low", self.schedule_queue_low)
                                    self.schedule_queue = self.schedule_queue_high + self.schedule_queue_medium + self.schedule_queue_low
                        else:  # 正常工作，前面的需求少于三台
                            serving_time[idx] = 0
                else:  # 不在送风队列
                    if slave['is_blowing_in'] == True:
                        roomid = trans_id_to_roomid(idx)
                        self.update_cost_and_wind(roomid, '5', '1', '0')
                        slave['is_blowing_in'] = False
                        self.serve_done(roomid)

            else:  # 关机
                # if idx in self.blowing_list:
                #     self.blowing_list.remove(idx)
                if idx in self.schedule_queue_medium:
                    self.schedule_queue_medium.remove(idx)
                    self.schedule_queue = self.schedule_queue_high + self.schedule_queue_medium + self.schedule_queue_low
                if idx in self.schedule_queue_high:
                    self.schedule_queue_high.remove(idx)
                    self.schedule_queue = self.schedule_queue_high + self.schedule_queue_medium + self.schedule_queue_low

                if idx in self.schedule_queue_low:
                    self.schedule_queue_low.remove(idx)
                    self.schedule_queue = self.schedule_queue_high + self.schedule_queue_medium + self.schedule_queue_low

                if slave['is_blowing_in'] == True:
                    # 空调关机,送风停止
                    roomid = trans_id_to_roomid(idx)
                    self.update_cost_and_wind(roomid, '5', '1', '0')
                    slave['is_blowing_in'] = False
                    self.serve_done(roomid)

            if slave['power'] == True and slave['is_blowing_in'] == True:
                # 开机状态温度变化
                roomid = trans_id_to_roomid(idx)
                tim = int(self.get_slave_timer(str(roomid)))
                if tim != 0:
                    if tim % wind[slave.speed] == 0:
                        if float(slave.expectTemp) - float(slave.temp) >= 0.5:
                            slave.temp = str(float(slave.temp) + 0.5)
                            print("更新")
                        elif float(slave.expectTemp) - float(slave.temp) <= -0.5:
                            slave.temp = str(float(slave.temp) - 0.5)
                            print("更新")

            else:  # 关机状态温度变化
                if self.opened_time % wind['Shutdown'] == 0:
                    if slave.init_temper > float(slave.temp):
                        slave.temp = str(float(slave.temp) + 0.5)
                    elif slave.init_temper < float(slave.temp):
                        slave.temp = str(float(slave.temp) - 0.5)

            detail_str = "%s" % "1" if slave._showDetails else "0"

            cursor = db.cursor()
            roomid = trans_id_to_roomid(idx)
            lock.acquire()
            cursor.execute("update slave set name=%s, idCard=%s, temp=%s, expectTemp=%s,showDetails=%s where id=%s",
                           (slave.name, slave.idCard, slave.temp, slave.expectTemp,detail_str, str(roomid)))
            lock.release()
            db.commit()
        cursor.close()
        db.close()

    def schedule(self):
        # 各种调度算法
        # self.blowing_list = list(set(self.blowing_list))
        # self.schedule_queue = list(set(self.schedule_queue))

        # 时间片轮转
        # if self.opened_time % 4 == 0:
        #     if self.blowing_list.__len__() > 0:
        #         temp_idx = self.blowing_list[0]
        #         self.blowing_list.remove(temp_idx)
        #         self.schedule_queue.append(temp_idx)

        #         self.slaves[temp_idx]['is_blowing_in'] = False
        #         self.update_cost_and_wind(temp_idx,'5','1','0')

        # print("\033c\n")
        #print("送风队列:",self.blowing_list)
        #print("等待队列:", self.schedule_queue)
        # 取前三个元素加入到blowing_list
        print("self.schedule_queue:",self.schedule_queue)
        num_elements_to_add = min(3, len(self.schedule_queue))
        elements_to_add = self.schedule_queue[:num_elements_to_add]

        # 将元素添加到blowing_list
        self.blowing_list = elements_to_add
        print("blowing_list =", elements_to_add)

        # 设置正在送风的目标
        # for idx in elements_to_add:
        #     # 假设self.slaves是一个具有is_blowing_in属性的对象列表
        #     self.slaves[idx].is_blowing_in = True

        # if self.blowing_list.__len__() < 3:
        #     # 如果存在空余,且有空调等待送风
        #     #print("<3")
        #     if self.schedule_queue.__len__() != 0:
        #         # 取队首元素加入到送风集合
        #         print(self.schedule_queue)
        #         idx = self.schedule_queue[0]
        #         self.schedule_queue.pop(0)
        #         self.blowing_list.append(idx)
        #         print("blowing_list.append",idx)
        #         # 将目标设置为正在送风
        #         # self.slaves[idx].is_blowing_in = True



    def background(self):
        """后台处理"""
        while 1:
            try:
                self.opened_time += 1
                #print(self.opened_time)
                time.sleep(1)
                self.respond_to_request()
                self.schedule()
                self.update_state()
                # 增加送风计时的代码
                # 当修改风速时，重新计时，原来的用来计算那一段的费用
                # 每计时一分钟，也输出一个结果，用来计算费用
                for i in range(self.SLAVE_NUM):
                    roomid = trans_id_to_roomid(i)
                    power = self.get_slave_power(str(roomid))
                    if power == '1':  # 如果已经入住且当前是开机状态，就计时,并且检查计时状态，进行
                        tim = int(self.get_slave_timer(str(roomid)))
                        min = int(self.get_slave_min(str(roomid)))
                        if tim % 60 == 0 and tim != 0:  # 如果当前计满了60s，就更新一次，然后计时器归0
                            print("now time = %s" % (tim))
                            self.update_cost_and_wind(str(roomid), '4', '0', '0')
                            self.update_slave_timer(str(roomid), 0)
                            self.update_slave_min(str(roomid), min+1)
                        else:
                            if self.slaves[i].is_blowing_in == False:
                                self.update_slave_timer(str(roomid), 0)
                                self.update_slave_min(str(roomid), 0)
                            else:
                                self.update_slave_timer(str(roomid), tim + 6)
            except Exception as e:
                print(e)
                print("********出现了一下错误***********:", e)
                time.sleep(1)
                print("尝试重连")
                self.db.ping(reconnect=True)
                print("重连成功")


    def respond_to_request(self):
        # 这个函数基本没啥用的,懒得去掉了.因为这个去掉了其他也得改
        while not self.request_queue.empty():
            request = self.request_queue.get()
            request()



if __name__ == "__main__":
    master = Master()
    print(master.keys())


