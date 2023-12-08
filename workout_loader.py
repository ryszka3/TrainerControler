import json


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

