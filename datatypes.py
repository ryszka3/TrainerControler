import copy

class MinMaxIncrement:
    def __init__(self) -> None:
        self.min = 0
        self.max = 0
        self.increment = 0

class WorkoutProgram:
    def __init__(self, name: str, segs: list) -> None:
        self.name: str = name
        self.segments:list = segs

    def copy(self):
        return copy.deepcopy(self)


class WorkoutSegment:
    def __init__(self, segType: str, dur: int, set: int, rep: int) -> None:
        self.segmentType: str = segType
        self.duration: int = dur
        self.setting: int = set
        self.reps: int = rep
        self.startTime = 0
        self.elapsedTime = 0


class WorkoutParameters:
     def __init__(self, name, totalDuration, avgPower, avgLevel, noSegments) -> None:
        self.name = name
        self.totalDuration = totalDuration
        self.avgPower = avgPower, 
        self.avgLevel = avgLevel,
        self.noSegments = noSegments

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
    
    def getIterableRecord(self):
        return list((self.cadence,
                     self.power,
                     self.heartRate,
                     self.gradient,
                     self.speed))


class DataContainer:
    def __init__(self):
        self.workoutTime: int = 0
        self.momentary: Dataset = Dataset()
        self.average: Dataset = Dataset()
        self.max: Dataset = Dataset()
        self.NoAverage:int = 0
        self.programmeRunningFlag = True

    def updateAverages(self):
        newNoAverage = self.NoAverage + 1
        self.average.cadence = (self.momentary.cadence +(self.NoAverage * self.average.cadence) / newNoAverage)
        self.average.power = (self.momentary.power +(self.NoAverage * self.average.power) / newNoAverage)
        self.average.heartRate = (self.momentary.heartRate +(self.NoAverage * self.average.heartRate) / newNoAverage)
        self.average.gradient = (self.momentary.gradient +(self.NoAverage * self.average.gradient) / newNoAverage)
        self.average.speed = (self.momentary.speed +(self.NoAverage * self.average.speed) / newNoAverage)
        self.NoAverage += 1

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
                         