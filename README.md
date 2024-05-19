# ASCII Image Generator
Started 2022, Updated 2024

A python script to convert image files into ASCII art displayed to the console.

![Image of ASCII art of a dog][imgFirstImg]

*My dog Tia (... and yes she is wearing a bow tie!)*

## Brief Description
A hobby project born out of my love for art and code. Loving both of these worlds I wanted to put them together. With a few image files, some colourful ASCII escape codes, and some inovative characters. Art can be *drawn* to the console with the hit of the enter key.

Utilizing 28 possible characters to show brightness, and the full 0-255 rgb colour space. Any image can be turned into lines written to the console. 

![Image of ASCII art of Saturno Devorando a Su Hijo](/img/ASCII_Saturno_Devorando_a_Su_Hijo.png)

*Francisco Goya - Saturno Devorando a Su Hijo*

## How It Works

The program produces an artistic output using four main steps:
1. Resize the image: By reducing the image's resolution to match the resolution of the console characters the quality of the image can be retained. I wrote a simple box image resizer to average proximal pixel values into a new resized pixel.
2. For each pixel the grayscale brightness is found and mapped onto the **Character Density Scale**. This allows the brightness of pixels on the image to be translated to the console output via different pixels. Kinda simulating a poor man's HDR.
3. For each pixel in the resized image the ASCII escape code is determined to apply the colour to the character.
4. Finally the determined pixel and its colour escape code is printed to the console.

## The Character Density Scale
The *character density scale* is a 28 character list containing the characters that are the most filled in ('Ñ') to the least filled in ('_')

`Ñ@#W$9876543210?!abc;:+=-,._`
`charDencity = [chr(209), chr(64), chr(35), chr(87), chr(36), chr(57), chr(56), chr(55), chr(54), chr(53), chr(52), chr(51), chr(50), chr(49), chr(48), chr(63), chr(33), chr(97), chr(98), chr(99), chr(59), chr(58), chr(43), chr(61), chr(45), chr(44), chr(46), chr(95)]`

[imgFirstImg]: /img/ASCIIDog.png