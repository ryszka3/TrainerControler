from paho.mqtt import client as mqtt_client
from paho.mqtt.client import MQTTMessage
import json
import hashlib
import time

class MQTT_Exporter:

    def __init__(self) -> None:
        self.broker = "broker.hivemq.com"  #"broker.emqx.io"
        self.port = 1883
        self.username = None
        self.password = None
        self.qos = 1
        self.data_block_size = 100000 ## 100 kBytes
        self.client_id = "TrainerControler"
        self.pub_ack = False
        self.topic = "TrainerControler/MQTT_export"


    def connect(self) -> bool:
        
        # Set Connecting Client ID
        self.client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2, self.client_id)
        print("A")
        if self.username is not None and self.password is not None:
            self.client.username_pw_set(self.username, self.password)

        self.client.on_connect = self.on_connect
        self.client.on_publish = self.on_publish
        self.client.connect(self.broker, self.port)
        self.client.loop_start()
        time.sleep(0.5)
        if self.client.is_connected():
            time.sleep(0.5)
            return True
        else:
            return False
        
        

    def on_publish(self, client, userdata, mid, reason_code, properties):

        self.mid_value = mid
        self.pub_ack = True


    def on_connect(self, client, userdata, connect_flags, reason_code, properties):
        if reason_code == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", reason_code)


    def mqtt_publish(self, message: str) -> bool:

        result, mid = self.client.publish(topic=self.topic, payload=message, qos=self.qos)    #### mid = message id
        
        if result == 0:
            t1 = time.time()
            while True:
                time.sleep(0.01)
                if self.client.on_publish:
                    if self.pub_ack == True:
                        if self.mid_value == mid:
                            self.pub_ack = False
                            return True
                        else:
                            return False
                if time.time() - t1 > 10:   #### timeout
                    return False


    def mqtt_on_message(self, client, userdata, msg:MQTTMessage):
            print(f"Received `{msg.payload.decode()}` from `{msg.topic}` topic")


    def disconnect(self) -> None:
        self.client.disconnect()


    def mqtt_subscribe(self, topic: str, callback) -> None:
        
        self.client.subscribe(topic)
        self.client.on_message = callback


    def export_file(self, filename: str) -> bool:
        with open(filename, "rb") as file:

            print("Publishing")

            file_params = filename.split("/")
            user = file_params[len(file_params)-2]
            file_type = ".csv" if file_params[len(file_params)-1].endswith(".csv") else ".tcx"
            file_name = file_params[len(file_params)-1].removesuffix(file_type)
            header = json.dumps({"Type": "Header", "User": user, "Filename": file_name, "Filetype": file_type})
            
            res = self.mqtt_publish(header)

            out_hash_md5 = hashlib.md5()
            bytes_out=0

            while True and res:
                chunk = file.read(self.data_block_size)
                if chunk:
                    out_hash_md5.update(chunk)
                    bytes_out = bytes_out+len(chunk)
                    res = self.mqtt_publish(chunk)
                    #print(bytes_out)
       
                else:
                    end = json.dumps({"Type": "End", "User": user, "Filename": file_name, "Filetype": file_type, "MD5": out_hash_md5.hexdigest()})
                    res = self.mqtt_publish(end)
                    break

            return res

