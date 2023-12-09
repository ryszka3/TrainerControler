import asyncio
import time
import datetime
import contextlib
import configparser
import queue
import csv
from   bleak              import BleakClient, BleakScanner
from   heart_rate_service import parse_hr_measurement
from   workout_loader     import Workouts
from   BLE_Device         import BLE_Device, QueueEntry


class Dataset:
    def __init__(self):
        self.cadence: float = 0
        self.power: float = 0
        self.heartRate: int = 0
        self.gradient: int = 0
    
    def getIterableRecord(self):
        return list((self.cadence,
                     self.power,
                     self.heartRate,
                     self.gradient))

class CurrentData:
    def __init__(self):
        self.workoutTime: int = 0
        self.momentary: Dataset = Dataset()
        self.average: Dataset = Dataset()
        self.max: Dataset = Dataset()
        self.NoAverage:int = 0

    def updateAverages(self):
        newNoAverage = self.NoAverage + 1
        self.average.cadence = (self.momentary.cadence +(self.NoAverage * self.average.cadence) / newNoAverage)
        self.average.power = (self.momentary.power +(self.NoAverage * self.average.power) / newNoAverage)
        self.average.heartRate = (self.momentary.heartRate +(self.NoAverage * self.average.heartRate) / newNoAverage)
        self.average.gradient = (self.momentary.gradient +(self.NoAverage * self.average.gradient) / newNoAverage)
        self.NoAverage += 1

    def getIterableRecord(self):
        
        ret = [self.workoutTime]
        for val in self.momentary.getIterableRecord():
            ret.append(val)
        return ret
    
    def getIterableAverages(self):
        ret:list = list(("AVERAGE:"))

        for val in self.average.getIterableRecord():
            ret.append(val)
        return ret

    def getIterableMaximums(self):
        ret:list = list(("MAX:"))

        for val in self.max.getIterableRecord():
            ret.append(val)
        return ret
                                

currentData = CurrentData()


class HeartRateMonitor(BLE_Device):
    UUID_HR_measurement: str = '00002a37-0000-1000-8000-00805f9b34fb'
    
    def subscribeToService(self):
        return super().subscribeToService(self.UUID_HR_measurement)
    
    def unsubscribeFromService(self):
        return super().unsubscribeFromService(self.UUID_HR_measurement)
    
    def Callback(self, sender, data):
        if sender.description == "Heart Rate Measurement":  # sanity check if the correct sensor 
            currentReading = parse_hr_measurement(data)
            currentData.momentary.heartRate = currentReading.bpm
            print(sender.description, " bpm: ", currentReading.bpm)

class MinMaxIncrement:
    def __init__(self) -> None:
        self.min = 0
        self.max = 0
        self.increment = 0


class FitnessMachine(BLE_Device):
   
    UUID_supported_resistance_level_range = "00002ad6-0000-1000-8000-00805f9b34fb" # (read):   Supported Resistance Level Range
    UUID_supported_power_range            = "00002ad8-0000-1000-8000-00805f9b34fb" # (read):   Supported Power Range
    UUID_features                         = "00002acc-0000-1000-8000-00805f9b34fb" # (read):   Fitness Machine Feature
    UUID_indoor_bike_data                 = "00002ad2-0000-1000-8000-00805f9b34fb" # (notify:  Indoor Bike Data
    UUID_status                           = "00002ada-0000-1000-8000-00805f9b34fb" # (notify): Fitness Machine Status
    UUID_training_status                  = "00002ad3-0000-1000-8000-00805f9b34fb" # (notify): Training Status
    UUID_control_point                    = "00002ad9-0000-1000-8000-00805f9b34fb" # (write, indicate): Fitness Machine Control Point

    supported_resistance = MinMaxIncrement()
    supported_power = MinMaxIncrement()

    def __init__(self):
        super().__init__()

    def requestSupportedPower(self) -> MinMaxIncrement:
        super().queue.put(QueueEntry("Read", self.UUID_supported_power_range))

    def requestSupportedResistance(self) -> MinMaxIncrement:
        super().queue.put(QueueEntry("Read", self.UUID_supported_resistance_level_range))

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

    def Callback(self, sender, data):
        print("Sender: ", sender)
        print("\tData: ", data)

    def subscribeToTrainerStatus(self):
        super().subscribeToService(self.UUID_training_status)
    def subscribeToControlPoint(self):
        super().subscribeToService(self.UUID_control_point)
    def subscribeToIndoorBikeData(self):
        super().subscribeToService(self.UUID_indoor_bike_data)




device_heartRateSensor = HeartRateMonitor()
device_turboTrainer    = FitnessMachine()


#####    Reading configuration file    ####

config = configparser.ConfigParser()
mainProgrammePower: bool = True

try:
    config.read('config.ini')
except:
    pass

if 'HeartRateSensor' in config:
    try:
        device_heartRateSensor.address = config['HeartRateSensor']['Address']
        device_heartRateSensor.name    = config['HeartRateSensor']['Sensor_Name']
        device_heartRateSensor.type    = config['HeartRateSensor']['Sensor_Type']
    except:
        raise Exception("Config file does not contain correct entries for devices")
    
if 'TurboTrainer' in config:
    try:
        device_turboTrainer.address = config['TurboTrainer']['Address']
        device_turboTrainer.name    = config['TurboTrainer']['Sensor_Name']
        device_turboTrainer.type    = config['TurboTrainer']['Sensor_Type']
    except:
        raise Exception("Config file does not contain correct entries for devices")


#####    Main Programme functions here    ####

async def supervisor():
    device_turboTrainer.subscribeToIndoorBikeData()
    await asyncio.sleep(35.0)
    print("end Wait1")
    global mainProgrammePower
    mainProgrammePower = False
    print("im here")
    


class WorkoutManager():
    def __init__(self) -> None:
        self.state:str = "IDLE"
        self.currentWorkout: dict = None
        self.workoutTimer: int = 0
        self.queue = queue.SimpleQueue()
        self.workouts = Workouts()
        self.currentSegmentStartTime: float= 0
        self.currentSegment:dict  = None
        self.currentSegmentElapsedTime: float = 0
    
    async def run(self,):
        print("starting workout manager")
        while(mainProgrammePower == True):
            entry: QueueEntry = None
            
            if not self.queue.empty():
                try:
                    entry = self.queue.get(timeout = 0.2)
                except:
                    pass


            if self.state == "IDLE": 
                if not entry == None: 
                    if entry.type == "Start":   # Starting a new workout
                     
                        self.currentWorkout = self.workouts.getWorkout(entry.data).copy()   ## Get a local version of the workout
                        self.state = "RUNNING"
                    
                    elif entry.type == "Freeride":
                        self.state = "FREERIDE"
                    
                    try:
                        workout_logfile = open(datetime.datetime.now().strftime("Workouts/Workout-%y-%m-%d-(%Hh%Mm%S).csv"), 'w+', newline='')
                        csvWriter = csv.writer(workout_logfile, dialect='excel')
                        csvWriter.writerow(list(("Workout log file","")))
                        csvWriter.writerow(list(("Created:",
                                                datetime.datetime.now().strftime("%d %b %Y"),
                                                "at:",
                                                datetime.datetime.now().strftime("%X")                                                
                                                )))
                        csvWriter.writerow(list(("Time", "Cadence", "Power", "HR BPM", "Gradient")))
                        
                    except:
                        raise Exception("Failed creating a workout data file!")
                else:
                    await asyncio.sleep(0.1)
            

            if self.state == "PAUSED":
                if not entry == None: 
                    if entry.type == "Start":   # Resume
                        self.state = "RUNNING"
                else:
                    await asyncio.sleep(0.1)


            if self.state == "RUNNING":
                
                if not entry == None: 
                    if entry.type == "Stop":   # Stop the workout, go to STOP to close the datafile
                        self.state = "STOP"
                    
                    elif entry.type == "Pause": # Pause the workout, go to PAUSE and await futher instructions
                        self.state = "PAUSED"
                
                isSegmentTransition: bool = True
                try:
                    if self.currentSegmentElapsedTime < self.currentSegment["Duration"]:
                        isSegmentTransition = False
                except:
                    pass

                if isSegmentTransition: #need to start a new segment OR stop the machine
                   
                    if len(self.currentWorkout["Segments"]) > 0:
                        
                        self.currentSegment = self.currentWorkout["Segments"].pop(0)
                        self.currentSegmentStartTime = time.monotonic()
                        print("new segment")
                    
                    else:
                        
                        print("end of workout")
                        self.state = "STOP"
                
                await asyncio.sleep(0.1)
                oldElapsedTime = self.currentSegmentElapsedTime
                self.currentSegmentElapsedTime = time.monotonic() - self.currentSegmentStartTime

                if self.currentSegmentElapsedTime - oldElapsedTime > 1.0:   # 
                    
                    self.workoutTimer += self.currentSegmentElapsedTime - oldElapsedTime
                    csvWriter.writerow(currentData.getIterableRecord())
        
            if self.state == "STOP":
                #### Closing the logfile ####
                try:
                    csvWriter.writerow(currentData.getIterableAverages())
                    csvWriter.writerow(currentData.getIterableMaximums())
                    workout_logfile.close()
                except:
                    raise Exception("Failed to close the workout data file!")

                ##### reset variables and the state machine #####
                self.state = "IDLE"
                self.currentWorkout = None
                self.workoutTimer = 0
                self.currentSegmentStartTime = 0
                self.currentSegment = None
                self.currentSegmentElapsedTime = 0


workoutManager = WorkoutManager()

async def connection_to_BLE_Device(lock: asyncio.Lock, dev: BLE_Device):
    
    print("starting task:", dev.name)
    while(mainProgrammePower == True):

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
                     
                    while dev.connect:  ####    Internal state machine running while connected - Sending commands happen here
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
                                    await client.read_gatt_char(entry.data)
                                
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


async def main():
   
    lock = asyncio.Lock()

    await asyncio.gather(
        connection_to_BLE_Device(lock, device_heartRateSensor),
        connection_to_BLE_Device(lock, device_turboTrainer),
        supervisor(),
        workoutManager.run()
    )


####    Trigger Main    ####
asyncio.run(main())

