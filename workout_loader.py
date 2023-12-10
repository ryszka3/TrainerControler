import json
import queue
import datetime
import time
import csv
import asyncio
from   datatypes import QueueEntry, DataContainer

class Workouts:

    def __init__(self):

        try:
            json_file = open('Programmes.json', 'r+t')
        except:
            raise Exception("Failed opening JSON file")
        self.json_data = json.load(json_file)

    def getWorkoutNames(self):
        ret = list()
        for workout in self.json_data:
            ret.append(workout["Name"])
        return ret


    def getWorkout(self, workoutID: int) -> dict:
        return self.json_data[workoutID]

    def getWorkoutParameters(self, workoutID: int):
        
        totalDuration: int = 0
        averagePower: int = 0
        averageLevel: int = 0

        noSegments = 0

        for segment in self.json_data[workoutID]["Segments"]:
            totalDuration += segment["Duration"]
            noSegments += segment["Reps"]
            if segment["Type"] == "Power":
                averagePower += segment["Setting"] * segment["Reps"]
            elif segment["Type"] == "Level":
                averageLevel += segment["Setting"] * segment["Reps"]
        
        averagePower /= noSegments
        averageLevel /= noSegments


        return dict(name = self.json_data[workoutID]["Name"], 
                    duration = totalDuration, 
                    avgPower = averagePower, 
                    averageLevel = averageLevel,
                    noSegments = noSegments
                    )

class WorkoutManager():
    def __init__(self, container: DataContainer) -> None:
        self.state:str = "IDLE"
        self.currentWorkout: dict = None
        self.workoutTimer: int = 0
        self.queue = queue.SimpleQueue()
        self.workouts = Workouts()
        self.currentSegmentStartTime: float= 0
        self.currentSegment:dict  = None
        self.currentSegmentElapsedTime: float = 0
        self.dataContainer = container
    
    async def run(self):
        
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
                        self.state = "RUNNING"
                    
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
                        csvWriter.writerow(list(("Time", "Cadence", "Power", "HR BPM", "Gradient")))
                        
                    except:
                        raise Exception("Failed creating a workout data file!")
                else:
                    await asyncio.sleep(0.1)
            

            if self.state == "PAUSED":
                if not entry == None: 
                    if entry.type == "Start":   # Resume
                        self.state = "RUNNING"
                else:
                    await asyncio.sleep(0.1)


            if self.state == "RUNNING":
                
                if not entry == None: 
                    if entry.type == "Stop":   # Stop the workout, go to STOP to close the datafile
                        self.state = "STOP"
                    
                    elif entry.type == "Pause": # Pause the workout, go to PAUSE and await futher instructions
                        self.state = "PAUSED"
                
                isSegmentTransition: bool = True
                try:
                    if self.currentSegmentElapsedTime < self.currentSegment["Duration"]:
                        isSegmentTransition = False
                except:
                    pass

                if isSegmentTransition: #need to start a new segment OR stop the machine
                   
                    if len(self.currentWorkout["Segments"]) > 0:
                        
                        self.currentSegment = self.currentWorkout["Segments"].pop(0)
                        self.currentSegmentStartTime = time.monotonic()
                        print("new segment")
                    
                    else:
                        
                        print("end of workout")
                        self.state = "STOP"
                
                await asyncio.sleep(0.1)
                oldElapsedTime = self.currentSegmentElapsedTime
                self.currentSegmentElapsedTime = time.monotonic() - self.currentSegmentStartTime

                if self.currentSegmentElapsedTime - oldElapsedTime > 1.0:   # 
                    
                    self.workoutTimer += self.currentSegmentElapsedTime - oldElapsedTime
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
                self.currentSegmentStartTime = 0
                self.currentSegment = None
                self.currentSegmentElapsedTime = 0
        else:
            print("Workout manager closed")