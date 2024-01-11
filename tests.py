import xml.etree.ElementTree as ET


def indent(elem, level=0):
    # Add indentation
    indent_size = "  "
    i = "\n" + level * indent_size
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + indent_size
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
        for elem in elem:
            indent(elem, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


root  = ET.Element("TrainingCenterDatabase", attrib={"xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                                                     "xsi:schemaLocation":"http://www.garmin.com/xmlschemas/ActivityExtension/v2 http://www.garmin.com/xmlschemas/ActivityExtensionv2.xsd http://www.garmin.com/xmlschemas/FatCalories/v1 http://www.garmin.com/xmlschemas/fatcalorieextensionv1.xsd http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2 http://www.garmin.com/xmlschemas/TrainingCenterDatabasev2.xsd"})
activities = ET.SubElement(root, "Activities")
activity = ET.SubElement(activities, "Activity", Sport="Biking")
Id = ET.SubElement(activity, 'Id')
Id.text = "date goes here"

Lap = ET.SubElement(activity, "Lap", StartTime=Id.text)

TotalTimeSeconds = ET.SubElement(Lap, "TotalTimeSeconds")
TotalTimeSeconds.text = str(720)

DistanceMeters = ET.SubElement(Lap, "DistanceMeters")
DistanceMeters.text = str(2400)

MaximumSpeed = ET.SubElement(Lap, "MaximumSpeed")
MaximumSpeed.text = str(24.65)

Calories = ET.SubElement(Lap, "Calories")
Calories.text = str(250)    ### energy in kcal goes here


avgHR = ET.SubElement(Lap, "AverageHeartRateBpm", attrib={"xsi:type": "HeartRateInBeatsPerMinute_t"})
avgHRval = ET.SubElement(avgHR, "Value")
avgHRval.text = str(142)

maxHR = ET.SubElement(Lap, "MaximumHeartRateBpm", attrib={"xsi:type": "HeartRateInBeatsPerMinute_t"})
maxHRval = ET.SubElement(maxHR, "Value")
maxHRval.text = str(180)

intens = ET.SubElement(Lap, "Intensity")
intens.text = "Resting"

trigMethod = ET.SubElement(Lap, "TriggerMethod")
trigMethod.text = "Time"

track = ET.SubElement(Lap, "Track")

#trackPoint = ET.SubElement(track, "Trackpoint")

ET.SubElement(track, "Trackpoint")
ET.SubElement(track, "Trackpoint")
ET.SubElement(track, "Trackpoint")



#### Formatting and saving XML string
xmlstr = ET.tostring(root, encoding="unicode")
root2 = ET.fromstring(xmlstr)
indent(root2)
xmlstr = str("<?xml version=\'1.0\' encoding=\'UTF-8\'?>\n") + ET.tostring(root2, encoding="unicode")


with open('wk.tcx', 'wt') as file:
    file.write(xmlstr)
