

class MQTT_Exporter:

    def __init__(self) -> None:
        self.broker = "broker.emqx.io"
        self.port = 1883
        self.username = None
        self.password = None
        self.client_id = "TrainerControler"
        self.topic = "TrainerControler/MQTT_export"