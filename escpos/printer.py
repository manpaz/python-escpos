#!/usr/bin/python
"""
@author: Manuel F Martinez <manpaz@bashlinux.com>
@organization: Bashlinux
@copyright: Copyright (c) 2012 Bashlinux
@license: GNU GPL v3
"""

import usb.core
import usb.util
import serial
import socket

from escpos import *
from constants import *
from exceptions import *

class Usb(Escpos):
    """ Define USB printer """

    def __init__(self, idVendor, idProduct, interface=0, in_ep=0x82, out_ep=0x01):
        """
        @param idVendor  : Vendor ID
        @param idProduct : Product ID
        @param interface : USB device interface
        @param in_ep     : Input end point
        @param out_ep    : Output end point
        """
        self.idVendor  = idVendor
        self.idProduct = idProduct
        self.interface = interface
        self.in_ep     = in_ep
        self.out_ep    = out_ep
        self.open()


    def open(self):
        """ Search device on USB tree and set is as escpos device """
        self.device = usb.core.find(idVendor=self.idVendor, idProduct=self.idProduct)
        if self.device is None:
            print "Cable isn't plugged in"

        check_driver = None

        try:
            check_driver = self.device.is_kernel_driver_active(0)
        except NotImplementedError:
            pass

        if check_driver is None or check_driver:
            try:
                self.device.detach_kernel_driver(0)
            except usb.core.USBError as e:
                if check_driver is not None:
                    print "Could not detatch kernel driver: %s" % str(e)

        try:
            self.device.set_configuration()
            self.device.reset()
        except usb.core.USBError as e:
            print "Could not set configuration: %s" % str(e)


    def _raw(self, msg):
        """ Print any command sent in raw format """
        self.device.write(self.out_ep, msg, self.interface)


    def __del__(self):
        """ Release USB interface """
        if self.device:
            usb.util.dispose_resources(self.device)
        self.device = None



class Serial(Escpos):
    """ Define Serial printer """

    def __init__(self, devfile="/dev/ttyS0", baudrate=9600, bytesize=8, timeout=1,
                 parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE,
                 xonxoff=False , dsrdtr=True):
        """
        @param devfile  : Device file under dev filesystem
        @param baudrate : Baud rate for serial transmission
        @param bytesize : Serial buffer size
        @param timeout  : Read/Write timeout
        
        @param parity   : Parity checking
        @param stopbits : Number of stop bits
        @param xonxoff  : Software flow control
        @param dsrdtr   : Hardware flow control (False to enable RTS/CTS)
        """
        self.devfile  = devfile
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.timeout  = timeout
        
        self.parity = parity
        self.stopbits = stopbits
        self.xonxoff = xonxoff
        self.dsrdtr = dsrdtr
        
        self.open()


    def open(self):
        """ Setup serial port and set is as escpos device """
        self.device = serial.Serial(port=self.devfile, baudrate=self.baudrate,
                                    bytesize=self.bytesize, parity=self.parity,
                                    stopbits=self.stopbits, timeout=self.timeout,
                                    xonxoff=self.xonxoff, dsrdtr=self.dsrdtr)

        if self.device is not None:
            print "Serial printer enabled"
        else:
            print "Unable to open serial printer on: %s" % self.devfile


    def _raw(self, msg):
        """ Print any command sent in raw format """
        self.device.write(msg)


    def __del__(self):
        """ Close Serial interface """
        if self.device is not None:
            self.device.close()



class Network(Escpos):
    """ Define Network printer """

    def __init__(self,host,port=9100):
        """
        @param host : Printer's hostname or IP address
        @param port : Port to write to
        """
        self.host = host
        self.port = port
        self.open()


    def open(self):
        """ Open TCP socket and set it as escpos device """
        self.device = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.device.connect((self.host, self.port))

        if self.device is None:
            print "Could not open socket for %s" % self.host


    def _raw(self, msg):
        """ Print any command sent in raw format """
        self.device.send(msg)


    def __del__(self):
        """ Close TCP connection """
        self.device.close()



class File(Escpos):
    """ Define Generic file printer """

    def __init__(self, devfile="/dev/usb/lp0"):
        """
        @param devfile : Device file under dev filesystem
        """
        self.devfile = devfile
        self.open()


    def open(self):
        """ Open system file """
        self.device = open(self.devfile, "wb")

        if self.device is None:
            print "Could not open the specified file %s" % self.devfile


    def _raw(self, msg):
        """ Print any command sent in raw format """
        self.device.write(msg);


    def __del__(self):
        """ Close system file """
        self.device.close()
