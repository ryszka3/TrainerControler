import asyncio
import configparser
from   workout_loader     import WorkoutManager
from   BLE_Device         import HeartRateMonitor, FitnessMachine, connection_to_BLE_Device
from   datatypes          import DataContainer

dataAndFlagContainer   = DataContainer()
device_heartRateSensor = HeartRateMonitor(dataAndFlagContainer)
device_turboTrainer    = FitnessMachine(dataAndFlagContainer)
workoutManager         = WorkoutManager(dataAndFlagContainer)

#####    Reading configuration file    ####

config = configparser.ConfigParser()


try:
    config.read('config.ini')
except:
    pass

if 'HeartRateSensor' in config:
    try:
        device_heartRateSensor.address = config['HeartRateSensor']['Address']
        device_heartRateSensor.name    = config['HeartRateSensor']['Sensor_Name']
        device_heartRateSensor.type    = config['HeartRateSensor']['Sensor_Type']
    except:
        raise Exception("Config file does not contain correct entries for devices")
    
if 'TurboTrainer' in config:
    try:
        device_turboTrainer.address = config['TurboTrainer']['Address']
        device_turboTrainer.name    = config['TurboTrainer']['Sensor_Name']
        device_turboTrainer.type    = config['TurboTrainer']['Sensor_Type']
    except:
        raise Exception("Config file does not contain correct entries for devices")


#####    Main Programme functions here    ####

async def supervisor():
    
    await asyncio.sleep(15.0)
    print("end Wait1")

    device_turboTrainer.subscribeToService(device_turboTrainer.UUID_speedCadenceSensorData)
    device_turboTrainer.subscribeToService(device_turboTrainer.UUID_control_point)
    device_turboTrainer.subscribeToService(device_turboTrainer.UUID_powerSensorData)
    device_turboTrainer.subscribeToService(device_turboTrainer.UUID_training_status)
    device_turboTrainer.subscribeToService(device_turboTrainer.UUID_indoor_bike_data)
    device_turboTrainer.subscribeToService(device_turboTrainer.UUID_status)

    await asyncio.sleep(5.0)

    device_turboTrainer.requestFeatures()
    device_turboTrainer.requestSupportedPower()
    device_turboTrainer.requestSupportedResistance()

    await asyncio.sleep(5.0)
    dataAndFlagContainer.programmeRunningFlag = False
    print("Supervisor Closed")
    

async def main():
   
    lock = asyncio.Lock()

    await asyncio.gather(
        connection_to_BLE_Device(lock, device_heartRateSensor, dataAndFlagContainer),
        connection_to_BLE_Device(lock, device_turboTrainer,    dataAndFlagContainer),
        supervisor(),
        workoutManager.run()
    )


####    Trigger Main    ####
asyncio.run(main())

