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
            charPixel = ColourToAscii(r, g, b)
            # add the actual character that is going to be coloured
            # adding it twice because text is taller than it is wide
            charPixel += 2 * ColourToBrightness(r, g, b)
            line += charPixel
        lines.append("" + line)
        line = ""

    print("\u001b[0m")
    return lines


if __name__ == "__main__":
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