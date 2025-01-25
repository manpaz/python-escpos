""" Example for software_columns: Print text arranged into columns."""

from escpos import printer

p = printer.Dummy(profile="TM-U220")

font = "a"
p.set(font=font)

# Default: Automatic column width given the characters per line of the printer.
text_list = ["col1", "col2", "col3"]
charsxline = p.profile.get_columns(font)
p.software_columns(text_list=text_list, widths=charsxline, align="center")

# Tuning some columns:
text_list = ["col1", "col2", "col3"]
widths = [5, 20]  # col1 = 5 chars width, col2 + col3 = 20 chars width
align = ["left", "center"]  # col1 = left aligned, col2 + col3 = center aligned
p.software_columns(text_list=text_list, widths=widths, align=align)

# Tuning them all:
text_list = ["col1", "col2", "col3"]
widths = [5, 20, 15]
align = ["left", "center", "right"]
p.software_columns(text_list=text_list, widths=widths, align=align)
