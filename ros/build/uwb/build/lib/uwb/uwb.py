import csv
import os
import threading
import time

import numpy as np
import rclpy
from rclpy.node import Node

from std_msgs.msg import String
from geometry_msgs.msg import PointStamped

import serial
import serial.tools.list_ports
import re
from scipy.optimize import minimize
from msg_folder.msg import UwbMsg

lock = threading.Lock()  # 確保多執行緒存取安全

class stateMachine:
    def __init__(self):
        self.status = "build_coord_1"
    def update(self):
        if self.status == "built_coord_1":
            self.status = "built_coord_2"
        elif self.status == "built_coord_2":
            self.status == "self_calibration"
        elif self.status == "self_calibration":
            self.status == "flying"

state_machine = stateMachine()
class Position:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def __str__(self): 
        return f"({self.x}, {self.y}, {self.z})"

class UWBdata(Position):
    def __init__(self, x, y, z, EUI, name, output_folder):
        super().__init__(x, y, z)
        self.EUI = EUI
        self.name = name
        self.pooling_data = {}  # 存放對應 tag 的距離數據 (tag_name -> list of (range_m, timestamp))
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        self.output_file = os.path.join(output_folder, fr"{self.name}_{timestamp}.csv")#add timestamp

        # 初始化每個 anchor 的 CSV 檔案
        with open(self.output_file, mode='w', newline='') as file:
            csv_writer = csv.writer(file)
            csv_writer.writerow(["timestamp", "tag_name", "range_m", "sample_rate"])

    def store_pooling_data(self, tag_name, range_m, timestamp):
        """儲存 UWB 距離數據，並移除過期數據"""
        if tag_name not in self.pooling_data:
            self.pooling_data[tag_name] = []
        
        self.pooling_data[tag_name].append((range_m, timestamp))
        
        # 移除超過 0.5 秒的數據
        self.pooling_data[tag_name] = [
            (r, t) for r, t in self.pooling_data[tag_name] if timestamp - t <= 0.5
        ]

        # 將數據寫入對應 anchor 的 CSV 檔案
        with open(self.output_file, mode='a', newline='') as file:
            csv_writer = csv.writer(file)
            csv_writer.writerow([time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp)), tag_name, range_m])

    def get_pooled_distances(self)->dict: # key: tag, value: avg_distance
        """回傳平均距離"""
        return {tag: sum(r for r, _ in data) / len(data) for tag, data in self.pooling_data.items() if data}


class UWBNodePublisher(Node):

    def __init__(self):
        super().__init__('uwb_publisher')
        self.publisher_ = self.create_publisher(UwbMsg, 'uwb_topic', 10)
        self.timer = self.create_timer(1.0, self.timer_callback)
        
    
        self.range_value = 0.0
        self.power_value = 0.0
        self.from_address_value = ""
        self.anchor_key_x_value = 0
        self.anchor_key_y_value = 0

    def set_message_values(self, range_value, power_value, from_address_value, anchor_key_x_value, anchor_key_y_value):
     
        self.range_value = range_value
        self.power_value = power_value
        self.from_address_value = from_address_value
        self.anchor_key_x_value = anchor_key_x_value
        self.anchor_key_y_value = anchor_key_y_value

    def timer_callback(self):
  
        msg = UwbMsg()
        msg.range = self.range_value
        msg.power = self.power_value
        msg.from_address = self.from_address_value
        msg.anchor_key_x = self.anchor_key_x_value
        msg.anchor_key_y = self.anchor_key_y_value

        self.publisher_.publish(msg)
        self.get_logger().info("Publishing:", msg)


def gps_solve(distances_to_station, stations_coordinates):
	def error(x, c, r):
		return sum([(np.linalg.norm(x - c[i]) - r[i]) ** 2 for i in range(len(c))])

	l = len(stations_coordinates)
	S = sum(distances_to_station)
	# compute weight vector for initial guess
	W = [((l - 1) * S) / (S - w) for w in distances_to_station]
	# get initial guess of point location
	x0 = sum([W[i] * stations_coordinates[i] for i in range(l)])
	# optimize distance from signal origin to border of spheres
	return minimize(error, x0, args=(stations_coordinates, distances_to_station), method='Nelder-Mead').x

def multilateration(anchor_list, multilateration_file):
    """計算最新的 3D 位置"""
    with lock:  # 確保多執行緒安全存取
        # 取得每個 tag 與每個anchor的距離。假設我想要tag1的位置，我需要anchor1, anchor2, anchor3的距離
        print("enter multilateration")
        distances = {anchor.EUI: anchor.get_pooled_distances() for anchor in anchor_list}
        tag_distances_to_anchor = {}
        for anchor_EUI in distances:
            for tag, pooled_range in distances[anchor_EUI].items():
                if tag not in tag_distances_to_anchor:
                    tag_distances_to_anchor[tag] = {}
                tag_distances_to_anchor[tag][anchor_EUI] = pooled_range # 且要依照anchor的EUI順序


    
    anchor_locations = list(np.array([anchor_list[0].x,anchor_list[0].y,anchor_list[0].z],[anchor_list[1].x, anchor_list[1].y, anchor_list[1].z],[anchor_list[2].x, anchor_list[2].y, anchor_list[2].z],[anchor_list[3].x, anchor_list[3].y, anchor_list[3].z]))
    tag_pos = {}
    for tag in tag_distances_to_anchor:
        tag_pos[tag] = Position(*gps_solve(list(tag_distances_to_anchor[tag].values()), anchor_locations))
        print(f"Tag {tag} position: {tag_pos[tag]}")

    # 將 multilateration 結果寫入 CSV 檔案
    with open(multilateration_file, mode='a', newline='') as file:
        csv_writer = csv.writer(file)
        # csv_writer.writerow([time.strftime('%Y-%m-%d %H:%M:%S'), pos.x, pos.y, pos.z])
        for tag, pos in tag_pos.items():
            csv_writer.writerow([time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())), tag, pos.x, pos.y, pos.z])
    return tag_pos


def handle_serial_data(serial_port, data_pattern, anchor_list, uwbNode_publisher):
    """處理每個 COM 連接，讀取並解析 UWB 數據"""
    ser = serial.Serial(serial_port, baudrate=9600, timeout=1)
    this_anchor = None
    anchor_find = False
    while True:
        try:
            line = ser.readline().decode('utf-8').strip()
            if line:
                match = data_pattern.search(line)
                match_sample = re.search(r'Sampling rate\s*([0-9]+):\s*([0-9.]+)\s*Hz', line) #Sampling rate 1: 4.48 Hz
                print(f"{serial_port}: {line}!")
                if match:
                    range_m = float(match.group(1))
                    power = float(match.group(2))
                    from_address = match.group(3)
                    anchor_key = f"{match.group(4)}:{match.group(5)}"
                    timestamp = time.time()
                    print("Matched!")
                    print(f"Range: {range_m} m, Power: {power} dBm, From: {from_address}, Anchor: {anchor_key}")
                
                    ##publish to uwb_topic here   
                    
                    uwbNode_publisher.set_message_values(range_m, power, from_address, anchor_key[0], anchor_key[1])    
                            
                    with lock: 
                        print("Lock acquired.")
                        if not anchor_find:
                            for anchor in anchor_list:
                                if anchor_key in anchor.EUI:
                                    this_anchor = anchor
                                    anchor_finded = True
                                    print(f"Storing data to {anchor.name}")
                                    anchor.store_pooling_data(from_address, range_m, timestamp)
                        else:
                            this_anchor.store_pooling_data(from_address, range_m, timestamp)

                    # # 將數據加入 queue
                    # data_queue.put((anchor_key, from_address, range_m, timestamp))
                elif match_sample:
                    print("Matched sample rate!")
                    target_tag = match_sample.group(1)
                    sample_rate = float(match_sample.group(2))

                    with open(this_anchor.output_file, mode='a', newline='') as file:
                        csv_writer = csv.writer(file)
                        csv_writer.writerow([time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())), f"Sample rate {target_tag}",None ,None ,sample_rate])
                elif anchor_find and this_anchor.EUI == "00:01" and "State changed" in line:
                    state_machine.update()

        except KeyboardInterrupt:
            print(f"Stopped {serial_port}")
            break

    ser.close()

def processing_thread(anchor_list, multilateration_file):
    """每 0.1 秒處理一次數據並計算位置"""
    while True:
        time.sleep(0.1)  # 讓處理頻率穩定
        multilateration(anchor_list, multilateration_file)




def main(args=None):
    rclpy.init(args=args)

    uwbNode_publisher = UWBNodePublisher()
    
    output_folder = r"C:\Users\jianh\OneDrive\Desktop\safmc\UWB_test\Serial_testing\readingSerialUwbData\output"
    start_main_timestamp = time.strftime('%Y%m%d_%H%M%S')
    multilateration_file = os.path.join(output_folder, f"multilateration_results_{start_main_timestamp}.csv")

    # 建立資料夾
    os.makedirs(output_folder, exist_ok=True)
    
    # 初始化 multilateration CSV 檔案
    with open(multilateration_file, mode='w', newline='') as file:
        csv_writer = csv.writer(file)
        csv_writer.writerow(["timestamp", "x", "y", "z"])


    data_pattern = re.compile(r'Range:\s([0-9.]+)\s*m\s+RX power:\s*(-?[0-9.]+)\s*dBm\s*distance between anchor\/tag:\s*([0-9]+)\s*from Anchor\s*([0-9]+):([0-9]+)')
    # Range: 0.00 m      RX power: -59.80 dBm distance between anchor/tag:30 from Anchor 00:01

    ports_list = list(serial.tools.list_ports.comports())
    for port in ports_list:
        print(port[0])
    anchor_list = [
        UWBdata(0, 0, 0, "00:01", "AnchorA", output_folder),
        UWBdata(0, 0, 0, "00:02", "AnchorB", output_folder),
        UWBdata(0, 0, 0, "00:03", "AnchorC", output_folder),
        UWBdata(0, 0, 0, "00:04", "AnchorD", output_folder),
    ]

    if not ports_list:
        print("No serial ports found.")
        return
    
    selected_ports = input("Enter COM ports (e.g., COM3,COM4) or 'a' for All: ").split(',')
    if 'a' in selected_ports:
        selected_ports = [comport[0] for comport in ports_list]

    # 啟動 serial 讀取執行緒
    threads = []
    for port in selected_ports:
        thread = threading.Thread(target=handle_serial_data, args=(port, data_pattern, anchor_list, uwbNode_publisher))
        threads.append(thread)
        thread.start()

    # 啟動處理執行緒
    processing = threading.Thread(target=processing_thread, args=(anchor_list, multilateration_file, uwbNode_publisher), daemon=True)
    processing.start()
    

    for thread in threads:
        thread.join() # join 是等待執行緒結束
        print("Thread joined.")
    
    
    rclpy.spin(uwbNode_publisher)
    uwbNode_publisher.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
