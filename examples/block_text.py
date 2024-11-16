#!/usr/bin/env python3

from escpos import printer

txt = """Lorem ipsum dolor sit amet, consectetur adipiscing elit. Nulla pellentesque augue libero. Integer non erat in velit venenatis tristique. Phasellus id ultrices orci. Quisque est ligula, varius vel justo sit amet, laoreet porttitor orci. Nulla commodo porta augue id molestie. Duis tempor eget tellus vel posuere."""

p = printer.Usb(0x04B8, 0x0E20)


for i in [20, 30, 40, 60]:
    p.set_with_default(custom_size=True, width=3, height=3, underline=True)
    p.textln(f"Blk-txt({i} col)")

    p.set_with_default()
    p.block_text(txt, columns=i)
    p.ln(2)


p.ln(4)


p.cut(mode="PART", feed=True)
