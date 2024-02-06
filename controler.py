import logging
logging.basicConfig(filename='app.log', filemode='a', level=logging.DEBUG)


import asyncio, configparser, queue, os, csv
from   workouts    import WorkoutManager
from   BLE_Device  import HeartRateMonitor, FitnessMachine
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
    path = os.getcwd() + "\\Workouts\\" + userName
    try:
        files_in_folder:str = os.listdir(path=path)
    except:
        return None
    
    list_filtered = [it.removesuffix(".csv") for it in files_in_folder if it.find("Workout") >=0 and it.find(".csv") > 0] 
    

    ret = list()
    for item in list_filtered:
        with open(path+"\\"+item+".csv", mode="r") as file:
            last_two_line = file.readlines()[-2:]
            file.seek(0)
            csvObj  = csv.reader(file)
            
            name = None
            program_name = None
            for line in csvObj:
                if line[0] == "Created:":
                    name = line[1]
                    name = name.replace("-", " ")
                    name = name + " at " + line[3]
                elif line[0] == "Type:":
                    program_name = line[2]
                if name is not None and program_name is not None:
                    break
            
            if name is None:
                name = "no name"
            if program_name is None:
                program_name = ""
            
            csvObj2 = csv.DictReader(last_two_line, CSV_headers, restval="")
            list_of_stats = [it for it in csvObj2]
            workoutStats ={"Name":name, "Program": program_name, "Averages":list_of_stats[0], "Max":list_of_stats[1]}
        
            ret.append(workoutStats)
    
    return ret



#####    Main Program functions here    ####

class Supervisor:
    def __init__(self) -> None:
        self.queue = queue.SimpleQueue()
        self.state: str = "UserChange"
        self.oldState: str = "UserChange"
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
    

    
    async def stateHistory(self) -> None:
        print("state: ", "history method")

        workout_history_list = scanUserHistory(dataAndFlagContainer.activeUser)
        last_item = len(workout_history_list)-1

        self.touchActiveRegions = lcd.drawPageHistory(workout_history_list, last_item)

        def processTouch(value) -> bool:

            if value == "MainMenu":
                self.state = "MainMenu"
                self.oldState = "History"
                return True
            elif value == "Next":
                last_item = min(len(workout_history_list)-1, last_item+1)
            elif value == "Previous": 
                last_item = max(0, last_item-1)
            elif value == "Export":
                pass
            else:   ## go to detailed view state
                pass
            
            self.touchActiveRegions = lcd.drawPageHistory(workout_history_list, last_item)
            return False
        
        await self.touchTester(processTouch)    ## touch tester returns when callback returns true



    async def stringEdit(self, string:str) -> str:
        print("state: ", "stringEditor method")     
        
        self.keyboardUpperCase = False
        self.keyboardSpecials = False
        
        self.originalString = string
        self.editedString = string

        self.touchActiveRegions = lcd.drawStringEditor(string)
        
        def processTouch(value) -> bool:
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
    
    
    async def touchTester(self, callback):
        await asyncio.sleep(1.0)    ## Deadzone for touch
        while True: 
            touch, location = touchScreen.checkTouch()
            if touch == True:
                print("Touch! ", location)
                for region in self.touchActiveRegions:
                    boundary, value = region    #### unpack the tuple containing the area xy tuple and the value
                    if self.isInsideBoundaryBox(touchPoint=location, boundaryBox=boundary):
                        if callback(value) == True: 
                            return
                await asyncio.sleep(0.5)    ## Deadzone for touch
            await asyncio.sleep(self.sleepDuration)



    async def loopy(self):

        lcd.assignDataContainer(dataAndFlagContainer)
        
        while True:     #### Main loop
            if self.state == "MainMenu":
                print("state: ", self.state)
                touchActiveRegions = lcd.drawPageMainMenu(lcd.COLOUR_HEART, lcd.COLOUR_TT)
                loopCounter: int = 0
                MAX_COUNT = 5
                await asyncio.sleep(1.0)    ## Deadzone for touch
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
                        print("Touch! ", location)
                        for region in touchActiveRegions:
                            boundary, value = region    #### unpack the tuple containing the area xy tuple and the value
                            if self.isInsideBoundaryBox(touchPoint=location, boundaryBox=boundary):
                                self.oldState = self.state
                                self.state = value
                    
                    if self.state in ("RideProgram", "Freeride") and device_turboTrainer.connectionState == False:
                        #### no TT connection, display error message, cancel state change
                        lcd.drawConnectionErrorMessage()
                        self.state = "MainMenu"
                        await asyncio.sleep(4.0)
                        
                    
                    lcd.drawPageMainMenu(heartFillColour, TTFillColour)
                    
                    loopCounter = (loopCounter + 1) % MAX_COUNT
                    await asyncio.sleep(self.sleepDuration)

            if self.state == "RideProgram":

                print("state: ", self.state)

                if self.oldState == "MainMenu": ## if coming from the menu then go to prog select first 
                    self.oldState = "RideProgram"
                    self.state = "ProgSelect"
                    
                else:
                    #### if coming from prog select then start the workout
                    print("Loop: will be starting program no: ", self.selectedProgram)
                    if device_heartRateSensor.connectionState == True:
                        device_heartRateSensor.subscribeToService()
                    if device_turboTrainer.connectionState == True:
                        device_turboTrainer.subscribeToService(device_turboTrainer.UUID_indoor_bike_data)
                    
                    workoutManager.startWorkout(self.selectedProgram)
                    #### wait for the workout manager to start the program
                    while workoutManager.state == "IDLE":
                        await asyncio.sleep(self.sleepDuration)
                    
                    print("Program execution loop, workout manager state: ", workoutManager.state)

                    touchActiveRegions = lcd.drawPageWorkout("Program", "PROGRAM")
                    await asyncio.sleep(1.0)    ## Deadzone for touch
                    while workoutManager.state != "IDLE":
                        touch, location = touchScreen.checkTouch()
                        if touch == True:
                            print("Touch! ", location)
                            for region in touchActiveRegions:
                                boundary, value = region    #### unpack the tuple containing the area xy tuple and the value
                                if self.isInsideBoundaryBox(touchPoint=location, boundaryBox=boundary):
                                    
                                    if value == "End":
                                        ## do end of program routines
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
                        await asyncio.sleep(self.sleepDuration)
                    #### program has ended
                    print("Execution loop has finished!")
                    userList.updateUserRecord(userID=self.activeUserID,
                                                noWorkouts=dataAndFlagContainer.activeUser.noWorkouts + 1,
                                                distance = dataAndFlagContainer.distance,
                                                energy = dataAndFlagContainer.totalEnergy)
                    
                    self.selectedProgram = None
                    self.oldState = self.state
                    self.state = "MainMenu"


            if self.state == "ProgEdit":

                print("state: ", self.state)

                if self.oldState == "MainMenu": ## if coming from the menu then go to prog select first 
                    self.oldState = "ProgEdit"
                    self.state = "ProgSelect"
                else:
                    #### if coming from prog select then start the editor
                    
                    if self.selectedProgram is not None:
                        editedWorkoutProgram = workoutManager.workouts.getWorkout(self.selectedProgram)
                    else:
                        editedWorkoutProgram, self.selectedProgram = workoutManager.workouts.newWorkout()
                    
                    editedSegment = WorkoutSegment()
                    selectedSegmentID = None
                    touchActiveRegions = lcd.drawProgramEditor(editedWorkoutProgram, selectedSegmentID, editedSegment)
                    await asyncio.sleep(1.0)    ## Deadzone for touch
                    while self.state == "ProgEdit":
                        
                        touch, location = touchScreen.checkTouch()
                        if touch == True:
                            print("Touch! ", location)
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
                                        editedSegment.duration += int(str(value).replace("s","")) * 1

                                    elif value in range(0, 999):    ## clicked on a segments chart
                                        print("Segment selection: ", value)
                                        selectedSegmentID = value
                                        editedSegment = editedWorkoutProgram.segments[selectedSegmentID].copy()  ## load segment to editor
                                    
                                    elif value == "Insert":
                                        editedWorkoutProgram.insertSegment(selectedSegmentID, editedSegment)

                                    elif value == "Add":
                                        editedWorkoutProgram.appendSegment(editedSegment)

                                        ## reset edited seg and pointer
                                        editedSegment = WorkoutSegment()
                                        selectedSegmentID = None

                                    elif value == "Update":
                                        editedWorkoutProgram.updateSegment(selectedSegmentID, editedSegment)
                                        
                                        ## reset edited seg and pointer
                                        editedSegment = WorkoutSegment()
                                        selectedSegmentID = None

                                    elif value == "Name:":
                                        newName = await self.stringEdit(editedWorkoutProgram.name)
                                        editedWorkoutProgram.name = newName

                                    elif value == "Remove":
                                        editedWorkoutProgram.removeSegment(selectedSegmentID)

                                        # reset edited seg and pointer
                                        editedSegment = WorkoutSegment()
                                        selectedSegmentID = None

                                    elif value == "Finish":
                                        touchActiveRegions = lcd.drawMessageBox("Finish editing?", ["Save", "Discard", "Cancel"])
                                        while True:
                                            touch, location = touchScreen.checkTouch()
                                            if touch == True:
                                                for region in touchActiveRegions:
                                                    boundary, value = region    #### unpack the tuple containing the area xy tuple and the value
                                                    if self.isInsideBoundaryBox(touchPoint=location, boundaryBox=boundary):
                                    
                                                        if value == "Save":
                                                            workoutManager.workouts.saveToFile()
                                                            self.state = "MainMenu"
                                                            break

                                                        elif value == "Discard":
                                                            workoutManager.workouts.reloadFromFile()
                                                            self.state = "MainMenu"
                                                            break

                                                        elif value == "Cancel":
                                                            break
                                                else:
                                                    continue    #### if the "for" loop was not broken (i.e. not a valid touch), go to the next iteration of the while loop
                                                
                                                break   ## exits while loop if clicked on a valid button

                                            await asyncio.sleep(self.sleepDuration)


                            touchActiveRegions = lcd.drawProgramEditor(editedWorkoutProgram, selectedSegmentID, editedSegment)
                            await asyncio.sleep(0.5)    ## Deadzone for touch
                        await asyncio.sleep(self.sleepDuration)

            if self.state == "ProgSelect":

                print("state: ", self.state)
                
                numberOfWorkoutPrograms = workoutManager.numberOfWorkoutPrograms()
                
                displayedPrograms = (0, min(4, numberOfWorkoutPrograms)-1)
                workoutParametres = workoutManager.workouts.getListOfWorkoutParametres(displayedPrograms)

                showNextPageButton = False
                showPrevPageButton = False
                showNewProgramButton = False

                if numberOfWorkoutPrograms > 4:
                    showNextPageButton = True

                if self.oldState == "ProgEdit":
                    showNewProgramButton = True

                touchActiveRegions = lcd.drawProgramSelector(workoutParametres, previousEnabled=showPrevPageButton, 
                                                                nextEnabled=showNextPageButton, newProgramEnabled=showNewProgramButton)
                await asyncio.sleep(1.0)    ## Deadzone for touch
                while self.state == "ProgSelect":
                    touch, location = touchScreen.checkTouch()
                    if touch == True:
                        print("Touch! ", location)
                        for region in touchActiveRegions:
                            boundary, value = region    #### unpack the tuple containing the area xy tuple and the value
                            if self.isInsideBoundaryBox(touchPoint=location, boundaryBox=boundary):

                                if value == "NextPage":
                                    displayedPrograms = (displayedPrograms(1) + 1, min(displayedPrograms(1)+4, numberOfWorkoutPrograms-1))

                                elif value == "PreviousPage":
                                    displayedPrograms = (displayedPrograms(0)-4, displayedPrograms(0)-1)

                                elif value == "NewProgram":
                                    self.selectedProgram = None
                                    self.state = self.oldState
                                    self.oldState = "ProgSelect"
                                    break   ## break the loop, skip new page drawing

                                else:
                                    self.selectedProgram = value
                                    ## then go back to the correct state
                                    self.state = self.oldState
                                    self.oldState = "ProgSelect"
                                    break   ## break the loop, skip new page drawing

                                if displayedPrograms[0] > 0:
                                    showPrevPageButton = True
                                else:
                                    showPrevPageButton = False

                                if displayedPrograms[1] < numberOfWorkoutPrograms:
                                    showNextPageButton = True
                                else:
                                    showNextPageButton = False

                                workoutParametres = workoutManager.workouts.getListOfWorkoutParametres(displayedPrograms)
                                touchActiveRegions = lcd.drawProgramSelector(workoutParametres, previousEnabled=showPrevPageButton, 
                                                                nextEnabled=showNextPageButton, newProgramEnabled=showNewProgramButton)
                                await asyncio.sleep(1.0)    ## Deadzone for touch  
                    await asyncio.sleep(self.sleepDuration)

            if self.state == "Settings":
                print("state: ", self.state)
                touchActiveRegions = lcd.drawPageSettings()
                await asyncio.sleep(1.0)    ## Deadzone for touch
                while self.state == "Settings":
                    touch, location = touchScreen.checkTouch()
                    if touch == True:
                        print("Touch! ", location)
                        for region in touchActiveRegions:
                            boundary, value = region    #### unpack the tuple containing the area xy tuple and the value
                            if self.isInsideBoundaryBox(touchPoint=location, boundaryBox=boundary):

                                self.oldState = self.state
                                self.state = value
                                break

                    await asyncio.sleep(self.sleepDuration)

            if self.state == "Calibrate":    ## screen alibration

                print("state: ", self.state)
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
                            # both points acquired,  now do calculation:
                            calibration = touchScreen.calculateCalibrationConstants(requestedPoints=(point1, point2),
                                                                                    measuredPoints= (measuredP1, measuredP2))
                            
                            config.set("TouchScreen", "x_multiplier", str(calibration[0]))
                            config.set("TouchScreen", "x_offset",     str(calibration[1]))
                            config.set("TouchScreen", "y_multiplier", str(calibration[2]))
                            config.set("TouchScreen", "y_offset",     str(calibration[3]))
                            
                            with open('config.ini', 'wt') as file:
                                config.write(file)

                            lcd.drawMessageBox("Calibration applied!", ("OK",))
                            self.oldState = self.state
                            self.state = "MainMenu"
                            await asyncio.sleep(3)

                    await asyncio.sleep(self.sleepDuration)    

            if self.state == "Trainer":
                print("state: ", self.state)

                self.oldState = self.state
                self.state = "MainMenu"
                                    
            if self.state == "HRMonitor":
                print("state: ", self.state)

                self.oldState = self.state
                self.state = "MainMenu"
                                    
            if self.state == "Climbr":
                print("state: ", self.state)

                self.oldState = self.state
                self.state = "MainMenu"

            if self.state == "History":
                await self.stateHistory()

            if self.state == "UserChange":
                print("state: ", self.state)

                numberOfUsers = len(userList.listOfUsers)
                
                displayedUsers = (0, min(2, numberOfUsers)-1)
                print("displaying users:", displayedUsers," out of: ", numberOfUsers)
                showNextPageButton = False
                showPrevPageButton = False

                if numberOfUsers > 2:
                    showNextPageButton = True

                touchActiveRegions = lcd.drawPageUserSelect(userList, displayedUsers, showPrevPageButton, showNextPageButton)
                await asyncio.sleep(1.0)    ## Deadzone for touch
                while self.state == "UserChange":
                    touch, location = touchScreen.checkTouch()
                    if touch == True:
                        print("Touch! ", location)
                        for region in touchActiveRegions:
                            boundary, value = region    #### unpack the tuple containing the area xy tuple and the value
                            if self.isInsideBoundaryBox(touchPoint=location, boundaryBox=boundary):

                                if value == "PreviousPage":
                                    displayedUsers = (displayedUsers(0)-2, displayedUsers(0)-1)

                                elif value == "NextPage":
                                    displayedUsers = (displayedUsers(1) + 1, min(displayedUsers(1)+2, numberOfUsers-1))
                                
                                else:
                                    self.activeUserID = value
                                    dataAndFlagContainer.assignUser(userList.listOfUsers[self.activeUserID])

                                    self.oldState = self.state
                                    self.state = "MainMenu"
                                

                    await asyncio.sleep(self.sleepDuration)
            
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
    

