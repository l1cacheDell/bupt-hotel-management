# -*- coding: UTF-8 -*-

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO, send, emit

import json
import threading
import multiprocessing
import time
from master import *
from master import trans_roomid_to_id
global MASTER
global center
MASTER = Master()

center = MASTER.center_data()

app = Flask('server')
CORS(app)
app.config['SECRET_KEY'] = '199624f47e49f3fb1e3f66484f4f7814'
socketio = SocketIO(app, cors_allowed_origins="*")

MASTER.socketio = socketio


@socketio.on('connect')
def handle_connect():
    print('received connection!')


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected!')


@socketio.on('message')
def handle_message(message):
    print("receive: " + message)


@app.route('/')
@app.route('/home')
def home():
    return "Server Home"


@socketio.on('update_rooms')
def handle_update_rooms():
    d = MASTER.get_all_room()
    # print(d)
    emit("getRooms", d)


@app.route('/api/login', methods=['POST'])
def login():
    req = request.get_json(force=True)
    print(req)
    if MASTER.login(req['account'], req['password']) == False:
        return jsonify({'identity': 9})
    return jsonify({'identity': MASTER.login(req['account'], req['password']),
                    'status': 200})

@app.route('/api/rooms/checkIn', methods=['POST'])
def checkIn():
    req = request.get_json(force=True)
    print(req)
    req['checkInDate'] = time.strftime('%Y-%m-%d %H:%M:%S ', time.localtime(time.time()))
    req['haveCheckIn'] = True
    id = trans_roomid_to_id(int(req['room_number']))
    MASTER.slaves[id].name = req['name']
    MASTER.slaves[id].idCard = req['idCard']
    MASTER.slaves[id].checkInDate = req['checkInDate']
    MASTER.slaves[id].haveCheckIn = req['haveCheckIn']
    MASTER.slaves[id]._showDetails = req['_showDetails']
    print(MASTER.slaves[id].__dict__)
    MASTER.checkIn(req['room_number'], req['name'], req['idCard'], req['checkInDate'], req['_showDetails'])
    print("checkin")
    d = MASTER.get_all_room()
    socketio.emit("getRooms", d)
    return req


@app.route('/api/rooms/checkOut', methods=['POST'])
def checkOut():
    req = request.get_json(force=True)
    print(req)
    for k in req.keys():
        if k == 'room_number':
            continue
        if k == 'power' or k == '_showDetails':
            req[k] = 'False'
        else:
            req[k] = ''
    id=trans_roomid_to_id(int(req['room_number']))
    #MASTER.slaves[int(req['id'])].__dict__.update(MASTER.slave_init[int(req['id'])])
    MASTER.slaves[id].__dict__.update(MASTER.slave_init[id])
    now_time = time.strftime('%Y-%m-%d %H:%M:%S ', time.localtime(time.time()))
    print(1)
    MASTER.checkOut(req['room_number'], now_time)
    socketio.emit("getRooms", MASTER.get_all_room())
    # 其实这个return还是会被rooms信息覆盖，走个形式
    return req

# 从房间开机
@app.route('/api/turn_on', methods=['POST'])
def turn_on_Power():
    req = request.get_json(force=True)
    print(req)
    #id = int(req['id'])
    roomid = int(req['room_number'])
    id = trans_roomid_to_id(roomid)
    print(id)
    MASTER.slaves[id]['power'] = 1
    def task(roomid):
        MASTER.slaveFilpPower(str(roomid))
    send_and_wait_task(task, roomid)
    MASTER.respond_to_request()
    MASTER.update_state()
    data = MASTER.get_one_room(req['room_number'])
    socketio.emit("getRooms", MASTER.get_all_room())
    return jsonify(data)

# 从房间关机
@app.route('/api/turn_off', methods=['POST'])
def turn_off_Power():
    req = request.get_json(force=True)
    print(req)
    roomid = int(req['room_number'])
    id = trans_roomid_to_id(roomid)
    MASTER.slaves[id]['power'] = 0
    def task(roomid):
        MASTER.slaveFilpPower(str(roomid))
    send_and_wait_task(task, roomid)
    MASTER.respond_to_request()
    MASTER.update_state()
    data = MASTER.get_one_room(req['room_number'])
    socketio.emit("getRooms", MASTER.get_all_room())
    return jsonify(data)

# 房间设置预期温度
@app.route('/api/setTemperature', methods=['POST'])
def expecttemp_set():
    req = request.get_json(force=True)
    print(req)
    roomid = int(req['room_number'])
    id = trans_roomid_to_id(roomid)
    MASTER.slaves[id].expectTemp = int(req['temperature'])
    def task(roomid):
        MASTER.ExpectTemSet(str(roomid), int(req['temperature']))
    send_and_wait_task(task, roomid)
    MASTER.respond_to_request()
    MASTER.update_state()
    data = MASTER.get_one_room(str(roomid))
    print(data)
    socketio.emit("getRooms", MASTER.get_all_room())
    return jsonify(data)

# 房间设置初始温度
@app.route('/api/setTemperature_init', methods=['POST'])
def init_temp_set():
    req = request.get_json(force=True)
    print(req)
    roomid = int(req['room_number'])
    id = trans_roomid_to_id(roomid)
    MASTER.slaves[id].temp = int(req['temperature'])
    MASTER.slaves[id].init_temper = int(req['temperature'])
    def task(roomid):
        MASTER.InitTemSet(str(roomid), int(req['temperature']))
    send_and_wait_task(task, roomid)
    MASTER.respond_to_request()
    MASTER.update_state()
    data = MASTER.get_one_room(req['room_number'])
    print(data)
    socketio.emit("getRooms", MASTER.get_all_room())
    return jsonify(data)

# 房间设置风速
@app.route('/api/setSpeed', methods=['POST'])
def slave_set_speed():
    req = request.get_json(force=True)
    print(req)
    roomid = int(req['room_number'])
    id = trans_roomid_to_id((roomid))
    speed = req['speed'].lower()
    MASTER.slaves[id]['speed'] = speed

    def task(roomid):
        MASTER.setSpeed(roomid, req['speed'])

    send_and_wait_task(task, roomid)
    MASTER.respond_to_request()
    MASTER.update_state()
    data = MASTER.get_one_room(req['room_number'])
    socketio.emit("getRooms", MASTER.get_all_room())
    return jsonify(data)



# 查看房间当前信息
@app.route('/api/query_room_info/', methods=['GET'])
def query_room_info():
    # req = request.get_json(force=True) 不能这么写
    
    # print(req)
    roomid = request.args.get('room_number', default=1, type=int)  # 获取查询参数
    data = MASTER.get_one_room(str(roomid))
    d={
        'cur_temperature': data['temp'],
        'set_temperature': int(data['expectTemp']),
        'speed': str(data['speed']),
        'bill': data['cost']
    }
    return jsonify(d)




def send_and_wait_task(t, id):
    def task():
        t(id)
        return
    MASTER.request_queue.put(task)





@app.route('/api/rooms/updateRooms', methods=['POST'])
def slave_updateRooms():
    req = request.get_json(force=True)
    for slave_state in req:
        MASTER.slaves[int(slave_state['id'])].__dict__.update(slave_state)

        slave = MASTER.slaves[int(slave_state['id'])]
        db = pymysql.connect("localhost", DATABASE_USER_NAME,
                             DATABASE_USER_PASSWORD, DATABASE_SCHEMA)  # 打开数据库连接
        cursor = db.cursor()
        cursor.execute("update slave set name=%s, idCard=%s where id=%s",
                       (slave.name, slave.idCard, slave.id))
        cursor.close()
        db.commit()
        db.close()
    return jsonify([s.__dict__ for s in MASTER.slaves])


# 查看房间账单
@app.route('/api/query_room_bill', methods=['GET'])
def query_room_bill():
    roomid = request.args.get('room_number', default=1, type=int)
    data = MASTER.get_room_bill(str(roomid))
    return jsonify(data)

# 查看调度信息
@app.route('/api/query_schedule', methods=['GET'])
def query_schedule():
    serving_queue = []
    waiting_queue = []
    schedule_all = MASTER.schedule_queue
    blowing_list = MASTER.blowing_list
    schedule = list(set(schedule_all) - set(blowing_list))
    for i in schedule:
        roomid = trans_id_to_roomid(i)
        waiting_queue.append(roomid)
    for i in blowing_list:
        roomid = trans_id_to_roomid(i)
        serving_queue.append(roomid)
    data = {
        'serving_queue': serving_queue,
        'waiting_queue': waiting_queue
    }
    return jsonify(data)

# 详单
@app.route('/api/detail_bill', methods=['GET'])
def query_room_detail():
    roomid = request.args.get('room_number', default=1, type=int)
    data = MASTER.get_room_detail(str(roomid))
    return jsonify(data)

@app.route('/api/form/roomList', methods=['GET'])
def get_room_list():
    ret = MASTER.get_room_list()
    print(ret)
    return jsonify(ret)



if __name__ == "__main__":
    th = threading.Thread(target=MASTER.background, name="我是后台线程")
    th.daemon = True
    th.start()
    socketio.run(app, allow_unsafe_werkzeug=True, port=4000)
    # use this on server: 
    
    # socketio.run(app, host='0.0.0.0', allow_unsafe_werkzeug=True, port=4000)
    print("server.py中: main 函数退出.")
