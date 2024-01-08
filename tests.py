from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

COLOUR_BG:         tuple = (31,   31,  31)

im = Image.new('RGB', (320,240), COLOUR_BG)

draw = ImageDraw.Draw(im)
font = ImageFont.load_default(12)
touchActiveRegions = tuple()

options = ("Save", "Discard", "Cancel")


numberOfButtons = len(options)

max = max([draw.textlength(opt, font=font) for opt in options])

print(max)

#im.save("dialog.png")