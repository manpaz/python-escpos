#!/usr/bin/env python3

# This demo allows testing multiple combination of specific font variations.
# Two lines will be printed for every entry in "variations[]",
# First line showing the entry index and parametes,
# Second line being "Hello World".
#
# Example:
# If a printed line shows:
#   variations[2] =
#   Hello World
#   F=b B U AL=R
# It is the 3rd entry (zero-based index 2),
# with Font="B", Bold, Underline, Align=right.

from escpos import printer

p = printer.Usb(0x04B8, 0x0E20, profile="TM-P80")

p.set_with_default()
p.textln("Default Text")

# Use any combination of parameters allowed in set_with_default()
# See: https://python-escpos.readthedocs.io/en/latest/user/methods.html
variations = [
    {"font": "a", "custom_size": True, "width": 3, "height": 1},
    {"font": "a", "custom_size": True, "width": 1, "height": 2},
    {"font": "a", "bold": True},
    {"font": "a", "custom_size": True, "width": 2, "height": 2},
    {"font": "b", "underline": True},
    {"font": "b", "align": "right", "double_width": True, "double_height": True},
]

for idx, v in enumerate(variations):
    p.set_with_default(**v)

    txt = "variations[%d] =" % idx
    p.textln(txt)

    p.textln("Hello World")

    tags = []
    if v.get("font"):
        tags.append("F=" + v["font"])
    if v.get("align"):
        tags.append("AL=" + v.get("align")[:1])
    if v.get("custom_size"):
        tags.append("CS")
    if "width" in v:
        tags.append("W=" + str(v["width"]))
    if "height" in v:
        tags.append("H=" + str(v["height"]))
    if v.get("bold"):
        tags.append("B")
    if v.get("underline"):
        tags.append("U")
    if v.get("smooth"):
        tags.append("S")
    if v.get("flip"):
        tags.append("F")

    txt = " ".join(tags)
    p.textln(txt)

    p.ln(1)

p.cut(mode="PART", feed=True)
