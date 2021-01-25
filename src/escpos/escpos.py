#!/usr/bin/python
#  -*- coding: utf-8 -*-
""" Main class

This module contains the abstract base class :py:class:`Escpos`.

:author: `Manuel F Martinez <manpaz@bashlinux.com>`_ and others
:organization: Bashlinux and `python-escpos <https://github.com/python-escpos>`_
:copyright: Copyright (c) 2012-2017 Bashlinux and python-escpos
:license: MIT
"""


import qrcode
import textwrap
import six
import time
from re import match as re_match

import barcode
from barcode.writer import ImageWriter

import os

from .constants import ESC, GS, NUL, QR_ECLEVEL_L, QR_ECLEVEL_M, QR_ECLEVEL_H, QR_ECLEVEL_Q
from .constants import QR_MODEL_1, QR_MODEL_2, QR_MICRO, BARCODE_TYPES, BARCODE_HEIGHT, BARCODE_WIDTH
from .constants import BARCODE_FONT_A, BARCODE_FONT_B, BARCODE_FORMATS
from .constants import BARCODE_TXT_OFF, BARCODE_TXT_BTH, BARCODE_TXT_ABV, BARCODE_TXT_BLW
from .constants import TXT_SIZE, TXT_NORMAL
from .constants import SET_FONT
from .constants import LINESPACING_FUNCS, LINESPACING_RESET
from .constants import LINE_DISPLAY_OPEN, LINE_DISPLAY_CLEAR, LINE_DISPLAY_CLOSE
from .constants import CD_KICK_DEC_SEQUENCE, CD_KICK_5, CD_KICK_2, PAPER_FULL_CUT, PAPER_PART_CUT
from .constants import HW_RESET, HW_SELECT, HW_INIT
from .constants import CTL_VT, CTL_CR, CTL_FF, CTL_LF, CTL_SET_HT, PANEL_BUTTON_OFF, PANEL_BUTTON_ON
from .constants import TXT_STYLE
from .constants import RT_STATUS_ONLINE, RT_MASK_ONLINE
from .constants import RT_STATUS_PAPER, RT_MASK_PAPER, RT_MASK_LOWPAPER, RT_MASK_NOPAPER

from .exceptions import BarcodeTypeError, BarcodeSizeError, TabPosError
from .exceptions import CashDrawerError, SetVariableError, BarcodeCodeError
from .exceptions import ImageWidthError

from .magicencode import MagicEncode

from abc import ABCMeta, abstractmethod  # abstract base class support
from escpos.image import EscposImage
from escpos.capabilities import get_profile, BARCODE_B


@six.add_metaclass(ABCMeta)
class Escpos(object):
    """ ESC/POS Printer object

    This class is the abstract base class for an esc/pos-printer. The printer implementations are children of this
    class.
    """
    device = None

    def __init__(self, profile=None, magic_encode_args=None, **kwargs):
        """ Initialize ESCPOS Printer

        :param profile: Printer profile"""
        self.profile = get_profile(profile)
        self.magic = MagicEncode(self, **(magic_encode_args or {}))

    def __del__(self):
        """ call self.close upon deletion """
        self.close()

    @abstractmethod
    def _raw(self, msg):
        """ Sends raw data to the printer

        This function has to be individually implemented by the implementations.

        :param msg: message string to be sent to the printer
        :type msg: bytes
        """
        pass

    def _read(self):
        """ Returns a NotImplementedError if the instance of the class doesn't override this method.
        :raises NotImplementedError
        """
        raise NotImplementedError()

    def image(self, img_source, high_density_vertical=True, high_density_horizontal=True, impl="bitImageRaster",
              fragment_height=960, center=False):
        """ Print an image

        You can select whether the printer should print in high density or not. The default value is high density.
        When printing in low density, the image will be stretched.

        Esc/Pos supplies several commands for printing. This function supports three of them. Please try to vary the
        implementations if you have any problems. For example the printer `IT80-002` will have trouble aligning
        images that are not printed in Column-mode.

        The available printing implementations are:

            * `bitImageRaster`: prints with the `GS v 0`-command
            * `graphics`: prints with the `GS ( L`-command
            * `bitImageColumn`: prints with the `ESC *`-command

        When trying to center an image make sure you have initialized the printer with a valid profile, that
        contains a media width pixel field. Otherwise the centering will have no effect.

        :param img_source: PIL image or filename to load: `jpg`, `gif`, `png` or `bmp`
        :param high_density_vertical: print in high density in vertical direction *default:* True
        :param high_density_horizontal: print in high density in horizontal direction *default:* True
        :param impl: choose image printing mode between `bitImageRaster`, `graphics` or `bitImageColumn`
        :param fragment_height: Images larger than this will be split into multiple fragments *default:* 960
        :param center: Center image horizontally *default:* False

        """
        im = EscposImage(img_source)

        try:
            if self.profile.profile_data['media']['width']['pixels'] == "Unknown":
                print("The media.width.pixel field of the printer profile is not set. " +
                      "The center flag will have no effect.")

            max_width = int(self.profile.profile_data['media']['width']['pixels'])

            if im.width > max_width:
                raise ImageWidthError('{} > {}'.format(im.width, max_width))

            if center:
                im.center(max_width)
        except KeyError:
            # If the printer's pixel width is not known, print anyways...
            pass
        except ValueError:
            # If the max_width cannot be converted to an int, print anyways...
            pass

        if im.height > fragment_height:
            fragments = im.split(fragment_height)
            for fragment in fragments:
                self.image(fragment,
                           high_density_vertical=high_density_vertical,
                           high_density_horizontal=high_density_horizontal,
                           impl=impl,
                           fragment_height=fragment_height)
            return

        if impl == "bitImageRaster":
            # GS v 0, raster format bit image
            density_byte = (0 if high_density_horizontal else 1) + (0 if high_density_vertical else 2)
            header = GS + b"v0" + six.int2byte(density_byte) + self._int_low_high(im.width_bytes, 2) +\
                self._int_low_high(im.height, 2)
            self._raw(header + im.to_raster_format())

        if impl == "graphics":
            # GS ( L raster format graphics
            img_header = self._int_low_high(im.width, 2) + self._int_low_high(im.height, 2)
            tone = b'0'
            colors = b'1'
            ym = six.int2byte(1 if high_density_vertical else 2)
            xm = six.int2byte(1 if high_density_horizontal else 2)
            header = tone + xm + ym + colors + img_header
            raster_data = im.to_raster_format()
            self._image_send_graphics_data(b'0', b'p', header + raster_data)
            self._image_send_graphics_data(b'0', b'2', b'')

        if impl == "bitImageColumn":
            # ESC *, column format bit image
            density_byte = (1 if high_density_horizontal else 0) + (32 if high_density_vertical else 0)
            header = ESC + b"*" + six.int2byte(density_byte) + self._int_low_high(im.width, 2)
            outp = [ESC + b"3" + six.int2byte(16)]  # Adjust line-feed size
            for blob in im.to_column_format(high_density_vertical):
                outp.append(header + blob + b"\n")
            outp.append(ESC + b"2")  # Reset line-feed size
            self._raw(b''.join(outp))

    def _image_send_graphics_data(self, m, fn, data):
        """
        Wrapper for GS ( L, to calculate and send correct data length.

        :param m: Modifier//variant for function. Usually '0'
        :param fn: Function number to use, as byte
        :param data: Data to send
        """
        header = self._int_low_high(len(data) + 2, 2)
        self._raw(GS + b'(L' + header + m + fn + data)

    def qr(self, content, ec=QR_ECLEVEL_L, size=3, model=QR_MODEL_2,
           native=False, center=False, impl="bitImageRaster"):
        """ Print QR Code for the provided string

        :param content: The content of the code. Numeric data will be more efficiently compacted.
        :param ec: Error-correction level to use. One of QR_ECLEVEL_L (default), QR_ECLEVEL_M, QR_ECLEVEL_Q or
            QR_ECLEVEL_H.
            Higher error correction results in a less compact code.
        :param size: Pixel size to use. Must be 1-16 (default 3)
        :param model: QR code model to use. Must be one of QR_MODEL_1, QR_MODEL_2 (default) or QR_MICRO (not supported
            by all printers).
        :param native: True to render the code on the printer, False to render the code as an image and send it to the
            printer (Default)
        :param center: Centers the code *default:* False
        :param impl: Image-printing-implementation, refer to :meth:`.image()` for details
        """
        # Basic validation
        if ec not in [QR_ECLEVEL_L, QR_ECLEVEL_M, QR_ECLEVEL_H, QR_ECLEVEL_Q]:
            raise ValueError("Invalid error correction level")
        if not 1 <= size <= 16:
            raise ValueError("Invalid block size (must be 1-16)")
        if model not in [QR_MODEL_1, QR_MODEL_2, QR_MICRO]:
            raise ValueError("Invalid QR model (must be one of QR_MODEL_1, QR_MODEL_2, QR_MICRO)")
        if content == "":
            # Handle edge case by printing nothing.
            return
        if not native:
            # Map ESC/POS error correction levels to python 'qrcode' library constant and render to an image
            if model != QR_MODEL_2:
                raise ValueError("Invalid QR model for qrlib rendering (must be QR_MODEL_2)")
            python_qr_ec = {
                QR_ECLEVEL_H: qrcode.constants.ERROR_CORRECT_H,
                QR_ECLEVEL_L: qrcode.constants.ERROR_CORRECT_L,
                QR_ECLEVEL_M: qrcode.constants.ERROR_CORRECT_M,
                QR_ECLEVEL_Q: qrcode.constants.ERROR_CORRECT_Q
            }
            qr_code = qrcode.QRCode(version=None, box_size=size, border=1, error_correction=python_qr_ec[ec])
            qr_code.add_data(content)
            qr_code.make(fit=True)
            qr_img = qr_code.make_image()
            im = qr_img._img.convert("RGB")

            # Convert the RGB image in printable image
            self.text('\n')
            self.image(im, center=center, impl=impl)
            self.text('\n')
            self.text('\n')
            return

        if center:
            raise NotImplementedError("Centering not implemented for native QR rendering")

        # Native 2D code printing
        cn = b'1'  # Code type for QR code
        # Select model: 1, 2 or micro.
        self._send_2d_code_data(six.int2byte(65), cn, six.int2byte(48 + model) + six.int2byte(0))
        # Set dot size.
        self._send_2d_code_data(six.int2byte(67), cn, six.int2byte(size))
        # Set error correction level: L, M, Q, or H
        self._send_2d_code_data(six.int2byte(69), cn, six.int2byte(48 + ec))
        # Send content & print
        self._send_2d_code_data(six.int2byte(80), cn, content.encode('utf-8'), b'0')
        self._send_2d_code_data(six.int2byte(81), cn, b'', b'0')

    def _send_2d_code_data(self, fn, cn, data, m=b''):
        """ Wrapper for GS ( k, to calculate and send correct data length.

        :param fn: Function to use.
        :param cn: Output code type. Affects available data.
        :param data: Data to send.
        :param m: Modifier/variant for function. Often '0' where used.
        """
        if len(m) > 1 or len(cn) != 1 or len(fn) != 1:
            raise ValueError("cn and fn must be one byte each.")
        header = self._int_low_high(len(data) + len(m) + 2, 2)
        self._raw(GS + b'(k' + header + cn + fn + m + data)

    @staticmethod
    def _int_low_high(inp_number, out_bytes):
        """ Generate multiple bytes for a number: In lower and higher parts, or more parts as needed.

        :param inp_number: Input number
        :param out_bytes: The number of bytes to output (1 - 4).
        """
        max_input = (256 << (out_bytes * 8) - 1)
        if not 1 <= out_bytes <= 4:
            raise ValueError("Can only output 1-4 bytes")
        if not 0 <= inp_number <= max_input:
            raise ValueError("Number too large. Can only output up to {0} in {1} bytes".format(max_input, out_bytes))
        outp = b''
        for _ in range(0, out_bytes):
            outp += six.int2byte(inp_number % 256)
            inp_number //= 256
        return outp

    def charcode(self, code="AUTO"):
        """ Set Character Code Table

        Sets the control sequence from ``CHARCODE`` in :py:mod:`escpos.constants` as active. It will be sent with
        the next text sequence. If you set the variable code to ``AUTO`` it will try to automatically guess the
        right codepage. (This is the standard behaviour.)

        :param code: Name of CharCode
        :raises: :py:exc:`~escpos.exceptions.CharCodeError`
        """
        if code.upper() == "AUTO":
            self.magic.force_encoding(False)
        else:
            self.magic.force_encoding(code)

    @staticmethod
    def check_barcode(bc, code):
        """
        This method checks if the barcode is in the proper format.
        The validation concerns the barcode length and the set of characters, but won't compute/validate any checksum.
        The full set of requirement for each barcode type is available in the ESC/POS documentation.

        As an example, using EAN13, the barcode `12345678901` will be correct, because it can be rendered by the
        printer. But it does not suit the EAN13 standard, because the checksum digit is missing. Adding a wrong
        checksum in the end will also be considered correct, but adding a letter won't (EAN13 is numeric only).

        .. todo:: Add a method to compute the checksum for the different standards

        .. todo:: For fixed-length standards with mandatory checksum (EAN, UPC),
            compute and add the checksum automatically if missing.

        :param bc: barcode format, see :py:meth:`.barcode()`
        :param code: alphanumeric data to be printed as bar code, see :py:meth:`.barcode()`
        :return: bool
        """
        if bc not in BARCODE_FORMATS:
            return False

        bounds, regex = BARCODE_FORMATS[bc]
        return any(bound[0] <= len(code) <= bound[1] for bound in bounds) and re_match(regex, code)

    def barcode(self, code, bc, height=64, width=3, pos="BELOW", font="A",
                align_ct=True, function_type=None, check=True):
        """ Print Barcode

        This method allows to print barcodes. The rendering of the barcode is done by the printer and therefore has to
        be supported by the unit. By default, this method will check whether your barcode text is correct, that is
        the characters and lengths are supported by ESCPOS. Call the method with `check=False` to disable the check, but
        note that uncorrect barcodes may lead to unexpected printer behaviour.
        There are two forms of the barcode function. Type A is default but has fewer barcodes,
        while type B has some more to choose from.

        Use the parameters `height` and `width` for adjusting of the barcode size. Please take notice that the barcode
        will not be printed if it is outside of the printable area. (Which should be impossible with this method, so
        this information is probably more useful for debugging purposes.)

        .. todo:: On TM-T88II width from 1 to 6 is accepted. Try to acquire command reference and correct the code.
        .. todo:: Supplying pos does not have an effect for every barcode type. Check and document for which types this
                  is true.

        If you do not want to center the barcode you can call the method with `align_ct=False`, which will disable
        automatic centering. Please note that when you use center alignment, then the alignment of text will be changed
        automatically to centered. You have to manually restore the alignment if necessary.

        .. todo:: If further barcode-types are needed they could be rendered transparently as an image. (This could also
                  be of help if the printer does not support types that others do.)

        :param code: alphanumeric data to be printed as bar code
        :param bc: barcode format, possible values are for type A are:

            * UPC-A
            * UPC-E
            * EAN13
            * EAN8
            * CODE39
            * ITF
            * NW7

            Possible values for type B:

            * All types from function type A
            * CODE93
            * CODE128
            * GS1-128
            * GS1 DataBar Omnidirectional
            * GS1 DataBar Truncated
            * GS1 DataBar Limited
            * GS1 DataBar Expanded

            If none is specified, the method raises :py:exc:`~escpos.exceptions.BarcodeTypeError`.
        :param height: barcode height, has to be between 1 and 255
            *default*: 64
        :type height: int
        :param width: barcode width, has to be between 2 and 6
            *default*: 3
        :type width: int
        :param pos: where to place the text relative to the barcode, *default*: BELOW

            * ABOVE
            * BELOW
            * BOTH
            * OFF

        :param font: select font (see ESC/POS-documentation, the device often has two fonts), *default*: A

            * A
            * B

        :param align_ct: If this parameter is True the barcode will be centered. Otherwise no alignment command will be
                         issued.
        :type align_ct: bool

        :param function_type: Choose between ESCPOS function type A or B,
            depending on printer support and desired barcode. If not given,
            the printer will attempt to automatically choose the correct
            function based on the current profile.
            *default*: A

        :param check: If this parameter is True, the barcode format will be checked to ensure it meets the bc
            requirements as definged in the ESC/POS documentation. See :py:meth:`.check_barcode()`
            for more information. *default*: True.

        :raises: :py:exc:`~escpos.exceptions.BarcodeSizeError`,
                 :py:exc:`~escpos.exceptions.BarcodeTypeError`,
                 :py:exc:`~escpos.exceptions.BarcodeCodeError`
        """
        if function_type is None:
            # Choose the function type automatically.
            if bc in BARCODE_TYPES['A']:
                function_type = 'A'
            else:
                if bc in BARCODE_TYPES['B']:
                    if not self.profile.supports(BARCODE_B):
                        raise BarcodeTypeError((
                            "Barcode type '{bc} not supported for "
                            "the current printer profile").format(bc=bc))
                    function_type = 'B'
                else:
                    raise BarcodeTypeError((
                        "Barcode type '{bc} is not valid").format(bc=bc))

        bc_types = BARCODE_TYPES[function_type.upper()]
        if bc.upper() not in bc_types.keys():
            raise BarcodeTypeError((
                "Barcode '{bc}' not valid for barcode function type "
                "{function_type}").format(
                    bc=bc,
                    function_type=function_type,
                ))

        if check and not self.check_barcode(bc, code):
            raise BarcodeCodeError((
                "Barcode '{code}' not in a valid format for type '{bc}'").format(
                code=code,
                bc=bc,
            ))

        # Align Bar Code()
        if align_ct:
            self._raw(TXT_STYLE['align']['center'])
        # Height
        if 1 <= height <= 255:
            self._raw(BARCODE_HEIGHT + six.int2byte(height))
        else:
            raise BarcodeSizeError("height = {height}".format(height=height))
        # Width
        if 2 <= width <= 6:
            self._raw(BARCODE_WIDTH + six.int2byte(width))
        else:
            raise BarcodeSizeError("width = {width}".format(width=width))
        # Font
        if font.upper() == "B":
            self._raw(BARCODE_FONT_B)
        else:  # DEFAULT FONT: A
            self._raw(BARCODE_FONT_A)
        # Position
        if pos.upper() == "OFF":
            self._raw(BARCODE_TXT_OFF)
        elif pos.upper() == "BOTH":
            self._raw(BARCODE_TXT_BTH)
        elif pos.upper() == "ABOVE":
            self._raw(BARCODE_TXT_ABV)
        else:  # DEFAULT POSITION: BELOW
            self._raw(BARCODE_TXT_BLW)

        self._raw(bc_types[bc.upper()])

        if function_type.upper() == "B":
            self._raw(six.int2byte(len(code)))

        # Print Code
        if code:
            self._raw(code.encode())
        else:
            raise BarcodeCodeError()

        if function_type.upper() == "A":
            self._raw(NUL)

    def soft_barcode(self, barcode_type, data, impl='bitImageColumn',
                     module_height=5, module_width=0.2, text_distance=1,
                     center=True):

        image_writer = ImageWriter()

        # Check if barcode type exists
        if barcode_type not in barcode.PROVIDED_BARCODES:
            raise BarcodeTypeError(
                'Barcode type {} not supported by software barcode renderer'
                .format(barcode_type))

        # Render the barcode to a fake file
        barcode_class = barcode.get_barcode_class(barcode_type)
        my_code = barcode_class(data, writer=image_writer)

        with open(os.devnull, "wb") as nullfile:
            my_code.write(nullfile, {
                'module_height': module_height,
                'module_width': module_width,
                'text_distance': text_distance
            })

        # Retrieve the Pillow image and print it
        image = my_code.writer._image
        self.image(image, impl=impl, center=center)

    def text(self, txt):
        """ Print alpha-numeric text

        The text has to be encoded in the currently selected codepage.
        The input text has to be encoded in unicode.

        :param txt: text to be printed
        :raises: :py:exc:`~escpos.exceptions.TextError`
        """
        txt = six.text_type(txt)
        self.magic.write(txt)

    def textln(self, txt=''):
        """Print alpha-numeric text with a newline

        The text has to be encoded in the currently selected codepage.
        The input text has to be encoded in unicode.

        :param txt: text to be printed with a newline
        :raises: :py:exc:`~escpos.exceptions.TextError`
        """
        self.text('{}\n'.format(txt))

    def ln(self, count=1):
        """Print a newline or more

        :param count: number of newlines to print
        :raises: :py:exc:`ValueError` if count < 0
        """
        if count < 0:
            raise ValueError('Count cannot be lesser than 0')
        if count > 0:
            self.text('\n' * count)

    def block_text(self, txt, font="0", columns=None):
        """ Text is printed wrapped to specified columns

        Text has to be encoded in unicode.

        :param txt: text to be printed
        :param font: font to be used, can be :code:`a` or :code:`b`
        :param columns: amount of columns
        :return: None
        """
        col_count = self.profile.get_columns(font) if columns is None else columns
        self.text(textwrap.fill(txt, col_count))

    def set(self, align='left', font='a', bold=False, underline=0, width=1,
            height=1, density=9, invert=False, smooth=False, flip=False,
            double_width=False, double_height=False, custom_size=False):
        """ Set text properties by sending them to the printer

        :param align: horizontal position for text, possible values are:

            * 'center'
            * 'left'
            * 'right'

            *default*: 'left'

        :param font: font given as an index, a name, or one of the
            special values 'a' or 'b', referring to fonts 0 and 1.
        :param bold: text in bold, *default*: False
        :param underline: underline mode for text, decimal range 0-2,  *default*: 0
        :param double_height: doubles the height of the text
        :param double_width: doubles the width of the text
        :param custom_size: uses custom size specified by width and height
            parameters. Cannot be used with double_width or double_height.
        :param width: text width multiplier when custom_size is used, decimal range 1-8,  *default*: 1
        :param height: text height multiplier when custom_size is used, decimal range 1-8, *default*: 1
        :param density: print density, value from 0-8, if something else is supplied the density remains unchanged
        :param invert: True enables white on black printing, *default*: False
        :param smooth: True enables text smoothing. Effective on 4x4 size text and larger, *default*: False
        :param flip: True enables upside-down printing, *default*: False

        :type font: str
        :type invert: bool
        :type bold: bool
        :type underline: bool
        :type smooth: bool
        :type flip: bool
        :type custom_size: bool
        :type double_width: bool
        :type double_height: bool
        :type align: str
        :type width: int
        :type height: int
        :type density: int
        """

        if custom_size:
            if 1 <= width <= 8 and 1 <= height <= 8 and isinstance(width, int) and\
              isinstance(height, int):
                size_byte = TXT_STYLE['width'][width] + TXT_STYLE['height'][height]
                self._raw(TXT_SIZE + six.int2byte(size_byte))
            else:
                raise SetVariableError()
        else:
            self._raw(TXT_NORMAL)
            if double_width and double_height:
                self._raw(TXT_STYLE['size']['2x'])
            elif double_width:
                self._raw(TXT_STYLE['size']['2w'])
            elif double_height:
                self._raw(TXT_STYLE['size']['2h'])
            else:
                self._raw(TXT_STYLE['size']['normal'])

        self._raw(TXT_STYLE['flip'][flip])
        self._raw(TXT_STYLE['smooth'][smooth])
        self._raw(TXT_STYLE['bold'][bold])
        self._raw(TXT_STYLE['underline'][underline])
        self._raw(SET_FONT(six.int2byte(self.profile.get_font(font))))
        self._raw(TXT_STYLE['align'][align])

        if density != 9:
            self._raw(TXT_STYLE['density'][density])

        self._raw(TXT_STYLE['invert'][invert])

    def line_spacing(self, spacing=None, divisor=180):
        """ Set line character spacing.

        If no spacing is given, we reset it to the default.

        There are different commands for setting the line spacing, using
        a different denominator:

        '+'' line_spacing/360 of an inch, 0 <= line_spacing <= 255
        '3' line_spacing/180 of an inch, 0 <= line_spacing <= 255
        'A' line_spacing/60 of an inch, 0 <= line_spacing <= 85

        Some printers may not support all of them. The most commonly
        available command (using a divisor of 180) is chosen.
        """
        if spacing is None:
            self._raw(LINESPACING_RESET)
            return

        if divisor not in LINESPACING_FUNCS:
            raise ValueError("divisor must be either 360, 180 or 60")
        if (divisor in [360, 180]
                and (not(0 <= spacing <= 255))):
            raise ValueError("spacing must be a int between 0 and 255 when divisor is 360 or 180")
        if divisor == 60 and (not(0 <= spacing <= 85)):
            raise ValueError("spacing must be a int between 0 and 85 when divisor is 60")

        self._raw(LINESPACING_FUNCS[divisor] + six.int2byte(spacing))

    def cut(self, mode='FULL', feed=True):
        """ Cut paper.

        Without any arguments the paper will be cut completely. With 'mode=PART' a partial cut will
        be attempted. Note however, that not all models can do a partial cut. See the documentation of
        your printer for details.

        :param mode: set to 'PART' for a partial cut. default: 'FULL'
        :param feed: print and feed before cutting. default: true
        :raises ValueError: if mode not in ('FULL', 'PART')
        """

        if not feed:
            self._raw(GS + b'V' + six.int2byte(66) + b'\x00')
            return

        self.print_and_feed(6)

        mode = mode.upper()
        if mode not in ('FULL', 'PART'):
            raise ValueError("Mode must be one of ('FULL', 'PART')")

        if mode == "PART":
            if self.profile.supports('paperPartCut'):
                self._raw(PAPER_PART_CUT)
            elif self.profile.supports('paperFullCut'):
                self._raw(PAPER_FULL_CUT)
        elif mode == "FULL":
            if self.profile.supports('paperFullCut'):
                self._raw(PAPER_FULL_CUT)
            elif self.profile.supports('paperPartCut'):
                self._raw(PAPER_PART_CUT)

    def cashdraw(self, pin):
        """ Send pulse to kick the cash drawer

        Kick cash drawer on pin 2 or pin 5 according to default parameter.
        For non default parameter send a decimal sequence i.e. [27,112,48] or [27,112,0,25,255]

        :param pin: pin number, 2 or 5 or list of decimals
        :raises: :py:exc:`~escpos.exceptions.CashDrawerError`
        """
        if pin == 2:
            self._raw(CD_KICK_2)
        elif pin == 5:
            self._raw(CD_KICK_5)
        else:
            try:
                self._raw(CD_KICK_DEC_SEQUENCE(*pin))
            except TypeError as err:
                raise CashDrawerError(err)

    def linedisplay_select(self, select_display=False):
        """ Selects the line display or the printer

        This method is used for line displays that are daisy-chained between your computer and printer.
        If you set `select_display` to true, only the display is selected and if you set it to false,
        only the printer is selected.

        :param select_display: whether the display should be selected or the printer
        :type select_display: bool
        """
        if select_display:
            self._raw(LINE_DISPLAY_OPEN)
        else:
            self._raw(LINE_DISPLAY_CLOSE)

    def linedisplay_clear(self):
        """ Clears the line display and resets the cursor

        This method is used for line displays that are daisy-chained between your computer and printer.
        """
        self._raw(LINE_DISPLAY_CLEAR)

    def linedisplay(self, text):
        """
        Display text on a line display connected to your printer

        You should connect a line display to your printer. You can do this by daisy-chaining
        the display between your computer and printer.

        :param text: Text to display
        """
        self.linedisplay_select(select_display=True)
        self.linedisplay_clear()
        self.text(text)
        self.linedisplay_select(select_display=False)

    def hw(self, hw):
        """ Hardware operations

        :param hw: hardware action, may be:

            * INIT
            * SELECT
            * RESET
        """
        if hw.upper() == "INIT":
            self._raw(HW_INIT)
        elif hw.upper() == "SELECT":
            self._raw(HW_SELECT)
        elif hw.upper() == "RESET":
            self._raw(HW_RESET)
        else:  # DEFAULT: DOES NOTHING
            pass

    def print_and_feed(self, n=1):
        """ Print data in print buffer and feed *n* lines

            if n not in range (0, 255) then ValueError will be raised

            :param n: number of n to feed. 0 <= n <= 255. default: 1
            :raises ValueError: if not 0 <= n <= 255
        """
        if 0 <= n <= 255:
            # ESC d n
            self._raw(ESC + b"d" + six.int2byte(n))
        else:
            raise ValueError("n must be betwen 0 and 255")

    def control(self, ctl, count=5, tab_size=8):
        """ Feed control sequences

        :param ctl: string for the following control sequences:

            * LF *for Line Feed*
            * FF *for Form Feed*
            * CR *for Carriage Return*
            * HT *for Horizontal Tab*
            * VT *for Vertical Tab*

        :param count: integer between 1 and 32, controls the horizontal tab count. Defaults to 5.
        :param tab_size: integer between 1 and 255, controls the horizontal tab size in characters. Defaults to 8
        :raises: :py:exc:`~escpos.exceptions.TabPosError`
        """
        # Set position
        if ctl.upper() == "LF":
            self._raw(CTL_LF)
        elif ctl.upper() == "FF":
            self._raw(CTL_FF)
        elif ctl.upper() == "CR":
            self._raw(CTL_CR)
        elif ctl.upper() == "HT":
            if not (0 <= count <= 32 and
                    1 <= tab_size <= 255 and
                    count * tab_size < 256):
                raise TabPosError()
            else:
                # Set tab positions
                self._raw(CTL_SET_HT)
                for iterator in range(1, count):
                    self._raw(six.int2byte(iterator * tab_size))
                self._raw(NUL)
        elif ctl.upper() == "VT":
            self._raw(CTL_VT)

    def panel_buttons(self, enable=True):
        """ Controls the panel buttons on the printer (e.g. FEED)

        When enable is set to False the panel buttons on the printer will be disabled. Calling the method with
        enable=True or without argument will enable the panel buttons.

        If panel buttons are enabled, the function of the panel button, such as feeding, will be executed upon pressing
        the button. If the panel buttons are disabled, pressing them will not have any effect.

        This command is effective until the printer is initialized, reset or power-cycled. The default is enabled panel
        buttons.

        Some panel buttons will always work, especially when printer is opened. See for more information the manual
        of your printer and the escpos-command-reference.

        :param enable: controls the panel buttons
        :rtype: None
        """
        if enable:
            self._raw(PANEL_BUTTON_ON)
        else:
            self._raw(PANEL_BUTTON_OFF)

    def query_status(self, mode):
        """
        Queries the printer for its status, and returns an array of integers containing it.

        :param mode: Integer that sets the status mode queried to the printer.
            - RT_STATUS_ONLINE: Printer status.
            - RT_STATUS_PAPER: Paper sensor.
        :rtype: array(integer)
        """
        self._raw(mode)
        time.sleep(1)
        status = self._read()
        return status

    def is_online(self):
        """
        Queries the online status of the printer.

        :returns: When online, returns ``True``; ``False`` otherwise.
        :rtype: bool
        """
        status = self.query_status(RT_STATUS_ONLINE)
        if len(status) == 0:
            return False
        return not (status[0] & RT_MASK_ONLINE)

    def paper_status(self):
        """
        Queries the paper status of the printer.

        Returns 2 if there is plenty of paper, 1 if the paper has arrived to
        the near-end sensor and 0 if there is no paper.

        :returns: 2: Paper is adequate. 1: Paper ending. 0: No paper.
        :rtype: int
        """
        status = self.query_status(RT_STATUS_PAPER)
        if len(status) == 0:
            return 2
        if (status[0] & RT_MASK_NOPAPER == RT_MASK_NOPAPER):
            return 0
        if (status[0] & RT_MASK_LOWPAPER == RT_MASK_LOWPAPER):
            return 1
        if (status[0] & RT_MASK_PAPER == RT_MASK_PAPER):
            return 2


class EscposIO(object):
    """ESC/POS Printer IO object

    Allows the class to be used together with the `with`-statement. You have to define a printer instance
    and assign it to the EscposIO class.
    This example explains the usage:

    .. code-block:: Python

        with EscposIO(printer.Serial('/dev/ttyUSB0')) as p:
            p.set(font='a', height=2, align='center', text_type='bold')
            p.printer.set(align='left')
            p.printer.image('logo.gif')
            p.writelines('Big line\\n', font='b')
            p.writelines('Привет')
            p.writelines('BIG TEXT', width=2)

    After the `with`-statement the printer automatically cuts the paper if `autocut` is `True`.
    """

    def __init__(self, printer, autocut=True, autoclose=True, **kwargs):
        """
        :param printer: An EscPos-printer object
        :type printer: escpos.Escpos
        :param autocut: If True, paper is automatically cut after the `with`-statement *default*: True
        :param kwargs: These arguments will be passed to :py:meth:`escpos.Escpos.set()`
        """
        self.printer = printer
        self.params = kwargs
        self.autocut = autocut
        self.autoclose = autoclose

    def set(self, **kwargs):
        """ Set the printer-parameters

        Controls which parameters will be passed to :py:meth:`Escpos.set() <escpos.escpos.Escpos.set()>`.
        For more information on the parameters see the :py:meth:`set() <escpos.escpos.Escpos.set()>`-methods
        documentation. These parameters can also be passed with this class' constructor or the
        :py:meth:`~escpos.escpos.EscposIO.writelines()`-method.

        :param kwargs: keyword-parameters that will be passed to :py:meth:`Escpos.set() <escpos.escpos.Escpos.set()>`
        """
        self.params.update(kwargs)

    def writelines(self, text, **kwargs):
        params = dict(self.params)
        params.update(kwargs)

        if isinstance(text, six.text_type):
            lines = text.split('\n')
        elif isinstance(text, list) or isinstance(text, tuple):
            lines = text
        else:
            lines = ["{0}".format(text), ]

        # TODO check unicode handling
        # TODO flush? or on print? (this should prob rather be handled by the _raw-method)
        for line in lines:
            self.printer.set(**params)
            if isinstance(text, six.text_type):
                self.printer.text(u"{0}\n".format(line))
            else:
                self.printer.text("{0}\n".format(line))

    def close(self):
        """ called upon closing the `with`-statement
        """
        self.printer.close()

    def __enter__(self, **kwargs):
        return self

    def __exit__(self, type, value, traceback):
        """

        If :py:attr:`autocut <escpos.escpos.EscposIO.autocut>` is `True` (set by this class' constructor),
        then :py:meth:`printer.cut() <escpos.escpos.Escpos.cut()>` will be called here.
        """
        if not (type is not None and issubclass(type, Exception)):
            if self.autocut:
                self.printer.cut()

        if self.autoclose:
            self.close()
