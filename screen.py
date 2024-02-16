import logging
from PIL import Image, ImageDraw, ImageFont

import ILI9341 as TFT
import SPI
from   XPT2046 import Touch

from datatypes import DataContainer, WorkoutSegment, WorkoutParameters, WorkoutProgram, UserList, User
from mqtt import MQTT_Exporter

def formatTime(duration: int) -> str:
    duration = round(duration)

    minutes: int = int(duration / 60)
    hours:int = int(minutes / 60)
    minutes -= hours * 60
    seconds = duration - hours * 60 * 60 -minutes * 60

    ret = str()
    if hours > 0:
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
        
        self.setCalibration(0.176264, -14.6438, 0.133167, -12.7923)   # default calibration, to be overwriten with values loaded from config

    
    def setCalibration(self, x_multiplier: float, x_offset: float, y_multiplier: float, y_offset: float) -> None:
        
        self.x_multiplier = x_multiplier
        self.x_offset = x_offset

        self.y_multiplier = y_multiplier
        self.y_offset = y_offset
    

    def scaleCoordinates(self, point: tuple) -> tuple:
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

        self.COLOUR_BG:         tuple = (15,   15,  15)
        self.COLOUR_BG_LIGHT:   tuple = (42,   42,  42) ## was 62
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

    def assignDataContainer (self, container: DataContainer) -> None:
        self.dataContainer:DataContainer = container
    

    def drawPageSettings(self) -> tuple:
        draw = self.display.draw() # Get a PIL Draw object
        self.display.clear(self.COLOUR_BG) 
        
        touchActiveRegions = tuple()

        font = ImageFont.truetype(font=self.font_name, size=10)
        button_mainMenu_xy = (self.MARGIN_SMALL, self.MARGIN_SMALL,
                              self.MARGIN_SMALL + int(font.getlength("Main Menu"))+4, self.MARGIN_SMALL+16)
        button_centre = ((button_mainMenu_xy[2]+button_mainMenu_xy[0])/2, (button_mainMenu_xy[3]+button_mainMenu_xy[1])/2)
        draw.rounded_rectangle(xy=button_mainMenu_xy, radius=3, fill=self.COLOUR_BG_LIGHT, outline=self.COLOUR_OUTLINE)
        draw.text(xy=button_centre, text="Main Menu", anchor="mm", font=font, fill=self.COLOUR_TEXT_LIGHT, align="center")
        touchActiveRegions += ((button_mainMenu_xy, "MainMenu"),)

        font = ImageFont.truetype(font=self.font_name, size=12)

        button_height = 50
        button_width  = int((self.WIDTH - 3 * self.MARGIN_LARGE)/2)
        b_gap    = 10
        x_0      = self.MARGIN_LARGE
        y_0      = 60
        buttons_xy = list()
        for i in range(6):
            x_start = x_0 + int(i/3) * (button_width + x_0)
            y_start = y_0 + (button_height + b_gap) * (i % 3)
            buttons_xy.append((x_start, y_start, x_start + button_width, y_start+button_height))

        buttons_screeen_names = ("Calibrate Touchscreen", "TBD", "General", "Connect Trainer", "Connect HR Monitor", "TBD")
        buttons_touch_labels  = ("Calibrate", "UserEdit", "General", "TurboTrainer", "HeartRateSensor", "Climbr")

        for button_xy, screenLabel, touchLabel in zip(buttons_xy, buttons_screeen_names, buttons_touch_labels):
        
            button_centre = ((button_xy[2]+button_xy[0])/2, (button_xy[3]+button_xy[1])/2)
            draw.rounded_rectangle(xy=button_xy, radius=3, fill=self.COLOUR_BG_LIGHT, outline=self.COLOUR_OUTLINE)
            draw.text(xy=button_centre, text=screenLabel, anchor="mm", font=font, fill=self.COLOUR_TEXT_LIGHT, align="center")
            touchActiveRegions += ((button_xy, touchLabel),)

        self.display.display()
        return touchActiveRegions

    def drawStringEditor(self, string: str, caretPos:int = None, selection: tuple = None, keyboardUpperCase: bool = None, keyboardSpecials:str=False):
        draw = self.display.draw() # Get a PIL Draw object
        self.display.clear(self.COLOUR_BG) 
        
        #image = Image.new(mode="RGB", size= (self.WIDTH, self.HEIGHT), color=self.COLOUR_BG)
        #draw = ImageDraw.Draw(image)
        font = ImageFont.truetype(font=self.font_name, size=12)
        
        
        touchActiveRegions = tuple()
        keyboard, keyboardTouchActiveRegions = self.drawKeyboard(keyboardUpperCase, keyboardSpecials)

        keyboard_x = int((self.WIDTH - keyboard.width)/2)
        keyboard_y = int(self.HEIGHT - keyboard.height)
        
        for region, value in keyboardTouchActiveRegions:  #### shift touch region by chart's x,y 
            x1, y1, x2, y2 = region
            x1 += keyboard_x
            x2 += keyboard_x
            y1 += keyboard_y
            y2 += keyboard_y

            touchActiveRegions += (((x1, y1, x2, y2), value),)

        #### buttons
        buttons_labels = ("Bcksp", "Del", "Save", "Discard")
        button_width = int(max([font.getlength(label) for label in buttons_labels]) + 6)
        editor_box_xy = (self.MARGIN_SMALL, self.MARGIN_SMALL, self.WIDTH-2*self.MARGIN_SMALL- button_width, keyboard_y-self.MARGIN_SMALL)
        
        button_height = 18
        button_X_pos = self.WIDTH - self.MARGIN_SMALL - button_width
        y_pos = self.MARGIN_SMALL * 2
        button_y_spacing = (editor_box_xy[3]-editor_box_xy[1]-2*self.MARGIN_SMALL)/len(buttons_labels)


        for label in buttons_labels:
            button_xy = (button_X_pos, y_pos, button_X_pos+button_width, y_pos+button_height)
            button_centre_xy = ((button_xy[0]+button_xy[2])/2, (button_xy[1]+button_xy[3])/2)
            draw.rounded_rectangle(xy=button_xy, radius=4, fill=self.COLOUR_BUTTON)
            draw.text(xy=button_centre_xy, text=label, anchor="mm", font=font, fill=self.COLOUR_TEXT_LIGHT )
            touchActiveRegions +=  ((button_xy, label),)
            y_pos += button_y_spacing
        
        #### edit box
        box_corner_radius = 12
        draw.rounded_rectangle(xy=editor_box_xy, radius=box_corner_radius, fill=self.COLOUR_BG_LIGHT)
        font = ImageFont.truetype(font=self.font_name, size=12)
        draw.text(xy=(editor_box_xy[0]+self.MARGIN_SMALL, editor_box_xy[1]+box_corner_radius+self.MARGIN_SMALL), text=string, font=font, anchor="lt", fill=self.COLOUR_OUTLINE)


        self.display.buffer.paste(im = keyboard, box=(int(keyboard_x), int(keyboard_y)))
        self.display.display()
        return touchActiveRegions
    

    def draw_xy_plot(self, data: tuple, width: int, height: int, autoscale:bool = True, stroke: tuple = (32,  140,  20)) -> Image.Image:

        im = Image.new(mode="RGB", size=(width, height), color=(42, 42, 42))
        draw  = ImageDraw.Draw(im)
        font_name = "Roboto-Regular.ttf"

        LINE_WIDTH = 2
        AXIS_WIDTH = 1
        TICKS_X = 5
        TICKS_Y = 4
        #### scale data to fit the width
        #### Resulting 1D list, X remapped to pixels
        height_reserved_for_axis = 10
        width_reserved_for_axis = 18
        width_chartArea = width - width_reserved_for_axis
        height_chartArea = height - height_reserved_for_axis
        dx = (data[len(data)-1][0]-data[0][0]) / width_chartArea

        data_rescaled = list()
        sum_y = 0
        pos_x = 1
        count_y = 0
        for i, point in enumerate(data):
            scaled_x = point[0]/dx
            if scaled_x < pos_x:
                sum_y += point[1]
                count_y += 1
            else:
                data_rescaled.append(sum_y/count_y)
                sum_y = point[1]
                count_y = 1
                pos_x += 1

        ##### Scale data in Y to fit in the chart area
        Y_MARGINS_RATIO = 0.8
        min_raw_y = min(data_rescaled) if autoscale else 0
        max_raw_y = max(data_rescaled)
        ratio_raw_to_pixel = (max_raw_y-min_raw_y) / (Y_MARGINS_RATIO * height_chartArea)
        scale_y_min = (0 - (1-Y_MARGINS_RATIO) * height_chartArea / 2) * ratio_raw_to_pixel + min_raw_y
        scale_y_max = (height_chartArea - (1-Y_MARGINS_RATIO) * height_chartArea / 2) * ratio_raw_to_pixel + min_raw_y


        if autoscale:
            data_rescaled = [point - min_raw_y for point in data_rescaled]

        max_value = max(data_rescaled)
        if max_value == 0:
            data_rescaled = [0 for point in data_rescaled]
        else:
            data_rescaled = [height-height_reserved_for_axis - int(round(point / max_value * Y_MARGINS_RATIO * height_chartArea + (1 - Y_MARGINS_RATIO) * height_chartArea / 2)) for point in data_rescaled]
        
        #### plot the data

        for it in range(1, len(data_rescaled)):
            draw.line(xy=(it-1+width_reserved_for_axis, data_rescaled[it-1], it+width_reserved_for_axis, data_rescaled[it]), fill=stroke, width=LINE_WIDTH)
        
        #### Drawing axis box and ticks

        draw.rectangle(xy=(width_reserved_for_axis, 0, width-LINE_WIDTH/2, height-height_reserved_for_axis),
                    outline=self.COLOUR_OUTLINE, width=AXIS_WIDTH)
        
        tick_distance_x = int(width_chartArea / TICKS_X)
        tick_distance_y = int(height_chartArea / TICKS_Y)
        tick_length = 2 + AXIS_WIDTH
        font = ImageFont.truetype(font=font_name, size=8)


        for it in range(TICKS_X):
            draw.line(xy=(width_reserved_for_axis + (it+1) * tick_distance_x, 0,
                        width_reserved_for_axis + (it+1) * tick_distance_x, tick_length),
                    fill=self.COLOUR_OUTLINE, width=AXIS_WIDTH)
            
            draw.line(xy=(width_reserved_for_axis + (it+1) * tick_distance_x, height-height_reserved_for_axis,
                        width_reserved_for_axis + (it+1) * tick_distance_x, height-height_reserved_for_axis-tick_length),
                    fill=self.COLOUR_OUTLINE, width=AXIS_WIDTH)
            
            label = formatTime(data[len(data)-1][0] / (TICKS_X - it))

            draw.text(xy=(width_reserved_for_axis + (it+1) * tick_distance_x, height),
                    text=label, fill=self.COLOUR_OUTLINE, font=font, anchor="mb" if it+1<TICKS_X else "rb")

        
        for it in range(TICKS_Y):
            
            label = str(round((scale_y_max-scale_y_min)/(TICKS_Y+1)*(it+1)+scale_y_min))
            
            draw.line(xy=(width_reserved_for_axis, height_reserved_for_axis + it * tick_distance_y,
                        width_reserved_for_axis + tick_length, height_reserved_for_axis + it * tick_distance_y),
                    fill=self.COLOUR_OUTLINE, width=AXIS_WIDTH)
            
            draw.text(xy=(width_reserved_for_axis-2, height - (it+1) * tick_distance_y-1),
                    text=label, fill=self.COLOUR_OUTLINE, font=font, anchor="rm")
            
            draw.line(xy=(width, height_reserved_for_axis + it * tick_distance_y,
                        width - tick_length, height_reserved_for_axis + it * tick_distance_y),
                    fill=self.COLOUR_OUTLINE, width=AXIS_WIDTH)

        return im 

    def drawPageHistory(self, list_of_workouts: list, lastDisplayedItem: int) -> tuple:
        
        draw = self.display.draw() # Get a PIL Draw object
        self.display.clear(self.COLOUR_BG) 
        touchActiveRegions = tuple()
        
        font = ImageFont.truetype(font=self.font_name, size=16)
        draw.text(xy = (self.WIDTH / 2, self.MARGIN_SMALL), 
                    text = "Workout History", # Box title
                    fill = self.COLOUR_TEXT_LIGHT,
                    font = font,
                    anchor="mt")
        
        font = ImageFont.truetype(font=self.font_name, size=10)
        button_mainMenu_xy = (self.MARGIN_SMALL, self.MARGIN_SMALL,
                              self.MARGIN_SMALL + int(font.getlength("Main Menu"))+4, self.MARGIN_SMALL+16)
        button_centre = ((button_mainMenu_xy[2]+button_mainMenu_xy[0])/2, (button_mainMenu_xy[3]+button_mainMenu_xy[1])/2)
        draw.rounded_rectangle(xy=button_mainMenu_xy, radius=3, fill=self.COLOUR_BG_LIGHT, outline=self.COLOUR_OUTLINE)
        draw.text(xy=button_centre, text="Main Menu", anchor="mm", font=font, fill=self.COLOUR_TEXT_LIGHT, align="center")
        touchActiveRegions += ((button_mainMenu_xy, "MainMenu"),)

        
        no_boxes = 3
        Y_Pos = 30
        box_height = 60

        for i in range(no_boxes):
            box_xy = (self.MARGIN_SMALL, Y_Pos, self.WIDTH-60, Y_Pos+box_height)
            draw.rounded_rectangle(xy=box_xy, radius=10, fill=self.COLOUR_BG_LIGHT)
            touchActiveRegions += ((box_xy, lastDisplayedItem-i),)

            font = ImageFont.truetype(font=self.font_name, size=11)
            draw.text(xy=(self.MARGIN_SMALL+10, Y_Pos+8), text=list_of_workouts[lastDisplayedItem-i]["Name"], 
                      font=font, anchor="lt", fill=self.COLOUR_TEXT_LIGHT)
            font = ImageFont.truetype(font=self.font_name, size=10)

            ##### Duration
            draw.text(xy=(self.MARGIN_SMALL+10, Y_Pos+27), text="Duration:", font=font, anchor="lt", fill=self.COLOUR_FILL)
            try:
                duration = list_of_workouts[lastDisplayedItem-i]["Max"]["Time"]
                duration = formatTime(int(duration))
            except:
                duration = "0"
            draw.text(xy=(self.MARGIN_SMALL+10+45, Y_Pos+28), text=duration, font=font, anchor="lt", fill=self.COLOUR_OUTLINE)
            
            #### Average power
            draw.text(xy=(self.MARGIN_SMALL+110, Y_Pos+27), text="Avg. Power:", font=font, anchor="lt", fill=self.COLOUR_FILL)
            try:
                average_power = list_of_workouts[lastDisplayedItem-i]["Averages"]["Power"]
                average_power = str(round(float(average_power))) + " W"
            except:
                average_power = ""
            draw.text(xy=(self.MARGIN_SMALL+110+62, Y_Pos+27), 
                      text=average_power, font=font, anchor="lt", fill=self.COLOUR_OUTLINE)
            
            #### Energy
            draw.text(xy=(self.MARGIN_SMALL+10, Y_Pos+43), text="Energy:", font=font, anchor="lt", fill=self.COLOUR_FILL)
            try:
                energy = list_of_workouts[lastDisplayedItem-i]["Max"]["Energy"]
                energy = str(round(float(energy)))
            except:
                energy = ""

            draw.text(xy=(self.MARGIN_SMALL+10+45, Y_Pos+43), 
                      text=energy+" kJ", font=font, anchor="lt", fill=self.COLOUR_OUTLINE)

            #### Program name
            draw.text(xy=(self.MARGIN_SMALL+110, Y_Pos+43), text="Program:", font=font, anchor="lt", fill=self.COLOUR_FILL)
            program_name = list_of_workouts[lastDisplayedItem-i]["Program"]
            program_name = (program_name[:14] + "…") if len(program_name) > 14 else program_name
            draw.text(xy=(self.MARGIN_SMALL+110+62, Y_Pos+43), text=program_name, font=font, anchor="lt", fill=self.COLOUR_OUTLINE)

            Y_Pos += box_height+8
        
        
        displayed_range = str(lastDisplayedItem-1)+" to  "+str(lastDisplayedItem+1)+"\nOut of:  "+str(len(list_of_workouts))
        draw.text(xy=(self.WIDTH-30, int(self.HEIGHT/2)), text=displayed_range, anchor="mm", 
                  align="center", fill=self.COLOUR_FILL, font=font)


        triangle_width = 12
        triangle_height = 16

        if lastDisplayedItem+1 < len(list_of_workouts):
            Y_Pos = 80
            draw.polygon(xy=(int(self.WIDTH-30), Y_Pos,
                             int(self.WIDTH-30 - triangle_width/2), Y_Pos+triangle_height,
                             int(self.WIDTH-30 + triangle_width/2), Y_Pos+triangle_height),
                         fill=self.COLOUR_BUTTON)
            
            triangle_box = (int(self.WIDTH-30 - triangle_width/2), Y_Pos,  int(self.WIDTH-30 + triangle_width/2), Y_Pos+triangle_height)
            touchActiveRegions += ((triangle_box, "Next"),)
            
        if lastDisplayedItem-1 > 0:
            Y_Pos = 147
            draw.polygon(xy=(int(self.WIDTH-30 - triangle_width/2), Y_Pos,
                             int(self.WIDTH-30 + triangle_width/2), Y_Pos,
                             int(self.WIDTH-30), Y_Pos+triangle_height),
                         fill=self.COLOUR_BUTTON)
            
            triangle_box = (int(self.WIDTH-30 - triangle_width/2), Y_Pos,  int(self.WIDTH-30 + triangle_width/2), Y_Pos+triangle_height)
            touchActiveRegions += ((triangle_box, "Previous"),)

        self.display.display()
        return touchActiveRegions
    
    
    def drawKeyboard(self, isUpperCase: bool = False, specials: bool = False) -> tuple:

        touchActiveRegions = tuple()

        line_letters_1 = "qwertyyuiop"
        line_letters_2 = "asdfghjkl"
        line_letters_3 = "zxcvbnm"
        line_numbers   = "1234567890"
        line_special_1 = "!\"£$%^&*()="
        line_special_2 = "_-+[];:@#"
        line_special_3 = "'~,<>.?"

        if specials == True:
            selected_lines = (line_numbers, line_special_1, line_special_2, line_special_3)
        else:
            selected_lines= (line_numbers, line_letters_1, line_letters_2, line_letters_3)

        max_number_of_chars = max([len(line) for line in selected_lines])
        char_spacing = 3  
        char_width = int((self.WIDTH - (max_number_of_chars+1)*char_spacing)/max_number_of_chars)

        Y_pos = char_spacing  # first line Y
        lineSpacing = char_spacing
        char_height = 25
        
        image_height = char_height * 4 + 5 * char_spacing
        image_width  = max_number_of_chars*char_width + (max_number_of_chars + 1) * char_spacing

        image = Image.new(mode="RGB", size= (image_width, image_height), color=self.COLOUR_BG)
        draw = ImageDraw.Draw(image)

        font = ImageFont.truetype(font=self.font_name, size=14)
        
        line_X_pos_starts = (char_spacing + char_width/2, char_spacing, char_spacing + char_width/2, 2*char_spacing + char_width*3/2)
        
        for line, X_pos_start in zip(selected_lines, line_X_pos_starts):
            X_pos = X_pos_start
            line = line.upper() if isUpperCase == True else line
            
            for character in line:
                
                box_xy = (X_pos, Y_pos, X_pos+char_width, Y_pos+char_height)
                box_centre_xy = (int((box_xy[0]+box_xy[2])/2), int((box_xy[1]+box_xy[3])/2))

                draw.rounded_rectangle(xy = box_xy, radius=3, fill=self.COLOUR_BG_LIGHT)
                draw.text(xy = box_centre_xy, text = character, fill = self.COLOUR_OUTLINE, font = font, anchor="mm")
                touchActiveRegions += ((box_xy, character),)
                X_pos += char_width + char_spacing

            Y_pos += char_height + lineSpacing

        font = ImageFont.truetype(font=self.font_name, size=10)

        specials_xy = (X_pos, char_height * 3 + lineSpacing * 4, X_pos + 2*char_width, char_height * 4 + lineSpacing * 4)
        specials_centre_xy = (int((specials_xy[0]+specials_xy[2])/2), int((specials_xy[1]+specials_xy[3])/2))
        draw.rounded_rectangle(xy = specials_xy, radius=3, fill=self.COLOUR_BG_LIGHT)
        draw.text(xy = specials_centre_xy, text = "!#1£", fill = self.COLOUR_OUTLINE, font = font, anchor="mm")
        touchActiveRegions += ((specials_xy, "specials"),)

        shift_xy = (char_spacing, char_height * 3 + lineSpacing * 4, int(char_spacing+char_width*3/2), char_height * 4 + lineSpacing * 4)
        shift_centre_xy = (int((shift_xy[0]+shift_xy[2])/2), int((shift_xy[1]+shift_xy[3])/2))
        draw.rounded_rectangle(xy = shift_xy, radius=3, fill=self.COLOUR_BG_LIGHT)
        draw.text(xy = shift_centre_xy, text = "Shift", fill = self.COLOUR_OUTLINE, font = font, anchor="mm")
        touchActiveRegions += ((shift_xy, "shift"),)

        return (image, touchActiveRegions)

    def draw_page_historical_record_details(self, metadata, data, chart1:str, chart2:str) -> tuple:

        RAD = 8

        draw = self.display.draw() # Get a PIL Draw object
        self.display.clear(self.COLOUR_BG) 
        touchActiveRegions = tuple()

        font = ImageFont.truetype(font=self.font_name, size=10)
        button_mainMenu_xy = (2, 2, 2 + int(font.getlength("Back"))+12, 2+16)
        button_centre = ((button_mainMenu_xy[2]+button_mainMenu_xy[0])/2, (button_mainMenu_xy[3]+button_mainMenu_xy[1])/2)
        draw.rounded_rectangle(xy=button_mainMenu_xy, radius=3, fill=self.COLOUR_BG_LIGHT, outline=self.COLOUR_OUTLINE)
        draw.text(xy=button_centre, text="Back", anchor="mm", font=font, fill=self.COLOUR_TEXT_LIGHT, align="center")
        touchActiveRegions += ((button_mainMenu_xy, "Back"),)
        
        font = ImageFont.truetype(font=self.font_name, size=16)
        Y_Pos = 2
        draw.text(xy = (self.WIDTH / 2, Y_Pos), text = metadata["Name"], fill = self.COLOUR_TEXT_LIGHT, font = font, anchor="mt")
        
        Y_Pos += font.getbbox(text=metadata["Name"],anchor="mt")[3] + 8
        summary_box_height = 28
        draw.rounded_rectangle(xy=(2, Y_Pos, self.WIDTH-2, Y_Pos+summary_box_height), fill=self.COLOUR_BG_LIGHT, radius=RAD)
        
        font = ImageFont.truetype(font=self.font_name, size=10)
        Y_Pos_box = Y_Pos+16
        X_Pos_box = 8
        draw.text(xy=(X_Pos_box, Y_Pos_box), text="Duration:", font=font, anchor="ls", fill=self.COLOUR_FILL)
        try:
            duration = metadata["Max"]["Time"]
            duration = formatTime(int(duration))
        except:
            duration = "0"

        X_Pos_box += font.getlength(text="Duration") + 5
        draw.text(xy=(X_Pos_box, Y_Pos_box), text=duration, font=font, anchor="ls", fill=self.COLOUR_OUTLINE)
        X_Pos_box += font.getlength(text=duration) + 12
        
        draw.text(xy=(X_Pos_box, Y_Pos_box), text="Program:", font=font, anchor="ls", fill=self.COLOUR_FILL)
        X_Pos_box += font.getlength(text="Program:") + 5
        program_name = metadata["Program"]
        program_name = (program_name[:14] + "…") if len(program_name) > 14 else program_name
        draw.text(xy=(X_Pos_box, Y_Pos_box), text=program_name, font=font, anchor="ls", fill=self.COLOUR_OUTLINE)
        X_Pos_box += font.getlength(text=program_name) + 12
        
        draw.text(xy=(X_Pos_box, Y_Pos_box), text="Energy:", font=font, anchor="ls", fill=self.COLOUR_FILL)
        X_Pos_box += font.getlength(text="Energy:") + 5
        try:
            energy = metadata["Max"]["Energy"]
            energy = str(round(float(energy))) + " kJ"
        except:
            energy = ""
        draw.text(xy=(X_Pos_box, Y_Pos_box), text=energy, font=font, anchor="ls", fill=self.COLOUR_OUTLINE)
        X_Pos_box += font.getlength(text=energy) + 12

        GAP = 10
        CHART_HEIGH = 84
        HEADERS = 20
        ARROWS_ZONE = 40
        

        Y_Pos += summary_box_height+GAP
        
        def slicer(data, key:str) -> tuple:
            sliced_data = tuple()
            for line in data:
                try:
                    x = float(line["T"])
                except:
                    x = 0
                try:
                    y = float(line[key])
                except:
                    y = 0

                sliced_data += ((x, y),)
            return sliced_data
        
        font = ImageFont.truetype(font=self.font_name, size=10)    
        chart_keys = (chart1, chart2)
        charts = [self.draw_xy_plot(slicer(data, chart), self.WIDTH-ARROWS_ZONE-RAD-2, CHART_HEIGH - HEADERS, True) for chart in chart_keys]

        for ch, key in zip(charts, chart_keys):
            draw.rounded_rectangle(xy=(2, Y_Pos, self.WIDTH-ARROWS_ZONE, Y_Pos+CHART_HEIGH), fill=self.COLOUR_BG_LIGHT,radius=RAD)
            self.display.buffer.paste(ch, box=(2, Y_Pos+HEADERS))
            X_Pos_box = 10
            draw.text(xy=(X_Pos_box, Y_Pos+14), text=key, anchor="ls", fill=self.COLOUR_FILL, font=font)
            X_Pos_box += 80
            draw.text(xy=(X_Pos_box, Y_Pos+14), text="Max:", anchor="ls", fill=self.COLOUR_FILL, font=font)
            X_Pos_box += 25
            draw.text(xy=(X_Pos_box, Y_Pos+14), text=str(round(float(metadata["Max"][key]))), anchor="ls", fill=self.COLOUR_OUTLINE, font=font)
            X_Pos_box += 35
            draw.text(xy=(X_Pos_box, Y_Pos+14), text="Average:", anchor="ls", fill=self.COLOUR_FILL, font=font)
            X_Pos_box += 42
            draw.text(xy=(X_Pos_box, Y_Pos+14), text=str(round(float(metadata["Averages"][key]),1)), anchor="ls", fill=self.COLOUR_OUTLINE, font=font)

            Y_Pos+=CHART_HEIGH+GAP

        Y_Pos = int(Y_Pos - 1.6 * (CHART_HEIGH+GAP))
        arrow_centre = self.WIDTH-ARROWS_ZONE/2
        arrow_width = 10
        arrow_height = 15

        draw.polygon(xy=(arrow_centre, Y_Pos, 
                        arrow_centre-arrow_width/2, Y_Pos+arrow_height, 
                        arrow_centre+arrow_width/2, Y_Pos+arrow_height),
                    fill=self.COLOUR_BUTTON)
        arrow_box = (arrow_centre-arrow_width/2, Y_Pos, arrow_centre+arrow_width/2, Y_Pos+arrow_height)
        touchActiveRegions += ((arrow_box, "Previous"),)
        

        Y_Pos += CHART_HEIGH+GAP
        draw.polygon(xy=(arrow_centre-arrow_width/2, Y_Pos,
                        arrow_centre+arrow_width/2, Y_Pos,
                        arrow_centre, Y_Pos+ arrow_height),
                    fill=self.COLOUR_BUTTON)
        
        arrow_box = (arrow_centre-arrow_width/2, Y_Pos, arrow_centre+arrow_width/2, Y_Pos+arrow_height)
        touchActiveRegions += ((arrow_box, "Next"),)
                        
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

        chart, chartTouchActiveRegions = self.drawSegmentsChart(chartWidth      = int(self.WIDTH - 2 * self.MARGIN_LARGE),
                                                           chartHeight     = int(self.HEIGHT * 1 / 3),
                                                           bgColour        = self.COLOUR_BG_LIGHT,
                                                           segmentsColour  = self.COLOUR_FILL,
                                                           selectionColour = self.COLOUR_OUTLINE,
                                                           selectedSegment = selected_segment,
                                                           workoutParams   = program.getParameters())

        chartBox_x = self.MARGIN_LARGE
        chartBox_y = int(self.HEIGHT * 2 / 3)-self.MARGIN_LARGE
        
        for region, value in chartTouchActiveRegions:  #### shift touch region by chart's x,y 
            x1, y1, x2, y2 = region
            x1 += chartBox_x
            x2 += chartBox_x
            y1 += chartBox_y
            y2 += chartBox_y

            touchActiveRegions += (((x1, y1, x2, y2), value),)

        self.display.buffer.paste(im = chart, box=(int(chartBox_x), int(chartBox_y)))
        
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
            Y_Pos_start = Y_Pos
            Y_Pos += 13

            font = ImageFont.truetype(font=self.font_name, size=size)
            draw.text(xy=(X_Pos + Xoffset, Y_Pos), text=str(value)+unit, fill=self.COLOUR_OUTLINE, font=font)
            
            text_length = int(max(font.getlength(text=label), font.getlength(text=str(value)+unit)))
            touchBox_xy = (X_Pos, Y_Pos_start, X_Pos+text_length, Y_Pos)

            touchActiveRegions += ((touchBox_xy, label),)
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
    
    def draw_page_ble_discovery(self, device_type: str, list_of_devices: list, last_displayed_item, scan_completion_percentage: int = 0) -> tuple:

        draw = self.display.draw() # Get a PIL Draw object
        self.display.clear(self.COLOUR_BG) 
        touchActiveRegions = tuple()

        font = ImageFont.truetype(font=self.font_name, size=10)
        button_mainMenu_xy = (2, 2, 2 + int(font.getlength("Back"))+12, 2+16)
        button_centre = ((button_mainMenu_xy[2]+button_mainMenu_xy[0])/2, (button_mainMenu_xy[3]+button_mainMenu_xy[1])/2)
        draw.rounded_rectangle(xy=button_mainMenu_xy, radius=3, fill=self.COLOUR_BG_LIGHT, outline=self.COLOUR_OUTLINE)
        draw.text(xy=button_centre, text="Back", anchor="mm", font=font, fill=self.COLOUR_TEXT_LIGHT, align="center")
        touchActiveRegions += ((button_mainMenu_xy, "Back"),)

        font = ImageFont.truetype(font=self.font_name, size=16)
        Y_Pos = self.MARGIN_LARGE
        draw.text(xy = (self.WIDTH / 2, Y_Pos), text = device_type, fill =self.COLOUR_TEXT_LIGHT, font = font, anchor="mt")
        
        if list_of_devices is not None:
            button_rescan_xy = (240, 26, 240 + int(font.getlength("Re-scan"))+12, 26+22)
            button_centre = ((button_rescan_xy[2]+button_rescan_xy[0])/2, (button_rescan_xy[3]+button_rescan_xy[1])/2)
            draw.rounded_rectangle(xy=button_rescan_xy, radius=3, fill=self.COLOUR_BG_LIGHT, outline=self.COLOUR_OUTLINE)
            draw.text(xy=button_centre, text="Re-scan", anchor="mm", font=font, fill=self.COLOUR_TEXT_LIGHT, align="center")
            touchActiveRegions += ((button_rescan_xy, "Rescan"),)

            font = ImageFont.truetype(font=self.font_name, size=12)

            box_height = 30
            box_width = 250
            GAP = 14
            RADIUS = 8
            ARROWS_ZONE = 50
            
            Y_Pos = 60
            
            if len(list_of_devices) > 0:
                for dev_id in range(last_displayed_item-4, last_displayed_item):
                    box_xy = (self.MARGIN_LARGE, Y_Pos, self.MARGIN_LARGE+box_width, Y_Pos+box_height)
                    draw.rounded_rectangle(xy=box_xy, radius=RADIUS, fill=self.COLOUR_BG_LIGHT)
                    
                    dev_name = (list_of_devices[dev_id]["Name"][:14] + "…") if len(list_of_devices[dev_id]["Name"]) > 14 else list_of_devices[dev_id]["Name"]
                    draw.text(xy=(self.MARGIN_LARGE+RADIUS*2, Y_Pos+box_height/2), text=dev_name, font=font, anchor="lm", fill=self.COLOUR_TEXT_LIGHT)
                    draw.text(xy=(self.MARGIN_LARGE+RADIUS+120, Y_Pos+box_height/2), text=list_of_devices[dev_id]["Address"], font=font, anchor="lm", fill=self.COLOUR_TEXT_LIGHT)
                    
                    touchActiveRegions +=  ((box_xy, dev_id),)
                    Y_Pos += box_height + GAP
            else:
                draw.rounded_rectangle(xy=(self.MARGIN_LARGE, Y_Pos, self.MARGIN_LARGE+box_width, Y_Pos+box_height), radius=RADIUS, fill=self.COLOUR_BG_LIGHT)
                draw.text(xy=(self.MARGIN_LARGE+RADIUS*2, Y_Pos+box_height/2), text="No devices found...", font=font, anchor="lm", fill=self.COLOUR_TEXT_LIGHT)

            
            Y_Pos = 110
            arrow_centre = self.WIDTH-ARROWS_ZONE/2
            arrow_width = 10
            arrow_height = 15
            
            if last_displayed_item > 4:
                draw.polygon(xy=(arrow_centre, Y_Pos, 
                                arrow_centre-arrow_width/2, Y_Pos+arrow_height, 
                                arrow_centre+arrow_width/2, Y_Pos+arrow_height),
                            fill=self.COLOUR_BUTTON)
                arrow_box = (arrow_centre-arrow_width/2, Y_Pos, arrow_centre+arrow_width/2, Y_Pos+arrow_height)
                touchActiveRegions += ((arrow_box, "Previous"),)
            

            Y_Pos += arrow_height + 30
            if len(list_of_devices) > last_displayed_item:
                draw.polygon(xy=(arrow_centre-arrow_width/2, Y_Pos,
                                arrow_centre+arrow_width/2, Y_Pos,
                                arrow_centre, Y_Pos+ arrow_height),
                            fill=self.COLOUR_BUTTON)
                
                arrow_box = (arrow_centre-arrow_width/2, Y_Pos, arrow_centre+arrow_width/2, Y_Pos+arrow_height)
                touchActiveRegions += ((arrow_box, "Next"),)
        else:
            box_width = self.WIDTH-2*self.MARGIN_LARGE
            box_width_filled = int(scan_completion_percentage * box_width / 100)
            
            draw.rounded_rectangle(xy=(self.MARGIN_LARGE, 80, self.MARGIN_LARGE+ box_width, 120), radius=8, fill=self.COLOUR_BG_LIGHT)
            draw.rounded_rectangle(xy=(self.MARGIN_LARGE, 80, self.MARGIN_LARGE+box_width_filled, 120), radius=8, 
                                   fill= self.COLOUR_OUTLINE, corners=(True, False, False, True))
        
        self.display.display()

        return touchActiveRegions


    def drawMessageBox(self, message:str, options: tuple) -> tuple:
        
        self.display.buffer = self.display.buffer.convert("L")
        self.display.buffer = self.display.buffer.convert("RGB")

        draw = self.display.draw() # Get a PIL Draw object
        font = ImageFont.truetype(font=self.font_name, size=12)
        touchActiveRegions = tuple()
        
        numberOfButtons = len(options)
        buttonLength = int(max(max([draw.textlength(opt, font=font) for opt in options]), font.getlength(message)) + 4)
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
            draw.text(xy=(X_pos+buttonLength/2, Y_pos+buttonHeight/2), text=opt, fill=self.COLOUR_TEXT_LIGHT, anchor="mm", font=font)
            X_pos += buttonLength+marginLength
            touchActiveRegions += ((button_xy, opt),)

        self.display.display()
        return touchActiveRegions

    def drawProgramSelector(self, listOfParametres: list, previousEnabled: bool = False, 
                            nextEnabled: bool = False, newProgramEnabled: bool = True) -> tuple:
        
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
                            fill = self.COLOUR_OUTLINE,
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
                            fill = self.COLOUR_OUTLINE,
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
                            fill = self.COLOUR_OUTLINE,
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
                            fill = self.COLOUR_OUTLINE,
                            font = font,
                            anchor="lm")
                
                #### chart
                Y_offset += 15
                chartImage, chartActiveRegions = self.drawSegmentsChart(chartWidth=chartWidth,
                                                    chartHeight=chartHeight,
                                                    workoutParams=thisWorkoutParams,
                                                    bgColour=self.COLOUR_BG_LIGHT,
                                                    segmentsColour=self.COLOUR_FILL)
                
                self.display.buffer.paste(chartImage, (int(box_xy[0]+7), int(self.MARGIN_SMALL+Y_offset)))

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

        box_Labels = (("Elapsed Time:", formatTime(self.dataContainer.workoutTime), 
                                        formatTime(self.dataContainer.currentSegment.elapsedTime)),
                      (workoutType,),
                      ("Remaining Time:", formatTime(self.dataContainer.workoutDuration - self.dataContainer.workoutTime),
                                          formatTime(self.dataContainer.currentSegment.duration - self.dataContainer.currentSegment.elapsedTime))
                     )
        
        for i in range(noBoxes):
            box_xy = ((self.MARGIN_LARGE + i * (box_width + self.MARGIN_LARGE), 0),
                      (self.MARGIN_LARGE + i * (box_width + self.MARGIN_LARGE) + box_width, self.MARGIN_SMALL+box_height))
            
            box_centre_xy = (box_xy[0][0] + box_width / 2, box_xy[0][1] + box_height / 2)
            
            font = ImageFont.truetype(font=self.font_name, size=12)
            
            draw.text(xy = (box_centre_xy[0], box_xy[0][1]+3),
                    text = box_Labels[i][0], # Box title
                    fill = self.COLOUR_TEXT_LIGHT,
                    font = font,
                    anchor="mt")
            
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

            font = ImageFont.truetype(font=self.font_name, size=11)

            valuesOffset = max(font.getlength("Segment:"), font.getlength("Total:")) + font.getlength("  ")

            draw.text(xy = (box_centre_xy[0] - box_width / 2 , box_centre_xy[1]+8), 
                    text = "Total:", # total
                    fill = self.COLOUR_TEXT_LIGHT,
                    font = font,
                    anchor="lm")

            draw.text(xy = (int(box_centre_xy[0] - box_width / 2 + valuesOffset), box_centre_xy[1]+8), 
                    text = str(box_Labels[i][1]), # total
                    fill = self.COLOUR_OUTLINE,
                    font = font,
                    anchor="lm")

            draw.text(xy = (box_centre_xy[0] - box_width / 2, box_centre_xy[1]+24), 
                    text = "Segment: ",
                    fill = self.COLOUR_TEXT_LIGHT,
                    font = font,
                    anchor="lm")

            draw.text(xy = (box_centre_xy[0] - box_width / 2 + valuesOffset, box_centre_xy[1]+24), 
                    text = str(box_Labels[i][2]), # Segment
                    fill = self.COLOUR_OUTLINE,
                    font = font,
                    anchor="lm")

        Y_Pos: int = Y_POS_SECTIONS

        section1: dict = {"Section": "Speed", "labels": {
                    "km/h": str(round(self.dataContainer.momentary.speed,1)), 
                    "Average":str(round(self.dataContainer.average.speed,1)), 
                    "Max":str(round(self.dataContainer.max.speed,1))}}
        
        section2: dict = {"Section": "Power", "labels": {
                    "W": str(round(self.dataContainer.momentary.power,0)), 
                    "Average":str(round(self.dataContainer.average.power,0)), 
                    "Max":str(round(self.dataContainer.max.power,0))}}
        
        section3: dict = {"Section": "Cadence", "labels": {
                    "RPM": str(round(self.dataContainer.momentary.cadence,1)), 
                    "Average":str(round(self.dataContainer.average.cadence,1)), 
                    "Max":str(round(self.dataContainer.max.cadence,1))}}
        
        section4: dict = {"Section": "Heart Rate", "labels": {
                    "BPM": str(round(self.dataContainer.momentary.heartRate,0)), 
                    "Average":str(round(self.dataContainer.average.heartRate,0)), 
                    "Max":str(round(self.dataContainer.max.heartRate,0)),
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

                spacing = ((X_POS_END - self.MARGIN_LARGE) - self.MARGIN_LARGE) / (len(all_sections) - 1)

                font = ImageFont.truetype(font=self.font_name, size=8)
                draw.text(xy = (X_Pos, Y_Pos+35),
                        text = key,
                        fill = self.COLOUR_TEXT_LIGHT,
                        font = font,
                        anchor="mm")
                
                font_size = 16
                font = ImageFont.truetype(font=self.font_name, size=font_size)
                while font.getlength(str(section["labels"][key])) > spacing - 4:
                    font_size -= 1
                    font = ImageFont.truetype(font=self.font_name, size=font_size)
               
                value = str(section["labels"][key])
                if value ==  "Recovery":
                    colour = self.COLOUR_CLIMBER
                elif value == "Aerobic":
                    colour = self.COLOUR_TEXT_LIGHT
                elif value == "Tempo":
                    colour = self.COLOUR_OUTLINE
                elif value == "Threshold":
                    colour = self.COLOUR_BUTTON
                elif value == "Anaerobic":
                    colour = self.COLOUR_HEART
                else:
                    colour = self.COLOUR_TEXT_LIGHT
                
                draw.text(xy = (X_Pos, Y_Pos+15), text = value, fill = colour, font = font, anchor="mm")

                # calculate spacing accordinly:
                X_Pos += spacing
            
            Y_Pos += section_height

        self.display.display()
        return touchActiveRegions
    

    def draw_page_user_editor(self, user: User) -> tuple:
        self.display.clear(self.COLOUR_BG)
        draw = self.display.draw() # Get a PIL Draw object
        
        touchActiveRegions = tuple()
        font = ImageFont.truetype(font=self.font_name, size=18)
        draw.text(xy=(self.WIDTH/2, self.MARGIN_LARGE), text="User editor", font=font, anchor="mm", fill=self.COLOUR_TEXT_LIGHT)


        BUTTONS_X = 270
        draw_area_y_start = 40
        
        button_height = 20
        button_gap = 12
        font = ImageFont.truetype(font=self.font_name, size=12)
        buttons_labels = ("Finish", "Add new user", "Delete user", "Change user")

        button_width = max([int(font.getlength(text=label))+12 for label in buttons_labels])
        
        draw.rounded_rectangle(xy=(self.MARGIN_LARGE, draw_area_y_start, 210, self.HEIGHT-self.MARGIN_LARGE), radius=8, fill=self.COLOUR_BG_LIGHT)

        try:
            image = Image.open(user.picture)
        except:
            try:
                image = Image.open("nopicture.png")
            except:
                image = Image.new("RGB",(65,60), self.COLOUR_BG)
        
        imageRatio = image.width/image.height
        targetHeight = 60
        image = image.resize((int(imageRatio*targetHeight), int(targetHeight)))

        self.display.buffer.paste(image, (int(self.MARGIN_LARGE*2), int(draw_area_y_start+10)))
        
        text_x = self.MARGIN_LARGE + 80
        text_y = draw_area_y_start+20
        labels = ("Name", "Picture", "YoB", "FTP")
        values = (user.Name, user.picture, user.yearOfBirth, round(user.FTP))

        for label, value in zip(labels, values):
            draw.text(xy=(text_x, text_y), text=label, anchor="ls", font=font, fill=self.COLOUR_FILL)
            text_y += 16
            draw.text(xy=(text_x+30, text_y), text=str(value), anchor="ls", font=font, fill=self.COLOUR_TEXT_LIGHT)
            text_y += 24
            box_xy = (text_x, text_y, 210, text_y + 32)
            touchActiveRegions += ((box_xy, label),)


        button_y = draw_area_y_start
        for label in buttons_labels:
            
            button_xy = (BUTTONS_X-int(button_width/2), button_y, BUTTONS_X+int(button_width/2), button_y + button_height)
            button_centre_xy = (BUTTONS_X, button_y+ int(button_height/2))
            draw.rounded_rectangle(xy=button_xy, radius=3, fill=self.COLOUR_BUTTON)
            draw.text(xy=button_centre_xy, text=label, font=font, fill=self.COLOUR_TEXT_LIGHT, anchor="mm")
            button_y += button_height+button_gap
            touchActiveRegions += ((button_xy, label),)

        self.display.display()
        return touchActiveRegions



    def draw_page_settings_mqtt(self, mqtt: MQTT_Exporter) -> tuple:
        
        self.display.clear(self.COLOUR_BG)
        draw = self.display.draw() # Get a PIL Draw object
        
        touchActiveRegions = tuple()
        font = ImageFont.truetype(font=self.font_name, size=18)
        draw.text(xy=(self.WIDTH/2, self.MARGIN_LARGE), text="MQTT Settings", font=font, anchor="mm", fill=self.COLOUR_TEXT_LIGHT)

        BUTTONS_X = 270
        draw_area_y_start = 40
        
        button_height = 20
        button_gap = 14
        font = ImageFont.truetype(font=self.font_name, size=12)
        buttons_labels = ("Save", "Discard")

        button_width = max([int(font.getlength(text=label))+12 for label in buttons_labels])
        
        draw.rounded_rectangle(xy=(self.MARGIN_LARGE, draw_area_y_start, 210, 226), radius=8, fill=self.COLOUR_BG_LIGHT)
        draw.rounded_rectangle(xy=(self.MARGIN_LARGE, 110, 300, 226), radius=8, fill=self.COLOUR_BG_LIGHT)
        
        
        text_x = self.MARGIN_LARGE + 20
        text_y = draw_area_y_start+30
        labels = ("Broker", "Port", "Topic", "Client ID", "Username", "Password")
        values = (mqtt.broker, mqtt.port, mqtt.topic, mqtt.client_id, mqtt.username, mqtt.password)

        for label, value in zip(labels, values):
            draw.text(xy=(text_x, text_y), text=label, anchor="ls", font=font, fill=self.COLOUR_FILL)
            draw.text(xy=(text_x+60, text_y), text=str(value), anchor="ls", font=font, fill=self.COLOUR_TEXT_LIGHT)
            text_y += 26
            box_xy = (text_x, text_y, 210, text_y + 32)
            touchActiveRegions += ((box_xy, label),)


        button_y = draw_area_y_start
        for label in buttons_labels:
            
            button_xy = (BUTTONS_X-int(button_width/2), button_y, BUTTONS_X+int(button_width/2), button_y + button_height)
            button_centre_xy = (BUTTONS_X, button_y+ int(button_height/2))
            draw.rounded_rectangle(xy=button_xy, radius=3, fill=self.COLOUR_BUTTON)
            draw.text(xy=button_centre_xy, text=label, font=font, fill=self.COLOUR_TEXT_LIGHT, anchor="mm")
            button_y += button_height+button_gap
            touchActiveRegions += ((button_xy, label),)


        self.display.display()
        return touchActiveRegions




    def drawPageUserSelect(self, userList: UserList, displayRange: tuple, 
                           previousEnabled: bool = False, nextEnabled: bool = False) -> tuple:
        
        self.display.clear(self.COLOUR_BG)
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

            self.display.buffer.paste(image, (int(BOX_X+10), int(box_y+10)))

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
        
        self.display.clear(self.COLOUR_BG)
        draw = self.display.draw() # Get a PIL Draw object
        #draw = ImageDraw.Draw(self.im)
        touchActiveRegions = tuple()

        noBoxes = (3, 2)    # in x and y
        box_width  = int((self.WIDTH - self.MARGIN_LARGE * (noBoxes[0]+1))/noBoxes[0])
        box_height = int(box_width  * 0.8)
        box_labels = ("Change\nUser", "History", "Settings", "Edit\nProgram","Ride\nProgram", "Freeride")

        stateMachineStates = ("UserChange", "History", "Settings", "ProgEdit", "RideProgram", "Freeride", "ProgSelect")
        
        HEART_HEIGHT = 23
        TRAINER_HEIGHT = 27
        heartImage: Image   = self.drawHeart(HEART_HEIGHT, colour_heart, self.COLOUR_OUTLINE, self.COLOUR_BG)
        trainerImage: Image = self.drawTrainer(TRAINER_HEIGHT, colour_trainer, self.COLOUR_OUTLINE, self.COLOUR_BG)
        #climberImage: Image = self.drawClimber(DEVICES_HEIGHT, colour_climber, self.COLOUR_OUTLINE, self.COLOUR_BG)
        
        Y_Pos = self.MARGIN_LARGE
        X_Pos = int(self.MARGIN_LARGE*1.5 + box_width -heartImage.width/2)

        #self.display.buffer
        self.display.buffer.paste(heartImage, (int(X_Pos), int(Y_Pos)))
       
        X_Pos = int(self.WIDTH/2 - trainerImage.width/2) 
        self.display.buffer.paste(trainerImage, (int(X_Pos), int(Y_Pos)))

        #X_Pos = int(self.MARGIN_LARGE*2.5 + 2*box_width -climberImage.width/2)
        #self.im.paste(climberImage, (X_Pos, Y_Pos))

        Y_Pos = HEART_HEIGHT + 3 * self.MARGIN_LARGE
        X_Pos = self.MARGIN_LARGE
        for i, zipped in enumerate(zip(box_labels, stateMachineStates)):
            
            label, state = zipped

            box_xy = (X_Pos, Y_Pos, X_Pos + box_width, Y_Pos + box_height)

            draw.rounded_rectangle(xy = box_xy, radius = 4, fill = self.COLOUR_BG_LIGHT, outline = self.COLOUR_OUTLINE, width = 5)
            
            touchActiveRegions += ((box_xy, state),)
            
            font = ImageFont.truetype(font=self.font_name, size=12)
            box_centre_xy = (box_xy[0] + box_width / 2, box_xy[1] + box_height / 2)
            draw.text(xy = box_centre_xy, text = label, fill = self.COLOUR_TEXT_LIGHT, font = font, align="center", anchor="mm")
            
            X_Pos += box_width + 12

            if i + 1 == noBoxes[0]:
                X_Pos = self.MARGIN_LARGE
                Y_Pos += box_height + 25
                
        self.display.display()
        return touchActiveRegions


    def drawConnectionErrorMessage(self) -> None:
        WIDTH = 150
        HEIGHT = 68
        
        image = Image.new('RGB', (WIDTH, HEIGHT), self.COLOUR_BG_LIGHT)
        draw = ImageDraw.Draw(image)

        draw.rectangle(xy=(0,0, WIDTH-1, HEIGHT-1), outline=self.COLOUR_OUTLINE, fill=self.COLOUR_BG_LIGHT, width=2)

        font = ImageFont.truetype(font=self.font_name, size=12)
        draw.text(xy=(WIDTH/2, 10), text="Trainer Not Connected!", anchor="mt", font=font)
        font = ImageFont.truetype(font=self.font_name, size=9)
        draw.text(xy=(WIDTH/2, 47), text="Power up  or  start  pedalling\nto  wake up  the  trainer", anchor="mm", font=font, align="center")

        self.display.buffer = self.display.buffer.convert("L")
        self.display.buffer = self.display.buffer.convert("RGB")

        self.display.buffer.paste(image, (int(self.WIDTH/2-WIDTH/2), int(self.HEIGHT - HEIGHT - 40)))
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

if __name__ == "__main__":

    lcd = ScreenManager()
    #lcd.drawKeyboard(case="upper", specials=True)
    lcd.drawStringEditor("workout no1")