from paho.mqtt.client import Client as mqtt_client
from paho.mqtt.client import MQTTMessage
import json
import hashlib
import time

class MQTT_Exporter:

    def __init__(self) -> None:
        self.broker = "broker.emqx.io"
        self.port = 1883
        self.username = None
        self.password = None
        self.qos = 1
        self.data_block_size=2000
        self.client_id = "TrainerControler"
        self.pub_ack = False
        self.topic = "TrainerControler/MQTT_export"


    async def connect(self) -> bool:
        
        # Set Connecting Client ID
        self.client = mqtt_client(self.client_id)
        
        if self.username is not None and self.password is not None:
            self.client.username_pw_set(self.username, self.password)

        self.client.on_connect = self.on_connect
        self.client.on_publish = self.on_publish
        self.client.connect(self.broker, self.port)
        if self.client.is_connected():
            self.client.loop_start()
        else:
            return False
        time.sleep(1)
        return True
        

    def on_publish(self, client, userdata, mid):

        self.mid_value = mid
        self.pub_ack = True


    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)


    def mqtt_publish(self, message: str) -> bool:

        result, mid = self.client.publish(self.topic, message, self.qos)    #### mid = message id
        
        if result == 0:
            t1 = time.time()
            while True:
                time.sleep(0.01)
                if self.client.on_publish:
                    if self.pub_ack == True:
                        if self.mid_value == mid:
                            self.pub_ack = False
                            return True
                if time.time() - t1 > 10:   #### timeout
                    return False


    def mqtt_on_message(self, client, userdata, msg:MQTTMessage):
            print(f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")


    def disconnect(self) -> None:
        self.client.disconnect()


    def mqtt_subscribe(self, topic: str, callback) -> None:
        
        self.client.subscribe(topic)
        self.client.on_message = callback


    def send_header(self, filename):
        file_data = {"filename": filename}
        file_data_json = json.dumps(file_data)
        header = "header" + ",," + file_data_json + ",,"
        header = bytearray(header, "utf-8")
        header.extend(b',' * (200 - len(header)))
        self.mqtt_publish(header)


    def export_file(self, filename: str) -> None:
        with open(filename, "rb") as file:

            print("Publishing")
            self.send_header(filename)
            out_hash_md5 = hashlib.md5()
            bytes_out=0

            while True:
                chunk = file.read(self.data_block_size)
                if chunk:
                    out_hash_md5.update(chunk)
                    bytes_out = bytes_out+len(chunk)
                    self.mqtt_publish(chunk)
       
                else:
                    end="end" + ",," + filename + ",," + out_hash_md5.hexdigest()
                    end=bytearray(end, "utf-8")
                    end.extend(b'x' * (200 - len(end)))
                    self.mqtt_publish(end)
                    break
