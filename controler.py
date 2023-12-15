import asyncio
import configparser
import queue
from   workouts    import WorkoutManager
from   BLE_Device  import HeartRateMonitor, FitnessMachine
from   datatypes   import DataContainer, UserList


userList               = UserList()
dataAndFlagContainer   = DataContainer()
device_heartRateSensor = HeartRateMonitor()
device_turboTrainer    = FitnessMachine()
workoutManager         = WorkoutManager()


#####    Reading configuration file    ####

config = configparser.ConfigParser()

try:
    config.read("config.ini")
except:
    raise Exception("Config files damaged / not available")

if "HeartRateSensor" in config:
    try:
        device_heartRateSensor.address = config["HeartRateSensor"]["Address"]
        device_heartRateSensor.name    = config["HeartRateSensor"]["Sensor_Name"]
        device_heartRateSensor.type    = config["HeartRateSensor"]["Sensor_Type"]
    except:
        raise Exception("Config file does not contain correct entries for devices")
    
if "TurboTrainer" in config:
    try:
        device_turboTrainer.address = config["TurboTrainer"]["Address"]
        device_turboTrainer.name    = config["TurboTrainer"]["Sensor_Name"]
        device_turboTrainer.type    = config["TurboTrainer"]["Sensor_Type"]
    except:
        raise Exception("Config file does not contain correct entries for devices")



#####    Main Programme functions here    ####

class Supervisor:
    def __init__(self) -> None:
        self.queue = queue.SimpleQueue()

    async def loop(self):
        dataAndFlagContainer.assignUser(userList.listOfUsers[0])
        await asyncio.sleep(20.0)
        print("end Wait1")
        if device_heartRateSensor.connectionState == True:
            device_heartRateSensor.subscribeToService()
        if device_turboTrainer.connectionState == True:
            device_turboTrainer.subscribeToService(device_turboTrainer.UUID_indoor_bike_data) # should register for internal callback automatically, but check it plz 

        print(workoutManager.workouts.getWorkoutNames())
        workoutManager.startWorkout(0)
        await asyncio.sleep(30.0)
        while workoutManager.state != "IDLE":
            await asyncio.sleep(1) 
        dataAndFlagContainer.programmeRunningFlag = False
        print("Supervisor Closed")
    
supervisor = Supervisor()

async def main():
   
    lock = asyncio.Lock()

    await asyncio.gather(
        device_heartRateSensor.connection_to_BLE_Device(lock, dataAndFlagContainer),
        device_turboTrainer.connection_to_BLE_Device(lock, dataAndFlagContainer),
        supervisor.loop(),
        workoutManager.run(device_turboTrainer, dataAndFlagContainer)
    )


####    Trigger Main    ####
asyncio.run(main())

