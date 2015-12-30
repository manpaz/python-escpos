""" ESC/POS Commands (Constants) """

import binascii as ba

#{ Control characters
# as labelled in http://www.novopos.ch/client/EPSON/TM-T20/TM-T20_eng_qr.pdf
NUL = ba.hexlify(b'\x00')
EOT = ba.hexlify(b'\x04')
ENQ = ba.hexlify(b'\x05')
DLE = ba.hexlify(b'\x10')
DC4 = ba.hexlify(b'\x14')
CAN = ba.hexlify(b'\x18')
ESC = ba.hexlify(b'\x1b')
FS  = ba.hexlify(b'\x1c')
GS  = ba.hexlify(b'\x1d')

#{ Feed control sequences
CTL_LF = ba.hexlify(b'\n')                      # Print and line feed
CTL_FF = ba.hexlify(b'\f')                      # Form feed
CTL_CR = ba.hexlify(b'\r')                      # Carriage return
CTL_HT = ba.hexlify(b'\t')                      # Horizontal tab
CTL_VT = ba.hexlify(b'\v')                      # Vertical tab

#{ Printer hardware
HW_INIT   = ESC + ba.hexlify(b'@')              # Clear data in buffer and reset modes
HW_SELECT = ESC + ba.hexlify(b'=\x01')          # Printer select
HW_RESET  = ESC + ba.hexlify(b'\x3f\x0a\x00')   # Reset printer hardware
                                                # (TODO: Where is this specified?)

#{ Cash Drawer (ESC p <pin> <on time: 2*ms> <off time: 2*ms>)
_CASH_DRAWER = lambda m, t1='', t2='': ESC + ba.hexlify(b'p' + m + chr(t1) + chr(t2))
CD_KICK_2 = _CASH_DRAWER(b'\x00', 50, 50)  # Sends a pulse to pin 2 []
CD_KICK_5 = _CASH_DRAWER(b'\x01', 50, 50)  # Sends a pulse to pin 5 []

#{ Paper Cutter
_CUT_PAPER = lambda m: GS + ba.hexlify(b'V' + m)
PAPER_FULL_CUT = _CUT_PAPER(b'\x00')  # Full cut paper
PAPER_PART_CUT = _CUT_PAPER(b'\x01')  # Partial cut paper

#{ Text format
# TODO: Acquire the "ESC/POS Application Programming Guide for Paper Roll
#       Printers" and tidy up this stuff too.
TXT_NORMAL     = ESC + ba.hexlify(b'!\x00')     # Normal text
TXT_2HEIGHT    = ESC + ba.hexlify(b'!\x10')     # Double height text
TXT_2WIDTH     = ESC + ba.hexlify(b'!\x20')     # Double width text
TXT_4SQUARE    = ESC + ba.hexlify(b'!\x30')     # Quad area text
TXT_UNDERL_OFF = ESC + ba.hexlify(b'\x2d\x00')  # Underline font OFF
TXT_UNDERL_ON  = ESC + ba.hexlify(b'\x2d\x01')  # Underline font 1-dot ON
TXT_UNDERL2_ON = ESC + ba.hexlify(b'\x2d\x02')  # Underline font 2-dot ON
TXT_BOLD_OFF   = ESC + ba.hexlify(b'\x45\x00')  # Bold font OFF
TXT_BOLD_ON    = ESC + ba.hexlify(b'\x45\x01')  # Bold font ON
TXT_FONT_A     = ESC + ba.hexlify(b'\x4d\x00')  # Font type A
TXT_FONT_B     = ESC + ba.hexlify(b'\x4d\x01')  # Font type B
TXT_ALIGN_LT   = ESC + ba.hexlify(b'\x61\x00')  # Left justification
TXT_ALIGN_CT   = ESC + ba.hexlify(b'\x61\x01')  # Centering
TXT_ALIGN_RT   = ESC + ba.hexlify(b'\x61\x02')  # Right justification

#{ Barcode format
_SET_BARCODE_TXT_POS = lambda n: GS + ba.hexlify(b'H' + n)
BARCODE_TXT_OFF = _SET_BARCODE_TXT_POS(b'\x00')  # HRI barcode chars OFF
BARCODE_TXT_ABV = _SET_BARCODE_TXT_POS(b'\x01')  # HRI barcode chars above
BARCODE_TXT_BLW = _SET_BARCODE_TXT_POS(b'\x02')  # HRI barcode chars below
BARCODE_TXT_BTH = _SET_BARCODE_TXT_POS(b'\x03')  # HRI both above and below

_SET_HRI_FONT = lambda n: GS + b'f' + n
BARCODE_FONT_A = _SET_HRI_FONT(b'\x00')  # Font type A for HRI barcode chars
BARCODE_FONT_B = _SET_HRI_FONT(b'\x01')  # Font type B for HRI barcode chars

BARCODE_HEIGHT = GS + ba.hexlify(b'h')  # Barcode Height [1-255]
BARCODE_WIDTH  = GS + ba.hexlify(b'w')  # Barcode Width  [2-6]

#NOTE: This isn't actually an ESC/POS command. It's the common prefix to the
#      two "print bar code" commands:
#      -  "GS k <type as integer> <data> NUL"
#      -  "GS k <type as letter> <data length> <data>"
#      The latter command supports more barcode types
_SET_BARCODE_TYPE = lambda m: GS + ba.hexlify(b'k' + m)
BARCODE_UPC_A  = _SET_BARCODE_TYPE(b'\x00')  # Barcode type UPC-A
BARCODE_UPC_E  = _SET_BARCODE_TYPE(b'\x01')  # Barcode type UPC-E
BARCODE_EAN13  = _SET_BARCODE_TYPE(b'\x02')  # Barcode type EAN13
BARCODE_EAN8   = _SET_BARCODE_TYPE(b'\x03')  # Barcode type EAN8
BARCODE_CODE39 = _SET_BARCODE_TYPE(b'\x04')  # Barcode type CODE39
BARCODE_ITF    = _SET_BARCODE_TYPE(b'\x05')  # Barcode type ITF
BARCODE_NW7    = _SET_BARCODE_TYPE(b'\x06')  # Barcode type NW7

#{ Image format
# NOTE: _PRINT_RASTER_IMG is the obsolete ESC/POS "print raster bit image"
#       command. The constants include a fragment of the data's header.
_PRINT_RASTER_IMG = lambda data: GS + b'v0' + data
S_RASTER_N  = _PRINT_RASTER_IMG(b'\x00')  # Set raster image normal size
S_RASTER_2W = _PRINT_RASTER_IMG(b'\x01')  # Set raster image double width
S_RASTER_2H = _PRINT_RASTER_IMG(b'\x02')  # Set raster image double height
S_RASTER_Q  = _PRINT_RASTER_IMG(b'\x03')  # Set raster image quadruple
