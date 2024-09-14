import pandas as pd
import argparse
import time
import threading

import requests
from typing import List

FILENAME = './test_case_empty.xlsx'

url = None
port = None

room_map = {
    '房间1': 101,
    '房间2': 102,
    '房间3': 103,
    '房间4': 104,
    '房间5': 105,
}

def read_excel_case(filename):
    df = pd.read_excel(filename, sheet_name='测试用例')
    return df.iloc[2:28, 0:6]

class Action:
    def __init__(self, room_id: str, input: str):
        self.room_id = int(room_id)
        self.input = input
        
    def post(self):
        if self.input == '开机' or self.input == '关机':
            self.api = '/api/turn_on' if self.input == '开机' else '/api/turn_off'
            params = {
                'room_number': self.room_id
            }
        elif self.input == '高' or self.input == '中' or self.input == '低':
            self.api = '/api/setSpeed'
            speed_map = {
                '高': "high",
                '中': "medium",
                '低': "low"
            }
            params = {
                'room_number': self.room_id,
                'speed': speed_map[self.input]
            }
        else:
            self.api = '/api/setTemperature'
            params = {
                'room_number': self.room_id,
                'temperature': int(self.input)
            }
        try:
            res = requests.post(url + ':' + str(port) + self.api, json=params, timeout=5)
        except requests.Timeout:
            print("请求超时,重新发送")
            res = requests.post(url + ':' + str(port) + self.api, json=params)

time_lock = [False] * 26
condition = threading.Condition()


def thread_request(actions: List[List[Action]]):
    global time_lock, condition
    try:
        # 发起请求
        for idx, action_list in enumerate(actions):
            for action in action_list:
                print('第%d分钟，%d，%s' % (idx, action.room_id, action.input))
                try:
                    action.post()
                except Exception as e:
                    print(f"请求失败: {e}")
                    exit(0)
                time.sleep(0.4)
        
            with condition:
                time_lock[idx] = True
                time.sleep(1.5)
                condition.notify_all()
            time.sleep(10)
    except KeyboardInterrupt:
        print("线程请求被中断")
        return

roomInfo = None
scheduleInfo = None

def thread_query(actions):
    global time_lock, condition
    try:
        api_room_info = '/api/query_room_info/'
        api_schedule = '/api/query_schedule'
        df_rooms = pd.DataFrame()
        df_schedule = pd.DataFrame()
        for idx, _ in enumerate(actions):
            with condition:
                condition.wait_for(lambda: time_lock[idx])
            print('第%d分钟' % idx)
            tmp_df = pd.DataFrame()
            for room_id in room_map.values():
                params = {
                    'room_number': room_id
                }
                try:
                    res = requests.get(url + ':' + str(port) + api_room_info, params=params, timeout=5)
                except requests.Timeout:
                    print("请求超时,重新发送")
                    res = requests.get(url + ':' + str(port) + api_room_info, params=params)
                data_dict = res.json()
                # convert to a dataframe
                data = [data_dict]
                columns_order = ['cur_temperature', 'set_temperature', 'speed', 'bill']
                this_df = pd.DataFrame(data, columns=columns_order)
                tmp_df = pd.concat([tmp_df, this_df], axis=1)
                time.sleep(0.5)
            try:
                res2 = requests.get(url + ':' + str(port) + api_schedule, timeout=5)
            except requests.Timeout:
                print("请求超时,重新发送")
                res2 = requests.get(url + ':' + str(port) + api_schedule)
                    
            df_rooms = pd.concat([df_rooms, tmp_df], axis=0)
            print(df_rooms)
            
            data_schedule = res2.json()
            serving_queue = ['', '', '']
            waiting_queue = ['', '']
            for idx, value in enumerate(data_schedule['serving_queue']):
                serving_queue[idx] = str(value)
            for idx, value in enumerate(data_schedule['waiting_queue']):
                waiting_queue[idx] = str(value)
            
            df1 = pd.DataFrame([serving_queue])
            df2 = pd.DataFrame([waiting_queue])
            df_cat = pd.concat([df1, df2], axis=1)
            df_schedule = pd.concat([df_schedule, df_cat], axis=0)
            print(df_schedule)
            
    except KeyboardInterrupt:
        print("线程查询被中断")
        return
    
    global roomInfo, scheduleInfo
    roomInfo = df_rooms
    scheduleInfo = df_schedule

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-u',
                        '--url', 
                        type=str, 
                        default='127.0.0.1')
    parser.add_argument('-p',
                        '--port', 
                        type=int, 
                        default=4000)
    args = parser.parse_args()

    url = args.url
    port = args.port
    
    url = 'http://' + url
    
    # read excel case
    case_df = read_excel_case(FILENAME)
    
    # 表格中的数据在取用的时候全部变成str格式
    # 遍历每一行
    actions = []    # 一个二级列表
    for index, row in case_df.iterrows():
        time_ = row['时间(min)']
        # 遍历该行
        action_once = []
        for room in case_df.columns[1:]:
            operation = row[room]   # 取每个房间的信息
            if not pd.isna(operation):
                # 如果房间有操作，则记录
                tmp_op = str(operation)
                room_id = room_map[room]
                op = []
                if '，' in tmp_op:
                    op = tmp_op.split('，')
                else:
                    op.append(tmp_op)
                for item in op:
                    action_once.append(Action(room_id, item))
                    
        actions.append(action_once)

    thread1 = threading.Thread(target=thread_request, args=(actions,), daemon=True)
    thread2 = threading.Thread(target=thread_query, args=(actions,), daemon=True)
    
    thread1.start()
    
    time.sleep(1)
    
    thread2.start()
    
    try:
        # 等待线程完成
        thread1.join()
        thread2.join()
    except KeyboardInterrupt:
        print("主程序中断")
    df = pd.read_excel(FILENAME, sheet_name='测试用例')
    target1 = df.iloc[2:28, 6:26]
    target2 = df.iloc[2:28, 27:32]
    assert target1.size == roomInfo.size
    assert target2.size == scheduleInfo.size
    # df.iloc[2:28, 6:26] = roomInfo.values
    # df.iloc[2:28, 27:32] = scheduleInfo.values
    
    # create a file to store the result
    writer = pd.ExcelWriter('result.xlsx')
    df.to_excel(writer, sheet_name='测试用例', index=False)
    roomInfo.to_excel(writer, sheet_name='房间信息', index=False)
    scheduleInfo.to_excel(writer, sheet_name='调度信息', index=False)
    writer.save()