import copy
import json
import datetime
from collections import namedtuple


User = namedtuple("User", ["Name", "Max_HR", "FTP"])

class UserList:
    def __init__(self) -> None:
        
        try:
            json_file = open('users.json', 'r+t')
        except:
            raise Exception("Failed opening JSON file")
        
        json_data: list = json.load(json_file)
        self.listOfUsers: list = list()

        for entry in json_data:
            maxhr = 220 - int(datetime.datetime.now().strftime("%Y")) + entry["YearOfBirth"]
            record = User(entry["Name"], maxhr, entry["FTP"])
            self.listOfUsers.append(record)



class MinMaxIncrement:
    def __init__(self) -> None:
        self.min = 0
        self.max = 0
        self.increment = 0


class WorkoutParameters:
     def __init__(self, name, totalDuration, avgPower, maxPower, totWork, avgLevel, segChartData, minPow) -> None:
        self.name = name
        self.totalDuration = totalDuration
        self.avgPower = avgPower
        self.totalWork = totWork
        self.avgLevel = avgLevel
        self.segmentsChartData:list = segChartData
        self.maxPower = maxPower
        self.minPower = minPow



class WorkoutProgram:
    def __init__(self) -> None:
        self.name: str = None
        self.segments:list = None

    def copy(self):
        return copy.deepcopy(self)
    
    def getParameters(self) -> WorkoutParameters:
        
        totalDuration: int = 0
        maxPower: int = 0
        minPower: int = 24*60*60
        averagePower: int = 0
        averageLevel: int = 0
        totalWork: float = 0
        segmentChartData = list()

        noSegments = 0

        segment: WorkoutSegment
        if self.segments is not None:
            for segment in self.segments: 

                totalDuration += segment.duration
                noSegments += 1
                if segment.segmentType == "Power":

                    averagePower += segment.setting
                    maxPower = max(maxPower, segment.setting)
                    minPower = min(minPower, segment.setting)
                    totalWork += segment.setting * segment.duration
                    chartPoint = tuple((noSegments, segment.setting, segment.duration))
                    segmentChartData.append(chartPoint)
                
                elif segment.segmentType == "Level":
                    averageLevel += segment.setting
        

        totalWork /= 1000
        try:
            averagePower /= noSegments
            averageLevel /= noSegments
        except:
            pass

        return WorkoutParameters(self.name, totalDuration, averagePower, maxPower, totalWork, averageLevel, segmentChartData, minPower)




class WorkoutSegment:
    def __init__(self, segType: str, dur: int, set: int) -> None:
        self.segmentType: str = segType
        self.duration: int = dur
        self.setting: int = set
        self.startTime = 0
        self.elapsedTime = 0


class QueueEntry:
    def __init__(self, messageType: str, data):
        self.type: str = messageType
        self.data = data

class Dataset:
    def __init__(self):
        self.cadence: float = 0
        self.power: float = 0
        self.heartRate: int = 0
        self.gradient: int = 0
        self.speed: float = 0
        self.hrZone: str = 0
    
    def getIterableRecord(self):
        return list((self.cadence,
                     self.power,
                     self.heartRate,
                     self.hrZone,
                     self.gradient,
                     self.speed))


class DataContainer:
    def __init__(self):
        self.workoutTime: int = 0
        self.workoutDuration: int = 0
        self.momentary: Dataset = Dataset()
        self.average: Dataset = Dataset()
        self.max: Dataset = Dataset()
        self.NoAverage:int = 0
        self.programmeRunningFlag = True
        self.activeUser: User = None
        self.currentSegment: WorkoutSegment = None

    def assignUser(self, user):
        self.activeUser = user

    def updateAveragesAndMaximums(self):
        #### Update averages:
        newNoAverage = self.NoAverage + 1
        self.average.cadence = (self.momentary.cadence +(self.NoAverage * self.average.cadence)) / newNoAverage
        self.average.power = (self.momentary.power +(self.NoAverage * self.average.power)) / newNoAverage
        self.average.heartRate = (self.momentary.heartRate +(self.NoAverage * self.average.heartRate)) / newNoAverage
        self.average.gradient = (self.momentary.gradient +(self.NoAverage * self.average.gradient)) / newNoAverage
        self.average.speed = (self.momentary.speed +(self.NoAverage * self.average.speed)) / newNoAverage
        self.NoAverage += 1

        #### Update Maximums:
        self.max.cadence = max(self.max.cadence, self.momentary.cadence)
        self.max.power =  max(self.max.power, self.momentary.power)
        self.max.heartRate = max(self.max.heartRate, self.momentary.heartRate)
        self.max.gradient = max(self.max.gradient, self.momentary.gradient)
        self.max.speed = max(self.max.speed, self.momentary.speed)
        

    def getIterableRecord(self):
        
        ret = [self.workoutTime]
        for val in self.momentary.getIterableRecord():
            ret.append(val)
        return ret
    
    def getIterableAverages(self):
        ret:list = list()
        ret.append("AVERAGE:")
        for val in self.average.getIterableRecord():
            ret.append(val)
        return ret

    def getIterableMaximums(self):
        ret:list = list()
        ret.append("MAX:")
        for val in self.max.getIterableRecord():
            ret.append(val)
        return ret
                         