import asyncio
import configparser
import queue
from   workouts    import WorkoutManager
from   BLE_Device  import HeartRateMonitor, FitnessMachine
from   datatypes   import DataContainer, UserList
from   screen      import ScreenManager, TouchScreen


userList               = UserList()
dataAndFlagContainer   = DataContainer()
device_heartRateSensor = HeartRateMonitor()
device_turboTrainer    = FitnessMachine()
workoutManager         = WorkoutManager()
lcd                    = ScreenManager()
touchScreen            = TouchScreen()

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
        self.state: str = "MainMenu"
        self.oldState: str = "MainMenu"

    async def loop(self):
        dataAndFlagContainer.assignUser(userList.listOfUsers[0])
        await asyncio.sleep(20.0)
        print("end Wait1")
        if device_heartRateSensor.connectionState == True:
            device_heartRateSensor.subscribeToService()
        #if device_turboTrainer.connectionState == True:
        device_turboTrainer.subscribeToService(device_turboTrainer.UUID_indoor_bike_data)

        print(workoutManager.workouts.getWorkoutNames())
        workoutManager.startWorkout(1)
        await asyncio.sleep(30.0)
        while workoutManager.state != "IDLE":
            await asyncio.sleep(1) 
        dataAndFlagContainer.programmeRunningFlag = False
        print("Supervisor Closed")

    async def loopy(self):
        dataAndFlagContainer.assignUser(userList.listOfUsers[0])
        lcd.assignDataContainer(dataAndFlagContainer)
        
        while True:     #### Main loop
            match self.state:
                case "MainMenu":
                    print("state: Main menu")
                    touchActiveRegions = lcd.drawPageMainMenu()
                    while self.state == "MainMenu":
                        touch, location = touchScreen.checkTouch()
                        if touch == True:
                            for region in touchActiveRegions:
                                if location[0] >= region[0][0] and location[1] >= region[0][1] and location[3] <= region[0][3] and location[4] <= region[0][4]:
                                    self.oldState = self.state
                                    self.state = region[1]

                case "RideProgramme":
                    print("state: Ride a Programme")
                    if self.oldState == "MainMenu": ## if coming from the menu then go to prog select first 
                        self.oldState = "RideProgramme"
                        self.state = "ProgSelect"
                        break
                    else:
                        #### if coming from prog select then start the workout
                        pass

                case "ProgEdit":
                    print("state: Programme editor")
                    if self.oldState == "MainMenu": ## if coming from the menu then go to prog select first 
                        self.oldState = "ProgEdit"
                        self.state = "ProgSelect"
                        break
                    else:
                        #### if coming from prog select then start the workout
                        pass
                case "ProgSelect":
                    print("state: Programme selector")
                    ##select a programme

                    ## then go back to the correct state
                    self.state = self.oldState
                    self.oldState = "ProgEdit"

                case "Settings":
                    print("state: Programme selector")
        



    
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

