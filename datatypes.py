import logging
import copy
import json
import datetime
from collections import namedtuple


CSV_headers = ["T","Cadence","Power","HR BPM","HR Zone","Gradient","Speed","Distance","Energy", "Time"]
WorkoutParameters = namedtuple("WorkoutParameters", ["name", "totalDuration", "avgPower", "maxPower", "totalWork", "avgLevel", "segmentsChartData", "minPower"])

class TCXLap:
    def __init__(self) -> None:
        self.lap = None
        self.totalTimeSeconds = None
        self.distanceMeters = None
        self.maximumSpeed = None
        self.calories = None
        self.averageHR = None
        self.averageHRValue = None
        self.maxHR = None
        self.maxHRValue = None
        self.intensity = None
        self.trigMethod = None
        self.track = None

class User:
    def __init__(self, name, yob, maxhr, FTP, noWorkouts, totalDistance, totalEnergy, picture: str) -> None:
        self.Name = name
        self.yearOfBirth = yob
        self.Max_HR = maxhr
        self.FTP = FTP
        self.noWorkouts = noWorkouts
        self.totalDistance = totalDistance
        self.totalEnergy = totalEnergy
        self.picture = picture


class WorkoutSegment:
    def __init__(self, segType: str = "Power", dur: int = 60, set: int = 150) -> None:
        self.segmentType: str = segType
        self.duration: int = dur
        self.setting: int = set
        self.startTime = 0
        self.elapsedTime = 0

    def copy(self):
        return copy.deepcopy(self)

class MinMaxIncrement:
    def __init__(self) -> None:
        self.min = 0
        self.max = 0
        self.increment = 0

        
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
            record = User(entry["Name"], entry["YearOfBirth"], maxhr, entry["FTP"], 
                          entry["noWorkouts"], entry["totDistance"], entry["totEnergy"], entry["Picture"])
            self.listOfUsers.append(record)

    def updateUserRecord(self, userID: int, noWorkouts: int, distance: float, energy: float):

        self.listOfUsers[userID].noWorkouts = noWorkouts
        self.listOfUsers[userID].totalDistance += distance
        self.listOfUsers[userID].totalEnergy += energy

        dataToJSON = list()

        user: User
        for user in self.listOfUsers:

            userDict = {"Name": user.Name, 
                        "YearOfBirth": user.yearOfBirth, 
                        "FTP": user.FTP, 
                        "noWorkouts": user.noWorkouts, 
                        "totDistance": user.totalDistance, 
                        "totEnergy": user.totalEnergy,
                        "Picture": user.picture}

            dataToJSON.append(userDict)

        with open('users.json', 'wt') as json_file:
            json.dump(dataToJSON, fp=json_file, indent=4)



class WorkoutProgram:
    def __init__(self) -> None:
        self.name: str = None
        self.segments:list = None

    def setName(self, name:int):
        self.name = str(name)

    def appendSegment(self, segment) -> None:
        self.segments.append(segment)

    def insertSegment(self, position: int, segment:WorkoutSegment) -> None:
        self.segments.insert(position, segment)

    def updateSegment(self, position: int, segment: WorkoutSegment) -> None:
        self.segments.pop(position)
        self.segments.insert(position, segment)

    def removeSegment(self, position) -> None:
        self.segments.pop(position)

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

        totalDurationOfPowerSegments = 0
        totalDurationOfLevelSegments = 0

        segment: WorkoutSegment
        if self.segments is not None:
            for segment in self.segments: 

                totalDuration += segment.duration
                
                if segment.segmentType == "Power":

                    totalDurationOfPowerSegments += segment.duration
                    averagePower += segment.setting * segment.duration
                    maxPower = max(maxPower, segment.setting)
                    minPower = min(minPower, segment.setting)
                    totalWork += segment.setting * segment.duration
                    chartPoint = tuple((totalDurationOfPowerSegments, segment.setting, segment.duration))
                    segmentChartData.append(chartPoint)
                
                elif segment.segmentType == "Level":
                    totalDurationOfLevelSegments += segment.duration
                    averageLevel += segment.setting
        

        totalWork /= 1000
        try:
            averagePower /= totalDurationOfPowerSegments
            averageLevel /= totalDurationOfLevelSegments
        except:
            pass

        return WorkoutParameters(name=self.name, totalDuration=totalDuration, avgPower=int(averagePower), 
                                 totalWork=totalWork, maxPower=maxPower, avgLevel=int(averageLevel), 
                                 segmentsChartData=segmentChartData, minPower=minPower)


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
        self.workoutTime = int(0)
        self.workoutDuration = int(0)
        self.momentary: Dataset = Dataset()
        self.average: Dataset = Dataset()
        self.lapAverage: Dataset = Dataset()
        self.max: Dataset = Dataset()
        self.lapMax: Dataset = Dataset()
        self.NoAverages = int(0)
        self.lapNoAverages = int(0)
        self.programRunningFlag = bool(True)
        self.activeUser: User = None
        self.currentSegment: WorkoutSegment = WorkoutSegment("Power", 0, 100)
        self.distance = float(0)    ## km
        self.totalEnergy = float(0) ## kJ

    def assignUser(self, user):
        self.activeUser = user

    def clearLapValues(self):
        self.lapNoAverages = 0
        self.lapMax = Dataset()
        self.lapAverage = Dataset()

    def updateAveragesAndMaximums(self):
        #### Update Gloabal Averages:
        newNoAverage = self.NoAverages + 1
        self.average.cadence = (self.momentary.cadence +(self.NoAverages * self.average.cadence)) / newNoAverage
        self.average.power = (self.momentary.power +(self.NoAverages * self.average.power)) / newNoAverage
        self.average.heartRate = (self.momentary.heartRate +(self.NoAverages * self.average.heartRate)) / newNoAverage
        self.average.gradient = (self.momentary.gradient +(self.NoAverages * self.average.gradient)) / newNoAverage
        self.average.speed = (self.momentary.speed +(self.NoAverages * self.average.speed)) / newNoAverage
        self.NoAverages += 1

        #### Update Lap Averages:
        newLapNoAverage = self.lapNoAverages + 1
        self.lapAverage.cadence = (self.momentary.cadence +(self.lapNoAverages * self.lapAverage.cadence)) / newLapNoAverage
        self.lapAverage.power = (self.momentary.power +(self.lapNoAverages * self.lapAverage.power)) / newLapNoAverage
        self.lapAverage.heartRate = (self.momentary.heartRate +(self.lapNoAverages * self.lapAverage.heartRate)) / newLapNoAverage
        self.lapAverage.gradient = (self.momentary.gradient +(self.lapNoAverages * self.lapAverage.gradient)) / newLapNoAverage
        self.lapAverage.speed = (self.momentary.speed +(self.lapNoAverages * self.lapAverage.speed)) / newLapNoAverage
        self.lapNoAverages += 1

        #### Update Global Maximums:
        self.max.cadence = max(self.max.cadence, self.momentary.cadence)
        self.max.power =  max(self.max.power, self.momentary.power)
        self.max.heartRate = max(self.max.heartRate, self.momentary.heartRate)
        self.max.gradient = max(self.max.gradient, self.momentary.gradient)
        self.max.speed = max(self.max.speed, self.momentary.speed)

        #### Update Lap Maximums:
        self.lapMax.cadence = max(self.lapMax.cadence, self.momentary.cadence)
        self.lapMax.power =  max(self.lapMax.power, self.momentary.power)
        self.lapMax.heartRate = max(self.lapMax.heartRate, self.momentary.heartRate)
        self.lapMax.gradient = max(self.lapMax.gradient, self.momentary.gradient)
        self.lapMax.speed = max(self.lapMax.speed, self.momentary.speed)

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

        ret.append(self.distance)
        ret.append(self.totalEnergy)
        ret.append(self.workoutTime)
            
        return ret
                         