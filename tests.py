import time
currentSegment:dict  = None
elapsedTime: float = 0
currentSegmentStartTime: float= 0

isSegmentTransition: bool = False
if currentSegmentStartTime == 0:
    isSegmentTransition = True
elif elapsedTime > currentSegment["Duration"]:
    isSegmentTransition = True

if isSegmentTransition: #need to start a new segment
    print("new")
    currentSegmentStartTime = time.monotonic()



isSegmentTransition = True
try:
    if elapsedTime < currentSegment["Duration"]:
        isSegmentTransition = False
except:
    pass

if isSegmentTransition:
    print("newnew")