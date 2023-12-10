

class cd:
    def __init__(self) -> None:
        self.hr = 17
        self.flag: bool = True

currentData = cd()

bar = 17


class foo:
    def __init__(self, dataContainer: cd) -> None:
        self.internal = 5
        self.container = dataContainer
    
    def callback(self, data):
        self.container.hr = data + 5
        print(self.container.flag)

kl = foo(currentData)
 
currentData.flag = False


kl.callback(5)


print(currentData.hr)
