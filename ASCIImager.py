import math
import numpy as np
from PIL import Image

# window sizes for resultant image in characters
width = 240
height = 135
charDencity = [
    chr(209),
    chr(64),
    chr(35),
    chr(87),
    chr(36),
    chr(57),
    chr(56),
    chr(55),
    chr(54),
    chr(53),
    chr(52),
    chr(51),
    chr(50),
    chr(49),
    chr(48),
    chr(63),
    chr(33),
    chr(97),
    chr(98),
    chr(99),
    chr(59),
    chr(58),
    chr(43),
    chr(61),
    chr(45),
    chr(44),
    chr(46),
    chr(95),
]


def ColourToAscii(r, g, b):
    """Returns the ASCII escape code for setting text colour to the specified RGB"""
    setForeground = "\u001b[38;2;"
    retString = setForeground + str(r) + ";" + str(g) + ";" + str(b) + "m"
    return retString


def ColourToBrightness(r, g, b):
    """Finds the grayscale value of the colour and returns a char corresponding to that"""
    ave = (r + g + b) / 3.0
    dencityPercent = ave / 255.0
    charIndex = round(dencityPercent * len(charDencity))
    char = charDencity[-charIndex]
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


def PrintImage(path, height):
    """
    Uses the provided path to parse an image file. Then it's scaled it to fit better in the console.
    Finally the scaled image is converted to ascii characters and escape codes are used to colour it.

    :param path: (String) The path to the image file
    :param height: (int) height of result image in # of chars
    :return: A list of strings, each element is a line of the image
    """

    # print(len(imgArr))
    # print(len(imgArr[0]))

    # open image and convert to 3d array
    image = Image.open(path)
    imgArr = np.asarray(image)

    # set result image
    scaleFactor = round(len(imgArr) / height)
    resizeWidth = int(len(imgArr) / scaleFactor)
    resizeHeight = int(len(imgArr[0]) / scaleFactor)
    resizeImg = []

    for x in range(0, resizeWidth):
        resizeImg.append([])  # row
        for y in range(0, resizeHeight):
            resizeImg[x].append([])  # another array for r green and blue
            for rgb in range(0, 3):
                resizeImg[x][y].append(0)  # set rgb to 0

    # find the average colour of the area that is scaled down
    for x in range(0, len(resizeImg)):
        for y in range(0, len(resizeImg[x])):
            rAve = 0
            gAve = 0
            bAve = 0
            for i in range(0, scaleFactor):
                for j in range(0, scaleFactor):
                    rAve += imgArr[(x * scaleFactor) + i][(y * scaleFactor) + j][0]
                    gAve += imgArr[(x * scaleFactor) + i][(y * scaleFactor) + j][1]
                    bAve += imgArr[(x * scaleFactor) + i][(y * scaleFactor) + j][2]
            rAve = rAve / (scaleFactor * scaleFactor)
            gAve = gAve / (scaleFactor * scaleFactor)
            bAve = bAve / (scaleFactor * scaleFactor)
            resizeImg[x][y][0] = int(rAve)
            resizeImg[x][y][1] = int(gAve)
            resizeImg[x][y][2] = int(bAve)

    line = ""
    lines = []
    for x in range(0, len(resizeImg)):
        for y in range(0, len(resizeImg[x])):
            # set the colour of the char pixel
            charPixel = ColourToAscii(
                resizeImg[x][y][0], resizeImg[x][y][1], resizeImg[x][y][2]
            )
            # add the actual character that is going to be coloured
            charPixel += 2 * ColourToBrightness(
                resizeImg[x][y][0], resizeImg[x][y][1], resizeImg[x][y][2]
            )
            # adding it twice because text is taller than it is wide
            line += charPixel
        lines.append("" + line)
        line = ""

    print("\u001b[0m")
    return lines


if __name__ == "__main__":
    for c in charDencity:
        print(c, end="")
    print()
    path = GetPath()
    scale = 0
    try:
        scale = int(input("What should the result image height be (whole number): "))
    except ValueError:
        print("Error in reading width using default")
        scale = 70
    outString = PrintImage(path, scale)
    for i in range(0, len(outString)):
        print(outString[i])
    # sets console back to default
    print("\u001b[0m")
