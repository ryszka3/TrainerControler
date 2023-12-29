import asyncio
import configparser
import queue
from   workouts    import WorkoutManager
from   BLE_Device  import HeartRateMonitor, FitnessMachine
from   datatypes   import DataContainer, UserList, QueueEntry
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

    def isInsideBoundaryBox(self, touchPoint: tuple, boundaryBox: tuple):
        
        x_touch, y_touch = touchPoint
        x1_box, y1_box, x2_box, y2_box = boundaryBox

        if x_touch >= x1_box and x_touch <= x2_box:
            if y_touch >= y1_box and y_touch <= y2_box:
                return True
            
        return False


    async def loopy(self):

        dataAndFlagContainer.assignUser(userList.listOfUsers[0])
        lcd.assignDataContainer(dataAndFlagContainer)
        
        while True:     #### Main loop
            match self.state:
                case "MainMenu":
                    print("state: Main menu")
                    touchActiveRegions = lcd.drawPageMainMenu()
                    while self.state == "MainMenu":
                        lcd.drawPageMainMenu()
                        touch, location = touchScreen.checkTouch()
                        if touch == True:
                            for region in touchActiveRegions:
                                boundary, value = region    #### unpack the tuple containing the area xy tuple and the value
                                if self.isInsideBoundaryBox(touchPoint=location, boundaryBox=boundary):
                                    self.oldState = self.state
                                    self.state = value
                        asyncio.sleep(0.1)

                case "RideProgramme":

                    if self.oldState == "MainMenu": ## if coming from the menu then go to prog select first 
                        self.oldState = "RideProgramme"
                        self.state = "ProgSelect"
                        break
                    else:
                        if device_heartRateSensor.connectionState == True:
                            device_heartRateSensor.subscribeToService()
                        if device_turboTrainer.connectionState == True:
                            device_turboTrainer.subscribeToService(device_turboTrainer.UUID_indoor_bike_data)
                        #### if coming from prog select then start the workout
                        touchActiveRegions = lcd.drawPageWorkout("Program", "PROGRAM")
                        workoutManager.startWorkout(self.selectedProgramme)
                        await asyncio.sleep(2)
                        while workoutManager.state != "IDLE":
                            touch, location = touchScreen.checkTouch()
                            if touch == True:
                                for region in touchActiveRegions:
                                    boundary, value = region    #### unpack the tuple containing the area xy tuple and the value
                                    if self.isInsideBoundaryBox(touchPoint=location, boundaryBox=boundary):
                                        
                                        if value == "End":
                                            workoutManager.queue.put(QueueEntry("Stop", 0))

                                        elif workoutManager.state == "PROGRAM":
                                            workoutManager.queue.put(QueueEntry("Pause", 0))

                                        else:
                                            workoutManager.queue.put(QueueEntry("Start", 0))

                            lcd.drawPageWorkout("Program", workoutManager.state)
                            asyncio.sleep(0.1)
                        

                case "ProgEdit":

                    if self.oldState == "MainMenu": ## if coming from the menu then go to prog select first 
                        self.oldState = "ProgEdit"
                        self.state = "ProgSelect"
                        break
                    else:
                        #### if coming from prog select then start the workout
                        #self.selectedProgramme
                        pass
                
                
                case "ProgSelect":

                    workoutParametres = workoutManager.workouts.getListOfWorkoutParametres(0,3)
                    touchActiveRegions = lcd.drawProgrammeSelector(workoutParametres)

                    while self.state == "ProgSelect":
                        touch, location = touchScreen.checkTouch()
                        if touch == True:
                            for region in touchActiveRegions:
                                boundary, value = region    #### unpack the tuple containing the area xy tuple and the value

                                if self.isInsideBoundaryBox(touchPoint=location, boundaryBox=boundary):
                                    self.selectedProgramme = value
                                    ## then go back to the correct state
                                    self.state = self.oldState
                                    self.oldState = "ProgSelect"
                                    break
                        asyncio.sleep(0.1)

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

