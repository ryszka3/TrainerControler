import asyncio
import configparser
import queue
from   workouts    import WorkoutManager
from   BLE_Device  import HeartRateMonitor, FitnessMachine
from   datatypes   import DataContainer, UserList, QueueEntry, WorkoutSegment
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
                    loopCounter: int = 0
                    MAX_COUNT = 14
                    while self.state == "MainMenu":
                        
                        heartFillColour = lcd.COLOUR_HEART
                        if device_heartRateSensor.connectionState == False and loopCounter > MAX_COUNT / 2 - 1:
                            heartFillColour = lcd.COLOUR_BG_LIGHT
                            device_heartRateSensor.connect = True  ## Maintain this flag true to continue to try to connect   

                        TTFillColour = lcd.COLOUR_TT
                        if device_turboTrainer.connectionState == False and loopCounter < MAX_COUNT / 2 - 1:
                            TTFillColour = lcd.COLOUR_BG_LIGHT
                            device_turboTrainer.connect = True  ## Maintain this flag true to continue to try to connect  

                        #ClimberFillColour = lcd.COLOUR_CLIMBER
                        #if device_climber.connectionState == False and loopCounter > MAX_COUNT / 2 - 1:
                        #    ClimberFillColour = lcd.COLOUR_BG_LIGHT
                        #    device_climber.connect = True  ## Maintain this flag true to continue to try to connect  

                        touch, location = touchScreen.checkTouch()
                        if touch == True:
                            for region in touchActiveRegions:
                                boundary, value = region    #### unpack the tuple containing the area xy tuple and the value
                                if self.isInsideBoundaryBox(touchPoint=location, boundaryBox=boundary):
                                    self.oldState = self.state
                                    self.state = value
                        
                        if self.state == "RideProgramme" or self.state == "Freeride" and device_turboTrainer.connectionState == False:
                            #### no TT connection, display error message, cancel state change
                            lcd.drawConnectionErrorMessage()
                            self.state == "MainMenu"
                            asyncio.sleep(4.0)
                        else:
                            lcd.drawPageMainMenu(heartFillColour, TTFillColour)
                        
                        loopCounter = (loopCounter + 1) % MAX_COUNT
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
                                            ## do end of programme routines
                                            workoutManager.queue.put(QueueEntry("End", 0))
                                            device_turboTrainer.unsubscribeFromService(device_turboTrainer.UUID_indoor_bike_data)

                                            ## then go to the main menu
                                            self.state = "MainMenu"
                                            break

                                        elif workoutManager.state in ("PROGRAM", "FREERIDE"):
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
                        #### if coming from prog select then start the editor
                        editedWorkout = workoutManager.workouts.getWorkout(self.selectedProgramme)
                        editedSegment = WorkoutSegment()
                        selectedSegmentID = None
                        touchActiveRegions = lcd.drawProgrammeEditor(editedWorkout, selectedSegmentID, editedSegment)
                        
                        while self.state == "ProgEdit":
                            
                            touch, location = touchScreen.checkTouch()
                            if touch == True:
                                for region in touchActiveRegions:
                                    boundary, value = region    #### unpack the tuple containing the area xy tuple and the value
                                    if self.isInsideBoundaryBox(touchPoint=location, boundaryBox=boundary):
                                        
                                        if value in ("Power", "Level"):
                                            editedSegment.segmentType = value

                                        elif value in ("- 50", "- 5", "+ 5", "+ 50"):
                                            editedSegment.setting += int(str(value).replace(" ", ""))
                                            #editedSegment.setting = min, max

                                        elif value in ("-10m", "-1m", "+1m", "+10m"):
                                            editedSegment.duration += int(str(value).replace("m","")) * 60

                                        elif value in ("-10s", "+10s"):
                                            editedSegment.duration += int(str(value).replace("m","")) * 1

                                        elif value in range(0, 999):    ## clicked on a segments chart
                                            selectedSegmentID = value
                                            editedSegment = editedWorkout.segments[selectedSegmentID].copy()  ## load segment to editor
                                        
                                        elif value == "Insert":
                                            editedWorkout.insertSegment(selectedSegmentID, editedSegment)

                                        elif value == "Add":
                                            numberOfSegments = len(editedWorkout.segments)
                                            editedWorkout.insertSegment(numberOfSegments, editedSegment)
                                            
                                            ## reset edited seg and pointer
                                            editedSegment = WorkoutSegment()
                                            selectedSegmentID = None

                                        elif value == "Update":
                                            editedWorkout.insertSegment(selectedSegmentID, editedSegment)
                                            
                                            ## reset edited seg and pointer
                                            editedSegment = WorkoutSegment()
                                            selectedSegmentID = None

                                        elif value == "Remove":
                                            editedWorkout.removeSegment(selectedSegmentID)

                                            # reset edited seg and pointer
                                            editedSegment = WorkoutSegment()
                                            selectedSegmentID = None

                                        elif value == "Finish":
                                            pass


                                touchActiveRegions = lcd.drawProgrammeEditor(editedWorkout, selectedSegmentID, editedSegment)


                                        
                
                
                case "ProgSelect":
                    
                    numberOfWorkoutProgrammes = workoutManager.numberOfWorkoutProgrammes()
                    
                    displayedProgrammes = (0, min(4, numberOfWorkoutProgrammes)-1)
                    workoutParametres = workoutManager.workouts.getListOfWorkoutParametres(displayedProgrammes)

                    touchActiveRegions = lcd.drawProgrammeSelector(workoutParametres)

                    while self.state == "ProgSelect":
                        touch, location = touchScreen.checkTouch()
                        if touch == True:
                            for region in touchActiveRegions:
                                boundary, value = region    #### unpack the tuple containing the area xy tuple and the value

                                if value == "NextPage":
                                    displayedProgrammes = (displayedProgrammes(1) + 1, min(displayedProgrammes(1)+4, numberOfWorkoutProgrammes-1))

                                elif value == "PreviousPage":
                                    displayedProgrammes = (displayedProgrammes(0)-4, displayedProgrammes(0)-1)

                                elif self.isInsideBoundaryBox(touchPoint=location, boundaryBox=boundary):
                                    self.selectedProgramme = value
                                    ## then go back to the correct state
                                    self.state = self.oldState
                                    self.oldState = "ProgSelect"
                                    break   ## break the loop, skip new page drawing

                                touchActiveRegions = lcd.drawProgrammeSelector(workoutParametres)   ### draw new page
                                break   ### skip the rest of the loop, b/c page has changes
                        asyncio.sleep(0.1)

                case "Settings":
                    print("state: Settings")
                    #### 
        print("End of main loop")
        

    
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
if __name__ == "__main__":
    asyncio.run(main())

