#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Gets information from smart meter with ECHONET Lite B-Route service.
# for RL7023 Stick-D/IPS
#

import sys
import serial
import time
import datetime
import json
import logging

class HEMS:

    GET_PREFIX  = b'\x10\x81'     # EHD1, EHD2
    GET_PREFIX += b'\x12\x34'     # TID
    GET_PREFIX += b'\x05\xFF\x01' # SEOJ, control class
    GET_PREFIX += b'\x02\x88\x01' # DEOJ, low voltage smart power meter class
    GET_PREFIX += b'\x62'         # ESV,  property read request

    def __init__(self, rbid, rbpwd):
        self.rbid = rbid # B-Route authentication ID
        self.rbpwd = rbpwd # B-Route authentication password
        self.serialPortDev = '/dev/ttyUSB0'
        self.ser = serial.Serial(self.serialPortDev, 115200)
        self.scanRes = {}
        self.mac = None
        self.ipv6Addr = None

    def readSer(self):
        line = self.ser.readline()
        logging.debug('read %s' % (line.decode()))
        return line

    def waitOk(self):
        self.readSer() # echo back
        self.readSer() # OK

    def writeSerial(self, msg):
        logging.debug('write %s' % (msg))
        self.ser.write(msg.encode())

    def requestGetProperty(self, props):
        msg = bytes([len(props)])
        for prop in props:
            msg += bytes([prop])
            msg += b'\x00'
        msg = self.GET_PREFIX + msg
        command = "SKSENDTO 1 {0} 0E1A 1 {1:04X} ".format(self.ipv6Addr, len(msg))
        command = command.encode() + msg
        logging.debug('requestGetProperty %s' % (command))
        self.ser.write(command)

    def sendCredential(self):
        self.writeSerial("SKSETPWD C " + self.rbpwd + "\r\n")
        self.waitOk()
        self.writeSerial("SKSETRBID " + self.rbid + "\r\n")
        self.waitOk()

    def scan(self):
        scanDuration = 4
        # seconds = 0.01 * (2^<scanDuration> + 1) * <num of channels (32?)>
        for i in range(0, 5):
            self.scanRes = {}
            # active scan (with IE)
            self.writeSerial('SKSCAN 2 FFFFFFFF ' + str(scanDuration) + "\r\n")
            scanEnd = False
            while not scanEnd :
                line = self.readSer().decode()
                if line.startswith('EVENT 22') : # end of scan
                    scanEnd = True
                elif line.startswith("  ") :
                    # If found, will be received data with 2 space indent.
                    # Example:
                    #  Channel:39
                    #  Channel Page:09
                    #  Pan ID:FFFF
                    #  Addr:FFFFFFFFFFFFFFFF
                    #  LQI:A7
                    #  PairID:FFFFFFFF
                    cols = line.strip().split(':')
                    self.scanRes[cols[0]] = cols[1]
            if 'Channel' in self.scanRes:
                return True
            if scanDuration < 7:
                scanDuration += 1
        return False

    def connect(self):
        self.sendCredential()
        if not self.scan():
            return False
        self.writeSerial("SKSREG S2 " + self.scanRes["Channel"] + "\r\n")
        self.waitOk()

        self.writeSerial("SKSREG S3 " + self.scanRes["Pan ID"] + "\r\n")
        self.waitOk()

        self.mac = self.scanRes["Addr"]

        # converts MAC to IPv6 link local
        self.writeSerial("SKLL64 " + self.scanRes["Addr"] + "\r\n")
        self.readSer() # echoback
        self.ipv6Addr = self.readSer().decode().strip()

        # start PANA connecting sequence
        self.writeSerial("SKJOIN " + self.ipv6Addr + "\r\n");
        self.waitOk()

        # waiting PANA connected
        bConnected = False
        while not bConnected :
            line = self.readSer().decode()
            if line.startswith("EVENT 24") :
                return False
            elif line.startswith("EVENT 25") :
                bConnected = True

        self.ser.timeout = 8

        # (ECHONET-Lite_Ver.1.12_02.pdf p.4-16)
        self.readSer()
        return True

    def decodeMsg(self, msg):
        o = {
            'EHD': msg[0:4],
            'TID': msg[4:8],
            'SEOJ': msg[8:14],
            'DEOJ': msg[14:20],
            'ESV': msg[20:22],
            'OPC': int(msg[22:24], 16),
            'PROPS': {}
        }
        offset = 24
        for i in range(0,o['OPC']):
            epc = msg[offset:offset+2]
            o['PROPS'][epc] = {}
            offset += 2
            pdc = int(msg[offset:offset+2], 16)
            o['PROPS'][epc]['PDC'] = pdc
            offset += 2
            o['PROPS'][epc]['EDT'] = msg[offset:offset+(pdc*2)]
            offset += (pdc * 2)
        return o

    def getData(self):
        data = {
            'mac': self.mac
        }
        self.requestGetProperty((0xD7, 0xE0, 0xE1, 0xE7, 0xE8, 0xEA))
        while True:
            line = self.readSer().decode()
            if len(line) <= 0:
                logging.error('read TIMEOUT\n')
                return None
            if line.startswith("ERXUDP"):
                break
        cols = line.strip().split(' ')
        res = cols[8]   # UDP data part
        o = self.decodeMsg(res)

        if o['SEOJ'] == '028801' and o['ESV'] == "72":
            for (epc, prop) in o['PROPS'].items():
                edt = prop['EDT']
                if epc == 'E0':
                    data['kwh'] = int(edt, 16)
                elif epc == 'E7':
                    data['w'] = int(edt, 16)
                elif epc == 'E8':
                    t = int(edt[0:4], 16) / 10.0
                    r = int(edt[4:8], 16) / 10.0
                    data['a_t'] = t
                    data['a_r'] = r
        return data
