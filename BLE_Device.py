import queue
import asyncio
import contextlib
#import csv # only for debugging
#import datetime # only for debugging
from   bleak        import BleakClient, BleakScanner, BleakGATTCharacteristic
from   bleak.exc    import BleakDBusError
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

    def subscribeToService(self, service_uuid, callback = None):
        self.queue.put(QueueEntry('Subscribe', {'UUID': service_uuid, 'Callback': callback}))

    def unsubscribeFromService(self, service_uuid):
        self.queue.put(QueueEntry('Unsubscribe', service_uuid))

    def readFromService(self, service_uuid):
        self.queue.put(QueueEntry('Read', service_uuid))

    def writeToService(self, service_uuid, message):
        self.queue.put(QueueEntry('Write', {'UUID': service_uuid, 'Message': message}))


    async def connection_to_BLE_Device(self, lock: asyncio.Lock, container: DataContainer):
        
        self.dataContainer = container
        print("starting task:", self.name)
        while(self.dataContainer.programRunningFlag == True):

            if self.connect == False and self.connectionState == False:
                #print("Staying off")
                await asyncio.sleep(0.1)
                continue

            elif self.connectionState == True:
                raise Exception("This state should never happen")
            
            elif self.connect == True and self.connectionState == False:
                try:
                    async with contextlib.AsyncExitStack() as stack:

                        # Trying to establish a connection to two+ devices at the same time
                        # can cause errors, so use a lock to avoid this.
                        print(self.name, ": awaiting lock")
                        async with lock:
                            
                            print("scanning for ", self.name)
                            device = await BleakScanner.find_device_by_address(self.address)

                            if device is None:
                                print(self.name, " not found")
                                self.connectionState = False
                                self.connect = False
                                continue

                            client = BleakClient(device)
                            
                            print("connecting to ", self.name)

                            await stack.enter_async_context(client)

                            print("connected to ", self.name)
                            self.connectionState = True

                            # This will be called immediately before client.__aexit__ when
                            # the stack context manager exits.
                            stack.callback(print, "disconnecting from ", self.name)

                        # The lock is released here. The device is still connected and the
                        # Bluetooth adapter is now free to scan and connect another device
                        # without disconnecting this one.

                        self.connectionState = True
                        
                        while self.connect and container.programRunningFlag:  ####    Internal state machine running while connected - Sending commands happen here
                            await asyncio.sleep(0)

                            if not self.queue.empty():
                                try:
                                    entry: QueueEntry = self.queue.get(timeout = 0.2)
                                    if entry.type == 'Subscribe':
                                        #print("subscribe")
                                       
                                        if entry.data["Callback"] is None:
                                            funtionToRegisterForCallback = self.Callback
                                        else:
                                            funtionToRegisterForCallback = entry.data["Callback"]

                                        await client.start_notify(entry.data["UUID"], funtionToRegisterForCallback)

                                    elif entry.type == 'Unsubscribe':
                                        #print('unsub')
                                        await client.stop_notify(entry.data["UUID"])
                                        
                                    elif entry.type == 'Read':
                                        #print('Read')
                                        message = await client.read_gatt_char(entry.data)
                                        self.incomingMessageHandler(entry.data, message)
                                    
                                    elif entry.type == 'Write':
                                        #print('Write:\t', entry.data["Message"])
                                        while(True):
                                            try:
                                                await client.write_gatt_char(entry.data["UUID"], entry.data["Message"] , True)
                                        
                                            except BleakDBusError as e:
                                                print("BleakDBusError, retrying...")
                                                print(e)
                                                continue
                                            break
                                except:
                                    pass

                    # The stack context manager exits here, triggering disconnection.
                    self.connectionState = False
                    print("disconnected from ", self.name)

                except Exception:
                    pass
        else:
            print("stopping task:", self.name)


class HeartRateMonitor(BLE_Device):
    UUID_HR_measurement: str = '00002a37-0000-1000-8000-00805f9b34fb'
    
    def __init__(self):
        super().__init__()

    def subscribeToService(self):
        return super().subscribeToService(self.UUID_HR_measurement, self.Callback)
    
    def unsubscribeFromService(self):
        return super().unsubscribeFromService(self.UUID_HR_measurement)
    
    def Callback(self, sender: BleakGATTCharacteristic, data):
        if sender.description == "Heart Rate Measurement":  # sanity check if the correct sensor 
            currentReading = parse_hr_measurement(data)
            self.dataContainer.momentary.heartRate = currentReading.bpm
            zone: str = None
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


            #print(sender.description, " bpm: ", currentReading.bpm)


class FitnessMachine(BLE_Device):
   
    UUID_supported_resistance_level_range = "00002ad6-0000-1000-8000-00805f9b34fb" # (read):   Supported Resistance Level Range
    UUID_supported_power_range            = "00002ad8-0000-1000-8000-00805f9b34fb" # (read):   Supported Power Range
    UUID_features                         = "00002acc-0000-1000-8000-00805f9b34fb" # (read):   Fitness Machine Feature
    UUID_indoor_bike_data                 = "00002ad2-0000-1000-8000-00805f9b34fb" # (notify:  Indoor Bike Data
    UUID_status                           = "00002ada-0000-1000-8000-00805f9b34fb" # (notify): Fitness Machine Status
    UUID_training_status                  = "00002ad3-0000-1000-8000-00805f9b34fb" # (notify): Training Status
    UUID_control_point                    = "00002ad9-0000-1000-8000-00805f9b34fb" # (write, indicate): Fitness Machine Control Point
    UUID_speedCadenceSensorData           = "00002a5b-0000-1000-8000-00805f9b34fb" # (notify): 
    UUID_powerSensorData                  = "00002a63-0000-1000-8000-00805f9b34fb" # (notify): 

    supported_resistance = MinMaxIncrement()
    supported_power = MinMaxIncrement()

    def __init__(self):
        super().__init__()
        self.remoteControlAcquired: bool = False

    def requestSupportedPower(self):
        super().readFromService(self.UUID_supported_power_range)

    def requestSupportedResistance(self):
        super().readFromService(self.UUID_supported_resistance_level_range)

    def requestFeatures(self):
        super().readFromService(self.UUID_features)

    def reset(self):
        super().writeToService(self.UUID_control_point, b"\x01")
        self.remoteControlAcquired = False

    def requestControl(self):
        super().writeToService(self.UUID_control_point, b"\x00")

    def start(self):
        super().writeToService(self.UUID_control_point, b"\x07")


    def setTarget(self, type: str, setting: int) -> None:
        
        if   type == "Speed":
            super().writeToService(self.UUID_control_point, b"\x02" + setting.to_bytes(2, "little", signed=False))
        
        elif type == "Incline":
            super().writeToService(self.UUID_control_point, b"\x03" + setting.to_bytes(2, "little", signed=True))

        elif type == "Level":
            super().writeToService(self.UUID_control_point, b"\x04" + setting.to_bytes(1, "little", signed=False))
        
        elif type == "Power":
            super().writeToService(self.UUID_control_point, b"\x05" + setting.to_bytes(2, "little", signed=True))


    def stop(self):
        super().writeToService(self.UUID_control_point, b"\x08\x01")

    def pause(self):
        super().writeToService(self.UUID_control_point, b"\x08\x02")
    
    def Callback(self, sender: BleakGATTCharacteristic, data):
        #print("Sender: ", sender)
        #print("Data: ", data)

        if sender.description == "Indoor Bike Data":
            parsedData = parse_indoor_bike_data(data)
            self.dataContainer.momentary.cadence = parsedData.instant_cadence
            self.dataContainer.momentary.power = parsedData.instant_power
            self.dataContainer.momentary.speed = parsedData.instant_speed
            self.dataContainer.updateAveragesAndMaximums()
            
        if sender.description == "CSC Measurement":
            pass

        if sender.description == "Cycling Power Measurement":
            pass

        if sender.description == "Fitness Machine Control Point":
            
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


    def incomingMessageHandler(self, uuid, message):
        if   uuid == self.UUID_features:
            print("Features: ", message, "\n")
            #wr = ("Features", message)
            #self.csvWriter.writerow(wr)

        elif uuid == self.UUID_supported_resistance_level_range:
            print("Resistance: ", message, "\n")
            #wr = ("Res", message)
            #self.csvWriter.writerow(wr)

        elif uuid == self.UUID_supported_power_range:
            print("Power: ", message, "\n")
            #wr = ("Power", message)
            #self.csvWriter.writerow(wr)



