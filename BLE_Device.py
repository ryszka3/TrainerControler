import queue
import asyncio
import contextlib
#import csv # only for debugging
#import datetime # only for debugging
from   bleak        import BleakClient, BleakScanner, BleakGATTCharacteristic
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

    def subscribeToService(self, service_uuid):
        self.queue.put(QueueEntry('Subscribe', service_uuid))

    def unsubscribeFromService(self, service_uuid):
        self.queue.put(QueueEntry('Unsubscribe', service_uuid))

    def readFromService(self, service_uuid):
        self.queue.put(QueueEntry('Read', service_uuid))

    def writeToService(self, service_uuid, message):
        self.queue.put(QueueEntry('Write', {'UUID': service_uuid, 'Message': message}))


class HeartRateMonitor(BLE_Device):
    UUID_HR_measurement: str = '00002a37-0000-1000-8000-00805f9b34fb'
    
    def __init__(self, container: DataContainer):
        super().__init__()
        self.dataContainer = container

    def subscribeToService(self):
        return super().subscribeToService(self.UUID_HR_measurement)
    
    def unsubscribeFromService(self):
        return super().unsubscribeFromService(self.UUID_HR_measurement)
    
    def Callback(self, sender: BleakGATTCharacteristic, data):
        if sender.description == "Heart Rate Measurement":  # sanity check if the correct sensor 
            currentReading = parse_hr_measurement(data)
            self.dataContainer.momentary.heartRate = currentReading.bpm
            print(sender.description, " bpm: ", currentReading.bpm)


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

    def __init__(self, container: DataContainer):
        super().__init__()
        #self.logfile = open(datetime.datetime.now().strftime("Logfile-%y-%m-%d-(%Hh%Mm%S).csv"), 'w+', newline='')
        #self.csvWriter = csv.writer(self.logfile, dialect='excel') # only for debugging
        self.dataContainer = container

    def requestSupportedPower(self):
        super().readFromService(self.UUID_supported_power_range)

    def requestSupportedResistance(self):
        super().readFromService(self.UUID_supported_resistance_level_range)

    def requestFeatures(self):
        super().readFromService(self.UUID_features)

    def reset(self):
        super().writeToService(self.UUID_control_point, b"\x01")

    def requestControl(self):
        super().writeToService(self.UUID_control_point, b"\x00")

    def start(self):
        super().writeToService(self.UUID_control_point, b"\x06")

    def responce(self):
        super().writeToService(self.UUID_control_point, b"\x80")

    def setTargetPower(self, power: int) -> None:
        super().writeToService(self.UUID_control_point, b"\x05" + power.to_bytes(2, "little", signed=True))

    def setTargetResistance(self, resistance: int) -> None:
        super().writeToService(self.UUID_control_point, b"\x04" + resistance.to_bytes(1, "little", signed=False))

    def setSpeed(self, speed: int):
        super().writeToService(self.UUID_control_point, b"\x02" + speed.to_bytes(2, "little", signed=False))

    def setIncline(self, incline):
        super().writeToService(self.UUID_control_point, b"\x03" + incline.to_bytes(2, "little", signed=True))

    def stop(self, parameter):
        super().writeToService(self.UUID_control_point, b"\x07" + parameter.to_bytes(1, "little", signed=False))

    def Callback(self, sender: BleakGATTCharacteristic, data):
        print("Sender: ", sender)
        print("Data: ", data, "\n")
        #wr = ("notify", sender, data)
        #self.csvWriter.writerow(wr) # only for debugging

        if sender.description == "Indoor Bike Data":
            parsedData = parse_indoor_bike_data(data)
            self.dataContainer.momentary.cadence = parsedData.instant_cadence
            self.dataContainer.momentary.power = parsedData.instant_power
            self.dataContainer.momentary.speed = parsedData.instant_speed
            
        if sender.description == "CSC Measurement":
            pass

        if sender.description == "Cycling Power Measurement":
            pass

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


    def subscribeToTrainingStatus(self):
        super().subscribeToService(self.UUID_training_status)

    def subscribeToMachineStatus(self):
        super().subscribeToService(self.UUID_status)

    def subscribeToControlPoint(self):
        super().subscribeToService(self.UUID_control_point)

    def subscribeToIndoorBikeData(self):
        super().subscribeToService(self.UUID_indoor_bike_data)

    def subscribeToSpeedCadenceData(self):
        super().subscribeToService(self.UUID_speedCadenceSensorData)

    def subscribeToPowerData(self):
        super().subscribeToService(self.UUID_powerSensorData)


async def connection_to_BLE_Device(lock: asyncio.Lock, dev: BLE_Device, container: DataContainer):
    
    print("starting task:", dev.name)
    while(container.programmeRunningFlag == True):

        if dev.connect == False and dev.connectionState == False:
            #print("Staying off")
            await asyncio.sleep(0.1)
            continue

        elif dev.connectionState == True:
            raise Exception("This state should never happen")
        
        elif dev.connect == True and dev.connectionState == False:
            try:
                async with contextlib.AsyncExitStack() as stack:

                    # Trying to establish a connection to two+ devices at the same time
                    # can cause errors, so use a lock to avoid this.
                    print(dev.name, ": awaiting lock")
                    async with lock:
                        
                        print("scanning for ", dev.name)
                        device = await BleakScanner.find_device_by_address(dev.address)

                        if device is None:
                            print(dev.name, " not found")
                            dev.connectionState = False
                            dev.connect = False
                            continue

                        client = BleakClient(device)
                        
                        print("connecting to ", dev.name)

                        await stack.enter_async_context(client)

                        print("connected to ", dev.name)
                        dev.connectionState = True

                        # This will be called immediately before client.__aexit__ when
                        # the stack context manager exits.
                        stack.callback(print, "disconnecting from ", dev.name)

                    # The lock is released here. The device is still connected and the
                    # Bluetooth adapter is now free to scan and connect another device
                    # without disconnecting this one.

                    dev.connectionState = True
                     
                    while dev.connect and container.programmeRunningFlag:  ####    Internal state machine running while connected - Sending commands happen here
                        await asyncio.sleep(0.1)

                        if not dev.queue.empty():
                            try:
                                entry: QueueEntry = dev.queue.get(timeout = 0.2)
                                if entry.type == 'Subscribe':
                                    print("subscribe")
                                    await client.start_notify(entry.data, dev.Callback)

                                elif entry.type == 'Unsubscribe':
                                    print('unsub')
                                    await client.stop_notify(entry.data)
                                    
                                elif entry.type == 'Read':
                                    print('Read')
                                    message = await client.read_gatt_char(entry.data)
                                    dev.incomingMessageHandler(entry.data, message)
                                
                                elif entry.type == 'Write':
                                    print('Write')
                                    await client.write_gatt_char(entry.data["UUID"], entry.data["Message"] , True)
                                
                            except:
                                pass

                # The stack context manager exits here, triggering disconnection.
                dev.connectionState = False
                print("disconnected from ", dev.name)

            except Exception:
                pass
    else:
        print("stopping task:", dev.name)