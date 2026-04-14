import numpy as np
from PIL import Image
import sys

# window sizes for resultant image in characters
width = 240
height = 135
charDensityOriginal = ['Ñ', '@', '#', 'W', '$', '9', '8', '7', '6', '5', '4', '3', '2', '1', '0', '?', '!', 'a', 'b', 'c', ';', ':', '+', '=', '-', ',', '.', '_']

# Punctuation only
charDensity = ['@', '#', '&', '%', '$', '8', '?', '*', '+', '=', ';', ':', '~', '-', ',', '.', '`', ' ']

charDensityPunct = ['@', '#', '&', '%', '$', '?', '!', '*', '+', '=', '/', '\\', '|', '(', ')', '[', ']', '<', '>', ';', ':', '"', "'", '~', '^', '-', ',', '.', '`', ' ']

# Numbers only (0-9)
charDensityNums = ['8', '0', '9', '6', '5', '3', '2', '4', '7', '1', ' ']

# Letters only (mix of cases, ordered by visual density)
charDensityLetters = ['M', 'W', 'N', 'Q', 'B', 'H', 'R', 'D', 'K', 'A', 'G', 'O', 'U', 'P', 'X', 'E', 'Z', 'S', 'Y', 'F', 'T', 'C', 'L', 'J', 'I', 'o', 'e', 'a', 'c', 'v', 'n', 'r', 's', 'x', 'z', 'i', 'l', 't', ';', ':', ',', '.', ' ']

charDensityLettersPure = ['M', 'W', 'N', 'Q', 'B', 'H', 'R', 'D', 'K', 'A', 'G', 'O', 'U', 'P', 'X', 'E', 'Z', 'S', 'Y', 'F', 'T', 'C', 'L', 'J', 'I', 'o', 'e', 'a', 'c', 'u', 'v', 'n', 'r', 's', 'x', 'z', 'i', 'l', 'j']

# Lowercase only
charDensityLower = ['m', 'w', 'q', 'b', 'h', 'd', 'k', 'a', 'o', 'g', 'p', 'e', 'u', 'n', 'r', 'c', 's', 'v', 'x', 'z', 'y', 'f', 't', 'j', 'i', 'l']

# Uppercase only
charDensityUpper = ['M', 'W', 'N', 'Q', 'B', 'H', 'R', 'D', 'K', 'A', 'G', 'O', 'U', 'P', 'X', 'E', 'Z', 'S', 'Y', 'F', 'T', 'C', 'L', 'J', 'I']

# Weird / extended ASCII & Unicode — block and shading characters
charDensityBlocks = ['█', '▓', '▒', '░', '▚', '▞', '▙', '▟', '▜', '▛', '▀', '▄', '▐', '▌', '■', '□', '▪', '▫', '·', ' ']

# Braille (each dot pattern has different density — really cool results)
charDensityBraille = ['⣿', '⣾', '⣽', '⣻', '⢿', '⡿', '⣷', '⣯', '⣟', '⣞', '⣝', '⣛', '⣚', '⣙', '⣘', '⣗', '⣖', '⣕', '⣔', '⣓', '⣒', '⣑', '⣐', '⣏', '⣎', '⣍', '⣌', '⣋', '⣊', '⣉', '⣈', '⡇', '⠿', '⠾', '⠽', '⠼', '⠻', '⠺', '⠹', '⠸', '⠷', '⠶', '⠵', '⠴', '⠳', '⠲', '⠱', '⠰', '⠯', '⠮', '⠭', '⠬', '⠫', '⠪', '⠩', '⠨', '⠧', '⠦', '⠥', '⠤', '⠣', '⠢', '⠡', '⠠', '⠟', '⠞', '⠝', '⠜', '⠛', '⠚', '⠙', '⠘', '⠗', '⠖', '⠕', '⠔', '⠓', '⠒', '⠑', '⠐', '⠏', '⠎', '⠍', '⠌', '⠋', '⠊', '⠉', '⠈', '⠇', '⠆', '⠅', '⠄', '⠃', '⠂', '⠁', '⠀']

# Math / symbols — chaotic but fun
charDensityMath = ['∰', '∯', '∮', '∑', '∏', '∆', '∇', '∞', '≈', '≡', '≠', '±', '∓', '×', '÷', '√', '∝', '∂', '∫', '∈', '∋', '∪', '⊆', '⊇',  '∩', '⊂', '⊃', '∧', '∨', '¬', '→', '←', '↑', '↓', '·', '∘', '°', ' ']

# Emoji-ish / geometric shapes
charDensityShapes = ['█', '●', '◉', '◆', '◼', '■', '▲', '▼', '◀', '▶', '◈', '◇', '◊', '○', '◌', '◯', '△', '▽', '◁', '▷', '·', '˙', ' ']

# Currency
charDensityCurrency = ['₩', '₿', '﷼', '₪', '€', '£', '¥', '$', '₽', '₹', '₺', '₱', '₴', '₦', '₡', '₵', '¢', ' ']

# Arrows
charDensityArrows = ['⇚', '⇛', '⇐', '⇒', '⇑', '⇓', '⇔', '⇕', '←', '→', '↑', '↓', '↔', '↕', '↖', '↗', '↘', '↙', '↞', '↠', '↢', '↣', '⇠', '⇢', '⤂', '⤃', '·', ' ']

# ASCII art classic (Paul Bourke's well-known 70-char ramp — the "correct" one)
charDensityBourke = list('$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,"^`\'. ')

# Minimal 10-step ramp (classic, low-detail but clean)
charDensityMinimal = ['@', '%', '#', '*', '+', '=', '-', ':', '.', ' ']


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
    if len(sys.argv) > 1:
        path = sys.argv[1]
        lines = int(sys.argv[2])
    else:
        path = GetPath()
        lines = 0
        try:
            lines = int(input("What should the result image height be (whole number): "))
        except ValueError:
            print("Error in reading width using default")
            lines = 70
    outString, term_height, term_width = ASCIIifyImage(path, lines, gamma_y=1, charDensityMap=charDensityBourke[:40])
    print(f"Shape: {term_width}x{term_height}")
    for i in range(0, len(outString)):
        print()
        print(outString[i], end="")
    # sets console back to default
    print("\u001b[0m")