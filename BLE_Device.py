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
        self.connect: bool = False
        self.connectionState: bool = False
        self.queue = queue.SimpleQueue()

    def subscribeToService(self, service_uuid):
        self.queue.put(QueueEntry('Subscribe', service_uuid))

    def unsubscribeFromService(self, service_uuid):
        self.queue.put(QueueEntry('Unsubscribe', service_uuid))