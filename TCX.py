import xml.etree.ElementTree as ET
from datatypes import TCXLap, Dataset
import datetime

class TXCWriter:

    def __init__(self) -> None:
        ET.register_namespace("", "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2")
        self.root  = ET.Element("TrainingCenterDatabase", attrib={"xsi:schemaLocation":"http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2 http://www.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd",
                                                     "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                                                     "xmlns": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"
                                                     })
        self.activities = ET.SubElement(self.root, "Activities")
        self.activity = ET.SubElement(self.activities, "Activity", Sport="Biking")
        self.Id = ET.SubElement(self.activity, 'Id')
        self.Id.text = datetime.datetime.now().strftime("%Y-%m-%dT%H:%m:%SZ")
        self.listOfLaps = list()


    def indent(self, elem, level=0):
        # Add indentation
        indent_size = "  "
        i = "\n" + level * indent_size
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + indent_size
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for elem in elem:
                self.indent(elem, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

    def newLap(self):
        newLap = TCXLap()
        newLap.lap = ET.SubElement(self.activity, "Lap", StartTime=datetime.datetime.now().strftime("%Y-%m-%dT%H:%m:%SZ"))

        newLap.totalTimeSeconds = ET.SubElement(newLap.lap, "TotalTimeSeconds")
        newLap.totalTimeSeconds.text = str(720)

        newLap.distanceMeters = ET.SubElement(newLap.lap, "DistanceMeters")
        newLap.distanceMeters.text = str(2400)

        newLap.maximumSpeed = ET.SubElement(newLap.lap, "MaximumSpeed")
        newLap.maximumSpeed.text = str(24.65)

        newLap.calories = ET.SubElement(newLap.lap, "Calories")
        newLap.calories.text = str(250)    ### energy in kcal goes here

        newLap.averageHR = ET.SubElement(newLap.lap, "AverageHeartRateBpm", attrib={"xsi:type": "HeartRateInBeatsPerMinute_t"})
        newLap.averageHRValue = ET.SubElement(newLap.averageHR, "Value")
        newLap.averageHRValue.text = str(142)

        newLap.maxHR = ET.SubElement(newLap.lap, "MaximumHeartRateBpm", attrib={"xsi:type": "HeartRateInBeatsPerMinute_t"})
        newLap.maxHRValue = ET.SubElement(newLap.maxHR, "Value")
        newLap.maxHRValue.text = str(180)

        newLap.intensity = ET.SubElement(newLap.lap, "Intensity")
        newLap.intensity.text = "Active"

        newLap.trigMethod = ET.SubElement(newLap.lap, "TriggerMethod")
        newLap.trigMethod.text = "Time"

        newLap.track = ET.SubElement(newLap.lap, "Track")

        self.listOfLaps.append(newLap)

    def updateLapValues(self, newparams, LapID = None):
        
        if LapID is None: ## then use most current lap
            LapID = len(self.listOfLaps)-1 

        lap: TCXLap = self.listOfLaps[LapID]

        lap.calories = 1
        lap.distanceMeters = 7
        lap.totalTimeSeconds = 32
        lap.maximumSpeed  =43
        lap.maxHRValue = 134
        lap.averageHRValue = 110



    def addTrackPoint(self, distance, data: Dataset, LapID=None):
        
        if len(self.listOfLaps) == 0:
            return
        
        if LapID is None: ## then use most current lap
            LapID = len(self.listOfLaps)-1 
        
        point = ET.SubElement(self.listOfLaps[LapID].track, "Trackpoint")

        Time = ET.SubElement(point, "Time")
        Time.text = datetime.datetime.now().strftime("%Y-%m-%dT%H:%m:%SZ")

        DistanceMeters = ET.SubElement(point, "DistanceMeters")
        DistanceMeters.text = str(distance)

        Cadence = ET.SubElement(point, "Cadence")
        Cadence.text = str(data.cadence)

        HeartRateBpm = ET.SubElement(point, "HeartRateBpm", attrib={"xsi:type": "HeartRateInBeatsPerMinute_t"})
        hrbpm_val = ET.SubElement(HeartRateBpm, "Value")
        hrbpm_val.text = str(data.heartRate)

        Extensions = ET.SubElement(point, "Extensions")
        Extension_no1 = ET.SubElement(Extensions, "TPX", attrib={"CadenceSensor": "Bike","xmlns":"http://www.garmin.com/xmlschemas/ActivityExtension/v2"})

        Speed = ET.SubElement(Extension_no1, "Speed")
        Speed.text = str(data.speed)

        Watts = ET.SubElement(Extension_no1, "Watts")
        Watts.text = str(data.power)


    def saveToFile(self, filename):
        xmlstr = ET.tostring(self.root, encoding="unicode")
        root2 = ET.fromstring(xmlstr)

        self.indent(root2)
        xmlstr = str("<?xml version=\'1.0\' encoding=\'UTF-8\'?>\n") + ET.tostring(root2, encoding="unicode")

        with open(filename, "wt") as file:
            file.write(xmlstr)


