import csv
import time
import datetime


class Dataset:
    def __init__(self):
        self.cadence: float = 0
        self.power: float = 0
        self.heartRate: int = 0
        self.gradient: int = 0
    
    def getIterableRecord(self):
        return list((self.cadence,
                     self.power,
                     self.heartRate,
                     self.gradient))

class CurrentData:
    def __init__(self):
        self.workoutTime: int = 0
        self.momentary: Dataset = Dataset()
        self.average: Dataset = Dataset()
        self.max: Dataset = Dataset()
        self.NoAverage:int = 0

    def updateAverages(self):
        newNoAverage = self.NoAverage + 1
        self.average.cadence = (self.momentary.cadence +(self.NoAverage * self.average.cadence) / newNoAverage)
        self.average.power = (self.momentary.power +(self.NoAverage * self.average.power) / newNoAverage)
        self.average.heartRate = (self.momentary.heartRate +(self.NoAverage * self.average.heartRate) / newNoAverage)
        self.average.gradient = (self.momentary.gradient +(self.NoAverage * self.average.gradient) / newNoAverage)
        self.NoAverage += 1

    def getIterableRecord(self):
        
        ret = [self.workoutTime]
        for val in self.momentary.getIterableRecord():
            ret.append(val)
        
        #for val in self.max.getIterableRecord():
        #    ret.append(val)
        return ret
    
    def getIterableAverages(self):
        ret:list = list(("-"))

        for val in self.average.getIterableRecord():
            ret.append(val)
        return ret

                                

currentData = CurrentData()

currentData.workoutTime = 62

currentData.momentary.cadence = 84
currentData.momentary.gradient = 3
currentData.momentary.heartRate = 124
currentData.momentary.power = 183

currentData.average.cadence = 80
currentData.average.gradient = 2
currentData.average.heartRate = 120
currentData.average.power = 180

currentData.max.cadence = 100
currentData.max.gradient = 5
currentData.max.heartRate = 170
currentData.max.power = 230


print(currentData.getIterableRecord())
print(currentData.getIterableAverages())




with open(datetime.datetime.now().strftime("Workouts/Workout-%y-%m-%d-(%Hh%Mm%S).csv"), 'a+', newline='') as csvfile:
    spamwriter = csv.writer(csvfile, dialect='excel')

    spamwriter.writerow(list(("Workout log file","")))
    spamwriter.writerow(list(("Created:",
                                                datetime.datetime.now().strftime("%d %b %Y"),
                                                "at:",
                                                datetime.datetime.now().strftime("%X")                                                
                                                )))
    spamwriter.writerow(list(("Time", "Cadence", "Power", "HR BPM", "Gradient")))
