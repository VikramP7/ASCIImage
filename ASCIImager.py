import os
import sys
import re
import numpy as np
from PIL import Image
from rich.console import Console
from rich.text import Text
import CharacterDensities

NO_CHROME_SVG_FORMAT = """\
<svg class="rich-terminal" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
    <style>
    .{unique_id}-matrix {{
        font-family: Fira Code, monospace;
        font-size: {char_height}px;
        line-height: {line_height}px;
        font-variant-east-asian: full-width;
    }}
    {styles}
    </style>
    <defs>
    <clipPath id="{unique_id}-clip-terminal">
      <rect x="0" y="0" width="{terminal_width}" height="{terminal_height}" />
    </clipPath>
    {lines}
    </defs>
    <rect fill="#0c0c0c" x="0" y="0" width="{width}" height="{height}" rx="8"/>
    <g transform="translate(9, 9)" clip-path="url(#{unique_id}-clip-terminal)">
    {backgrounds}
    <g class="{unique_id}-matrix">
    {matrix}
    </g>
    </g>
</svg>
"""
TIGHT_SVG_FORMAT = """\
<svg class="rich-terminal" viewBox="0 0 {terminal_width} {terminal_height}" xmlns="http://www.w3.org/2000/svg">
    <style>
    .{unique_id}-matrix {{
        font-family: Fira Code, monospace;
        font-size: {char_height}px;
        line-height: {line_height}px;
        font-variant-east-asian: full-width;
    }}
    {styles}
    </style>
    <defs>
    <clipPath id="{unique_id}-clip-terminal">
      <rect x="0" y="0" width="{terminal_width}" height="{terminal_height}" />
    </clipPath>
    {lines}
    </defs>
    <rect fill="#0c0c0c" x="0" y="0" width="{terminal_width}" height="{terminal_height}"/>
    <g clip-path="url(#{unique_id}-clip-terminal)">
    {backgrounds}
    <g class="{unique_id}-matrix">
    {matrix}
    </g>
    </g>
</svg>
"""
TIGHT_TRANSPARENT_SVG_FORMAT = """\
<svg class="rich-terminal" viewBox="0 0 {terminal_width} {terminal_height}" xmlns="http://www.w3.org/2000/svg">
    <style>
    .{unique_id}-matrix {{
        font-family: Fira Code, monospace;
        font-size: {char_height}px;
        line-height: {line_height}px;
        font-variant-east-asian: full-width;
    }}
    {styles}
    </style>
    <defs>
    <clipPath id="{unique_id}-clip-terminal">
      <rect x="0" y="0" width="{terminal_width}" height="{terminal_height}" />
    </clipPath>
    {lines}
    </defs>
    <g clip-path="url(#{unique_id}-clip-terminal)">
    {backgrounds}
    <g class="{unique_id}-matrix">
    {matrix}
    </g>
    </g>
</svg>
"""


# window sizes for resultant image in characters
width = 240
height = 135
charDensityOriginal = ['Ñ', '@', '#', 'W', '$', '9', '8', '7', '6', '5', '4', '3', '2', '1', '0', '?', '!', 'a', 'b', 'c', ';', ':', '+', '=', '-', ',', '.', '_']
charDensityBourke = list('$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,"^`\'. ')

def ColourToAscii(r, g, b, gamma_y=1):
    """Returns the ASCII escape code for setting text colour to the specified RGB"""
    # apply gamma 
    # r = min(round(r+(r*(gamma_y-1)*0.3)), 256)
    # g = min(round(g+(g*(gamma_y-1)*0.59)), 256)
    # b = min(round(b+(b*(gamma_y-1)*0.11)), 256)

    r = min(round(r+(255-r)*(gamma_y-1)), 256)
    g = min(round(g+(255-g)*(gamma_y-1)), 256)
    b = min(round(b+(255-b)*(gamma_y-1)), 256)

    setForeground = "\u001b[38;2;"
    retString = setForeground + str(r) + ";" + str(g) + ";" + str(b) + "m"
    return retString


def ColourToBrightness(r, g, b, densityList):
    """Finds the grayscale value of the colour and returns a char corresponding to that"""
    ave = (r + g + b) / 3.0
    densityPercent = ave / 255.0
    charIndex = round(densityPercent * len(densityList))
    char = densityList[-(charIndex + 1)] if charIndex < len(densityList) else densityList[0]
    return char


def GetPath():
    """Prompts the user to provide a path to an image file"""
    badImagePath = True
    path = ""
    while badImagePath:
        badImagePath = False
        path = input("What is the path for your image (include extension): ")
        try:
            image = Image.open(path)
        except TypeError:
            badImagePath = True
            print("File not parsable.")
        except FileNotFoundError:
            badImagePath = True
            print("No file found at path.")
    return path


def ASCIIifyImage(path, height, gamma_y=1, charDensityMap=charDensityBourke):
    """
    Uses the provided path to parse an image file. Then it's scaled it to fit better in the console.
    Finally the scaled image is converted to ascii characters and escape codes are used to colour it.

    :param path: (String) The path to the image file
    :param height: (int) height of result image in # of chars
    :return: A list of strings, each element is a line of the image
    """

    # open image and convert to 3d array (int32 to avoid uint8 overflow when averaging)
    image = Image.open(path).convert("RGB")
    imgArr = np.asarray(image, dtype=np.int32)

    # compute scale factor and cropped dimensions
    scaleFactor = round(len(imgArr) / height)
    if scaleFactor < 1:
        scaleFactor = 1

    h, w = imgArr.shape[:2]
    sh = h // scaleFactor
    sw = w // scaleFactor

    # crop so dimensions are divisible by scaleFactor, then block-average via reshape
    cropped = imgArr[:sh * scaleFactor, :sw * scaleFactor, :3]
    resizeImg = (
        cropped.reshape(sh, scaleFactor, sw, scaleFactor, 3)
        .mean(axis=(1, 3))
        .astype(np.uint8)
    )

    line = ""
    lines = []
    for x in range(0, len(resizeImg)):
        for y in range(0, len(resizeImg[x])):
            r = int(resizeImg[x][y][0])
            g = int(resizeImg[x][y][1])
            b = int(resizeImg[x][y][2])
            # set the colour of the char pixel
            charPixel = ColourToAscii(r, g, b, gamma_y=gamma_y)
            # add the actual character that is going to be coloured
            # adding it twice because text is taller than it is wide
            charPixel += 2 * ColourToBrightness(r, g, b, charDensityMap)
            line += charPixel
        lines.append("" + line)
        line = ""

    print("\u001b[0m")
    return lines, len(resizeImg), len(resizeImg[0])*2


if __name__ == "__main__":
    path = None
    lines = 70
    saving = False
    save_path = None
    transparent = False
    if len(sys.argv) == 2:
        print("HELP MENU:\n\tpython ASCIImager.py [./path/to/img] [LineCount] [-s] [-t]\n\n\t-s is used to save the console output to .svg (saves to the `./path/to/img`)\n\t-t is used to save the image as a transparent background")
        exit(0)

    elif len(sys.argv) == 3:
        path = sys.argv[1]
        if not os.path.isfile(path):
            print("Source file doesn't exist!")
            exit(1)
        try:
            lines = int(sys.argv[2])
        except ValueError:
            print("Invalid number of lines using default 70")
            lines = 70

    elif len(sys.argv) >= 4:
        path = sys.argv[1]
        if not os.path.isfile(path):
            print("Source file doesn't exist!")
            exit(1)
        try:
            lines = int(sys.argv[2])
        except ValueError:
            print("Invalid number of lines using default 70")
            lines = 70
        if str(sys.argv[3]).lower().count('s') != 0:
            saving = True
            save_path = path[:path.rfind('.')] + "_svg.svg"
        if len(sys.argv) == 5:
            transparent = True

    else:
        path = GetPath()
        lines = 0
        try:
            lines = int(input("What should the result image height be (whole number): "))
        except ValueError:
            print("Error in reading width using default")
            lines = 70
    if (path == None):
        print("ERR: Bad Path")
        exit(1)

    saving = True
    outString, term_height, term_width = ASCIIifyImage(path, lines, gamma_y=1, charDensityMap=charDensityBourke[:40])
    print(f"Shape: {term_width}x{term_height}")
    
    console = Console(record=True, width=term_width)
    for i in range(0, len(outString)):
        console.print()
        parsed = Text.from_ansi(outString[i])
        console.print(parsed, end="")

    if saving:
        if transparent:
            console.save_svg(save_path, code_format=TIGHT_TRANSPARENT_SVG_FORMAT)
        else:
            console.save_svg(save_path, code_format=TIGHT_SVG_FORMAT)
    
    # sets console back to default
    console.print("\u001b[0m")