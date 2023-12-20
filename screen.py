
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

#import Adafruit_ILI9341 as TFT
#import Adafruit_GPIO.SPI as SPI

from datatypes import DataContainer, WorkoutSegment

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

        self.X_POS_START: int  = 12
        self.Y_POS_START: int  = 6

        self.COLOUR_BG: tuple      = (31,   31,  31)
        self.COLOUR_FILL: tuple    = (139, 175, 255)
        self.COLOUR_OUTLINE: tuple = (208, 220, 170)
        self.COLOUR_TEXT: tuple    = (156, 223, 250)
        self.COLOUR_BUTTON: tuple  = (200,  60, 100)

        #self.display = TFT.ILI9341(dc     = PIN_DC, 
        #                           rst    = PIN_RST, 
         #                          spi    = SPI.SpiDev(SPI_PORT, SPI_DEVICE, max_speed_hz = BUS_FREQUENCY), 
          #                         width  = self.WIDTH, 
           #                        height = self.HEIGHT)
        #self.display.begin()
        #self.display.clear(self.COLOUR_BG)    # Clear to black

        self.chartsData = [list([0]), list([0]), list([0]), list([0])]
        self.im = Image.new('RGB', (self.WIDTH, self.HEIGHT), self.COLOUR_BG)

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
    
    def drawPageWorkout(self, workoutType:str, workoutState: str):
        #self.display.clear(self.COLOUR_BG)
        #draw = self.display.draw() # Get a PIL Draw object
        draw = ImageDraw.Draw(self.im)
        

        X_POS_CHARTS: int = 180
        LINE_THICKNESS: int = 2
        Y_POS_SECTIONS = self.HEIGHT / 4    # Sections begin at 1/4 height, i.e. 240 / 4 = 60
        
        noBoxes = 3
        box_width = (self.WIDTH - self.X_POS_START * (noBoxes+1))/noBoxes
        box_height = 45
        box_Labels = (("Elapsed Time:", self.dataContainer.workoutTime, self.dataContainer.currentSegment.elapsedTime),
                     (workoutType,),
                     ("Remaining Time:", self.dataContainer.workoutDuration - self.dataContainer.workoutTime
                                      , self.dataContainer.currentSegment.duration - self.dataContainer.currentSegment.elapsedTime))
        
        for i in range(noBoxes):
            box_xy = ((self.X_POS_START + i * (box_width + self.X_POS_START), self.Y_POS_START), 
                      (self.X_POS_START + i * (box_width + self.X_POS_START) + box_width, self.Y_POS_START+box_height))
            
            box_centre_xy = (box_xy[0][0] + box_width / 2, box_xy[0][1] + box_height / 2)

            #draw.rounded_rectangle(xy = box_xy,
             #                   radius = 4,
              #                  fill = self.COLOUR_BG,
               #                 outline = self.COLOUR_BG,
                #                width = 3)
            
            font = ImageFont.load_default(10)
            draw.text(xy = (box_centre_xy[0], box_centre_xy[1]-12), 
                    text = box_Labels[i][0], # Box title
                    fill = self.COLOUR_TEXT,
                    font = font,
                    anchor="mm")
            
            if i == 1:  # central box, 
                
                start_stop_button_dims = (65, 20)
                start_stop_button_xy = (((self.WIDTH - start_stop_button_dims[0]) / 2, (Y_POS_SECTIONS - start_stop_button_dims[1]) / 2 + 8),
                                        ((self.WIDTH + start_stop_button_dims[0]) / 2, (Y_POS_SECTIONS + start_stop_button_dims[1]) / 2 + 8)
                                        )
               
                draw.rounded_rectangle(xy = start_stop_button_xy,
                                radius = 3,
                                fill = self.COLOUR_BUTTON,
                                outline = self.COLOUR_BUTTON,
                                width = 2)

                if workoutState == "FREERIDE" or workoutState == "PROGRAM":
                    button_label = "Pause / End"
                else:
                    button_label = "Resume" 

                font = ImageFont.load_default(10)
                draw.text(xy = (self.WIDTH / 2, Y_POS_SECTIONS / 2 + 8), 
                    text = button_label,
                    fill = self.COLOUR_TEXT,
                    font = font,
                    anchor="mm")

                # no extra info to print, skip the rest of the iteration
                continue

            font = ImageFont.load_default(9)

            draw.text(xy = (box_centre_xy[0] - box_width / 2 + 7, box_centre_xy[1]+5), 
                    text = "Total:    " + str(box_Labels[i][1]), # total
                    fill = self.COLOUR_TEXT,
                    font = font,
                    anchor="lm")
            
            draw.text(xy = (box_centre_xy[0] - box_width / 2 + 7, box_centre_xy[1]+17), 
                    text = "Segment:  "+ str(box_Labels[i][2]), # Segment
                    fill = self.COLOUR_TEXT,
                    font = font,
                    anchor="lm")

        
        Y_Pos: int = Y_POS_SECTIONS

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
        section_height = self.HEIGHT * 3 / 4 / len(all_sections)
        
        for section in all_sections:
            
            X_Pos: int = self.X_POS_START + 100

            draw.line(xy  = (self.X_POS_START, Y_Pos, self.WIDTH - self.X_POS_START , Y_Pos), 
                    fill  = self.COLOUR_OUTLINE, 
                    width = LINE_THICKNESS)
            
            font = ImageFont.load_default(11)

            draw.text(xy = (self.X_POS_START+15, Y_Pos + section_height / 2),
                    text = section["Section"],
                    fill = self.COLOUR_TEXT,
                    font = font,
                    anchor="lm")
            
            X_Pos += 20
            for key in section["labels"]:

                font = ImageFont.load_default(8)
                draw.text(xy = (X_Pos, Y_Pos+35),
                        text = key,
                        fill = self.COLOUR_TEXT,
                        font = font,
                        anchor="mm")
                

                font = ImageFont.load_default(16)
                draw.text(xy = (X_Pos, Y_Pos+15),
                        text = str(section["labels"][key]),
                        fill = self.COLOUR_TEXT,
                        font = font,
                        anchor="mm")
                
                #chart area will be drawn here

                # calculate spacing accordinly:
                X_Pos += ((X_POS_CHARTS - self.X_POS_START) - self.X_POS_START) / (len(all_sections) - 1)
            
            Y_Pos += section_height
        self.im.save("workout.png")
            

    def drawPageMainMenu(self):
        #self.display.clear()
        #draw = self.display.draw() # Get a PIL Draw object
        draw = ImageDraw.Draw(self.im)

        noBoxes = (3, 2)    # in x and y
        box_width  = (self.WIDTH - self.X_POS_START * (noBoxes[0]+1))/noBoxes[0]
        box_height = box_width  *0.8 
        box_Labels = (("Change\nUser", "History", "Settings"), ("Edit\nProgrammes","Ride\na\nProgramme", "Freeride"))

        for i in range(noBoxes[1]):
            for j in range(noBoxes[0]):
                box_xy = ((self.X_POS_START + j * (box_width + self.X_POS_START), 
                           self.Y_POS_START + i * (box_height + self.Y_POS_START+30)+25), 
                          (self.X_POS_START + j * (box_width + self.X_POS_START) + box_width, 
                           self.Y_POS_START + i * (box_height + self.Y_POS_START+30) + box_height+25))

                draw.rounded_rectangle(xy = box_xy,
                                    radius = 4,
                                    fill = self.COLOUR_BG,
                                    outline = self.COLOUR_OUTLINE,
                                    width = 3)
                
                font = ImageFont.load_default(12)
                box_centre_xy = (box_xy[0][0] + box_width / 2, box_xy[0][1] + box_height / 2)
                draw.text(xy = box_centre_xy, 
                    text = box_Labels[i][j], # Box title
                    fill = self.COLOUR_TEXT,
                    font = font,
                    align="center",
                    anchor="mm")
                
        self.im.save("mainMenu.png")

data = DataContainer()
data.currentSegment = WorkoutSegment("power", 24, 110)
data.currentSegment.elapsedTime = 5
data.workoutDuration = 60
data.workoutTime = 20

lcd = ScreenManager()
lcd.assignDataContainer(data)
#lcd.drawPageWorkout("Program", "PROGRAM")
lcd.drawPageMainMenu()

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

