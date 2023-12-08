import asyncio
import time
import contextlib
import configparser
import queue
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

class CurrentData:
    def __init__(self):
        self.workoutTime: int = 0
        self.momentary: Dataset
        self.average: Dataset
        self.max: Dataset
        self.NoAverage:int = 0

    def updateAverages(self):
        newNoAverage = self.NoAverage + 1
        self.average.cadence = (self.momentary.cadence +(self.NoAverage * self.average.cadence) / newNoAverage)
        self.average.power = (self.momentary.power +(self.NoAverage * self.average.power) / newNoAverage)
        self.average.heartRate = (self.momentary.heartRate +(self.NoAverage * self.average.heartRate) / newNoAverage)
        self.average.gradient = (self.momentary.gradient +(self.NoAverage * self.average.gradient) / newNoAverage)
        self.NoAverage += 1
                                

currentData = CurrentData()



class HeartRateMonitor(BLE_Device):
    heart_rate_measurement_characteristic_id: str = '00002a37-0000-1000-8000-00805f9b34fb'
    
    def subscribeToService(self):
        return super().subscribeToService(self.heart_rate_measurement_characteristic_id)
    
    def unsubscribeFromService(self):
        return super().unsubscribeFromService(self.heart_rate_measurement_characteristic_id)
    
    def Callback(sender, data):
        if sender.description == "Heart Rate Measurement":  # sanity check if the correct sensor 
            currentReading = parse_hr_measurement(data)
            currentData.momentary.heartRate = currentReading.bpm
            print(sender.description, " bpm: ", currentReading.bpm)



device_heartRateSensor = HeartRateMonitor()
device_turboTrainer    = BLE_Device()


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
        device_heartRateSensor.connect = True
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
    await asyncio.sleep(10.0)
    print("end Wait")
    device_heartRateSensor.connect = True
    await asyncio.sleep(10.0)
    print("end Wait")
    global mainProgrammePower
    mainProgrammePower = False
    print("im here")
    device_heartRateSensor.queue.put(QueueEntry('Subscribe', 43))


class WorkoutManager():
    def __init__(self) -> None:
        self.state:str = "IDLE"
        self.currentWorkout: dict = None
        self.timer: int = None
        self.queue = queue.SimpleQueue()
        self.workouts = Workouts()
        self.currentSegmentStartTime: float= 0
        self.currentSegment:dict  = None
        self.elapsedTime: float = 0
    
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
                        self.state = "Running"
                else:
                    await asyncio.sleep(0.1)
            

            if self.state == "PAUSED":
                await asyncio.sleep(0.1)
            

            if self.state == "RUNNING":
                
                isSegmentTransition: bool = True
                try:
                    if self.elapsedTime < self.currentSegment["Duration"]:
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
                        self.state = "Stop"
                
                await asyncio.sleep(0.1)
                self.elapsedTime = time.monotonic() - self.currentSegmentStartTime
            


            if self.state == "Stop":
                #### TO DO: save workout, reset variables etc then go to IDLE
                await asyncio.sleep(0.1)


workoutManager = WorkoutManager()

async def connection_to_BLE_Device(lock: asyncio.Lock, dev):
    
    print("starting task:", dev.name)
    while(mainProgrammePower == True):

        if dev.connect == False and dev.connectionState == False:
            print("Staying off")
            await asyncio.sleep(0.1)
            continue

        elif dev.connectionState == True:
            raise Exception("This state should never happen")
        
        elif dev.connect == True and dev.connectionState == False:
            try:
                async with contextlib.AsyncExitStack() as stack:

                    # Trying to establish a connection to two+ devices at the same time
                    # can cause errors, so use a lock to avoid this.
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
                     
                    while dev.connect:  ####    Internal loop running while connected - Sending commands happen here
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
                                    
                                elif entry.type == 'Send':
                                    print('Send')
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
        supervisor(),
        workoutManager.run()
    )


####    Trigger Main    ####
asyncio.run(main())

