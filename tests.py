#import shutil

#import setuptools

#shutil.copytree("Workouts", "C:/users/MichalRyszka/Desktop/Workouts", dirs_exist_ok = True)


from workouts import Workouts

my = Workouts()
my.saveToFile()