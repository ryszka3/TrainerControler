
from PIL import Image, ImageDraw, ImageFont

import ILI9341 as TFT
import SPI
from   XPT2046 import Touch

from datatypes import DataContainer, WorkoutSegment, WorkoutParameters, WorkoutProgram, UserList
from workouts  import Workouts

def formatTime(dur: int) -> str:
    minutes: int = int(dur / 60)
    hours:int = int(minutes / 60)
    minutes -= hours * 60
    seconds = dur - hours * 60 * 60 -minutes * 60
    
    ret = str()
    if hours < 10:
        ret += "0"
    ret += str(hours) + ":"
    if minutes < 10:
        ret += "0"
    ret += str(minutes) + ":"
    if seconds <10:
        ret += "0"
    ret += str(seconds)

    return ret


class TouchScreen:

    def __init__(self) -> None:
        BUS_FREQUENCY = 4000000
        # Raspberry Pi configuration
        SPI_PORT   = 0
        SPI_DEVICE = 1
        self.WIDTH  = 320
        self.HEIGHT = 240
    
        self.touchscreen = Touch(spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE, max_speed_hz = BUS_FREQUENCY))
        
        self.setCalibration(0.17, -17, 0.17, -17)   # default calibration, to be overwriten with values loaded from config

    
    def setCalibration(self, x_multiplier: float, x_offset: float, y_multiplier: float, y_offset: float):
        
        self.x_multiplier = x_multiplier
        self.x_offset = x_offset

        self.y_multiplier = y_multiplier
        self.y_offset = y_offset
    

    def scaleCoordinates(self, point: tuple):
        """Scales raw X,Y values to match the LCD screen pixel dimensions."""
        a, b = point
        x = self.WIDTH  - int(self.x_multiplier * b + self.x_offset)
        y = self.HEIGHT - int(self.y_multiplier * a + self.y_offset)
        
        return (x, y)
    
    
    def calculateCalibrationConstants(self, requestedPoints: tuple, measuredPoints: tuple) -> tuple:

        measuredP1,  measuredP2  = measuredPoints
        requestedP1, requestedP2 = requestedPoints

        requestedPoint_1x, requestedPoint_1y = requestedP1    # unpack into x, y pair
        requestedPoint_2x, requestedPoint_2y = requestedP2
        
        measuredPoint_1x, measuredPoint_1y = measuredP1     # unpack into x, y pair
        measuredPoint_2x, measuredPoint_2y = measuredP2

        measuredPoint_1x_raw = ((self.WIDTH - measuredPoint_1x) - self.x_offset) / self.x_multiplier
        measuredPoint_2x_raw = ((self.WIDTH - measuredPoint_2x) - self.x_offset) / self.x_multiplier

        measuredPoint_1y_raw = ((self.HEIGHT - measuredPoint_1y) - self.y_offset) / self.y_multiplier
        measuredPoint_2y_raw = ((self.HEIGHT - measuredPoint_2y) - self.y_offset) / self.y_multiplier

        self.x_multiplier = (requestedPoint_2x - requestedPoint_1x) / abs((measuredPoint_2x_raw - measuredPoint_1x_raw))
        self.x_offset = self.WIDTH - self.x_multiplier * measuredPoint_1x_raw - requestedPoint_1x

        self.y_multiplier = (requestedPoint_2y - requestedPoint_1y) / abs((measuredPoint_2y_raw - measuredPoint_1y_raw))
        self.y_offset = self.HEIGHT - self.y_multiplier * measuredPoint_1y_raw - requestedPoint_1y

        return (self.x_multiplier, self.x_offset, self.y_multiplier, self.y_offset)


    def checkTouch(self) -> tuple:
        rawTouch = self.touchscreen.get_touch()

        if rawTouch is None:
            return (False, (0,0))
        
        elif rawTouch[1] > 2000:
            return (False, (0,0))
            
        else:
            scaled = self.scaleCoordinates(rawTouch)
            return (True, scaled)

class ScreenManager:
    
    dataContainer = DataContainer()
    
    def __init__(self) -> None:
        
        self.WIDTH  = 320
        self.HEIGHT = 240
        BUS_FREQUENCY = 4000000
        # Raspberry Pi configuration
        PIN_DC     = 24
        PIN_RST    = 25
        SPI_PORT   = 0
        SPI_DEVICE = 0

        self.font_name = "Roboto-Regular.ttf"

        self.MARGIN_LARGE: int  = 12
        self.MARGIN_SMALL: int  = 6

        self.COLOUR_BG:         tuple = (31,   31,  31)
        self.COLOUR_BG_LIGHT:   tuple = (62,   62,  62)
        self.COLOUR_FILL:       tuple = (139, 175, 255)
        self.COLOUR_OUTLINE:    tuple = (255, 215, 10)
        self.COLOUR_TEXT_LIGHT: tuple = (156, 223, 250)
        self.COLOUR_TEXT_DARK:  tuple = (30,   50,  60)
        self.COLOUR_BUTTON:     tuple = (200,  60, 100)
        self.COLOUR_HEART:      tuple = (207,  17,  17)
        self.COLOUR_TT:         tuple = (38,  188, 196)
        self.COLOUR_CLIMBER:    tuple = (32,  140,  20)

        self.display = TFT.ILI9341(dc     = PIN_DC, 
                                   rst    = PIN_RST, 
                                   spi    = SPI.SpiDev(SPI_PORT, SPI_DEVICE, max_speed_hz = BUS_FREQUENCY), 
                                   width  = self.WIDTH, 
                                   height = self.HEIGHT)
        self.display.begin()
        self.display.clear(self.COLOUR_BG)    # Clear to background

        #self.im = Image.new('RGB', (self.WIDTH, self.HEIGHT), self.COLOUR_BG)

    def assignDataContainer (self, container: DataContainer):
        self.dataContainer:DataContainer = container
    

    def drawPageSettings(self) -> tuple:
        draw = self.display.draw() # Get a PIL Draw object
        self.display.clear(self.COLOUR_BG) 
        #draw = ImageDraw.Draw(self.im)
        touchActiveRegions = tuple()
        font = ImageFont.truetype(font=self.font_name, size=14)
        buttonWidth = 110
        buttonHeight = 70
        Xmargin = (self.WIDTH - 2 * buttonWidth) / 3
        Ymargin = (self.HEIGHT - 2 * buttonHeight) / 3
        Yoffset = 16

        button_mainMenu_xy = (self.MARGIN_SMALL, self.MARGIN_SMALL, self.MARGIN_SMALL + 80, self.MARGIN_SMALL+20)
        button_mainMenu_Screenlabel = "Main Menu"
        button_mainMenu_touchlabel = "MainMenu"

        button1_xy = (self.WIDTH - Xmargin - buttonWidth, Ymargin + Yoffset, 
                      self.WIDTH - Xmargin, Ymargin + buttonHeight + Yoffset)
        button1_screenLabel = "Calibrate\nTouchscreen"
        button1_touchLabel = "Calibrate"

        button2_xy = (Xmargin, Ymargin+Yoffset, 
                      Xmargin + buttonWidth, Ymargin + buttonHeight+Yoffset)
        
        button2_screenLabel = "Connect\nTrainer"
        button2_touchLabel = "Trainer"

        button3_xy = (Xmargin, self.HEIGHT - Ymargin - buttonHeight+Yoffset, 
                      Xmargin + buttonWidth, self.HEIGHT - Ymargin+Yoffset)
        
        button3_screenLabel = "Connect\nHR Monitor"
        button3_touchLabel = "HRMonitor"

        button4_xy = (self.WIDTH - buttonWidth -Xmargin, self.HEIGHT - Ymargin - buttonHeight + Yoffset, 
                      self.WIDTH - Xmargin, self.HEIGHT - Ymargin+Yoffset)
        
        button4_screenLabel = "TBD"
        button4_touchLabel = "Climbr"
        
        allButtons = zip((button1_xy, button2_xy, button3_xy, button4_xy, button_mainMenu_xy),
                         (button1_screenLabel, button2_screenLabel, button3_screenLabel, button4_screenLabel, button_mainMenu_Screenlabel),
                         (button1_touchLabel, button2_touchLabel, button3_touchLabel, button4_touchLabel, button_mainMenu_touchlabel))


        for button_xy, screenLabel, touchLabel in allButtons:
        
            button_centre = ((button_xy[2]+button_xy[0])/2, (button_xy[3]+button_xy[1])/2)
            draw.rounded_rectangle(xy=button_xy, radius=3, fill=self.COLOUR_BG_LIGHT, outline=self.COLOUR_OUTLINE)
            draw.text(xy=button_centre, text=screenLabel, anchor="mm", font=font, fill=self.COLOUR_TEXT_LIGHT, align="center")
            touchActiveRegions += ((button_xy, touchLabel),)

        #self.im.show()
        self.display.display()
        return touchActiveRegions

    def drawProgramEditor(self, program: WorkoutProgram, selected_segment: int = None, editedSegment: WorkoutSegment = None) -> tuple:

        
        draw = self.display.draw() # Get a PIL Draw object
        self.display.clear(self.COLOUR_BG) 
        #draw = ImageDraw.Draw(self.im)
        font = ImageFont.truetype(font=self.font_name, size=14)

        touchActiveRegions = tuple()
        
        draw.text(xy = (self.WIDTH / 2, self.MARGIN_SMALL), 
                    text = "Program Editor", # Box title
                    fill = self.COLOUR_TEXT_LIGHT,
                    font = font,
                    anchor="mt")

        chart, touchActiveRegions = self.drawSegmentsChart(chartWidth      = int(self.WIDTH - 2 * self.MARGIN_LARGE),
                                                           chartHeight     = int(self.HEIGHT * 1 / 3),
                                                           bgColour        = self.COLOUR_BG_LIGHT,
                                                           segmentsColour  = self.COLOUR_FILL,
                                                           selectionColour = self.COLOUR_OUTLINE,
                                                           selectedSegment = selected_segment,
                                                           workoutParams   = program.getParameters())

        self.display.buffer.paste(im = chart, box=(self.MARGIN_LARGE, int(self.HEIGHT * 2 / 3)-self.MARGIN_LARGE))
        
        button_dims = (65, 20)
        
        X_Pos = self.MARGIN_LARGE
        Y_Pos = self.MARGIN_SMALL

        button_label = "Finish"
        
        font = ImageFont.truetype(font=self.font_name, size=10)

        button_xy = (X_Pos, Y_Pos)
        button_xy += (button_xy[0] + button_dims[0], button_xy[1] + button_dims[1])
        button_centre = (button_xy[0] + button_dims[0] / 2, button_xy[1] + button_dims[1] / 2)
        
        draw.rounded_rectangle(xy = button_xy, radius = 3, fill = self.COLOUR_BUTTON, outline = self.COLOUR_BUTTON, width = 2)
        draw.text(xy = button_centre, text = button_label, fill = self.COLOUR_TEXT_LIGHT, font = font, anchor="mm")
        touchActiveRegions += ((button_xy, button_label),)
        Y_Pos += 30
        
        paramsLabels = ("Name:", "Duration:", "Avg Power:", "Work:")
        paramsUnits = ("", "s", "W", "kJ")
        paramsXoffsets = (0, 40,40,40)
        paramsFontSize = (8, 10,10,10)

        for label, unit, Xoffset, size, value, in zip(paramsLabels, paramsUnits, paramsXoffsets, paramsFontSize, program.getParameters()):
            
            font = ImageFont.truetype(font=self.font_name, size=8)
            draw.text(xy=(X_Pos, Y_Pos), text=label, fill=self.COLOUR_TEXT_LIGHT, font=font)
            Y_Pos += 13

            font = ImageFont.truetype(font=self.font_name, size=size)
            draw.text(xy=(X_Pos + Xoffset, Y_Pos), text=str(value)+unit, fill=self.COLOUR_OUTLINE, font=font)
            Y_Pos += 13


        font = ImageFont.truetype(font=self.font_name, size=10)
        button_label = tuple()
        if selected_segment is None:
            button_label += ("Add",)
        else:
            button_label += ("Insert", "Update", "Remove")
        
        X_Pos = self.WIDTH - button_dims[0] - self.MARGIN_LARGE
        Y_Pos = self.MARGIN_SMALL

        for i, label in enumerate(button_label):

            button_xy = (X_Pos, Y_Pos + i * 30)
            button_xy += (button_xy[0] + button_dims[0], button_xy[1] + button_dims[1])
            button_centre = (button_xy[0] + button_dims[0] / 2, button_xy[1] + button_dims[1] / 2)
            
            draw.rounded_rectangle(xy = button_xy,
                                radius = 3,
                                fill = self.COLOUR_BUTTON,
                                outline = self.COLOUR_BUTTON,
                                width = 2)
            
            draw.text(xy = button_centre, 
                                text = label,
                                fill = self.COLOUR_TEXT_LIGHT,
                                font = font,
                                anchor="mm")
            
            touchActiveRegions += ((button_xy, label),)

        ## central edit box
        font = ImageFont.truetype(font=self.font_name, size=10)

        box_wd = (140, 110)
        box_xy = (self.WIDTH / 2 - box_wd[0] / 2, 28)
        box_xy += (box_xy[0] + box_wd[0], box_xy[1] + box_wd[1])

        draw.rounded_rectangle(xy = box_xy,
                                radius = 5,
                                fill = self.COLOUR_BG_LIGHT,
                                outline = self.COLOUR_BG_LIGHT,
                                width = 1)


        X_Pos = box_xy[0] + self.MARGIN_SMALL
        Y_Pos = box_xy[1] + self.MARGIN_SMALL
        draw.text(xy=(X_Pos, Y_Pos+5),
                  text="Segm. type:",
                  anchor="lt",
                  fill=self.COLOUR_TEXT_LIGHT,
                  font=font)

        X_Pos += 60
        button_label = ("Power", "Level")
        for label in button_label:
            
            button_xy = (X_Pos, Y_Pos, X_Pos + 30, Y_Pos + 14)
            button_centre = ((button_xy[2] + button_xy[0])/2, (button_xy[3] + button_xy[1])/2)
            if label == editedSegment.segmentType:
                button_colour = self.COLOUR_OUTLINE
                text_colour = self.COLOUR_TEXT_DARK
            else:
                button_colour = self.COLOUR_BUTTON
                text_colour = self.COLOUR_TEXT_LIGHT

            draw.rectangle(xy=button_xy, fill=button_colour)
            draw.text(xy=(X_Pos+15, Y_Pos+7), anchor="mm", text=label, font=font, fill=text_colour)
            touchActiveRegions +=  ((button_xy, label),)

            X_Pos += 35

        X_Pos -= 130
        Y_Pos += 20
        draw.text(xy=(X_Pos, Y_Pos+5), text="Setting: ", anchor="lt", fill=self.COLOUR_TEXT_LIGHT, font=font)
        
        X_Pos += 60
        draw.text(xy=(X_Pos, Y_Pos+5), text=str(editedSegment.setting) + " W", anchor="lt", fill=self.COLOUR_FILL, font=font)

        Y_Pos += 18
        X_Pos -= 38
        button_label = ("- 50", "- 5", "+ 5", "+ 50")
        
        for i, label in enumerate(button_label):
            
            button_xy = (X_Pos+ i * 28, Y_Pos, X_Pos + 20 + i * 28, Y_Pos + 12)
            button_centre = ((button_xy[2] + button_xy[0])/2, (button_xy[3] + button_xy[1])/2)
            
            draw.rectangle(xy=button_xy,fill=self.COLOUR_BUTTON)
            draw.text(xy=button_centre, text=label, anchor="mm", fill=self.COLOUR_TEXT_LIGHT, font=font)
            touchActiveRegions +=  ((button_xy, label),)

        
        X_Pos -= 22
        Y_Pos += 16
        draw.text(xy=(X_Pos, Y_Pos+5), text="Duration: ", anchor="lt", fill=self.COLOUR_TEXT_LIGHT, font=font)
        
        X_Pos += 60
        draw.text(xy=(X_Pos, Y_Pos+5), text=formatTime(editedSegment.duration),
                   anchor="lt", fill=self.COLOUR_FILL, font=font)

        Y_Pos += 18
        X_Pos -= 42
        button_label = ("-10m", "-1m", "-10s", "+10s", "+1m", "+10m")
        
        for i, label in enumerate(button_label):
            
            button_xy = (X_Pos + i * 32, Y_Pos)
            button_xy += (button_xy[0] + 26, button_xy[1] + 12)
            button_centre = ((button_xy[2] + button_xy[0])/2, (button_xy[3] + button_xy[1])/2)

            draw.rectangle(xy=button_xy,fill=self.COLOUR_BUTTON)
            draw.text(xy=button_centre, text=label, anchor="mm", fill=self.COLOUR_TEXT_LIGHT, font=font)
            touchActiveRegions +=  ((button_xy, label),)

            if i==2:    #### Break the line of buttons
                Y_Pos += 16
                X_Pos -= 3*26


        self.display.display()
        return touchActiveRegions
    
    def drawMessageBox(self, message:str, options: tuple) -> tuple:
        
        #self.im=self.im.convert("L")
        #self.im=self.im.convert("RGB")

        self.display.buffer = self.display.buffer.convert("L")
        self.display.buffer = self.display.buffer.convert("RGB")

        draw = self.display.draw() # Get a PIL Draw object
        #draw = ImageDraw.Draw(self.im)
        font = ImageFont.truetype(font=self.font_name, size=12)
        touchActiveRegions = tuple()
        
        numberOfButtons = len(options)
        buttonLength = int(max([draw.textlength(opt, font=font) for opt in options]) + 4)
        buttonHeight = 16
        marginLength = 8

    
        messageWidth = numberOfButtons * buttonLength + marginLength * (numberOfButtons + 1)
        messageHeight = 50

        box_xy = (self.WIDTH/2-messageWidth/2, self.HEIGHT/2,
                  self.WIDTH/2+messageWidth/2, self.HEIGHT/2+messageHeight)
        
        box_bg_extent = 8
        box_bg_xy = (box_xy[0]-box_bg_extent, box_xy[1]-box_bg_extent, box_xy[2]+box_bg_extent, box_xy[3]+box_bg_extent)
        draw.rectangle(xy=box_bg_xy, fill=self.COLOUR_BG_LIGHT)
        draw.rectangle(xy=box_xy, outline=self.COLOUR_OUTLINE, fill=self.COLOUR_BG_LIGHT, width=2)

        draw.text(xy=(self.WIDTH/2, self.HEIGHT/2+12), text=message, font=font, fill=self.COLOUR_TEXT_LIGHT, anchor="mm")
        
        font = ImageFont.truetype(font=self.font_name, size=10)

        X_pos = box_xy[0] + marginLength 
        Y_pos = box_xy[1] + 25
        for opt in options:

            button_xy = (X_pos, Y_pos, X_pos+buttonLength, Y_pos+buttonHeight)
            draw.rectangle(xy=button_xy, fill=self.COLOUR_BUTTON)
            draw.text(xy=(X_pos+buttonLength/2, Y_pos+buttonHeight/2), text=opt, fill=self.COLOUR_TEXT_LIGHT, anchor="mm")
            X_pos += buttonLength+marginLength
            touchActiveRegions += ((button_xy, opt),)

        self.display.display()
        return touchActiveRegions

    def drawProgramSelector(self, listOfParametres: list, previousEnabled: bool = False, nextEnabled: bool = False, newProgramEnabled: bool = True) -> tuple:
        
        self.display.clear(self.COLOUR_BG)
        draw = self.display.draw() # Get a PIL Draw object
        #draw = ImageDraw.Draw(self.im)
        font = ImageFont.truetype(font=self.font_name, size=14)
        draw.text(xy = (self.WIDTH / 2, self.MARGIN_SMALL), text = "Select program", fill = self.COLOUR_TEXT_LIGHT, font = font, anchor="mt")

        touchActiveRegions = tuple()

        triangleWidth = 15
        triangleHeight = 10

        if previousEnabled == True:

            triangle_xy = (self.MARGIN_SMALL, self.MARGIN_LARGE, 
                        self.MARGIN_SMALL+triangleWidth, self.MARGIN_LARGE - triangleHeight/2, 
                        self.MARGIN_SMALL+triangleWidth, self.MARGIN_LARGE + triangleHeight/2)

            draw.polygon(xy=triangle_xy, outline=self.COLOUR_OUTLINE, width=1, fill=self.COLOUR_BUTTON)
            
            triangle_touchbox_xy = (triangle_xy[0], triangle_xy[3], triangle_xy[4], triangle_xy[5])
            
            touchActiveRegions += ((triangle_touchbox_xy, "PreviousPage"),)
        
        if nextEnabled== True:
            
            triangle_xy = (self.WIDTH - self.MARGIN_SMALL, self.MARGIN_LARGE, 
                        self.WIDTH - self.MARGIN_SMALL - triangleWidth, self.MARGIN_LARGE - triangleHeight/2, 
                        self.WIDTH - self.MARGIN_SMALL - triangleWidth, self.MARGIN_LARGE + triangleHeight/2)
            
            draw.polygon(xy=triangle_xy, outline=self.COLOUR_OUTLINE, width=1, fill=self.COLOUR_BUTTON)

            triangle_touchbox_xy = (triangle_xy[2], triangle_xy[3], triangle_xy[0], triangle_xy[5])
            
            touchActiveRegions += ((triangle_touchbox_xy, "NextPage"),)
        

        if newProgramEnabled == True:

            font = ImageFont.truetype(font=self.font_name, size=10)
            newButtonWidth = 70
            newButtonHeigh = 14
            newButtonStartX = 30

            newButton_xy = (newButtonStartX, self.MARGIN_SMALL, newButtonStartX + newButtonWidth, self.MARGIN_SMALL+newButtonHeigh)
            draw.rectangle(xy=newButton_xy, fill=self.COLOUR_BUTTON)
            draw.text(xy=(newButtonStartX+newButtonWidth/2, self.MARGIN_SMALL+newButtonHeigh/2),
                       text="New Program", font=font, fill=self.COLOUR_TEXT_LIGHT, anchor="mm")
            
            touchActiveRegions += ((newButton_xy, "NewProgram"),)

        X_offset_start = 0
        Y_offset_start = 30
        box_width_height = (140, 85)
        chartWidth = box_width_height[0]-10
        chartHeight = 30

        

        for i in range(2):
            
            Y_offset = Y_offset_start
                  
            for j in range(2):
                progID = i*2+j
                if progID > len(listOfParametres) - 1:
                    break

                thisWorkoutParams: WorkoutParameters = listOfParametres[progID]
                
                X_offset = X_offset_start

                box_xy = (self.MARGIN_LARGE + X_offset - 4, self.MARGIN_SMALL + Y_offset - 4)
                box_xy += (box_xy[0] + box_width_height[0], box_xy[1] + box_width_height[1])

                draw.rounded_rectangle(xy = (box_xy[0], box_xy[1], box_xy[2], box_xy[3]),
                                        radius = 3,
                                        fill = self.COLOUR_BG_LIGHT,
                                        outline = self.COLOUR_BG_LIGHT,
                                        width = 1)

                touchActiveRegions += ((box_xy, progID),)

                font = ImageFont.truetype(font=self.font_name, size=12)
                draw.text(xy = (self.MARGIN_LARGE + X_offset, self.MARGIN_SMALL+Y_offset), 
                            text =  thisWorkoutParams.name, # Box title
                            fill = self.COLOUR_TEXT_LIGHT,
                            font = font,
                            anchor="lt")
                
                
                Y_offset += 18
                font = ImageFont.truetype(font=self.font_name, size=8)
                draw.text(xy = (self.MARGIN_LARGE + X_offset, self.MARGIN_SMALL+Y_offset), 
                            text = "Time", # Box title
                            fill = self.COLOUR_TEXT_LIGHT,
                            font = font,
                            anchor="lm")
                
                X_offset += 22
                draw.text(xy = (self.MARGIN_LARGE + X_offset, self.MARGIN_SMALL+Y_offset), 
                            text = formatTime(thisWorkoutParams.totalDuration), # Box title
                            fill = self.COLOUR_FILL,
                            font = font,
                            anchor="lm")
                
                X_offset += 40
                draw.text(xy = (self.MARGIN_LARGE + X_offset, self.MARGIN_SMALL+Y_offset), 
                            text = "Avg. Power:", # Box title
                            fill = self.COLOUR_TEXT_LIGHT,
                            font = font,
                            anchor="lm")
                
                X_offset += 45
                draw.text(xy = (self.MARGIN_LARGE + X_offset, self.MARGIN_SMALL+Y_offset), 
                            text = str(thisWorkoutParams.avgPower) + " W", # Box title
                            fill = self.COLOUR_FILL,
                            font = font,
                            anchor="lm")
                
                Y_offset += 13
                X_offset = X_offset_start
                draw.text(xy = (self.MARGIN_LARGE + X_offset, self.MARGIN_SMALL+Y_offset), 
                            text = "Work:", # Box title
                            fill = self.COLOUR_TEXT_LIGHT,
                            font = font,
                            anchor="lm")
                
                X_offset += 22
                draw.text(xy = (self.MARGIN_LARGE + X_offset, self.MARGIN_SMALL+Y_offset), 
                            text = str(thisWorkoutParams.totalWork) + " kJ", # Box title
                            fill = self.COLOUR_FILL,
                            font = font,
                            anchor="lm")
                
                X_offset += 40
                draw.text(xy = (self.MARGIN_LARGE + X_offset, self.MARGIN_SMALL+Y_offset), 
                            text = "Max Power:", # Box title
                            fill = self.COLOUR_TEXT_LIGHT,
                            font = font,
                            anchor="lm")
                
                X_offset += 45
                draw.text(xy = (self.MARGIN_LARGE + X_offset, self.MARGIN_SMALL+Y_offset), 
                            text = str(thisWorkoutParams.maxPower) + " W", # Box title
                            fill = self.COLOUR_FILL,
                            font = font,
                            anchor="lm")
                
                #### chart
                Y_offset += 15
                chartImage, chartActiveRegions = self.drawSegmentsChart(chartWidth=chartWidth,
                                                    chartHeight=chartHeight,
                                                    workoutParams=thisWorkoutParams,
                                                    bgColour=self.COLOUR_BG_LIGHT,
                                                    segmentsColour=self.COLOUR_FILL)
                
                self.display.buffer.paste(chartImage, (box_xy[0]+7, self.MARGIN_SMALL+Y_offset))

                Y_offset = Y_offset_start + box_width_height[1]+18

            X_offset_start += self.WIDTH / 2

        self.display.display()
        return touchActiveRegions
    

    
    def drawSegmentsChart(self, chartWidth: int, 
                          chartHeight: int, 
                          workoutParams: WorkoutParameters, 
                          bgColour: tuple, 
                          segmentsColour: tuple, 
                          selectionColour: tuple = None, 
                          selectedSegment: int = None) -> tuple:
        
        image = Image.new('RGB', (chartWidth, chartHeight), bgColour)
        draw = ImageDraw.Draw(image)

        noSegments = len(workoutParams.segmentsChartData)
        segment_width_normalisation_factor  = workoutParams.totalDuration / (chartWidth - noSegments * 2)
        segment_height_normalisation_factor = workoutParams.maxPower / chartHeight 

        if segment_height_normalisation_factor == 0:
            segment_height_normalisation_factor = 1

        barHeightAdjustment: int = 0
        minBarHeight = int(workoutParams.minPower / segment_height_normalisation_factor) +1
        if minBarHeight > chartHeight / 5:
            barHeightAdjustment = minBarHeight - chartHeight / 5
        
        maxBarHeight = int(workoutParams.maxPower / segment_height_normalisation_factor) +1 - barHeightAdjustment
        barHeightScaler = chartHeight / maxBarHeight * 0.9

        chartXPos = 0

        touchActiveRegions = tuple()

        for counter, segment in enumerate(workoutParams.segmentsChartData):

            if selectedSegment == counter and selectionColour is not None:
                colour = selectionColour
            else:
                colour = segmentsColour

            segment_wh = (int(segment[2] / segment_width_normalisation_factor) + 1,
                         int((segment[1] / segment_height_normalisation_factor +1 - barHeightAdjustment) * barHeightScaler))

            
            segment_xy = (chartXPos, chartHeight-segment_wh[1], chartXPos + segment_wh[0], chartHeight)
            
            draw.rectangle(xy=segment_xy, fill=colour)
            touchActiveRegions += ((segment_xy, counter),)

            chartXPos += segment_wh[0] + 2

        return (image, touchActiveRegions)

    def drawPageCalibration(self, point:tuple) -> None:
        
        self.display.clear(self.COLOUR_BG)
        draw = self.display.draw() # Get a PIL Draw object
        #draw = ImageDraw.Draw(self.im)

        LINE_LENGTH = 6
        GAP = 3

        point_x, point_y = point

        draw.line(xy=((point_x - LINE_LENGTH - GAP, point_y), (point_x - GAP, point_y)), fill=self.COLOUR_OUTLINE, width=1)
        draw.line(xy=((point_x + GAP, point_y), (point_x + LINE_LENGTH + GAP, point_y)), fill=self.COLOUR_OUTLINE, width=1)

        draw.line(xy=((point_x, point_y - LINE_LENGTH - GAP), (point_x, point_y - GAP)), fill=self.COLOUR_OUTLINE, width=1)
        draw.line(xy=((point_x, point_y + GAP), (point_x, point_y + LINE_LENGTH + GAP)), fill=self.COLOUR_OUTLINE, width=1)

        font = ImageFont.truetype(font=self.font_name, size=14)
        draw.text(xy=(self.WIDTH/2, self.HEIGHT/2), text="Touch the screen\nat the indicated spot", 
                  align="center", anchor="mm", fill=self.COLOUR_FILL, font=font)

        self.display.display()
        #self.im.show()

    def drawPageWorkout(self, workoutType:str, workoutState: str) -> tuple:
        
        self.display.clear(self.COLOUR_BG)
        draw = self.display.draw() # Get a PIL Draw object
        #draw = ImageDraw.Draw(self.im)
        touchActiveRegions = tuple()

        X_POS_END: int = 180
        LINE_THICKNESS: int = 2
        Y_POS_SECTIONS = self.HEIGHT / 4    # Sections begin at 1/4 height, i.e. 240 / 4 = 60

        noBoxes = 3
        box_width = (self.WIDTH - self.MARGIN_LARGE * (noBoxes+1))/noBoxes
        box_height = 45
        box_Labels = (("Elapsed Time:", self.dataContainer.workoutTime, self.dataContainer.currentSegment.elapsedTime),
                     (workoutType,),
                     ("Remaining Time:", self.dataContainer.workoutDuration - self.dataContainer.workoutTime
                                      , self.dataContainer.currentSegment.duration - self.dataContainer.currentSegment.elapsedTime))
        
        for i in range(noBoxes):
            box_xy = ((self.MARGIN_LARGE + i * (box_width + self.MARGIN_LARGE), self.MARGIN_SMALL), 
                      (self.MARGIN_LARGE + i * (box_width + self.MARGIN_LARGE) + box_width, self.MARGIN_SMALL+box_height))
            
            box_centre_xy = (box_xy[0][0] + box_width / 2, box_xy[0][1] + box_height / 2)
            
            font = ImageFont.truetype(font=self.font_name, size=10)
            
            draw.text(xy = (box_centre_xy[0], box_centre_xy[1]-12), 
                    text = box_Labels[i][0], # Box title
                    fill = self.COLOUR_TEXT_LIGHT,
                    font = font,
                    anchor="mm")
            
            if i == 1:  # central box, 
                
                if workoutState == "FREERIDE" or workoutState == "PROGRAM":
                    button_label = "Pause"
                else:
                    button_label = "Resume" 
                
                button_dims = (38, 20)
                button_x_separation = 14
                
                button_xy = ((self.WIDTH / 2 - button_dims[0] - button_x_separation/2), (Y_POS_SECTIONS - button_dims[1]) / 2 + 8,
                             (self.WIDTH / 2 - button_x_separation/2), (Y_POS_SECTIONS + button_dims[1]) / 2 + 8)
                                        
                button_centre = ((button_xy[2] + button_xy[0])/2, (button_xy[3] + button_xy[1])/2)
                draw.rounded_rectangle(xy = button_xy, radius = 3, fill = self.COLOUR_BUTTON, 
                                       outline = self.COLOUR_BUTTON, width = 2)
                draw.text(xy = button_centre, text = button_label, fill = self.COLOUR_TEXT_LIGHT, font = font, anchor="mm")
                touchActiveRegions += ((button_xy, "Pause"),)


                button_xy = ((self.WIDTH / 2 + button_x_separation/2), (Y_POS_SECTIONS - button_dims[1]) / 2 + 8,
                             (self.WIDTH / 2 + button_x_separation/2 + button_dims[0]), (Y_POS_SECTIONS + button_dims[1]) / 2 + 8)
                
                button_centre = ((button_xy[2] + button_xy[0])/2, (button_xy[3] + button_xy[1])/2)

                draw.rounded_rectangle(xy = button_xy, radius = 3, fill = self.COLOUR_BUTTON,
                                        outline = self.COLOUR_BUTTON, width = 2)
                
                touchActiveRegions += ((button_xy, "End"),)
                draw.text(xy = button_centre, text = "End", fill = self.COLOUR_TEXT_LIGHT, font = font, anchor="mm")

                # no extra info to print, skip the rest of the iteration
                continue

            font = ImageFont.truetype(font=self.font_name, size=9)

            draw.text(xy = (box_centre_xy[0] - box_width / 2 + 7, box_centre_xy[1]+5), 
                    text = "Total:    " + str(box_Labels[i][1]), # total
                    fill = self.COLOUR_TEXT_LIGHT,
                    font = font,
                    anchor="lm")
            
            draw.text(xy = (box_centre_xy[0] - box_width / 2 + 7, box_centre_xy[1]+17), 
                    text = "Segment:  "+ str(box_Labels[i][2]), # Segment
                    fill = self.COLOUR_TEXT_LIGHT,
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
            
            X_Pos: int = self.MARGIN_LARGE + 100

            draw.line(xy  = (self.MARGIN_LARGE, Y_Pos, self.WIDTH - self.MARGIN_LARGE , Y_Pos), 
                    fill  = self.COLOUR_OUTLINE, 
                    width = LINE_THICKNESS)
            
            font = ImageFont.truetype(font=self.font_name, size=11)

            draw.text(xy = (self.MARGIN_LARGE+15, Y_Pos + section_height / 2),
                    text = section["Section"],
                    fill = self.COLOUR_TEXT_LIGHT,
                    font = font,
                    anchor="lm")
            
            X_Pos += 20
            for key in section["labels"]:

                font = ImageFont.truetype(font=self.font_name, size=8)
                draw.text(xy = (X_Pos, Y_Pos+35),
                        text = key,
                        fill = self.COLOUR_TEXT_LIGHT,
                        font = font,
                        anchor="mm")
                

                font = ImageFont.truetype(font=self.font_name, size=16)
                draw.text(xy = (X_Pos, Y_Pos+15),
                        text = str(section["labels"][key]),
                        fill = self.COLOUR_TEXT_LIGHT,
                        font = font,
                        anchor="mm")

                # calculate spacing accordinly:
                X_Pos += ((X_POS_END - self.MARGIN_LARGE) - self.MARGIN_LARGE) / (len(all_sections) - 1)
            
            Y_Pos += section_height

        self.display.display()
        return touchActiveRegions

    def drawPageUserSelect(self, userList: UserList, displayRange: tuple, previousEnabled: bool = False, nextEnabled: bool = False) -> tuple:
        
        self.display.clear()
        draw = self.display.draw() # Get a PIL Draw object

        font = ImageFont.truetype(font=self.font_name, size=16)
        #draw = ImageDraw.Draw(self.im)
        
        triangleWidth = 10
        triangleHeight = 15

        draw.text(xy=(self.WIDTH/2, self.MARGIN_LARGE), text="Select User", font=font, anchor="mm", fill=self.COLOUR_TEXT_LIGHT)
        
        touchActiveRegions = tuple()

        if previousEnabled == True:

            prev_y = 40
            triangle_xy = (self.MARGIN_LARGE+triangleWidth/2, prev_y, 
                           self.MARGIN_LARGE, prev_y+triangleHeight,
                           self.MARGIN_LARGE+triangleWidth, prev_y+triangleHeight)

            draw.polygon(xy=triangle_xy, outline=self.COLOUR_OUTLINE, width=1, fill=self.COLOUR_BUTTON)
            
            triangle_touchbox_xy = (triangle_xy[2], triangle_xy[1], triangle_xy[4], triangle_xy[5])
            
            touchActiveRegions += ((triangle_touchbox_xy, "PreviousPage"),)
        
        if nextEnabled== True:
            
            next_y = 190
            triangle_xy = (self.MARGIN_LARGE, next_y,
                           self.MARGIN_LARGE+triangleWidth, next_y,
                           self.MARGIN_LARGE+triangleWidth/2, next_y+triangleHeight)
            
            draw.polygon(xy=triangle_xy, outline=self.COLOUR_OUTLINE, width=1, fill=self.COLOUR_BUTTON)

            triangle_touchbox_xy = (triangle_xy[0], triangle_xy[1], triangle_xy[2], triangle_xy[5])
            
            touchActiveRegions += ((triangle_touchbox_xy, "NextPage"),)

        BOX_X = 40
        box_y = 35
        
        box_width = self.WIDTH - 2 * box_y
        BOX_HEIGHT = 80
        PICTURE_WH = 40

        for i in range(displayRange[0], displayRange[1]+1):

            if i > len(userList.listOfUsers) - 1:
                break

            box_xy = (BOX_X, box_y, BOX_X+box_width, box_y+BOX_HEIGHT)
            draw.rounded_rectangle(xy=box_xy, fill=self.COLOUR_BG_LIGHT, radius=5)
            touchActiveRegions += ((box_xy, i),)
            
            try:
                image = Image.open(userList.listOfUsers[i].picture)
            except:
                try:
                    image = Image.open("nopicture.png")
                except:
                    image = Image.new("RGB",(65,60), self.COLOUR_BG)
            
            imageRatio = image.width/image.height
            targetHeight = 60
            image = image.resize((int(imageRatio*targetHeight), int(targetHeight)))

            self.display.buffer.paste(image, (BOX_X+10, box_y+10))

            pos_x = BOX_X+80
            pos_y = box_y + 40
            font=ImageFont.truetype(font=self.font_name, size=14)

            draw.text(xy=(pos_x, box_y+16), text=userList.listOfUsers[i].Name, font=font, anchor="lm", fill=self.COLOUR_FILL)

            font=ImageFont.truetype(font=self.font_name, size=9)

            labels_col1 = ("Times riden: ", "Total Distance:", "Total Energy:")
            values_col1 = (userList.listOfUsers[i].noWorkouts, round(userList.listOfUsers[i].totalDistance,1), round(userList.listOfUsers[i].totalEnergy,0))

            for label, value in zip(labels_col1, values_col1):
                draw.text(xy=(pos_x, pos_y), text=label, fill=self.COLOUR_FILL, anchor="lm", font=font)
                draw.text(xy=(pos_x+65, pos_y), text=str(value), fill=self.COLOUR_OUTLINE, font=font, anchor="lm")
                pos_y += 12
            
            pos_y = box_y + 40
            pos_x += 100

            labels_col2 = ("FTP:", "Max HR:")
            values_col2 = (userList.listOfUsers[i].FTP, userList.listOfUsers[i].Max_HR)

            for label, value in zip(labels_col2, values_col2):
                draw.text(xy=(pos_x, pos_y), text=label, fill=self.COLOUR_FILL, anchor="lm", font=font)
                draw.text(xy=(pos_x+40, pos_y), text=str(value), fill=self.COLOUR_OUTLINE, font=font, anchor="lm")
                pos_y += 12


            box_y += BOX_HEIGHT+20
        
        self.display.display()

        return touchActiveRegions


    #def drawPageMainMenu(self, colour_heart: tuple, colour_trainer: tuple, colour_climber: tuple) -> tuple:
    def drawPageMainMenu(self, colour_heart: tuple, colour_trainer: tuple) -> tuple:
        
        self.display.clear()
        draw = self.display.draw() # Get a PIL Draw object
        #draw = ImageDraw.Draw(self.im)
        touchActiveRegions = tuple()

        noBoxes = (3, 2)    # in x and y
        box_width  = int((self.WIDTH - self.MARGIN_LARGE * (noBoxes[0]+1))/noBoxes[0])
        box_height = int(box_width  * 0.8)
        box_labels = ("Change\nUser", "History", "Settings", "Edit\nProgram","Ride\nProgram", "Freeride")

        stateMachineStates = ("UserChange", "History", "Settings", "ProgEdit", "RideProgram", "Freeride", "ProgSelect")
        
        DEVICES_HEIGHT = 23
        heartImage: Image   = self.drawHeart(DEVICES_HEIGHT, colour_heart, self.COLOUR_OUTLINE, self.COLOUR_BG)
        trainerImage: Image = self.drawTrainer(DEVICES_HEIGHT, colour_trainer, self.COLOUR_OUTLINE, self.COLOUR_BG)
        #climberImage: Image = self.drawClimber(DEVICES_HEIGHT, colour_climber, self.COLOUR_OUTLINE, self.COLOUR_BG)
        
        Y_Pos = self.MARGIN_LARGE
        X_Pos = int(self.MARGIN_LARGE*1.5 + box_width -heartImage.width/2)

        #self.display.buffer
        self.display.buffer.paste(heartImage, (X_Pos, Y_Pos))
       
        X_Pos = int(self.WIDTH/2 - trainerImage.width/2) 
        self.display.buffer.paste(trainerImage, (X_Pos, Y_Pos))

        #X_Pos = int(self.MARGIN_LARGE*2.5 + 2*box_width -climberImage.width/2)
        #self.im.paste(climberImage, (X_Pos, Y_Pos))

        Y_Pos = DEVICES_HEIGHT + 3 * self.MARGIN_LARGE
        X_Pos = self.MARGIN_LARGE
        for i, zipped in enumerate(zip(box_labels, stateMachineStates)):
            
            label, state = zipped

            box_xy = (X_Pos, Y_Pos, X_Pos + box_width, Y_Pos + box_height)

            draw.rounded_rectangle(xy = box_xy, radius = 4, fill = self.COLOUR_BG_LIGHT, outline = self.COLOUR_OUTLINE, width = 3)
            
            touchActiveRegions += ((box_xy, state),)
            
            font = ImageFont.truetype(font=self.font_name, size=12)
            box_centre_xy = (box_xy[0] + box_width / 2, box_xy[1] + box_height / 2)
            draw.text(xy = box_centre_xy, text = label, fill = self.COLOUR_TEXT_DARK, font = font, align="center", anchor="mm")
            
            X_Pos += box_width + 12

            if i + 1 == noBoxes[0]:
                X_Pos = self.MARGIN_LARGE
                Y_Pos += box_height + 25
                

        draw.rectangle(xy=(0,0,100,100), fill=(255,0,0))
        draw.rectangle(xy=(100,0,200,100), fill=(0,255,0))
        draw.rectangle(xy=(200,0,300,100), fill=(0,0,255))
        self.display.display()
        return touchActiveRegions
cp

    def drawConnectionErrorMessage(self):
        WIDTH = 150
        HEIGHT = 68
        
        image = Image.new('RGB', (WIDTH, HEIGHT), self.COLOUR_BG_LIGHT)
        draw = ImageDraw.Draw(image)

        draw.rectangle(xy=(0,0, WIDTH-1, HEIGHT-1), outline=self.COLOUR_OUTLINE, fill=self.COLOUR_BG_LIGHT, width=2)

        font = ImageFont.truetype(font=self.font_name, size=12)
        draw.text(xy=(WIDTH/2, 10), text="Trainer Not Connected!", anchor="mt", font=font)
        font = ImageFont.truetype(font=self.font_name, size=9)
        draw.text(xy=(WIDTH/2, 47), text="Power up  or  start  pedalling\nto  wake up  the  trainer", anchor="mm", font=font, align="center")

        self.display.buffer.paste(image,(int(self.WIDTH/2), int(self.HEIGHT/5*4)))
        self.display.display()

    def drawTrainer(self, height: int, colour_fill: tuple, colour_outline: tuple, colour_bg: tuple) -> Image:
        
        WH_RATIO = 1
        width = int(height * WH_RATIO / 2) * 2 + 1
        
        image = Image.new('RGB', (width, height), colour_bg)
        draw = ImageDraw.Draw(image)

        stroke_wide = max(3, int(1/10 * height))
        stroke_narrow = max(1, int(3/50 * height))
        
        draw.line((width/3, height/2+2, width/5, height/4), fill=colour_outline, width=stroke_wide)
        draw.line((width/3, height/2+2, width/5, height/4), fill=colour_fill, width=stroke_narrow)

        draw.line((width/8, height/4, width*3/8, height/4), fill=colour_outline, width=stroke_wide)
        draw.line((width/8+1, height/4, width*3/8-1, height/4), fill=colour_fill, width=stroke_narrow)

        draw.line((width*6/8, height/10, width*6/8, height*4/6), fill=colour_outline, width=stroke_wide)
        draw.line((width*6/8, height/10+1, width*6/8, height*4/6+1), fill=colour_fill, width=stroke_narrow)

        draw.line((width*5/8, height/6, width*7/8, height/11), fill=colour_outline, width=stroke_narrow)
        
        draw.ellipse(xy=(width/10, height/2, width/10*9, height/10*9), fill=colour_fill, outline=colour_outline, width=1)

        draw.regular_polygon((width*4/11, height*7/10, stroke_narrow), n_sides=80, fill=colour_outline)
        draw.line(xy=(width*4/11, height*7/10, width*6/10, height*7/10), fill=colour_outline, width=stroke_narrow-1)
        draw.line(xy=(width*5/10, height*7/10, width*6/10, height*7/10), fill=colour_outline, width=stroke_narrow)

        return image

    def drawHeart(self, height: int, colour_fill: tuple, colour_outline: tuple, colour_bg: tuple) -> Image:

        if height % 2 == 1:
            height = int(height/2)*2 + 1 ## make sure height is odd
        WH_RATIO = 13/11
        width = int(height * WH_RATIO / 2) * 2 + 1

        image = Image.new('RGB', (width, height), colour_bg)
        draw = ImageDraw.Draw(image)

        X_pos_offset = -1
        Y_pos_offset = -1
        Y_pos = height + Y_pos_offset
        X_pos = int(width / 2) + 1 + X_pos_offset

        for lineLength in range(0, width-1, 2):
            start = (X_pos, Y_pos)
            end = (X_pos + lineLength, Y_pos)
            
            draw.line((start, end), colour_fill)
            draw.point(start, colour_outline) ## black outline
            draw.point(end, colour_outline)
            Y_pos -= 1
            X_pos -= 1
        
        X_pos += 1
        FLATRATIO = 4/13
        flatHeight = int(FLATRATIO * height)

        for i in range(flatHeight):
            start = (X_pos, Y_pos)
            end = (X_pos + lineLength, Y_pos)

            draw.line((start, end), colour_fill)
            draw.point(start, colour_outline) ## black outline
            draw.point(end, colour_outline)
            Y_pos -= 1

        TOP_RATIO = 2/13
        topSteps = int(TOP_RATIO * height) + 1 
        
        for lineLength in range(lineLength, lineLength - topSteps, -2):
            start = (X_pos+1, Y_pos)
            end = (X_pos + lineLength-1, Y_pos)
            
            draw.line((start, end), colour_fill)
            draw.point(start, colour_outline) ## black outline
            draw.point(end, colour_outline)
            Y_pos -= 1
            X_pos += 1

        Y_pos += 1
        draw.line((start, end), colour_outline)
        
        Y_pos += topSteps-1
        X_pos = int(width / 2) + 1 + X_pos_offset

        for lineLength in range(0, topSteps*2, 2):
            start = (X_pos, Y_pos)
            end = (X_pos + lineLength, Y_pos)

            draw.line((start, end), colour_bg)
            draw.point(start, colour_outline) ## black outline
            draw.point(end, colour_outline)
            Y_pos -= 1
            X_pos -= 1

        return image





#### Run this bit of code when debugging:

if __name__ == "__main__":
    
    data = DataContainer()
    data.currentSegment = WorkoutSegment("power", 24, 110)
    data.currentSegment.elapsedTime = 5
    data.workoutDuration = 60
    data.workoutTime = 20

    lcd = ScreenManager()
    lcd.assignDataContainer(data)
    #lcd.drawPageWorkout("Program", "PROGRAM")
    #lcd.drawPageMainMenu(lcd.COLOUR_BG_LIGHT, lcd.COLOUR_BG_LIGHT)
    #lcd.drawHeart(21, colour_outline=(250,240,240), colour_fill=(207,17,17), colour_bg=(0,0,0))
    #lcd.drawTrainer(21, colour_outline=lcd.COLOUR_OUTLINE, colour_fill=lcd.COLOUR_TT, colour_bg=lcd.COLOUR_BG)
    #lcd.drawConnectionErrorMessage()

    workouts = Workouts()

    seg = WorkoutSegment(segType="Power", dur=185, set="180")

    #lcd.drawProgramSelector(workouts.getListOfWorkoutParametres((0,2)), True)
    #lcd.drawProgramEditor(workouts.getWorkout(1),1,editedSegment=seg)
    #lcd.drawPageCalibration((20,20))
    #lcd.drawPageSettings()
    from datatypes import UserList
    my=UserList()
    lcd.drawPageUserSelect(userList=my, displayRange=(0,1), previousEnabled=True, nextEnabled=True)