import queue


class QueueEntry:
    def __init__(self, dtype: str, data):
        self.type: str = dtype
        self.data = data

class BLE_Device:
    def __init__(self):
        self.address: str = None
        self.name: str = None
        self.type:str = None
        self.connect: bool = True
        self.connectionState: bool = False
        self.queue = queue.SimpleQueue()

    def subscribeToService(self, service_uuid):
        self.queue.put(QueueEntry('Subscribe', service_uuid))

    def unsubscribeFromService(self, service_uuid):
        self.queue.put(QueueEntry('Unsubscribe', service_uuid))

    def readFromService(self, service_uuid):
        self.queue.put(QueueEntry('Read', service_uuid))

    def writeToService(self, service_uuid, message):
        self.queue.put(QueueEntry('Write', {'UUID': service_uuid, 'Message': message}))
