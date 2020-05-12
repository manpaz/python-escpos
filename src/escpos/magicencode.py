#!/usr/bin/python
#  -*- coding: utf-8 -*-
""" Magic Encode

This module tries to convert an UTF-8 string to an encoded string for the printer.
It uses trial and error in order to guess the right codepage.
The code is based on the encoding-code in py-xml-escpos by @fvdsn.

:author: `Patrick Kanzler <dev@pkanzler.de>`_
:organization: `python-escpos <https://github.com/python-escpos>`_
:copyright: Copyright (c) 2016 Patrick Kanzler and Frédéric van der Essen
:license: MIT
"""


from builtins import bytes
from .constants import CODEPAGE_CHANGE
from .exceptions import Error
from .codepages import CodePages
import six
import re


class Encoder(object):
    """Takes a list of available code spaces. Picks the right one for a
    given character.

    Note: To determine the code page, it needs to do the conversion, and
    thus already knows what the final byte in the target encoding would
    be. Nevertheless, the API of this class doesn't return the byte.

    The caller use to do the character conversion itself.

        $ python -m timeit -s "{u'ö':'a'}.get(u'ö')"
        100000000 loops, best of 3: 0.0133 usec per loop

        $ python -m timeit -s "u'ö'.encode('latin1')"
        100000000 loops, best of 3: 0.0141 usec per loop
    """

    def __init__(self, codepage_map):
        self.codepages = codepage_map
        self.available_encodings = set(codepage_map.keys())
        self.available_characters = {}
        self.used_encodings = set()

    def get_sequence(self, encoding):
        return int(self.codepages[encoding])

    def get_encoding_name(self, encoding):
        """Given an encoding provided by the user, will return a
        canonical encoding name; and also validate that the encoding
        is supported.

        TODO: Support encoding aliases: pc437 instead of cp437.
        """
        encoding = CodePages.get_encoding_name(encoding)
        if encoding not in self.codepages:
            raise ValueError((
                'Encoding "{}" cannot be used for the current profile. '
                'Valid encodings are: {}'
                ).format(encoding, ','.join(self.codepages.keys())))
        return encoding

    @staticmethod
    def _get_codepage_char_list(encoding):
        """Get codepage character list

        Gets characters 128-255 for a given code page, as an array.

        :param encoding: The name of the encoding. This must appear in the CodePage list
        """
        codepage = CodePages.get_encoding(encoding)
        if 'data' in codepage:
            encodable_chars = list("".join(codepage['data']))
            assert(len(encodable_chars) == 128)
            return encodable_chars
        elif 'python_encode' in codepage:
            encodable_chars = [u" "] * 128
            for i in range(0, 128):
                codepoint = i + 128
                try:
                    encodable_chars[i] = bytes([codepoint]).decode(codepage['python_encode'])
                except UnicodeDecodeError:
                    # Non-encodable character, just skip it
                    pass
            return encodable_chars
        raise LookupError("Can't find a known encoding for {}".format(encoding))

    def _get_codepage_char_map(self, encoding):
        """ Get codepage character map

        Process an encoding and return a map of UTF-characters to code points
        in this encoding.

        This is generated once only, and returned from a cache.

        :param encoding: The name of the encoding.
        """
        # Skip things that were loaded previously
        if encoding in self.available_characters:
            return self.available_characters[encoding]
        codepage_char_list = self._get_codepage_char_list(encoding)
        codepage_char_map = dict((utf8, i + 128) for (i, utf8) in enumerate(codepage_char_list))
        self.available_characters[encoding] = codepage_char_map
        return codepage_char_map

    def can_encode(self, encoding, char):
        """Determine if a character is encodeable in the given code page.

        :param encoding: The name of the encoding.
        :param char: The character to attempt to encode.
        """
        available_map = {}
        try:
            available_map = self._get_codepage_char_map(encoding)
        except LookupError:
            return False

        # Decide whether this character is encodeable in this code page
        is_ascii = ord(char) < 128
        is_encodable = char in available_map
        return is_ascii or is_encodable

    @staticmethod
    def _encode_char(char, charmap, defaultchar):
        """ Encode a single character with the given encoding map

        :param char: char to encode
        :param charmap: dictionary for mapping characters in this code page
        """
        if ord(char) < 128:
            return ord(char)
        if char in charmap:
            return charmap[char]
        return ord(defaultchar)

    def encode(self, text, encoding, defaultchar='?'):
        """ Encode text under the given encoding

        :param text: Text to encode
        :param encoding: Encoding name to use (must be defined in capabilities)
        :param defaultchar: Fallback for non-encodable characters
        """
        codepage_char_map = self._get_codepage_char_map(encoding)
        output_bytes = bytes([self._encode_char(char, codepage_char_map, defaultchar) for char in text])
        return output_bytes

    def __encoding_sort_func(self, item):
        key, index = item
        return (
            key in self.used_encodings,
            index
        )

    def find_suitable_encoding(self, char):
        """The order of our search is a specific one:

        1. code pages that we already tried before; there is a good
           chance they might work again, reducing the search space,
           and by re-using already used encodings we might also
           reduce the number of codepage change instructiosn we have
           to send. Still, any performance gains will presumably be
           fairly minor.

        2. code pages in lower ESCPOS slots first. Presumably, they
           are more likely to be supported, so if a printer profile
           is missing or incomplete, we might increase our change
           that the code page we pick for this character is actually
           supported.
        """
        sorted_encodings = sorted(
            self.codepages.items(),
            key=self.__encoding_sort_func)

        for encoding, _ in sorted_encodings:
            if self.can_encode(encoding, char):
                # This encoding worked; at it to the set of used ones.
                self.used_encodings.add(encoding)
                return encoding


def split_writable_text(encoder, text, encoding):
    """Splits off as many characters from the begnning of text as
    are writable with "encoding". Returns a 2-tuple (writable, rest).
    """
    if not encoding:
        return None, text

    for idx, char in enumerate(text):
        if encoder.can_encode(encoding, char):
            continue
        return text[:idx], text[idx:]

    return text, None


class MagicEncode(object):
    """A helper that helps us to automatically switch to the right
    code page to encode any given Unicode character.

    This will consider the printers supported codepages, according
    to the printer profile, and if a character cannot be encoded
    with the current profile, it will attempt to find a suitable one.

    If the printer does not support a suitable code page, it can
    insert an error character.
    """
    def __init__(self, driver, encoding=None, disabled=False,
                 defaultsymbol='?', encoder=None):
        """

        :param driver:
        :param encoding: If you know the current encoding of the printer
        when initializing this class, set it here. If the current
        encoding is unknown, the first character emitted will be a
        codepage switch.
        :param disabled:
        :param defaultsymbol:
        :param encoder:
        """
        if disabled and not encoding:
            raise Error('If you disable magic encode, you need to define an encoding!')

        self.driver = driver
        self.encoder = encoder or Encoder(driver.profile.get_code_pages())

        self.encoding = self.encoder.get_encoding_name(encoding) if encoding else None
        self.defaultsymbol = defaultsymbol
        self.disabled = disabled

    def force_encoding(self, encoding):
        """Sets a fixed encoding. The change is emitted right away.

        From now one, this buffer will switch the code page anymore.
        However, it will still keep track of the current code page.
        """
        if not encoding:
            self.disabled = False
        else:
            self.write_with_encoding(encoding, None)
            self.disabled = True

    def write(self, text):
        """Write the text, automatically switching encodings.
        """

        if self.disabled:
            self.write_with_encoding(self.encoding, text)
            return

        if re.findall(r'[\u4e00-\u9fa5]', text):
            self.driver._raw(text.encode('GB18030'))
            return

        # See how far we can go into the text with the current encoding
        to_write, text = split_writable_text(self.encoder, text, self.encoding)
        if to_write:
            self.write_with_encoding(self.encoding, to_write)

        while text:
            # See if any of the code pages that the printer profile
            # supports can encode this character.
            encoding = self.encoder.find_suitable_encoding(text[0])
            if not encoding:
                self._handle_character_failed(text[0])
                text = text[1:]
                continue

            # Write as much text as possible with the encoding found.
            to_write, text = split_writable_text(self.encoder, text, encoding)
            if to_write:
                self.write_with_encoding(encoding, to_write)

    def _handle_character_failed(self, char):
        """Called when no codepage was found to render a character.
        """
        # Writing the default symbol via write() allows us to avoid
        # unnecesary codepage switches.
        self.write(self.defaultsymbol)

    def write_with_encoding(self, encoding, text):
        if text is not None and type(text) is not six.text_type:
            raise Error("The supplied text has to be unicode, but is of type {type}.".format(
                type=type(text)
            ))

        # We always know the current code page; if the new codepage
        # is different, emit a change command.
        if encoding != self.encoding:
            self.encoding = encoding
            self.driver._raw(
                CODEPAGE_CHANGE +
                six.int2byte(self.encoder.get_sequence(encoding)))

        if text:
            self.driver._raw(self.encoder.encode(text, encoding))
