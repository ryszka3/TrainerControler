"""XPT2046 Touch module."""
from time import sleep
import SPI


class Touch(object):
    """Serial interface for XPT2046 Touch Screen Controller."""

    # Command constants from ILI9341 datasheet
    GET_X = 0b11010000  # X position
    GET_Y = 0b10010000  # Y position
    GET_Z1 = 0b10110000  # Z1 position
    GET_Z2 = 0b11000000  # Z2 position
    GET_TEMP0 = 0b10000000  # Temperature 0
    GET_TEMP1 = 0b11110000  # Temperature 1
    GET_BATTERY = 0b10100000  # Battery monitor
    GET_AUX = 0b11100000  # Auxiliary input to ADC

    def __init__(self, spi: SPI.SpiDev):
        """Initialize touch screen controller.

        Args:
            spi (Class Spi):  SPI interface for OLED

        """
        self.spi = spi
        self.rx_buf = bytearray(3)  # Receive buffer
        self.tx_buf = bytearray(3)  # Transmit buffer


    def get_touch(self):
        """Take multiple samples to get accurate touch reading."""
        timeout = 2  # set timeout to 2 seconds
        confidence = 5
        buff = [[0, 0] for x in range(confidence)]
        buf_length = confidence  # Require a confidence of 5 good samples
        buffptr = 0  # Track current buffer position
        nsamples = 0  # Count samples
        while timeout > 0:
            if nsamples == buf_length:
                meanx = sum([c[0] for c in buff]) // buf_length
                meany = sum([c[1] for c in buff]) // buf_length
                dev = sum([(c[0] - meanx)**2 +
                          (c[1] - meany)**2 for c in buff]) / buf_length
                if dev <= 50:  # Deviation should be under margin of 50
                    return (meanx, meany)
            # get a new value
            sample = self.raw_touch()  # get a touch
            if sample is None:
                nsamples = 0    # Invalidate buff
            else:
                buff[buffptr] = sample  # put in buff
                buffptr = (buffptr + 1) % buf_length  # Incr, until rollover
                nsamples = min(nsamples + 1, buf_length)  # Incr. until max

            sleep(.05)
            timeout -= .05
        return None


    def raw_touch(self):

        x = self.send_command(self.GET_X)
        y = self.send_command(self.GET_Y)

        return (x, y)


    def send_command(self, command):

        self.tx_buf[0] = command
        self.rx_buf = self.spi.transfer(self.tx_buf)

        return (self.rx_buf[1] << 4) | (self.rx_buf[2] >> 4)
