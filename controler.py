import logging
logging.basicConfig(filename='app.log', filemode='a', level=logging.DEBUG)


import asyncio
import configparser
import queue
import os
import csv
import io
import fcntl
import time
import shutil
from   workouts    import WorkoutManager
from   BLE_Device  import HeartRateMonitor, FitnessMachine
from   datatypes   import DataContainer, UserList, QueueEntry, WorkoutSegment, CSV_headers
from   screen      import ScreenManager, TouchScreen
from   mqtt        import MQTT_Exporter



userList               = UserList()
dataAndFlagContainer   = DataContainer()
device_heartRateSensor = HeartRateMonitor()
device_turboTrainer    = FitnessMachine()
workoutManager         = WorkoutManager()
lcd                    = ScreenManager()
touchScreen            = TouchScreen()
mqtt                   = MQTT_Exporter()


def scanUserHistory(userName):
    path = os.getcwd() + "/Workouts/" + userName
    try:
        files_in_folder:str = os.listdir(path=path)
    except:
        return None
    
    list_filtered = [it.removesuffix(".csv") for it in files_in_folder if it.find("Workout") >=0 and it.find(".csv") > 0] 

    ret = list()
    for item in list_filtered:

        filename = path+"/"+item+".csv"
        with open(filename, mode="r") as file:

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

            workoutStats ={"Filename": filename, "Name": name, "Program": program_name, "Averages": averages, "Max": maxs}
        
            ret.append(workoutStats)
    
    return ret



#####    Main Program functions here    ####

class Supervisor:
    def __init__(self) -> None:
        self.queue = queue.SimpleQueue()
        self.state: str = "UserChange"
        self.activeUserID = 0
        self.sleepDuration = 0.02
        self.USBPATH = "/media/usb"
        self.wifi_ssid: str = None
        self.wifi_password: str = None
        self.wifi_status = "Unknown"
        
        MCP3021_I2CADDR = 0x4f
        I2C_SLAVE_COMMAND = 0x0703  #### Tells the OS this is an I2C Slave device

        self.I2C_File =  io.open("/dev/i2c-0", "rb", buffering=0)

        # set device address
        fcntl.ioctl(self.I2C_File, I2C_SLAVE_COMMAND, MCP3021_I2CADDR)


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
    
    async def scan_wlan(self) -> list:
        result = os.popen("sudo iwlist wlan0 scan | grep 'ESSID'")
        result = list(result)

        if "Device or resource busy" in result:
                return []
        else:
            ssid_list = [item.lstrip() for item in result]
            ssid_list = [item.removeprefix("ESSID:\"") for item in ssid_list]
            ssid_list = [item.removesuffix("\"\n") for item in ssid_list]
            return ssid_list

    def read_battery_SOC(self) -> int:

        # Read ADC (0-1023
        adc_reading = 0
        for i in range(5):
            values = list(self.I2C_File.read(2))
            adc_reading += ((values[0] << 8) + values[1]) >> 2
        
        adc_reading /= 5
        
        A = 1.2
        B = 540
        
        soc = (adc_reading - B) / A

        return max(0, min(int(soc), 100))
    
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
    
    async def state_discover(self) -> None:

        print("state: state Discover method")
        self.touchActiveRegions = lcd.draw_page_ble_discovery(self.state)
        
        if self.state == "HeartRateSensor":
            device = device_heartRateSensor
        elif self.state == "TurboTrainer":
            device = device_turboTrainer
        
        async def draw_scan_progress_bar():
            for i in range(25):
                print("Drawing progress bar")
                self.touchActiveRegions = lcd.draw_page_ble_discovery(self.state, None, None, scan_completion_percentage=i*4)
                await asyncio.sleep(0.4)

        print("Scanner: awaiting lock")
        async with self.lock:
            progress_bar_task = asyncio.create_task(draw_scan_progress_bar())
            self.discovered_devices = []
            self.discovered_devices = await device.discover_available_devices()

        self.last_item = min(len(self.discovered_devices), 4)
        await progress_bar_task
        self.selected_ble_device = None
        self.touchActiveRegions = lcd.draw_page_ble_discovery(self.state, self.discovered_devices, self.last_item)

        async def processTouch(value) -> bool:

            if value == "Back":
                return True
            
            elif value == "Next":
                self.last_item = min(len(self.discovered_devices), self.last_item + 4)
                
            elif value == "Previous":
                self.last_item = max(4, self.last_item - 4)

            elif value == "Rescan":
                self.discovered_devices = await device.discover_available_devices()
                self.last_item = min(len(self.discovered_devices), 4)

            else:
                self.selected_ble_device = value
                return True
            
            self.touchActiveRegions = lcd.draw_page_ble_discovery(self.state, self.discovered_devices, self.last_item)   
            return False
        
        await self.touchTester(processTouch)

        if self.selected_ble_device is not None:

            config.set(self.state, "sensor_name", self.discovered_devices[self.selected_ble_device]["Name"])
            config.set(self.state, "address", self.discovered_devices[self.selected_ble_device]["Address"])

            with open('config.ini', 'wt') as file:
                config.write(file)

            lcd.drawMessageBox("Config file updated", ("OK",))
            await asyncio.sleep(4)
        
        self.state = "Settings"
        

    async def state_main_menu(self):
        
        print("state: main menu method")
        soc = self.read_battery_SOC()
        self.touchActiveRegions = lcd.drawPageMainMenu(lcd.COLOUR_HEART, lcd.COLOUR_TT, soc)
        
        timer_heart   = time.time()
        timer_trainer = time.time()
        timer_soc     = time.time()

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

            if time.time() - timer_soc > 15:
                soc = self.read_battery_SOC()
                timer_soc = time.time()

            async def processTouch(value: str) -> bool:
                self.state = value
                return True
            
            await self.touchTester(processTouch, timeout=0.25)
    
            if self.state in ("RideProgram", "Freeride") and device_turboTrainer.connectionState == False:
                #### no TT connection, display error message, cancel state change
                lcd.drawConnectionErrorMessage()
                self.state = "MainMenu"
                await asyncio.sleep(4.0)
                        
            lcd.drawPageMainMenu(heart_fill_colour, trainer_fill_colour, soc)

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

            elif value == "Pause":
                workoutManager.queue.put(QueueEntry("PAUSE", 0))

            elif value == "Resume":
                workoutManager.queue.put(QueueEntry("START", 0))

            elif value in ("Increase", "Decrease"):
                workoutManager.queue.put(QueueEntry("Multiplier", value))
            
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
        t0 = time.time()
        soc: int = self.read_battery_SOC()
        while workoutManager.state != "END":
            self.touchActiveRegions = lcd.drawPageWorkout("Program", workoutManager.state, workoutManager.workouts.getWorkout(self.selected_program).getParameters(),
                                workoutManager.multiplier, workoutManager.current_segment_id, soc)
            await self.touchTester(processTouch, 0.25)
            if time.time() - t0 > 15:
                soc = self.read_battery_SOC()
                t0 = time.time()
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

    async def state_settings(self, buttons_screeen_names, buttons_touch_labels, back_state) -> None: 
        print("state: Setting method")
        self.touchActiveRegions = lcd.drawPageSettings(buttons_screeen_names, buttons_touch_labels, back_state)
        
        async def processTouch(value: str) -> bool:
            self.state = value
            return True

        await self.touchTester(processTouch)
    
    async def state_settings_mqtt(self):

        print("state: Setting method")

        self.touchActiveRegions = lcd.draw_page_settings_mqtt(mqtt)
        
        async def processTouch(value: str) -> bool:
            if value == "Broker":
                mqtt.broker = await self.stringEdit(mqtt.broker)
                config.set("MQTT", "broker", mqtt.broker)
                
            elif value == "Port":
                mqtt.port = int(await self.stringEdit(str(mqtt.port)))
                config.set("MQTT", "port", str(mqtt.port))

            elif value == "Topic":
                mqtt.topic = await self.stringEdit(mqtt.topic)
                config.set("MQTT", "topic", mqtt.topic)

            elif value == "Client ID":
                mqtt.client_id = await self.stringEdit(mqtt.client_id)
                config.set("MQTT", "client_id", mqtt.client_id)

            elif value == "Username":
                mqtt.username = await self.stringEdit(mqtt.username)
                config.set("MQTT", "username", mqtt.username)

            elif value == "Password":
                mqtt.password = await self.stringEdit(mqtt.password)
                config.set("MQTT", "password", mqtt.password)

            elif value == "Save":
          
                with open('config.ini', 'wt') as file:
                    config.write(file)

                return True
            
            elif value == "Discard":
                try:
                    mqtt.broker   = config["MQTT"]["broker"]
                    mqtt.port = int(config["MQTT"]["port"])
                    mqtt.username = config["MQTT"]["username"]
                    if mqtt.username == "None":
                        mqtt.username = None
                    mqtt.password = config["MQTT"]["password"]
                    if mqtt.password == "None":
                        mqtt.password = None
                    mqtt.client_id =config["MQTT"]["client_id"]
                    mqtt.topic     =config["MQTT"]["topic"]

                except:
                    mqtt.broker   = "broker.emqx.io"
                    mqtt.port = 1883
                    mqtt.username = None
                    mqtt.password = None
                    mqtt.client_id = "TrainerControler"
                    mqtt.topic     = "TrainerControler/MQTT_export"

                    config.set("MQTT", "broker", mqtt.broker)
                    config.set("MQTT", "port", str(mqtt.port))
                    config.set("MQTT", "topic", mqtt.topic)
                    config.set("MQTT", "client_id", mqtt.client_id)
                    config.set("MQTT", "username", mqtt.username)
                    config.set("MQTT", "password", mqtt.password)

                    with open('config.ini', 'wt') as file:
                        config.write(file)
                
                return True
            
            self.touchActiveRegions = lcd.draw_page_settings_mqtt(mqtt)
            return False

        await self.touchTester(processTouch)
        self.state = "General"

    async def state_settings_wifi(self):
        print("state: Setting method")

        self.list_of_SSID = await self.scan_wlan()
        self.last_item = min(len(self.list_of_SSID),4)
        self.touchActiveRegions = lcd.draw_page_wifi(self.list_of_SSID, self.last_item, self.wifi_ssid, self.wifi_password, self.wifi_status )
        
        async def processTouch(value: str) -> bool:
            if value in ("Save", "Discard"):
                if value == "Save":
                    config.set("WIFI", "ssid", self.wifi_ssid)
                    config.set("WIFI", "password", self.wifi_password)
                    
                    with open('config.ini', 'wt') as file:
                        config.write(file)
                else:
                    self.wifi_ssid = config["WIFI"]["ssid"]
                    self.wifi_password = config["WIFI"]["password"]
                
                self.state = "General"
                return True
            
            elif value == "Next":
                self.last_item = min(self.last_item+1, len(self.list_of_SSID))

            elif value == "Previous":
                self.last_item = max(self.last_item-1, 4)

            elif value == "SSID":
                self.wifi_ssid = await self.stringEdit(self.wifi_ssid)

            elif value == "Password":
                self.wifi_password = await self.stringEdit(self.wifi_password)
                
            elif value == "Connect":
                try:
                    os.system("sudo nmcli d wifi connect {} password {}".format(self.wifi_ssid, self.wifi_password))
                except:
                    self.wifi_status = "Disconnected"
                else:
                    self.wifi_status = "Connected"
            else:
                self.wifi_ssid = value
                
            self.touchActiveRegions = lcd.draw_page_wifi(self.list_of_SSID, self.last_item, self.wifi_ssid, self.wifi_password, self.wifi_status )
            return False
        
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
                self.displayedUsers = (self.displayedUsers[0]-2, self.displayedUsers[0]-1)

            elif value == "NextPage":
                self.displayedUsers = (self.displayedUsers[1] + 1, min(self.displayedUsers[1]+2, numberOfUsers-1))
                    
            else:
                self.activeUserID = value
                dataAndFlagContainer.assignUser(userList.listOfUsers[self.activeUserID])
                self.state = "MainMenu"
                return True
            
            showNextPageButton = True if numberOfUsers > self.displayedUsers[1] + 1 else False
            showPrevPageButton = True if self.displayedUsers[0] > 0 else False
            self.touchActiveRegions = lcd.drawPageUserSelect(userList, self.displayedUsers, showPrevPageButton, showNextPageButton)
            
            return False

        await self.touchTester(processTouch)

    async def state_user_edit(self) -> None:
        print("state: user edit method")
        self.touchActiveRegions = lcd.draw_page_user_editor(userList.listOfUsers[self.activeUserID])
        

        async def processTouch(value) -> bool:

            if value == "Add new user":
                new_user_id = userList.new_user()
                self.activeUserID = new_user_id
                dataAndFlagContainer.assignUser(userList.listOfUsers[self.activeUserID])

            elif value == "Change user":
                await self.state_user_change()

            elif value == "Delete user":
                self.touchActiveRegions = lcd.drawMessageBox("Delete user " + dataAndFlagContainer.activeUser.Name + "?", ("Delete", "Cancel"))
                
                async def process_touch_delete_user(value) -> bool:
                    if value == "Delete":
                        new_user_id = userList.delete_user(self.activeUserID)
                        self.activeUserID = new_user_id
                        dataAndFlagContainer.assignUser(userList.listOfUsers[self.activeUserID])
                    
                    return True
                
                await self.touchTester(process_touch_delete_user)
            
            elif value == "Name":
                new_name = await self.stringEdit(dataAndFlagContainer.activeUser.Name)
                dataAndFlagContainer.activeUser.Name = new_name

            elif value == "Picture":
                new_pic_filename = await self.stringEdit(dataAndFlagContainer.activeUser.picture)
                dataAndFlagContainer.activeUser.picture = new_pic_filename

            elif value == "YoB":
                try:
                    new_yob = int(await self.stringEdit(str(dataAndFlagContainer.activeUser.yearOfBirth)))
                    if new_yob > 1950 and new_yob < 2024:
                        dataAndFlagContainer.activeUser.yearOfBirth = new_yob
                except:
                    pass
                

            elif value == "FTP":
                try:
                    new_ftp = int(await self.stringEdit(str(dataAndFlagContainer.activeUser.FTP)))
                    if new_yob > 1950 and new_yob < 2024:
                        dataAndFlagContainer.activeUser.FTP = new_ftp
                except:
                    pass


            elif value == "Finish":
                self.touchActiveRegions = lcd.drawMessageBox("Finish editing?", ("Save edits", "Discard edits", "Cancel"))
                
                async def process_touch_finish_editing(value) -> bool:
                    
                    if value == "Save edits":
                        userList.save_user_list()
                        self.state = "Settings"

                    elif value == "Discard edits":
                        userList.reload_user_profiles()
                        dataAndFlagContainer.assignUser(self.activeUserID)
                        self.state = "Settings"
                    
                    return True
                    
                await self.touchTester(process_touch_finish_editing)

                if self.state == "Settings":
                    return True
                
            self.touchActiveRegions = lcd.draw_page_user_editor(userList.listOfUsers[self.activeUserID])
            return False


        await self.touchTester(processTouch)

    async def stateHistory(self) -> None:
        print("state: history method")

        self.workout_history_list = scanUserHistory(dataAndFlagContainer.activeUser.Name)
        self.last_item = len(self.workout_history_list)-1
        self.plottable_data = ("HR BPM", "Cadence", "Speed", "Power", "Gradient")
        self.selected_chart = 0
        self.selected_record = 0
        self.selected_filename = None
        self.selected_export_method = None

        self.touchActiveRegions = lcd.drawPageHistory(self.workout_history_list, self.last_item)

        async def processTouch(value) -> bool:

            async def copy_file_to_USB() -> None:
                if "sda" in os.listdir("/dev/"):
                    if not os.path.isdir(self.USBPATH):
                        os.system("sudo mkdir " + self.USBPATH)
                    if not os.path.ismount(self.USBPATH):
                        os.system("sudo mount /dev/sda " + self.USBPATH+ " -o umask=000")
                    file_params = self.selected_filename.split("/")
                    file_name = file_params[len(file_params)-1].removesuffix(".csv")
                    shutil.copyfile(self.selected_filename, self.USBPATH + "/" + file_name + ".csv")
                    selected_filename_tcx = self.selected_filename.removesuffix(".csv") + ".tcx"
                    if os.path.exists(selected_filename_tcx):
                        shutil.copyfile(selected_filename_tcx, self.USBPATH + "/" + file_name + ".tcx")
                    
                else:
                    lcd.drawMessageBox("No USB detected!", ("OK", ))
                    await asyncio.sleep(4)

            if value == "MainMenu":
                self.state = "MainMenu"
                return True
            elif value == "Next":
                self.last_item = min(len(self.workout_history_list)-1, self.last_item+1)
            elif value == "Previous": 
                self.last_item = max(0, self.last_item-1)
            elif value == "Export":
                self.touchActiveRegions = lcd.drawMessageBox("Export all workouts?", ("Garmin", "MQTT", "USB", "Cancel"))
                
                async def process_touch_export_options(value) -> bool:
                    self.selected_export_method = value
                    return True
                
                await self.touchTester(process_touch_export_options)

                if self.selected_export_method != "Cancel":
                    if self.selected_export_method == "MQTT":
                        mqtt.connect()
                    
                    for fi in self.workout_history_list:

                        self.selected_filename = fi["Filename"]
                        if self.selected_export_method == "Garmin":
                            pass

                        elif self.selected_export_method == "MQTT":
                            if mqtt.client.is_connected():
                                mqtt.export_file(self.selected_filename)
                                selected_filename_tcx = self.selected_filename.removesuffix(".csv") + ".tcx"
                                if os.path.exists(selected_filename_tcx):
                                    mqtt.export_file(selected_filename_tcx)

                        elif self.selected_export_method == "USB":
                            await copy_file_to_USB()

                        await asyncio.sleep(1)
                    
                    if self.selected_export_method == "MQTT":
                        mqtt.disconnect()
                    
                    if self.selected_export_method == "USB" and os.path.ismount(self.USBPATH):
                            os.system("sudo umount " + self.USBPATH)
                    
                    lcd.drawMessageBox("Export completed", ("OK",))
                    await asyncio.sleep(4)



            else:   ## go to detailed view state
                data_lines = list()
                try:
                    self.selected_filename = self.workout_history_list[value]["Filename"]
                    with open(self.selected_filename) as file:
                        all_lines = file.readlines()
                        first_data_line = -1
                        last_data_line = -1
 
                        for line_number, line in enumerate(all_lines):
                            if line.startswith("T,Cadence"):
                                first_data_line = line_number + 1
                            if line.startswith("AVERAGE:,"):
                                last_data_line = line_number

                        if first_data_line != -1 and last_data_line != -1:
                            data_lines = all_lines[first_data_line: last_data_line]

                    data = [entry for entry in csv.DictReader(data_lines, fieldnames=CSV_headers)]

                    chart1 = self.plottable_data[self.selected_chart]
                    chart2 = self.plottable_data[(self.selected_chart + 1) % len(self.plottable_data)]

                    self.selected_record = value
                    self.touchActiveRegions = lcd.draw_page_historical_record_details(self.workout_history_list[self.selected_record], data, chart1, chart2)
                    
                    async def process_touch_history_details(value) -> bool:
                        
                        if value == "Back":
                            return True
                        elif value == "Export":
                            self.touchActiveRegions = lcd.drawMessageBox("Export workout?", ("Garmin", "MQTT", "USB", "Cancel"))

                            async def process_touch_export_options(value) -> bool:
                                if value == "Cancel":
                                    return True
                                elif value == "Garmin":
                                    return True
                                elif value == "MQTT":
                                    mqtt.connect()
                                    if mqtt.client.is_connected():
                                        mqtt.export_file(self.selected_filename)
                                        selected_filename_tcx = self.selected_filename.removesuffix(".csv") + ".tcx"
                                        if os.path.exists(selected_filename_tcx):
                                            mqtt.export_file(selected_filename_tcx)
                                        mqtt.disconnect()
                                    
                                elif value == "USB":
                                    await copy_file_to_USB()
                                    if os.path.ismount(self.USBPATH):
                                        os.system("sudo umount " + self.USBPATH)
                                
                                lcd.drawMessageBox("Export completed", ("OK",))
                                await asyncio.sleep(4)
                                return True

                            
                            await self.touchTester(process_touch_export_options)

                        elif value == "Next":
                            self.selected_chart = (self.selected_chart+1) % len(self.plottable_data)
                        elif value == "Previous":
                            self.selected_chart = self.selected_chart - 1 if self.selected_chart >= 1 else 4

                        chart1 = self.plottable_data[self.selected_chart]
                        chart2 = self.plottable_data[(self.selected_chart + 1) % len(self.plottable_data)]
                        self.touchActiveRegions = lcd.draw_page_historical_record_details(self.workout_history_list[self.selected_record], data, chart1, chart2)
                    
                        return False
                    
                    await self.touchTester(process_touch_history_details)

                except:
                    lcd.drawMessageBox("Error accesing file!", ("OK", ))
                    await asyncio.sleep(3)
            
            self.touchActiveRegions = lcd.drawPageHistory(self.workout_history_list, self.last_item)
            return False
        
        await self.touchTester(processTouch)    ## touch tester returns when callback returns true


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



    async def loopy(self, lock: asyncio.Lock):
        self.lock = lock
        lcd.assignDataContainer(dataAndFlagContainer)
        
        while True:     #### Main loopS
            if self.state == "MainMenu":
                await self.state_main_menu()

            if self.state == "RideProgram":
                await self.programSelector()
                await self.state_ride_program()

            if self.state == "ProgEdit":
                await self.programSelector()
                await self.state_program_editor()

            if self.state == "Settings":
                buttons_screeen_names = ("Calibrate Touchscreen", "Edit Users", "General", "Connect Trainer", "Connect HR Monitor", "TBD")
                buttons_touch_labels  = ("Calibrate", "UserEdit", "General", "TurboTrainer", "HeartRateSensor", "Climbr")
                await self.state_settings(buttons_screeen_names, buttons_touch_labels, "MainMenu")

            if self.state == "Calibrate": 
                await self.state_calibrate()    

            if self.state == "TurboTrainer":
                await self.state_discover()
                                    
            if self.state == "HeartRateSensor":
                await self.state_discover()
                                    
            if self.state == "Climbr":
                print("state: ", self.state)
                self.state = "MainMenu"

            if self.state == "History":
                await self.stateHistory()

            if self.state == "UserChange":
                await self.state_user_change()

            if self.state == "General":
                buttons_screeen_names = ("MQTT Settings","WiFi Settings")
                await self.state_settings(buttons_screeen_names, None, "Settings")

            if self.state == "MQTT Settings":
                await self.state_settings_mqtt()

            if self.state == "WiFi Settings":
                await self.state_settings_wifi()

            if self.state == "UserEdit":
                await self.state_user_edit()
            
            if dataAndFlagContainer.programRunningFlag == False:
                break                               
           
        print("End of main loop")


supervisor = Supervisor()

#####    Reading configuration file    ####

config = configparser.ConfigParser()

try:
    config.read("config.ini")
except:
    raise Exception("Config files damaged / not available")



try:
    x_multiplier = float(config["TouchScreen"]["X_Multiplier"])
    x_offset =     float(config["TouchScreen"]["X_Offset"])
    y_multiplier = float(config["TouchScreen"]["Y_Multiplier"])
    y_offset =     float(config["TouchScreen"]["Y_Offset"])

    touchScreen.setCalibration(x_multiplier, x_offset, y_multiplier, y_offset)

except:
    supervisor.state = "TurboTrainer"
    asyncio.run(supervisor.state_calibrate())

try:
    device_heartRateSensor.address = config["HeartRateSensor"]["Address"]
    device_heartRateSensor.name    = config["HeartRateSensor"]["Sensor_Name"]
except:
    supervisor.state = "HeartRateSensor"
    asyncio.run(supervisor.state_discover())

try:
    device_turboTrainer.address = config["TurboTrainer"]["Address"]
    device_turboTrainer.name    = config["TurboTrainer"]["Sensor_Name"]
except:
    supervisor.state = "TurboTrainer"
    asyncio.run(supervisor.state_discover())

try:
    mqtt.broker   = config["MQTT"]["broker"]
    mqtt.port = int(config["MQTT"]["port"])
    mqtt.username = config["MQTT"]["username"]
    if mqtt.username == "None":
        mqtt.username = None
    mqtt.password = config["MQTT"]["password"]
    if mqtt.password == "None":
        mqtt.password = None
    mqtt.client_id =config["MQTT"]["client_id"]
    mqtt.topic     =config["MQTT"]["topic"]
except:
    pass

try:
    supervisor.wifi_ssid = config["WIFI"]["ssid"]
    supervisor.wifi_password = config["WIFI"]["password"]
except:
    pass


async def main():
   
    lock = asyncio.Lock()
    supervisor.state = "UserChange"

    await asyncio.gather(
        device_heartRateSensor.connection_to_BLE_Device(lock, dataAndFlagContainer),
        device_turboTrainer.   connection_to_BLE_Device(lock, dataAndFlagContainer),
        supervisor.loopy(lock),
        workoutManager.run(device_turboTrainer, dataAndFlagContainer)
    )


####    Trigger Main    ####
if __name__ == "__main__":
    asyncio.run(main())
    

