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
        self.listOfWorkout: list = list()

        for entry in json_data:
            segments = list()

            for seg in entry["Segments"]:
                thisSegment = WorkoutSegment(seg["Type"], seg["Duration"], seg["Setting"], seg["Reps"])
                segments.append(thisSegment)

            workout = WorkoutProgram(entry["Name"], segments)
            self.listOfWorkout.append(workout)

    def getWorkoutNames(self):
        ret = list()
        workout: WorkoutProgram
        for workout in self.listOfWorkout:
            ret.append(workout.name)
        return ret


    def getWorkout(self, workoutID: int) -> WorkoutProgram:
        return self.listOfWorkout[workoutID]

    def getWorkoutParameters(self, workoutID: int) -> WorkoutParameters:
        
        totalDuration: int = 0
        averagePower: int = 0
        averageLevel: int = 0

        noSegments = 0

        segment: WorkoutSegment
        for segment in self.listOfWorkout[workoutID].segments: 
            totalDuration += segment.duration
            noSegments += segment.reps
            if segment.segmentType == "Power":
                averagePower += segment.setting * segment.reps
            elif segment.segmentType     == "Level":
                averageLevel += segment.setting * segment.reps
        
        averagePower /= noSegments
        averageLevel /= noSegments

        return WorkoutParameters(self.listOfWorkout[workoutID].name, totalDuration, averagePower, averageLevel, noSegments)

class WorkoutManager():
    def __init__(self, container: DataContainer) -> None:
        self.state:str = "IDLE"
        self.currentWorkout: WorkoutProgram = None
        self.workoutTimer: int = 0
        self.queue = queue.SimpleQueue()
        self.workouts = Workouts()
        self.currentSegment:WorkoutSegment  = None
        self.dataContainer: DataContainer = container
    
    async def run(self, TurboTrainer: FitnessMachine):
        
        print("starting workout manager")
        while(self.dataContainer.programmeRunningFlag == True):
            entry: QueueEntry = None
            
            if not self.queue.empty():
                try:
                    entry = self.queue.get(timeout = 0.2)
                except:
                    pass


            if self.state == "IDLE": 
                if not entry == None: 
                    if entry.type == "Start":   # Starting a new workout
                     
                        self.currentWorkout = self.workouts.getWorkout(entry.data).copy()   ## Get a local version of the workout
                        self.state = "PROGRAM"
                    
                    elif entry.type == "Freeride":
                        self.state = "FREERIDE"
                    
                    try:
                        workout_logfile = open(datetime.datetime.now().strftime("Workouts/Workout-%y-%m-%d-(%Hh%Mm%S).csv"), 'w+', newline='')
                        csvWriter = csv.writer(workout_logfile, dialect='excel')
                        csvWriter.writerow(list(("Workout log file","")))
                        csvWriter.writerow(list(("Created:",
                                                datetime.datetime.now().strftime("%d %b %Y"),
                                                "at:",
                                                datetime.datetime.now().strftime("%X")                                                
                                                )))
                        csvWriter.writerow(list(("Time", "Cadence", "Power", "HR BPM", "Gradient", "Speed")))
                    
                    except:
                        raise Exception("Failed creating a workout data file!")
                    
                    TurboTrainer.subscribeToService(TurboTrainer.UUID_control_point)    # Need to be receiving control point notifications
                    TurboTrainer.requestControl()
                    
                    if TurboTrainer.remoteControlAcquired == True:
                        TurboTrainer.reset()
                    
                    else:
                        print("Failed to aquire remote control of the fitness machine!")
                        self.state = "STOP"

                else:
                    await asyncio.sleep(0.1)
            

            if self.state == "PAUSED":
                if not entry == None: 
                    if entry.type == "Start":   # Resume
                        self.state = "PROGRAM"
                else:
                    await asyncio.sleep(0.1)


            if self.state == "PROGRAM" or self.state == "FREERIDE":
                
                if not entry == None: 
                    if entry.type == "Stop":   # Stop the workout, go to STOP to close the datafile
                        self.state = "STOP"
                    
                    elif entry.type == "Pause": # Pause the workout, go to PAUSE and await futher instructions
                        self.state = "PAUSED"

                    elif entry.type == "Set Power":
                        TurboTrainer.setTarget("Power", entry.data)
                    
                    elif entry.type == "Set Level":
                        TurboTrainer.setTarget("Level", entry.data)
                
                if self.state == "PROGRAM":
                    isSegmentTransition: bool = True
                    try:
                        if self.currentSegment.elapsedTime < self.currentSegment.duration:
                            isSegmentTransition = False
                    except:
                        pass

                    if isSegmentTransition: #need to start a new segment OR stop the machine
                    
                        if len(self.currentWorkout.segments) > 0:
                            
                            self.currentSegment:WorkoutSegment = self.currentWorkout.segments.pop(0)
                            self.currentSegment.startTime = time.monotonic()
                            TurboTrainer.setTarget(self.currentSegment.segmentType, self.currentSegment.setting)
                            print("new segment")
                        
                        else:
                            print("end of workout")
                            self.state = "STOP"
                    

                await asyncio.sleep(0.1)
                oldElapsedTime = self.currentSegment.elapsedTime
                self.currentSegment.elapsedTime = time.monotonic() - self.currentSegment.startTime

                if self.currentSegment.elapsedTime - oldElapsedTime > 1.0:   # 
                    
                    self.workoutTimer += self.currentSegment.elapsedTime - oldElapsedTime
                    csvWriter.writerow(self.dataContainer.getIterableRecord())
        
            if self.state == "STOP":
                #### Closing the logfile ####
                try:
                    csvWriter.writerow(self.dataContainer.getIterableAverages())
                    csvWriter.writerow(self.dataContainer.getIterableMaximums())
                    workout_logfile.close()
                except:
                    raise Exception("Failed to close the workout data file!")

                ##### reset variables and the state machine #####
                self.state = "IDLE"
                self.currentWorkout = None
                self.workoutTimer = 0
                self.currentSegment.startTime = 0
                self.currentSegment = None
                self.currentSegment.elapsedTime = 0

                #### Release the fitnes machine
                TurboTrainer.unsubscribeFromService(TurboTrainer.UUID_control_point)
        else:
            print("Workout manager closed")





