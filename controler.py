import logging
logging.basicConfig(filename='app.log', filemode='a', level=logging.DEBUG)


import asyncio, configparser, queue, os, csv
import time
from   workouts    import WorkoutManager
from   BLE_Device  import HeartRateMonitor, FitnessMachine, BLE_Device
from   datatypes   import DataContainer, UserList, QueueEntry, WorkoutSegment, CSV_headers
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


if "TouchScreen" in config:
    try:
        x_multiplier = float(config["TouchScreen"]["X_Multiplier"])
        x_offset =     float(config["TouchScreen"]["X_Offset"])
        y_multiplier = float(config["TouchScreen"]["Y_Multiplier"])
        y_offset =     float(config["TouchScreen"]["Y_Offset"])

        touchScreen.setCalibration(x_multiplier, x_offset, y_multiplier, y_offset)

    except:
        pass    # no worries, will use the defaults for now


def scanUserHistory(userName):
    path = os.getcwd() + "/Workouts/" + userName
    try:
        files_in_folder:str = os.listdir(path=path)
    except:
        return None
    
    list_filtered = [it.removesuffix(".csv") for it in files_in_folder if it.find("Workout") >=0 and it.find(".csv") > 0] 

    ret = list()
    for item in list_filtered:
        with open(path+"/"+item+".csv", mode="r") as file:

            csvObj = csv.reader(file)
            
            name = None
            program_name = None
            averages = dict()
            maxs = dict()

            def parseLine(line: list) -> dict:
                var = dict()
                for it, key in enumerate(CSV_headers):
                    try:
                        var[key]=line[it]
                    except:
                        var[key]=""
                return var

            for line in csvObj:
                if line[0] == "Created:":
                    name = line[1].replace("-", " ") + " at " + line[3]
                    
                elif line[0] == "Type:":
                    program_name = line[2]

                elif line[0] == "AVERAGE:":
                    averages = parseLine(line)

                elif line[0] == "MAX:":
                    maxs = parseLine(line)

            
            if name is None:
                name="no name"
            if program_name is None:
                program_name = ""

            workoutStats ={"Name":name, "Program": program_name, "Averages":averages, "Max":maxs}
        
            ret.append(workoutStats)
    
    return ret



#####    Main Program functions here    ####

class Supervisor:
    def __init__(self) -> None:
        self.queue = queue.SimpleQueue()
        self.state: str = "UserChange"
        self.activeUserID = 0
        self.sleepDuration = 0.02

    async def loop(self):
        dataAndFlagContainer.assignUser(userList.listOfUsers[self.activeUserID])
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

        userList.updateUserRecord(userID=self.activeUserID,
                                  noWorkouts=dataAndFlagContainer.activeUser.noWorkouts + 1,
                                  distance = dataAndFlagContainer.distance,
                                  energy = dataAndFlagContainer.totalEnergy)
        
        dataAndFlagContainer.programRunningFlag = False
        print("Supervisor Closed")


    def isInsideBoundaryBox(self, touchPoint: tuple, boundaryBox: tuple):
        
        x_touch, y_touch = touchPoint
        x1_box, y1_box, x2_box, y2_box = boundaryBox

        if x_touch >= x1_box and x_touch <= x2_box:
            if y_touch >= y1_box and y_touch <= y2_box:
                return True
            
        return False

    async def programSelector(self) -> int:
        print("state: Program Selector method")
                
        numberOfWorkoutPrograms = workoutManager.numberOfWorkoutPrograms()
                
        self.displayedPrograms = (0, min(4, numberOfWorkoutPrograms)-1)
        workoutParametres = workoutManager.workouts.getListOfWorkoutParametres(self.displayedPrograms)

        showNextPageButton = True if numberOfWorkoutPrograms > 4 else False
        showPrevPageButton = False

        showNewProgramButton = True if self.state == "ProgEdit" else False

        async def processTouch(value) -> bool:
            if value == "NextPage":
                self.displayedPrograms = (self.displayedPrograms(1) + 1, min(self.displayedPrograms(1)+4, numberOfWorkoutPrograms-1))

            elif value == "PreviousPage":
                self.displayedPrograms = (self.displayedPrograms(0)-4, self.displayedPrograms(0)-1)

            elif value == "NewProgram":
                self.selected_program = None
                return True

            else:
                self.selected_program = value
                return True

            if self.displayedPrograms[0] > 0:
                showPrevPageButton = True
            else:
                showPrevPageButton = False
                showNextPageButton = True if self.displayedPrograms[1] < numberOfWorkoutPrograms else False
            

            workoutParametres = workoutManager.workouts.getListOfWorkoutParametres(self.displayedPrograms)
            showNewProgramButton = True if self.state == "ProgEdit" else False
            self.touchActiveRegions = lcd.drawProgramSelector(workoutParametres, previousEnabled=showPrevPageButton, 
                                                              nextEnabled=showNextPageButton, newProgramEnabled=showNewProgramButton)
            
            return False


        self.touchActiveRegions = lcd.drawProgramSelector(workoutParametres, previousEnabled=showPrevPageButton, 
                                                          nextEnabled=showNextPageButton, newProgramEnabled=showNewProgramButton)
        
        await self.touchTester(processTouch)

    async def stringEdit(self, string:str) -> str:
        print("state: stringEditor method")     
        
        self.keyboardUpperCase = False
        self.keyboardSpecials = False
        
        self.originalString = string
        self.editedString = string

        self.touchActiveRegions = lcd.drawStringEditor(string)
        
        async def processTouch(value) -> bool:
            if   value == "Discard":
                self.editedString = self.originalString
                return True
            elif value == "Bcksp":
                self.editedString=self.editedString[0:-1]
            elif value == "Del":
                pass
            elif value == "Save":
                return True
            elif value == "shift":
                self.keyboardUpperCase = not self.keyboardUpperCase
            elif value == "specials":
                self.keyboardSpecials  = not self.keyboardSpecials
            else:
                self.editedString = self.editedString + value
            
            self.touchActiveRegions = lcd.drawStringEditor(self.editedString, None, None, self.keyboardUpperCase, self.keyboardSpecials)
            return False
        

        await self.touchTester(processTouch)
        return self.editedString   

    async def state_calibrate(self):
        print("state: state Calibrate method")
        
        point1 = (20,20)
        point2 = (300,220)
        
        measuredP1 = None
        measuredP2 = None
        
        lcd.drawPageCalibration(point1)
                
        while self.state == "Calibrate":
            touch, location = touchScreen.checkTouch()
            if touch == True:
                print("Touch! ", location)
                if measuredP1 is None: # first point 
                    measuredP1 = location
                    lcd.drawPageCalibration(point2)
                    await asyncio.sleep(1.0)

                else:
                    measuredP2 = location
                    # both points acquired,  now do the calculation:
                    calibration = touchScreen.calculateCalibrationConstants(requestedPoints=(point1, point2),
                                                                            measuredPoints= (measuredP1, measuredP2))
                            
                    config.set("TouchScreen", "x_multiplier", str(calibration[0]))
                    config.set("TouchScreen", "x_offset",     str(calibration[1]))
                    config.set("TouchScreen", "y_multiplier", str(calibration[2]))
                    config.set("TouchScreen", "y_offset",     str(calibration[3]))
                            
                    with open('config.ini', 'wt') as file:
                        config.write(file)

                    lcd.drawMessageBox("Calibration applied!", ("OK",))
                    self.state = "MainMenu"
                    await asyncio.sleep(3)

            await asyncio.sleep(self.sleepDuration)
    
    async def state_main_menu(self):
        
        print("state: main menu method")
        self.touchActiveRegions = lcd.drawPageMainMenu(lcd.COLOUR_HEART, lcd.COLOUR_TT)
        
        timer_heart = time.time()
        timer_trainer = time.time()

        heart_fill_colour = lcd.COLOUR_BG_LIGHT
        trainer_fill_colour = lcd.COLOUR_BG_LIGHT
        
        
        while self.state == "MainMenu":

            

            if device_heartRateSensor.connectionState == False:
                device_heartRateSensor.connect = True           ## Maintain this flag true to continue to try to connect  
                
                if device_heartRateSensor.hasLock == False:
                    heart_fill_colour = lcd.COLOUR_BG_LIGHT
                elif time.time() - timer_heart > 0.2:
                    heart_fill_colour = lcd.COLOUR_BG_LIGHT if heart_fill_colour == lcd.COLOUR_HEART else lcd.COLOUR_HEART
                    timer_heart = time.time()
            else:
                heart_fill_colour = lcd.COLOUR_HEART

            if device_turboTrainer.connectionState == False:
                device_turboTrainer.connect = True           ## Maintain this flag true to continue to try to connect  
                
                if device_turboTrainer.hasLock == False:
                    trainer_fill_colour = lcd.COLOUR_BG_LIGHT
                elif time.time() - timer_trainer > 0.2:
                    trainer_fill_colour = lcd.COLOUR_BG_LIGHT if trainer_fill_colour == lcd.COLOUR_TT else lcd.COLOUR_TT
                    timer_trainer = time.time()
            else:
                trainer_fill_colour = lcd.COLOUR_TT

            async def processTouch(value: str) -> bool:
                self.state = value
                return True
            
            await self.touchTester(processTouch, timeout=0.25)
    
            if self.state in ("RideProgram", "Freeride") and device_turboTrainer.connectionState == False:
                #### no TT connection, display error message, cancel state change
                lcd.drawConnectionErrorMessage()
                self.state = "MainMenu"
                await asyncio.sleep(4.0)
                        
            lcd.drawPageMainMenu(heart_fill_colour, trainer_fill_colour)

            await asyncio.sleep(self.sleepDuration)
    
    async def state_program_editor(self):
        print("state: Program Editor method")

        if self.selected_program is not None:
            self.edited_workout_program = workoutManager.workouts.getWorkout(self.selected_program)
        else:
            self.edited_workout_program, self.selected_program = workoutManager.workouts.newWorkout()
                
        self.edited_segment = WorkoutSegment()
        self.selected_segment_ID = None
        self.touchActiveRegions = lcd.drawProgramEditor(self.edited_workout_program, self.selected_segment_ID, self.edited_segment)
        
        async def processTouch(value) -> bool:

            if value in ("Power", "Level"):
                self.edited_segment.segmentType = value

            elif value in ("- 50", "- 5", "+ 5", "+ 50"):
                self.edited_segment.setting += int(str(value).replace(" ", ""))
                        #self.editedSegment.setting = min, max

            elif value in ("-10m", "-1m", "+1m", "+10m"):
                self.edited_segment.duration += int(str(value).replace("m","")) * 60

            elif value in ("-10s", "+10s"):
                self.edited_segment.duration += int(str(value).replace("s","")) * 1

            elif value in range(0, 999):    ## clicked on a segments chart
                print("Segment selection: ", value)
                self.selected_segment_ID = value
                self.edited_segment = self.edited_workout_program.segments[self.selected_segment_ID].copy()  ## load segment to editor
                    
            elif value == "Insert":
                self.edited_workout_program.insertSegment(self.selected_segment_ID, self.edited_segment)

            elif value == "Finish":
                self.touchActiveRegions = lcd.drawMessageBox("Finish editing?", ["Save", "Discard", "Cancel"])
                
                async def processTouch(value) -> bool:
                    
                    if value == "Save":
                        workoutManager.workouts.saveToFile()
                        self.state = "MainMenu"
                        return True

                    elif value == "Discard":
                        workoutManager.workouts.reloadFromFile()
                        self.state = "MainMenu"
                        return True

                    elif value == "Cancel":
                        return True
                    
                    return False
                
                await self.touchTester(processTouch)
                if self.state != "ProgEdit":
                    return True
            
            elif value == "Name:":
                newName = await self.stringEdit(self.edited_workout_program.name)
                self.edited_workout_program.name = newName
            
            elif value == "Add":
                self.edited_workout_program.appendSegment(self.edited_segment)

            elif value == "Update":
                self.edited_workout_program.updateSegment(self.selected_segment_ID, self.edited_segment)

            elif value == "Remove":
                self.edited_workout_program.removeSegment(self.selected_segment_ID)

            if value in ("Add", "Update", "Remove"):    # reset edited seg and pointer
                
                self.edited_segment = WorkoutSegment()
                self.selected_segment_ID = None
            
            self.touchActiveRegions = lcd.drawProgramEditor(self.edited_workout_program, self.selected_segment_ID, self.edited_segment)
            return False

        await self.touchTester(processTouch)

    async def state_ride_program(self) -> None:
        print("State: RideProgram method")
        print("Loop: will be starting program no: ", self.selected_program)
        
        if device_heartRateSensor.connectionState == True:
            device_heartRateSensor.subscribeToService()
        if device_turboTrainer.connectionState == True:
            device_turboTrainer.subscribeToService(device_turboTrainer.UUID_indoor_bike_data)
                
        workoutManager.startWorkout(self.selected_program)
                
        while workoutManager.state == "IDLE":       #### wait for the workout manager to start the program
            await asyncio.sleep(self.sleepDuration)

        async def processTouch(value) -> bool:
            if value == "End":              ## do end of program routines      
                workoutManager.queue.put(QueueEntry("STOP", 0))
                device_turboTrainer.unsubscribeFromService(device_turboTrainer.UUID_indoor_bike_data)
                return True

            elif workoutManager.state in ("PROGRAM", "FREERIDE"):
                workoutManager.queue.put(QueueEntry("PAUSE", 0))

            else:
                workoutManager.queue.put(QueueEntry("START", 0))
            
            return False

        async def processTouchMessageBox(value: str) -> bool:
            if value == "Discard":
                workoutManager.queue.put(QueueEntry("DISCARD", 0))
                return True
            
            elif value.startswith("Save"):
                workoutManager.queue.put(QueueEntry("SAVE", 0))

                userList.updateUserRecord(userID = self.activeUserID,
                                  noWorkouts = dataAndFlagContainer.activeUser.noWorkouts + 1,
                                  distance = dataAndFlagContainer.distance,
                                  energy = dataAndFlagContainer.totalEnergy)
                
                if value == "Save + Upload" :
                    #### Code to upload will go here
                    pass

                return True
            
            return False

        print("Program execution loop, workout manager state: ", workoutManager.state)

        self.touchActiveRegions = lcd.drawPageWorkout("Program", "PROGRAM")
        while workoutManager.state != "END":
            await self.touchTester(processTouch, 0.25)
            lcd.drawPageWorkout("Program", workoutManager.state)
            await asyncio.sleep(self.sleepDuration)
        SAVE_DELAY = 15
        t0 = time.time()    
        elapsedTime = 0

        while True:
            option_save = "Save (" + str(round(SAVE_DELAY - elapsedTime)) + ")"
            self.touchActiveRegions = lcd.drawMessageBox("Workout finished!", (option_save, "Save + Upload", "Discard"))
            optionTouched = await self.touchTester(processTouchMessageBox, timeout=1)
            if optionTouched == True:
                break

            await asyncio.sleep(self.sleepDuration)
            elapsedTime = time.time() - t0
            if elapsedTime > SAVE_DELAY:        #### Message box timed out, using default option SAVE
                await processTouchMessageBox("Save")
                break

            
        
        print("Execution loop has finished!")
        self.selected_program = None
        self.state = "MainMenu" 

    async def state_settings(self):
        print("state: Setting method")
        self.touchActiveRegions = lcd.drawPageSettings()
        
        async def processTouch(value: str) -> bool:
            self.state = value
            return True

        await self.touchTester(processTouch)
    
    async def state_user_change(self):
        print("state: user change method")

        numberOfUsers = len(userList.listOfUsers)   
        self.displayedUsers = (0, min(2, numberOfUsers)-1)

        showPrevPageButton = False
        showNextPageButton = True if numberOfUsers > 2 else False

        self.touchActiveRegions = lcd.drawPageUserSelect(userList, self.displayedUsers, showPrevPageButton, showNextPageButton)
        
        async def processTouch(value: str) -> bool:
            
            numberOfUsers = len(userList.listOfUsers)
            
            if value == "PreviousPage":
                self.displayedUsers = (self.displayedUsers(0)-2, self.displayedUsers(0)-1)

            elif value == "NextPage":
                self.displayedUsers = (self.displayedUsers(1) + 1, min(self.displayedUsers(1)+2, numberOfUsers-1))
                    
            else:
                self.activeUserID = value
                dataAndFlagContainer.assignUser(userList.listOfUsers[self.activeUserID])
                self.state = "MainMenu"
                return True
            
            showNextPageButton = True if numberOfUsers > self.displayedUsers[1] else False
            showPrevPageButton = True if self.displayedUsers[0] > 0 else False
            self.touchActiveRegions = lcd.drawPageUserSelect(userList, self.displayedUsers, showPrevPageButton, showNextPageButton)
            
            return False

        await self.touchTester(processTouch)
                        
    async def touchTester(self, callback, timeout:float=None) -> bool:
        t1 = time.time()
        while True if timeout is None else time.time()-t1 < timeout: 
            touch, location = touchScreen.checkTouch()
            if touch == True:
                print("Touch! ", location)
                for region in self.touchActiveRegions:
                    boundary, value = region    #### unpack the tuple containing the area xy tuple and the value
                    if self.isInsideBoundaryBox(touchPoint=location, boundaryBox=boundary):
                        if await callback(value) == True: 
                            return True
                await asyncio.sleep(0.5)    ## Deadzone for touch
            await asyncio.sleep(self.sleepDuration)
        return False



    async def loopy(self):

        lcd.assignDataContainer(dataAndFlagContainer)
        
        while True:     #### Main loop
            if self.state == "MainMenu":
                await self.state_main_menu()

            if self.state == "RideProgram":
                await self.programSelector()
                await self.state_ride_program()

            if self.state == "ProgEdit":
                await self.programSelector()
                await self.state_program_editor()

            if self.state == "Settings":
                await self.state_settings()

            if self.state == "Calibrate": 
                await self.state_calibrate()    

            if self.state == "Trainer":
                print("state: ", self.state)
                self.state = "MainMenu"
                                    
            if self.state == "HRMonitor":
                print("state: ", self.state)
                self.state = "MainMenu"
                                    
            if self.state == "Climbr":
                print("state: ", self.state)
                self.state = "MainMenu"

            if self.state == "History":
                await self.stateHistory()

            if self.state == "UserChange":
                await self.state_user_change()
            
            if dataAndFlagContainer.programRunningFlag == False:
                break                               
           
        print("End of main loop")


    
supervisor = Supervisor()

async def main():
   
    lock = asyncio.Lock()

    await asyncio.gather(
        device_heartRateSensor.connection_to_BLE_Device(lock, dataAndFlagContainer),
        device_turboTrainer.   connection_to_BLE_Device(lock, dataAndFlagContainer),
        supervisor.loopy(),
        workoutManager.run(device_turboTrainer, dataAndFlagContainer)
    )


####    Trigger Main    ####
if __name__ == "__main__":
    asyncio.run(main())
    

