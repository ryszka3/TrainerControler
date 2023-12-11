import asyncio
import configparser
import queue
from   workouts    import WorkoutManager
from   BLE_Device         import HeartRateMonitor, FitnessMachine, connection_to_BLE_Device
from   datatypes          import DataContainer

dataAndFlagContainer   = DataContainer()
device_heartRateSensor = HeartRateMonitor(dataAndFlagContainer)
device_turboTrainer    = FitnessMachine(dataAndFlagContainer)
workoutManager         = WorkoutManager(dataAndFlagContainer)

#####    Reading configuration file    ####

config = configparser.ConfigParser()


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

class Supervisor:
    def __init__(self) -> None:
        self.queue = queue.SimpleQueue()

    async def loop(self):
        
        await asyncio.sleep(5.0)
        print("end Wait1")
        print(workoutManager.workouts.getWorkoutNames())

        workoutManager.startWorkout(0)
        await asyncio.sleep(30.0)


        #await asyncio.sleep(5.0)
        dataAndFlagContainer.programmeRunningFlag = False
        print("Supervisor Closed")
    
supervisor = Supervisor()

async def main():
   
    lock = asyncio.Lock()

    await asyncio.gather(
        #connection_to_BLE_Device(lock, device_heartRateSensor, dataAndFlagContainer),
        #connection_to_BLE_Device(lock, device_turboTrainer,    dataAndFlagContainer),
        supervisor.loop(),
        workoutManager.run(device_turboTrainer)
    )


####    Trigger Main    ####
asyncio.run(main())

