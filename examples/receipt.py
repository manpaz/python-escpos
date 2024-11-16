#!/usr/bin/env python3

# Print a fake receipt

import re
import textwrap
from datetime import datetime

from escpos import printer

items = [
    {"sku": 666, "desc": "Dragon Tears", "price": 5.6},
    {"sku": 661, "desc": "Lizard Tongue", "price": 7.77},
    {"sku": 911, "desc": "Bat Wing", "price": 13.7},
    {"sku": 42, "desc": "Towel", "price": 19.99},
]
tax_percent = 0.05
header = {"sku": "SKU", "desc": "Product Description", "price": "Price"}
header_format = "{sku:<6} {desc:<33} {price:<6}"
item_format = "{sku:>06} {desc:<33} {price:>6.2f}"
subtotals_format = "{dummy:6} {desc:>33} {price:>6.2f}"

# As good as time as any
timestamp = datetime(2012, 12, 21, 11, 59, 59)
served_by = "Imruryg the Brave"

address = """57 Dandelion Tower Drive
Glimmerhollow, TQ, 981-PPU
Phone: +1-403-555-2106"""

disclaimer = """For entertainment purposes only.
Do not use for summoning demons and/or conjuration of spirits.
Magick should only be perfomed by trained professionals.
All sales are final. No refunds or exchanges for enchanted items.
Hocus Pocus will not be responsible for any damages, injuries, or
losses that occur while using or misusing these items.
Always check local bylaws and regulations before invoking any spells.
"""

# Font "b" on my TM-P80-clone printer can squeeze 64 characters per line
disclaimer_width = 64

recipt_barcode = "1234567890"


# Justify-text on left AND right sides by padding spaces,
# code by: Georgina Skibinski https://stackoverflow.com/a/66087666
def justify(txt: str, width: int) -> str:
    prev_txt = txt
    while (l := width - len(txt)) > 0:
        txt = re.sub(r"(\s+)", r"\1 ", txt, count=l)
        if txt == prev_txt:
            break
    return txt.rjust(width)


p = printer.Usb(0x04B8, 0x0E20, profile="TM-P80")

# Store Logo at the Top
p.set_with_default()
p.image("hocus-pocus.gif", center=True)

# Print Address, centered
p.ln(1)
p.set_with_default(align="center")
for l in address.split("\n"):
    p.textln(l)
p.ln(1)


# Print date and time
p.set_with_default(align="left")
p.textln(timestamp.strftime("%A, %B %d, %Y   %I:%M%P"))

# Print cashier's name
p.set_with_default(align="right")
p.textln("Served by: " + served_by)

# Add some empty space before itemized list
p.ln(2)


## Add a bit of line spacing for itemized list for easier reading
p.set_with_default()
p.line_spacing(80, 180)

## Itemized list header (bold with underline)
p.set_with_default(bold=True, underline=True)
p.textln(header_format.format(**header))

## Itemized List
p.set_with_default()
for idx, item in enumerate(items):
    txt = item_format.format(**item)
    if idx == len(items) - 1:
        # If this is the last item, add underline
        # to visually "close" the list.
        p.set_with_default(underline=True)
    p.textln(txt)

p.set_with_default()

## Subtotal
subtotal = sum([x["price"] for x in items])
p.textln(subtotals_format.format(dummy="", desc="subtotal", price=subtotal))

## Tax
tax_amount = subtotal * tax_percent
tax_desc = "Guild Tax (%d%%)" % (int(tax_percent * 100.0))
p.textln(subtotals_format.format(dummy="", desc=tax_desc, price=tax_amount))

## Total
## NOTE: because we use double-sized font, alignment won't match
## the previous lines. Instead, with trim leading whitespace,
## and use the printer's built-in right-alignment feature.
p.set_with_default(align="right", custom_size=True, width=2, height=2)
total_amount = subtotal + tax_amount
total_desc = "Total"
total_text_line = subtotals_format.format(dummy="", desc=total_desc, price=total_amount)
total_text_line = total_text_line.strip()
p.textln(total_text_line)

# Add some empty space before disclaimer
p.ln(4)

# preprocess disclaimer text:
# In python it's easy to use multilined strings,
# but to print the disclaimer we want to merge lines
# and condense whitespaces.
txt = disclaimer.replace("\n", " ")
txt = re.sub("  +", " ", txt)
# textwrap.wrap() ensures words are not broken (unlike "escpos.block_text()").
txt = textwrap.wrap(txt, width=disclaimer_width)
# Justify each line
txt = [justify(x, disclaimer_width) for x in txt]
p.set_with_default(font="b")
for l in txt:
    p.textln(l)

# A creature for good luck
p.set_with_default()
p.ln(2)
p.image("creature5.gif", center=True)

p.cut(mode="PART", feed=True)
