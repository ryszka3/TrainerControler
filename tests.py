
state = "PROGRAM"


state = "PAUSED-" + state

print(state)

state = state.removeprefix("PAUSED-")

print(state)