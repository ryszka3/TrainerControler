import queue
import threading
import time
import simplepyble
#import csv # only for debugging
#import datetime # only for debugging
from   datatypes    import DataContainer, MinMaxIncrement, QueueEntry
from   data_parsers import parse_hr_measurement, parse_indoor_bike_data
    


class BLE_Device:
    def __init__(self):
        self.address: str = None
        self.name: str = None
        self.type:str = None
        self.connect: bool = True
        self.connectionState: bool = False
        self.queue = queue.SimpleQueue()
        self.dataContainer: DataContainer = None

    def subscribeToService(self, service_uuid:str, characteristic_uuid:str, callback = None) -> None:
        self.queue.put(QueueEntry("Subscribe", {"Service": service_uuid, 
                                                "Characteristic": characteristic_uuid, 
                                                "Callback": callback}))

    def unsubscribeFromService(self, service_uuid:str, characteristic_uuid:str) -> None:
        self.queue.put(QueueEntry("Unsubscribe", {"Service": service_uuid, 
                                                  "Characteristic": characteristic_uuid}))

    def readFromService(self, service_uuid: str, characteristic_uuid: str) -> None:
        self.queue.put(QueueEntry("Read", {"Service": service_uuid, 
                                           "Characteristic": characteristic_uuid}))

    def writeToService(self, service_uuid: str, characteristic_uuid: str,  message) -> None:
        self.queue.put(QueueEntry("Write", {"Service": service_uuid,
                                            "Characteristic": characteristic_uuid,
                                            "Message": message}))


    def connection_to_BLE_Device(self, adapter, lock: threading.Lock, container: DataContainer):
        self.ble_adapter = adapter
        self.dataContainer = container
        print("starting task:", self.name)
        while(True):

            if self.connect == False and self.connectionState == False:
                time.sleep(0.2)
                continue
            
            elif self.connect == True and self.connectionState == False:

                # Trying to establish a connection to two+ devices at the same time
                # can cause errors, so use a lock to avoid this.
                print(self.name, ": awaiting lock")
                with lock:
                            
                    def onFound(per):
                        if per.address() == self.address:
                            self.ble_adapter.scan_stop()

                    self.ble_adapter.set_callback_on_scan_start(lambda: print("Scanning for ", self.name, "[", self.address,"]"))
                    self.ble_adapter.set_callback_on_scan_stop(lambda: print("Scan complete."))
                    self.ble_adapter.set_callback_on_scan_found(onFound)
                    t1 = time.time()
                    # Scan for 10 seconds
                    self.ble_adapter.scan_start()
                    t1 = time.time()
                    while time.time()-t1 < 10:
                        time.sleep(0.1)
                        if self.ble_adapter.scan_is_active() == False:
                            break
                    else:
                        self.ble_adapter.scan_stop() 
                        
                    peripherals = self.ble_adapter.scan_get_results()

                    for p in peripherals:
                        if p.address() == self.address:
                            self.device = p
                            break
                    else:
                        print(self.name, " not found")
                        self.connectionState = False
                        self.connect = False
                        continue
                    
                    print("Connecting to ", self.name)

                    self.device.connect()

                    print("Connected to ", self.name)
                    self.connectionState = True

                # The lock is released here. The device is still connected and the
                # Bluetooth adapter is now free to scan and connect another device
                # without disconnecting this one.
                
                while self.connect:  ####    Internal state machine running while connected - Sending commands happen here

                    if not self.queue.empty():
                        try:
                            entry: QueueEntry = self.queue.get(timeout = 0.2)
                            if entry.type == "Quit":
                                self.connect = False
                                self.device.disconnect()
                                break
                            elif entry.type == "Subscribe":
                                if entry.data["Callback"] is None:
                                    funtionToRegisterForCallback = self.callback
                                else:
                                    funtionToRegisterForCallback = entry.data["Callback"]
                                self.device.notify(entry.data["Service"], entry.data["Characteristic"], funtionToRegisterForCallback)

                            elif entry.type == "Unsubscribe":
                                self.device.unsubscribe(entry.data["Service"], entry.data["Characteristic"])
                                
                            elif entry.type == "Read":
                                message = self.device.read(entry.data["Service"], entry.data["Characteristic"])
                                self.incomingMessageHandler(entry.data, message)
                            
                            elif entry.type == "Write":
                                self.device.write_request(entry.data["Service"], entry.data["Characteristic"], entry.data["Message"])

                        except:
                            pass

                    time.sleep(0.2)

                else:
                    self.device.disconnect()
                    continue    # self.connect became false, but not received quit command

                # Quit received and broken out of while loop

                self.connectionState = False
                print("disconnected from ", self.name)
                break

        print("stopping thread:", self.name)


class HeartRateMonitor(BLE_Device):
    #UUID_HR_measurement: str = '00002a37-0000-1000-8000-00805f9b34fb'
    
    UUID_HR_service: str = "0000180d-0000-1000-8000-00805f9b34fb"
    UUID_HR_measurement_char: str = "00002a37-0000-1000-8000-00805f9b34fb"
    
    def __init__(self):
        super().__init__()

    def subscribeToHRService(self):
        return super().subscribeToService(self.UUID_HR_service, self.UUID_HR_measurement_char, self.callback)
    
    def unsubscribeFromService(self):
        return super().unsubscribeFromService(self.UUID_HR_service, self.UUID_HR_measurement_char)
    

    def callback(self, data):
        currentReading = parse_hr_measurement(data)
        self.dataContainer.momentary.heartRate = currentReading.bpm
 
        if currentReading.bpm < (self.dataContainer.activeUser.Max_HR * 0.60):
            zone = "Recovery"
        elif currentReading.bpm < (self.dataContainer.activeUser.Max_HR * 0.70):
            zone = "Aerobic"
        elif currentReading.bpm < (self.dataContainer.activeUser.Max_HR * 0.80):
            zone = "Tempo"
        elif currentReading.bpm < (self.dataContainer.activeUser.Max_HR * 0.90):
            zone = "Threshold"
        else:
            zone = "Anaerobic"
            
        self.dataContainer.momentary.hrZone = zone
        print(currentReading.bpm, zone)



class FitnessMachine(BLE_Device):
   
    
    
    
    UUID_speedCadenceSensorData           = "00002a5b-0000-1000-8000-00805f9b34fb" # (notify): 
    UUID_powerSensorData                  = "00002a63-0000-1000-8000-00805f9b34fb" # (notify): 


    UUID_Fitness_Machine_service               = "00001826-0000-1000-8000-00805f9b34fb"
    UUID_supported_resistance_level_range_char = "00002ad6-0000-1000-8000-00805f9b34fb" # (read):   Supported Resistance Level Range
    UUID_supported_power_range_char            = "00002ad8-0000-1000-8000-00805f9b34fb" # (read):   Supported Power Range
    UUID_control_point_char                    = "00002ad9-0000-1000-8000-00805f9b34fb" # (write, indicate): Fitness Machine Control Point
    UUID_status_char                           = "00002ada-0000-1000-8000-00805f9b34fb" # (notify): Fitness Machine Status
    UUID_features_char                         = "00002acc-0000-1000-8000-00805f9b34fb" # (read):   Fitness Machine Feature
    UUID_indoor_bike_data_char                 = "00002ad2-0000-1000-8000-00805f9b34fb" # (notify:  Indoor Bike Data
    UUID_training_status_char                  = "00002ad3-0000-1000-8000-00805f9b34fb" # (notify): Training Status

    supported_resistance = MinMaxIncrement()
    supported_power = MinMaxIncrement()

    def __init__(self):
        super().__init__()
        self.remoteControlAcquired: bool = False


    def subscribeToControlPoint(self):
        super().subscribeToService(self.UUID_Fitness_Machine_service, self.UUID_control_point_char, self.callback_ftms_CP)

    def unsubscribeFromControlPoint(self):
        super().unsubscribeFromService(self.UUID_Fitness_Machine_service, self.UUID_control_point_char)

    def subscribeToIndoorBikeData(self):
        super().subscribeToService(self.UUID_Fitness_Machine_service, self.UUID_indoor_bike_data_char, self.callback_IndoorBikeData)

    def unsubscribeFromIndoorBikeData(self):
        super().unsubscribeFromService(self.UUID_Fitness_Machine_service, self.UUID_indoor_bike_data_char)

    def requestSupportedPower(self):
        super().readFromService(self.UUID_Fitness_Machine_service, self.supported_power)

    def requestSupportedResistance(self):
        super().readFromService(self.UUID_Fitness_Machine_service, self.supported_resistance)

    def requestFeatures(self):
        super().readFromService(self.UUID_Fitness_Machine_service, self.UUID_features_char)

    def reset(self):
        super().writeToService(self.UUID_Fitness_Machine_service, self.UUID_control_point_char, b"\x01")
        self.remoteControlAcquired = False

    def requestControl(self):
        super().writeToService(self.UUID_Fitness_Machine_service, self.UUID_control_point_char, b"\x00")

    def start(self):
        super().writeToService(self.UUID_Fitness_Machine_service, self.UUID_control_point_char, b"\x07")


    def setTarget(self, type: str, setting: int) -> None:
        
        if   type == "Speed":
            super().writeToService(self.UUID_Fitness_Machine_service, 
                                   self.UUID_control_point_char, 
                                   b"\x02" + setting.to_bytes(2, "little", signed=False))
        
        elif type == "Incline":
            super().writeToService(self.UUID_Fitness_Machine_service, 
                                   self.UUID_control_point_char, 
                                   b"\x03" + setting.to_bytes(2, "little", signed=True))

        elif type == "Level":
            super().writeToService(self.UUID_Fitness_Machine_service, 
                                   self.UUID_control_point_char, 
                                   b"\x04" + setting.to_bytes(1, "little", signed=False))
        
        elif type == "Power":
            super().writeToService(self.UUID_Fitness_Machine_service, 
                                   self.UUID_control_point_char, 
                                   b"\x05" + setting.to_bytes(2, "little", signed=True))


    def stop(self):
        super().writeToService(self.UUID_Fitness_Machine_service, self.UUID_control_point_char, b"\x08\x01")

    def pause(self):
        super().writeToService(self.UUID_Fitness_Machine_service, self.UUID_control_point_char, b"\x08\x02")
    
    def callback_ftms_CP(self, data):
            
        if data[0] == 0x80: # responce code has to be 0x80
            
            result: str = None
            if data[2] == 0x01:
                result = "Success"
            elif data[2] == 0x02:
                result = "Not Supported"
            elif data[2] == 0x03:
                result = "Invalid parameter"
            elif data[2] == 0x04:
                result = "Operation failed"
            elif data[2] == 0x05:
                result = "Control not permitted"
            
            if result == "Success" and data[1] == 0x00:  # Responding to request code 0x00, i.e. request control
                self.remoteControlAcquired = True

            print("Control point responce: (", data[1], ") -> ", result)

    def callback_IndoorBikeData(self, data):

        parsedData = parse_indoor_bike_data(data)
        print(parsedData)
        self.dataContainer.momentary.cadence = parsedData.instant_cadence
        self.dataContainer.momentary.power = parsedData.instant_power
        self.dataContainer.momentary.speed = parsedData.instant_speed
        self.dataContainer.updateAveragesAndMaximums()


    def incomingMessageHandler(self, uuid, message):
        if   uuid == self.UUID_features_char:
            print("Features: ", message, "\n")


        elif uuid == self.UUID_supported_resistance_level_range_char:
            print("Resistance: ", message, "\n")


        elif uuid == self.UUID_supported_power_range_char:
            print("Power: ", message, "\n")


