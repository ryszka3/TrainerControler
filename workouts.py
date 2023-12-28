import json
import queue
import datetime
import time
import csv
import asyncio
from   datatypes   import QueueEntry, DataContainer, WorkoutProgram, WorkoutSegment, WorkoutParameters
from   BLE_Device  import FitnessMachine


class Workouts:

    def __init__(self):

        try:
            json_file = open('Programmes.json', 'r+t')
        except:
            raise Exception("Failed opening JSON file")
        
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


    def getWorkoutNames(self):
        ret = list()
        workout: WorkoutProgram
        for workout in self.listOfWorkouts:
            ret.append(workout.name)
        return ret


    def getWorkout(self, workoutID: int) -> WorkoutProgram:
        return self.listOfWorkouts[workoutID]

    def getListOfWorkoutParametres(self, start:int, stop:int) -> list:

        ret = list()

        for i in range(start, stop + 1):
            try:
                ret.append(self.listOfWorkouts[i].getParameters())
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
        self.dataContainer: DataContainer = None

    def startWorkout(self, workoutID):
        self.queue.put(QueueEntry("Start", workoutID))
    
    async def run(self, TurboTrainer: FitnessMachine, container: DataContainer):
        
        self.dataContainer = container
        print("starting workout manager")
        
        while(self.dataContainer.programmeRunningFlag == True):
            entry: QueueEntry = None
            

            if not self.queue.empty():
                try:
                    entry = self.queue.get(timeout = 0.2)
                except:
                    raise Exception("Queue exception")


            if self.state == "IDLE": 
                if not entry == None: 
                    
                    if entry.type == "Start":   # Starting a new workout
                        print("Starting programme no: ", entry.data)
                        self.currentWorkout = self.workouts.getWorkout(entry.data).copy()   ## Get a local version of the workout
                        self.dataContainer.workoutDuration = self.workouts.getSingleWorkoutParameters(entry.data).totalDuration
                        self.state = "WARMUP-PROGRAM"
                    
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

                    try:
                        workout_logfile = open(datetime.datetime.now().strftime("Workouts/Workout-%y-%m-%d-(%Hh%Mm%S).csv"), 'w+', newline='')
                        csvWriter = csv.writer(workout_logfile, dialect='excel')
                        csvWriter.writerow(list(("Workout log file","")))
                        csvWriter.writerow(list(("Created:",
                                                datetime.datetime.now().strftime("%d %b %Y"),
                                                "at:",
                                                datetime.datetime.now().strftime("%X")                                                
                                                )))
                        csvWriter.writerow(list(("Time", "Cadence", "Power", "HR BPM", "HR Zone", "Gradient", "Speed")))
                        print("Workout data file created")
                    
                    except:
                        raise Exception("Failed creating a workout data file!")
                    
                else:
                    await asyncio.sleep(0.1)
            
            if self.state == "WARMUP-PROGRAM" or self.state == "WARMUP-FREERIDE":
                
                await asyncio.sleep(3.0)
                self.state = self.state.removeprefix("WARMUP-")
                self.workoutStartTime = time.time()



            if self.state == "PAUSED-PROGRAM" or self.state == "PAUSED_FREERIDE":
                if not entry == None: 
                    if entry.type == "Start":   # Resume
                        TurboTrainer.start()
                        self.state = "PROGRAM"
                else:
                    await asyncio.sleep(0.1)


            if self.state == "PROGRAM" or self.state == "FREERIDE":
                
                if not entry == None: 
                    if entry.type == "Stop":   # Stop the workout, go to STOP to close the datafile
                        self.state = "STOP"
                    
                    elif entry.type == "Pause": # Pause the workout, go to PAUSE and await futher instructions
                        TurboTrainer.pause()
                        self.state = "PAUSED-" + self.state

                    elif entry.type == "Set Power":
                        print("Setting power: ", entry.data)
                        TurboTrainer.setTarget("Power", entry.data)
                    
                    elif entry.type == "Set Level":
                        print("Setting level: ", entry.data)
                        TurboTrainer.setTarget("Level", entry.data)
                
                if self.state == "PROGRAM":
                    isSegmentTransition: bool = True
                    try:
                        if self.dataContainer.currentSegment.elapsedTime < self.dataContainer.currentSegment.duration:
                            isSegmentTransition = False
                    except:
                        pass

                    if isSegmentTransition: #need to start a new segment OR stop the machine
                        if len(self.currentWorkout.segments) > 0:
                            
                            self.dataContainer.currentSegment:WorkoutSegment = self.currentWorkout.segments.pop(0)
                            self.dataContainer.currentSegment.startTime = time.time()
                            TurboTrainer.setTarget(self.dataContainer.currentSegment.segmentType, self.dataContainer.currentSegment.setting)
                            print("new segment, type:", self.dataContainer.currentSegment.segmentType, 
                                  " Duration: ", self.dataContainer.currentSegment.duration,
                                  " Setting: ", self.dataContainer.currentSegment.setting,
                                  " Start time: ", self.dataContainer.currentSegment.startTime)
                        
                        else:
                            print("end of workout")
                            self.state = "STOP"
                    

                
                self.dataContainer.currentSegment.elapsedTime = time.time() - self.dataContainer.currentSegment.startTime
                self.dataContainer.workoutTime  = time.time() - self.workoutStartTime

                if self.dataContainer.workoutTime - self.lastSaveTime > 1.0:   # 
                    
                    self.lastSaveTime = self.dataContainer.workoutTime
                    #print("Saving data, time: ", self.dataContainer.workoutTime)
                    csvWriter.writerow(self.dataContainer.getIterableRecord())
                
                await asyncio.sleep(0.01)
        
            if self.state == "STOP":
                print("Ending  programme")
                #### Closing the logfile ####
                try:
                    csvWriter.writerow(self.dataContainer.getIterableAverages())
                    csvWriter.writerow(self.dataContainer.getIterableMaximums())
                    workout_logfile.close()
                except:
                    pass

                ##### reset variables and the state machine #####
                self.state = "IDLE"
                self.currentWorkout = None
                self.dataContainer.workoutTime = 0
                self.dataContainer.currentSegment = None
                self.dataContainer.workoutDuration = 0


                #### Release the fitnes machine
                TurboTrainer.unsubscribeFromService(TurboTrainer.UUID_control_point)
                TurboTrainer.stop()
                TurboTrainer.reset()
        else:
            print("Workout manager closed")





