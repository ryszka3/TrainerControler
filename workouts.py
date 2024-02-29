import logging
import json
import queue
import datetime
import time
import csv
import asyncio
import os
import GPIO
from   datatypes   import QueueEntry, DataContainer, WorkoutProgram, WorkoutSegment, CSV_headers
from   BLE_Device  import FitnessMachine
from   TCX         import TCXWriter


class Buzzer:
    def __init__(self, pin) -> None:
        self.pin = pin
        self.busy: bool = False
        self.gpio = GPIO.get_platform_gpio()
        self.gpio.setup(self.pin, GPIO.OUT)
        self.gpio.output(self.pin, False)


    async def beep(self, number_of_beeps: int, on_duration: float, period: float) -> None:
        self.busy = True
        for b in range(number_of_beeps):
            self.gpio.output(self.pin, True)
            await asyncio.sleep(on_duration)
            self.gpio.output(self.pin, False)
            await asyncio.sleep(period - on_duration)
        self.busy = False



class Workouts:

    def __init__(self) -> None:
        self.reloadFromFile()


    def saveToFile(self) -> None:

        dataToJSON = list()

        workoutObject: WorkoutProgram
        for workoutObject in self.listOfWorkouts:

            segmentsList: list = list()

            segmentObject: WorkoutSegment
            for segmentObject in workoutObject.segments:
                segmentDict = {"Type": segmentObject.segmentType, "Duration": segmentObject.duration, "Setting": segmentObject.setting}
                segmentsList.append(segmentDict)

            workoutDict = {"Name": workoutObject.name, "Segments": segmentsList}

            dataToJSON.append(workoutDict)

        with open('Programs.json', 'wt') as json_file:
            json.dump(dataToJSON, fp=json_file, indent=4)

    
    

    def reloadFromFile(self) -> None:
        
        with open('Programs.json', 'r+t') as json_file:
           json_data: list = json.load(json_file)
        
        self.listOfWorkouts: list = list()

        for entry in json_data:
            segments = list()

            for seg in entry["Segments"]:
                thisSegment = WorkoutSegment(seg["Type"], seg["Duration"], seg["Setting"])
                segments.append(thisSegment)

            workout = WorkoutProgram()
            workout.name = entry["Name"]
            workout.segments = segments
            self.listOfWorkouts.append(workout)


    def getWorkoutNames(self) -> list:
        ret = list()
        workout: WorkoutProgram
        for workout in self.listOfWorkouts:
            ret.append(workout.name)
        return ret

    def newWorkout(self, name:str=None) -> tuple:
        
        workout = WorkoutProgram()

        if name is None:
            name = datetime.datetime.now().strftime("wk-%y%m%d-%H%m")
        workout.name = name
        segment = WorkoutSegment()
        workout.segments = [segment]
        self.listOfWorkouts.append(workout)
        workoutID = len(self.listOfWorkouts)-1

        return (self.listOfWorkouts[workoutID],workoutID)

    def getWorkout(self, workoutID: int) -> WorkoutProgram:
        return self.listOfWorkouts[workoutID]

    def getListOfWorkoutParametres(self, rangeToGet: tuple ) -> list:

        start, stop = rangeToGet
        ret = list()

        for i in range(start, stop + 1):
            try:
                prog: WorkoutProgram = self.listOfWorkouts[i]
                ret.append(prog.getParameters())
            except:
                pass

        return ret



class WorkoutManager():
    
    def __init__(self) -> None:
        self.state:str = "IDLE"
        self.currentWorkout: WorkoutProgram = None
        self.workoutStartTime = 0
        self.lastSaveTime: float = 0
        self.queue = queue.SimpleQueue()
        self.workouts = Workouts()
        self.dataContainer = DataContainer()
        self.SAVEPERIOD = float(1.0)
        self.writeToTCX: bool = True
        self.filename = None
        self.TCX_Object: TCXWriter = None
        self.buzzer = Buzzer(16)
        self.multiplier:float = 100
        self.current_segment_id = 0


    def numberOfWorkoutPrograms(self) -> int:
        return len(self.workouts.listOfWorkouts)

    def startWorkout(self, workoutID):
        self.queue.put(QueueEntry("Start", workoutID))
    
    async def run(self, TurboTrainer: FitnessMachine, container: DataContainer):
        
        self.dataContainer = container
        print("starting workout manager")
        
        while(self.dataContainer.programRunningFlag == True):
            entry: QueueEntry = None
            

            if not self.queue.empty():
                try:
                    entry = self.queue.get(timeout = 0.2)
                except:
                    raise Exception("Queue exception")


            if self.state == "IDLE": 
                if not entry == None: 
                    if entry.type in ("Start", "Freeride"):
                        if entry.type == "Start":   # Starting a new workout
                            print("Starting program no: ", entry.data)
                            self.currentWorkout = self.workouts.getWorkout(entry.data).copy()   ## Get a local version of the workout
                            self.dataContainer.workoutDuration = self.currentWorkout.getParameters().totalDuration
                            self.dataContainer.distance = 0
                            self.dataContainer.totalEnergy = 0
                            self.state = "WARMUP-PROGRAM"
                            self.current_segment_id = 0
                        
                        elif entry.type == "Freeride":
                            self.state = "WARMUP-FREERIDE"
                        
                        TurboTrainer.subscribeToService(TurboTrainer.UUID_control_point)    # Need to be receiving control point notifications
                        
                        for i in range(3):
                            
                            #initialisation command sequence:
                            TurboTrainer.requestControl()
                            TurboTrainer.reset()
                            TurboTrainer.requestControl()
                            TurboTrainer.start()

                            #wait until device command queue empty but max 3 seconds
                            for j in range(6):
                                await asyncio.sleep(0.5)
                                if TurboTrainer.queue.empty() == True:
                                    break

                            if TurboTrainer.remoteControlAcquired == True:
                                break

                        
                        if TurboTrainer.remoteControlAcquired == False:
                            print("Failed to aquire remote control of the fitness machine!")
                            self.state = "STOP"
                            continue

                        path = "Workouts/" + str(self.dataContainer.activeUser.Name)
                        self.filename = datetime.datetime.now().strftime(path + "/Workout-%y-%m-%d-(%Hh%Mm%S)")

                        try:
                            workout_logfile = open(self.filename+".csv", 'w+', newline='')
                            csvWriter = csv.writer(workout_logfile, dialect='excel')
                            csvWriter.writerow(list(("Workout log file","")))
                            csvWriter.writerow(list(("Created:",
                                                    datetime.datetime.now().strftime("%d %b %Y"),
                                                    "at:",
                                                    datetime.datetime.now().strftime("%X")                                                
                                                    )))
                            csvWriter.writerow(["Type", "Program" if entry.type == "Start" else "Freeride", 
                                                self.currentWorkout.name if entry.type == "Start" else ""])
                            csvWriter.writerow(CSV_headers)
                            print("Workout data file (CSV) created")
                        
                        except:
                            raise Exception("Failed creating a workout data file!")
                        
                        if self.writeToTCX == True:
                            self.TCX_Object = TCXWriter()
                            self.TCX_Object.newLap()
                    
                else:
                    await asyncio.sleep(0.1)
            
            if self.state in ("WARMUP-PROGRAM", "WARMUP-FREERIDE"):
                
                self.multiplier = 100
                await asyncio.sleep(3.0)
                self.state = self.state.removeprefix("WARMUP-")
                self.workoutStartTime = time.time()


            if self.state in ("PAUSED-PROGRAM", "PAUSED_FREERIDE"):
                if not entry == None: 
                    if entry.type == "START":   # Resume
                        TurboTrainer.start()
                        self.state = "PROGRAM"
                else:
                    await asyncio.sleep(0.1)


            if self.state in ("PROGRAM", "FREERIDE"):
                
                if not entry == None: 
                    if entry.type == "STOP":   # Stop the workout, go to STOP to close the datafile
                        self.state = "STOP"
                    
                    elif entry.type == "PAUSE": # Pause the workout, go to PAUSE and await futher instructions
                        TurboTrainer.pause()
                        self.state = "PAUSED-" + self.state

                    elif entry.type == "Set Power":
                        print("Setting power: ", entry.data)
                        TurboTrainer.setTarget("Power", entry.data)
                    
                    elif entry.type == "Set Level":
                        print("Setting level: ", entry.data)
                        TurboTrainer.setTarget("Level", entry.data)

                    elif entry.type == "Multiplier":
                        
                        modifier = 10 if entry.data == "Increase" else -10
                        self.multiplier = min(max(self.multiplier + modifier, 40),300)
                        
                        TurboTrainer.setTarget(self.dataContainer.currentSegment.segmentType, 
                                               self.dataContainer.currentSegment.setting * self.multiplier / 100)
                
                if self.state == "PROGRAM":
                    isSegmentTransition: bool = True
                    try:
                        if self.dataContainer.currentSegment.elapsedTime < self.dataContainer.currentSegment.duration:
                            isSegmentTransition = False
                        if 0 < self.dataContainer.currentSegment.duration - self.dataContainer.currentSegment.elapsedTime <= 3 and self.buzzer.busy == False:
                            beep_task = asyncio.create_task(self.buzzer.beep(3, 0.2, 1))
                            
                    except:
                        pass

                    if isSegmentTransition: #need to start a new segment OR stop the machine
                        if len(self.currentWorkout.segments) > 0:
                            
                            self.dataContainer.currentSegment: WorkoutSegment = self.currentWorkout.segments.pop(0)
                            self.current_segment_id += 1
                            self.dataContainer.currentSegment.startTime = time.time()
                            TurboTrainer.setTarget(self.dataContainer.currentSegment.segmentType, 
                                                   self.dataContainer.currentSegment.setting * self.multiplier / 100)
                            
                            if self.writeToTCX == True:
                                self.TCX_Object.updateLapValues(self.dataContainer)

                                self.TCX_Object.newLap()
                                self.dataContainer.clearLapValues()
                            
                            print("New segment, type:", self.dataContainer.currentSegment.segmentType, 
                                  " Duration: ", self.dataContainer.currentSegment.duration,
                                  " Setting: ", self.dataContainer.currentSegment.setting,
                                  " Start time: ", self.dataContainer.currentSegment.startTime)
                        
                        else:
                            print("End of workout")
                            self.state = "STOP"
                    

                
                self.dataContainer.currentSegment.elapsedTime = time.time() - self.dataContainer.currentSegment.startTime
                self.dataContainer.workoutTime  = time.time() - self.workoutStartTime

                if self.dataContainer.workoutTime - self.lastSaveTime > self.SAVEPERIOD:   # 
                    
                    self.lastSaveTime = self.dataContainer.workoutTime
                    csvWriter.writerow(self.dataContainer.getIterableRecord())
                    self.dataContainer.distance += self.dataContainer.momentary.speed * self.SAVEPERIOD / 3600 # km
                    self.dataContainer.totalEnergy += self.dataContainer.momentary.power * self.SAVEPERIOD / 1000 # kJ

                    if self.writeToTCX == True:
                        self.TCX_Object.addTrackPoint(distance=self.dataContainer.distance*1000, data=self.dataContainer.momentary)
                
                await asyncio.sleep(0.01)
        
            if self.state == "STOP":
                print("Workout Stopped")
                
                ##### reset variables and the state machine #####
                self.currentWorkout = None
                self.dataContainer.workoutTime = 0
                self.dataContainer.currentSegment = WorkoutSegment("Power", 0, 100)
                self.dataContainer.workoutDuration = 0


                #### Release the fitnes machine
                TurboTrainer.unsubscribeFromService(TurboTrainer.UUID_control_point)
                TurboTrainer.stop()
                TurboTrainer.reset()

                self.state = "END"
                await asyncio.sleep(0.01)

            if self.state == "END":
                if not entry == None: 
                    if entry.type == "SAVE":  
                        #### Closing the cvs logfile ####
                        try:
                            csvWriter.writerow(self.dataContainer.getIterableAverages())
                            csvWriter.writerow(self.dataContainer.getIterableMaximums())
                            workout_logfile.close()
                        except:
                            pass

                        ####  Writing TCX file

                        if self.writeToTCX == True:
                            self.TCX_Object.saveToFile(self.filename+".tcx")
                    
                    elif entry.type == "DISCARD":   ## Delete CSV file

                        workout_logfile.close()
                        os.remove(self.filename + ".csv")

                    if entry.type in ("SAVE", "DISCARD"):   ## Common to both save and discard
                        self.TCX_Object = None
                        self.state = "IDLE"
                await asyncio.sleep(0.05)

        else:
            print("Workout manager closed")





