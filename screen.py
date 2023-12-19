
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

import Adafruit_ILI9341 as TFT
import Adafruit_GPIO.SPI as SPI

from datatypes import DataContainer

class ScreenManager:
    
    dataContainer = DataContainer()
    
    def __init__(self) -> None:
       
        self.WIDTH = 320
        self.HEIGHT = 240
        BUS_FREQUENCY = 4000000
        # Raspberry Pi configuration
        PIN_DC = 24
        PIN_RST = 25
        SPI_PORT = 0
        SPI_DEVICE = 0

        self.COLOUR_BG: tuple = (139, 175, 204)
        self.COLOUR_INTERFACE: tuple = (200, 200, 0)
        self.COLOUR_TEXT: tuple = (231, 223, 65)

        self.display = TFT.ILI9341(dc     = PIN_DC, 
                                   rst    = PIN_RST, 
                                   spi    = SPI.SpiDev(SPI_PORT, SPI_DEVICE, max_speed_hz = BUS_FREQUENCY), 
                                   width  = self.WIDTH, 
                                   height = self.HEIGHT)
        self.display.begin()
        self.display.clear(self.COLOUR_BG)    # Clear to black
        

    def assignDataContainer (self, container: DataContainer):
        self.dataContainer:DataContainer = container
    
    def drawPage(self, pageID: str):
       
        if pageID == "MainMenu":
            self.drawPageMainMenu()

        if pageID == "History":
            pass
        if pageID == "UserSelect":
            pass
        if pageID == "Programmes":
            pass
        if pageID == "WorkoutStart":
            self.drawPageWorkout()

        if pageID == "WorkoutRunning":
            pass
        if pageID == "WorkoutSave":
            pass

        self.display.display()
    
    def drawPageWorkout(self):
        self.display.clear(self.COLOUR_BG)
        draw = lcd.display.draw() # Get a PIL Draw object
        X_POS_START: int  = 12
        Y_POS_START: int  = 30
        X_POS_GRAPHS: int = 180
        LINE_THICKNESS: int = 3
        
        
        
        Y_Pos: int = self.HEIGHT / 4    # Sections begin at 1/4 height, i.e. 240 / 4 = 60

        section1: dict = {"Section": "Speed", "labels": {
                    "km/h": self.dataContainer.momentary.speed, 
                    "Average":self.dataContainer.average.speed, 
                    "Max":self.dataContainer.max.speed}}
        
        section2: dict = {"Section": "Power", "labels": {
                    "W": self.dataContainer.momentary.power, 
                    "Average":self.dataContainer.average.power, 
                    "Max":self.dataContainer.max.power}}
        
        section3: dict = {"Section": "Cadence", "labels": {
                    "RPM": self.dataContainer.momentary.cadence, 
                    "Average":self.dataContainer.average.cadence, 
                    "Max":self.dataContainer.max.cadence}}
        
        section4: dict = {"Section": "Heart Rate", "labels": {
                    "BPM": self.dataContainer.momentary.power, 
                    "Average":self.dataContainer.average.power, 
                    "Max":self.dataContainer.max.power,
                    "Zone": self.dataContainer.momentary.hrZone}}

        all_sections: tuple = (section1, section2, section3, section4)
        
        for section in all_sections:
            
            X_Pos: int = X_POS_START

            draw.line(xy  = (X_Pos, Y_Pos, self.WIDTH - X_Pos, Y_Pos), 
                    fill  = self.COLOUR_INTERFACE, 
                    width = LINE_THICKNESS)
            
            font = ImageFont.load_default(14)
            textXOffset  = draw.textlength(text=section["Section"], font=font)

            draw.text(xy = (X_Pos-textXOffset, self.WIDTH / 2), # to do: need to offset the position by 1/2 text length
                    text = section["Section"],
                    fill = self.COLOUR_BG,
                    stroke_fill = self.COLOUR_TEXT,
                    font = font)
            
            X_Pos += 20
            for key in section["labels"]:

                font = ImageFont.load_default(10)
                textXOffset  = draw.textlength(text=key, font=font)

                draw.text(xy = (X_Pos-textXOffset, Y_Pos+32),
                        text = key,
                        fill = self.COLOUR_BG,
                        stroke_fill = self.COLOUR_TEXT,
                        font = font)
                

                font = ImageFont.load_default(16)
                textXOffset  = draw.textlength(text=section["labels"][key], font=font)

                draw.text(xy = (X_Pos-textXOffset, Y_Pos+12),
                        text = section["labels"][key],
                        fill = self.COLOUR_BG,
                        stroke_fill = self.COLOUR_TEXT,
                        font = font)
                

                # Last label is at about midpoint, so calculate spacing accordinly:
                X_Pos += ((X_POS_GRAPHS - X_POS_START) - X_POS_START) / (len(section[1]) - 1)
            
            Y_Pos += self.HEIGHT * 3 / 4 / len(all_sections)
            

    def drawPageMainMenu(self):
        self.display.clear()

lcd = ScreenManager()


# Define a function to create rotated text.  Unfortunately PIL doesn't have good
# native support for rotated fonts, but this function can be used to make a
# text image and rotate it so it's easy to paste in the buffer.
def draw_rotated_text(image, text, position, angle, font, fill=(255,255,255)):
    # Get rendered font width and height.
    draw = ImageDraw.Draw(image)
    width, height = draw.textsize(text, font=font)
    # Create a new image with transparent background to store the text.
    textimage = Image.new('RGBA', (width, height), (0,0,0,0))
    # Render the text.
    textdraw = ImageDraw.Draw(textimage)
    textdraw.text((0,0), text, font=font, fill=fill)
    # Rotate the text image.
    rotated = textimage.rotate(angle, expand=1)
    # Paste the text into the image, using it as a mask for transparency.
    image.paste(rotated, position, rotated)

