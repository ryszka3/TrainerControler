from collections import namedtuple



HeartRateMeasurement = namedtuple('HeartRateMeasurement', ['sensor_contact', 'bpm', 'rr_interval', 'energy_expended'])
IndoorBikeData = namedtuple(
    "IndoorBikeData",
    [
        "instant_speed", # km/h
        "average_speed", # km/h
        "instant_cadence", # rpm
        "average_cadence", # rpm
        "total_distance", # m
        "resistance_level", # unitless
        "instant_power", # W
        "average_power", # W
        "total_energy", # kcal
        "energy_per_hour", # kcal/h
        "energy_per_minute", # kcal/min
        "heart_rate", # bpm
        "metabolic_equivalent", # unitless; metas
        "elapsed_time", # s
        "remaining_time", # s
    ]
)

def parse_hr_measurement(data):
    flags = data[0]

    is_uint16_measurement_mask = 0x01
    is_contact_detected_mask = 0x06
    is_energy_expended_present_mask = 0x08
    is_rr_interval_present_mask = 0x10

    sensor_contact = None
    bpm = None
    rr_interval = []
    energy_expended = None

    measurement_byte_offset = 1
    sensor_contact = bool(flags & is_contact_detected_mask)

    if flags & is_uint16_measurement_mask:
        bpm = int.from_bytes(data[measurement_byte_offset:measurement_byte_offset + 2], 'little')
        measurement_byte_offset += 2
    else:
        bpm = data[measurement_byte_offset]
        measurement_byte_offset += 1

    if flags & is_energy_expended_present_mask:
        energy_expended = int.from_bytes(data[measurement_byte_offset:measurement_byte_offset + 2], 'little')
        measurement_byte_offset += 2

    if flags & is_rr_interval_present_mask:
        while len(data[measurement_byte_offset:]) >= 2:
            rr_interval.append(int.from_bytes(data[measurement_byte_offset:measurement_byte_offset + 2], 'little'))
            measurement_byte_offset += 2

    return HeartRateMeasurement(sensor_contact=sensor_contact,
                                bpm=bpm,
                                rr_interval=rr_interval,
                                energy_expended=energy_expended)



def parse_indoor_bike_data(message) -> IndoorBikeData:
    flag_more_data = bool(message[0] & 0b00000001)
    flag_average_speed = bool(message[0] & 0b00000010)
    # ANOMALY: In the Bluetooth SIG spec, instantaneous_cadence is reversed (0
    # means present, 1 means not present). The Huawei docs do not mention this
    # reversal. In practice, the Huawei docs seem correct. There is no
    # reversal.
    flag_instantaneous_cadence = bool(message[0] & 0b00000100)
    flag_average_cadence = bool(message[0] & 0b00001000)
    flag_total_distance = bool(message[0] & 0b00010000)
    flag_resistance_level = bool(message[0] & 0b00100000)
    flag_instantaneous_power = bool(message[0] & 0b01000000)
    flag_average_power = bool(message[0] & 0b10000000)
    flag_expended_energy = bool(message[1] & 0b00000001)
    flag_heart_rate = bool(message[1] & 0b00000010)
    flag_metabolic_equivalent = bool(message[1] & 0b00000100)
    flag_elapsed_time = bool(message[1] & 0b00001000)
    flag_remaining_time = bool(message[1] & 0b00010000)

    instant_speed = None
    average_speed = None
    instant_cadence = None
    average_cadence = None
    total_distance = None
    resistance_level = None
    instant_power = None
    average_power = None
    total_energy = None
    energy_per_hour = None
    energy_per_minute = None
    heart_rate = None
    metabolic_equivalent = None
    elapsed_time = None
    remaining_time = None

    # for each True flag, get the value
    # confusingly, the order of the flags is not the same as the order of the
    # values
    i = 2  # start after the flags
    if flag_more_data == 0:
        instant_speed = int.from_bytes(message[i : i + 2], "little", signed=False)/100
        i += 2
    if flag_average_speed:
        average_speed = int.from_bytes(message[i : i + 2], "little", signed=False)/100
        i += 2
    if flag_instantaneous_cadence:
        instant_cadence = int.from_bytes(message[i : i + 2], "little", signed=False) / 2
        i += 2
    if flag_average_cadence:
        average_cadence = int.from_bytes(message[i : i + 2], "little", signed=False) / 2
        i += 2
    if flag_total_distance:
        total_distance = int.from_bytes(message[i : i + 3], "little", signed=False)
        i += 3
    if flag_resistance_level:
        resistance_level = int.from_bytes(message[i : i + 2], "little", signed=True)
        i += 2
    if flag_instantaneous_power:
        instant_power = int.from_bytes(message[i : i + 2], "little", signed=True)
        i += 2
    if flag_average_power:
        average_power = int.from_bytes(message[i : i + 2], "little", signed=True)
        i += 2
    if flag_expended_energy:
        total_energy = int.from_bytes(message[i : i + 2], "little", signed=False)
        energy_per_hour = int.from_bytes(message[i + 2 : i + 4], "little", signed=False)
        energy_per_minute = int.from_bytes(
            message[i + 4 : i + 5], "little", signed=False
        )
        i += 5
    if flag_heart_rate:
        heart_rate = int.from_bytes(message[i : i + 1], "little", signed=False)
        i += 1
    if flag_metabolic_equivalent:
        metabolic_equivalent = int.from_bytes(
            message[i : i + 1], "little", signed=False
        ) / 10
        i += 1
    if flag_elapsed_time:
        elapsed_time = int.from_bytes(message[i : i + 2], "little", signed=False)
        i += 2
    if flag_remaining_time:
        remaining_time = int.from_bytes(message[i : i + 2], "little", signed=False)
        i += 2

    return IndoorBikeData(
        instant_speed,
        average_speed,
        instant_cadence,
        average_cadence,
        total_distance,
        resistance_level,
        instant_power,
        average_power,
        total_energy,
        energy_per_hour,
        energy_per_minute,
        heart_rate,
        metabolic_equivalent,
        elapsed_time,
        remaining_time,
    )
