
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

#import Adafruit_ILI9341 as TFT
#import Adafruit_GPIO.SPI as SPI

from datatypes import DataContainer, WorkoutSegment, WorkoutParameters, WorkoutProgram
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

        self.MARGIN_LARGE: int  = 12
        self.MARGIN_SMALL: int  = 6

        self.COLOUR_BG:         tuple = (31,   31,  31)
        self.COLOUR_BG_LIGHT:   tuple = (62,   62,  62)
        self.COLOUR_FILL:       tuple = (139, 175, 255)
        self.COLOUR_OUTLINE:    tuple = (208, 220, 170)
        self.COLOUR_TEXT_LIGHT: tuple = (156, 223, 250)
        self.COLOUR_TEXT_DARK:  tuple = (30, 50, 60)
        self.COLOUR_BUTTON:     tuple = (200,  60, 100)

        #self.display = TFT.ILI9341(dc     = PIN_DC, 
        #                           rst    = PIN_RST, 
         #                          spi    = SPI.SpiDev(SPI_PORT, SPI_DEVICE, max_speed_hz = BUS_FREQUENCY), 
          #                         width  = self.WIDTH, 
           #                        height = self.HEIGHT)
        #self.display.begin()
        #self.display.clear(self.COLOUR_BG)    # Clear to background

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
            self.drawProgrammeSelector
        if pageID == "WorkoutStart":
           self.drawProgrammeSelector()

        if pageID == "WorkoutRunning":
            self.drawPageWorkout()

        if pageID == "WorkoutSave":
            pass

        self.display.display()


    def drawProgrammeEditor(self, programme: WorkoutProgram, selected_segment: int = None, editedSegment: WorkoutSegment = None) -> tuple:

        draw = ImageDraw.Draw(self.im)
        font = ImageFont.load_default(14)

        touchActiveRegions = tuple()
        
        draw.text(xy = (self.WIDTH / 2, self.MARGIN_SMALL), 
                    text = "Programme Editor", # Box title
                    fill = self.COLOUR_TEXT_LIGHT,
                    font = font,
                    anchor="mt")

        chart, touchActiveRegions = self.drawSegmentsChart(chartWidth      = int(self.WIDTH - 2 * self.MARGIN_LARGE),
                                                           chartHeight     = int(self.HEIGHT * 1 / 3),
                                                           bgColour        = self.COLOUR_BG_LIGHT,
                                                           segmentsColour  = self.COLOUR_FILL,
                                                           selectionColour = self.COLOUR_OUTLINE,
                                                           selectedSegment = selected_segment,
                                                           workoutParams   = programme.getParameters())

        self.im.paste(im = chart, box=(self.MARGIN_LARGE, int(self.HEIGHT * 2 / 3)-self.MARGIN_LARGE))
        
        button_dims = (65, 20)
        
        X_Pos = self.MARGIN_LARGE
        Y_Pos = self.MARGIN_SMALL

        button_label = ("Save", "Discard")
        
        font = ImageFont.load_default(10)
        for i, label in enumerate(button_label):
            button_xy = (X_Pos, Y_Pos)
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
            Y_Pos += i * 30


        
        paramsLabels = ("Name:", "Duration:", "Avg Power:", "Work:")
        paramsUnits = ("", "s", "W", "kJ")
        paramsXoffsets = (0, 40,40,40)
        paramsFontSize = (8, 10,10,10)

        for label, unit, Xoffset, size, value, in zip(paramsLabels, paramsUnits, paramsXoffsets, paramsFontSize, programme.getParameters()):
            
            font = ImageFont.load_default(8)
            draw.text(xy=(X_Pos, Y_Pos), text=label, fill=self.COLOUR_TEXT_LIGHT, font=font)
            Y_Pos += 13

            font = ImageFont.load_default(size)
            draw.text(xy=(X_Pos + Xoffset, Y_Pos), text=str(value)+unit, fill=self.COLOUR_OUTLINE, font=font)
            Y_Pos += 13


        font = ImageFont.load_default(10)
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
        font = ImageFont.load_default(10)

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


        for reg in touchActiveRegions:
            print(reg)
        self.im.save("progEditor.png")
        return touchActiveRegions
    
                

    def drawProgrammeSelector(self, listOfParametres: list) -> tuple:
        #self.display.clear(self.COLOUR_BG)
        #draw = self.display.draw() # Get a PIL Draw object
        draw = ImageDraw.Draw(self.im)
        font = ImageFont.load_default(14)
        draw.text(xy = (self.WIDTH / 2, self.MARGIN_SMALL), 
                    text = "Select programme", # Box title
                    fill = self.COLOUR_TEXT_LIGHT,
                    font = font,
                    anchor="mt")

        X_offset_start = 0
        Y_offset_start = 30
        box_width_height = (140, 85)
        chartWidth = box_width_height[0]-10
        chartHeight = 30

        touchActiveRegions = tuple()

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

                font = ImageFont.load_default(12)
                draw.text(xy = (self.MARGIN_LARGE + X_offset, self.MARGIN_SMALL+Y_offset), 
                            text =  thisWorkoutParams.name, # Box title
                            fill = self.COLOUR_TEXT_LIGHT,
                            font = font,
                            anchor="lt")
                
                
                Y_offset += 18
                font = ImageFont.load_default(8)
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
                
                self.im.paste(chartImage, (box_xy[0]+7, self.MARGIN_SMALL+Y_offset))

                Y_offset = Y_offset_start + box_width_height[1]+18

            X_offset_start += self.WIDTH / 2

        self.im.save("selector.png")
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



    def drawPageWorkout(self, workoutType:str, workoutState: str) -> tuple:
        #self.display.clear(self.COLOUR_BG)
        #draw = self.display.draw() # Get a PIL Draw object
        draw = ImageDraw.Draw(self.im)
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
            
            font = ImageFont.load_default(10)
            draw.text(xy = (box_centre_xy[0], box_centre_xy[1]-12), 
                    text = box_Labels[i][0], # Box title
                    fill = self.COLOUR_TEXT_LIGHT,
                    font = font,
                    anchor="mm")
            
            if i == 1:  # central box, 
                
                start_stop_button_dims = (65, 20)
                start_stop_button_xy = ((self.WIDTH - start_stop_button_dims[0]) / 2, (Y_POS_SECTIONS - start_stop_button_dims[1]) / 2 + 8,
                                        (self.WIDTH + start_stop_button_dims[0]) / 2, (Y_POS_SECTIONS + start_stop_button_dims[1]) / 2 + 8)
                                        
               
                draw.rounded_rectangle(xy = start_stop_button_xy,
                                radius = 3,
                                fill = self.COLOUR_BUTTON,
                                outline = self.COLOUR_BUTTON,
                                width = 2)
                
                touchActiveRegions += ((start_stop_button_xy, "button"),)


                if workoutState == "FREERIDE" or workoutState == "PROGRAM":
                    button_label = "Pause / End"
                else:
                    button_label = "Resume" 

                font = ImageFont.load_default(10)
                draw.text(xy = (self.WIDTH / 2, Y_POS_SECTIONS / 2 + 8), 
                    text = button_label,
                    fill = self.COLOUR_TEXT_LIGHT,
                    font = font,
                    anchor="mm")

                # no extra info to print, skip the rest of the iteration
                continue

            font = ImageFont.load_default(9)

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
            
            font = ImageFont.load_default(11)

            draw.text(xy = (self.MARGIN_LARGE+15, Y_Pos + section_height / 2),
                    text = section["Section"],
                    fill = self.COLOUR_TEXT_LIGHT,
                    font = font,
                    anchor="lm")
            
            X_Pos += 20
            for key in section["labels"]:

                font = ImageFont.load_default(8)
                draw.text(xy = (X_Pos, Y_Pos+35),
                        text = key,
                        fill = self.COLOUR_TEXT_LIGHT,
                        font = font,
                        anchor="mm")
                

                font = ImageFont.load_default(16)
                draw.text(xy = (X_Pos, Y_Pos+15),
                        text = str(section["labels"][key]),
                        fill = self.COLOUR_TEXT_LIGHT,
                        font = font,
                        anchor="mm")

                # calculate spacing accordinly:
                X_Pos += ((X_POS_END - self.MARGIN_LARGE) - self.MARGIN_LARGE) / (len(all_sections) - 1)
            
            Y_Pos += section_height
        self.im.save("workout.png")
        return touchActiveRegions
            

    def drawPageMainMenu(self) -> tuple:
        #self.display.clear()
        #draw = self.display.draw() # Get a PIL Draw object
        draw = ImageDraw.Draw(self.im)
        touchActiveRegions = tuple()

        noBoxes = (3, 2)    # in x and y
        box_width  = (self.WIDTH - self.MARGIN_LARGE * (noBoxes[0]+1))/noBoxes[0]
        box_height = box_width  *0.8 
        box_Labels = (("Change\nUser", "History", "Settings"), ("Edit\nProgrammes","Ride\na\nProgramme", "Freeride"))

        for i in range(noBoxes[1]):
            for j in range(noBoxes[0]):
                box_xy = ((self.MARGIN_LARGE + j * (box_width + self.MARGIN_LARGE), 
                           self.MARGIN_SMALL + i * (box_height + self.MARGIN_SMALL+30)+25), 
                          (self.MARGIN_LARGE + j * (box_width + self.MARGIN_LARGE) + box_width, 
                           self.MARGIN_SMALL + i * (box_height + self.MARGIN_SMALL+30) + box_height+25))

                draw.rounded_rectangle(xy = box_xy,
                                    radius = 4,
                                    fill = self.COLOUR_BG,
                                    outline = self.COLOUR_OUTLINE,
                                    width = 3)
                
                touchActiveRegions += ((box_xy, box_Labels[i][j]),)
                
                font = ImageFont.load_default(12)
                box_centre_xy = (box_xy[0][0] + box_width / 2, box_xy[0][1] + box_height / 2)
                draw.text(xy = box_centre_xy, 
                    text = box_Labels[i][j], # Box title
                    fill = self.COLOUR_TEXT_LIGHT,
                    font = font,
                    align="center",
                    anchor="mm")
                
        self.im.save("mainMenu.png")
        return touchActiveRegions

data = DataContainer()
data.currentSegment = WorkoutSegment("power", 24, 110)
data.currentSegment.elapsedTime = 5
data.workoutDuration = 60
data.workoutTime = 20

lcd = ScreenManager()
lcd.assignDataContainer(data)
#lcd.drawPageWorkout("Program", "PROGRAM")
#lcd.drawPageMainMenu()


workouts = Workouts()

seg = WorkoutSegment(segType="Power", dur=185, set="180")

#lcd.drawProgrammeSelector(workouts.getListOfWorkoutParametres(0,1))
lcd.drawProgrammeEditor(workouts.getWorkout(1),1,editedSegment=seg)