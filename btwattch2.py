#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Gets information from BTWATTCH2
#
import bluepy.btle
import json
import sys
import functools
import time
import datetime
import struct
import logging

def crc8(payload: bytearray):
    POLYNOMIAL = 0x85
    MSBIT = 0x80
    def crc1(crc, step=0):
        if step >= 8:
            return crc & 0xff
        elif crc & MSBIT :
            return crc1(crc << 1 ^ POLYNOMIAL, step+1)
        else:
            return crc1(crc << 1, step+1)
    return functools.reduce(lambda x, y: crc1(y ^ x), payload, 0x00)

class BTWATTChecker(bluepy.btle.DefaultDelegate):

    GATT_CHARACTERISTIC_UUID_TX = '6e400002-b5a3-f393-e0a9-e50e24dcca9e'
    GATT_CHARACTERISTIC_UUID_RX = '6e400003-b5a3-f393-e0a9-e50e24dcca9e'
    CMD_HEADER = bytearray.fromhex('aa')

    PAYLOAD_TIMER = bytearray.fromhex('01')
    PAYLOAD_TURN_ON = bytearray.fromhex('a701')
    PAYLOAD_TURN_OFF = bytearray.fromhex('a700')
    PAYLOAD_REALTIME_MONITORING = bytearray.fromhex('08')

    def __init__(self, mac):
        bluepy.btle.DefaultDelegate.__init__(self)
        self.mac = mac.upper()
        self.scannedDevice = None
        self.monitoredData = None
        self.monitoredDataLen = 0
        self.monitorFinished = False
        self.rec_data = {
            'id': 'kenji_aircon',
            'type': 'power',
            'done': False,
            'mac': self.mac
        }
        self.scanner = None
        self.peripheral = None
        self.tx = None
        self.rx = None

    def get_rec_data(self):
        now = datetime.datetime.now()
        self.rec_data['time'] = now.strftime('%Y/%m/%d %H:%M:%S')
        return self.rec_data

    def handleDiscovery(self, dev, isNewDev, isNewData):
        pass

    def handleNotification(self, cHandle, data):
        logging.debug('hendleNotification len=%d, data=%s' % (len(data), data))
        if len(data) >= 4 and data[0] == 0xaa and data[3] == 0x08:
            self.monitoredDataLen = struct.unpack_from('>H', data, 1)[0]
            self.monitoredData = data[4:]
            if len(self.monitoredData) >= self.monitoredDataLen:
                self.monitorFinished = True
        else:
            if not self.monitorFinished:
                if self.monitoredData is None:
                    return
                self.monitoredData += data
                if len(self.monitoredData) >= self.monitoredDataLen:
                    self.monitorFinished = True

    def cmd(self, payload: bytearray):
        pld_length = len(payload).to_bytes(2, 'big')
        return self.CMD_HEADER + pld_length + payload + crc8(payload).to_bytes(1, 'big')

    def write(self, payload: bytearray):
        command = self.cmd(payload)
        self.peripheral.writeCharacteristic(self.tx, command)

    def enableNotify(self):
        self.peripheral.writeCharacteristic((self.rx)+1, b'\x01\x00', True)

    def getHandles(self):
        for service in self.peripheral.getServices():
            for c in service.getCharacteristics():
                if c.uuid == bluepy.btle.UUID(self.GATT_CHARACTERISTIC_UUID_TX):
                    self.tx = c.getHandle()
                elif c.uuid == bluepy.btle.UUID(self.GATT_CHARACTERISTIC_UUID_RX):
                    self.rx = c.getHandle()

    def scan(self):
        self.scanner = bluepy.btle.Scanner()
        self.scanner.start()
        for i in range(0,10):
            self.scanner.process(1.0)
            rl = self.scanner.getDevices()
            if rl is None:
                logging.warning('scan not detect')
                continue
            for r in rl:
                logging.debug('scan detect %s, %s' % (r.addr, r.getScanData()))
                if r.addr.upper() == self.mac:
                    self.scannedDevice = r
                    break
            if not self.scannedDevice is None:
                break
            logging.debug('scanning')
        self.scanner.stop()

    def connect(self):
        p = None
        try:
            p = bluepy.btle.Peripheral(self.scannedDevice).withDelegate(self)
            logging.debug('connected')
        except bluepy.btle.BTLEDisconnectError as e:
            logging.error(e)
            p = None
        return p

    def disconnect(self):
        if self.peripheral is None:
            return
        self.peripheral.disconnect()
        self.peripheral = None

    def scanAndConnect(self):
        p = None
        for i in range(0, 3):
            self.scan()
            if self.scannedDevice is None:
                self.rec_data['error'] = 'scan failed'
                return False
            p = self.connect()
            if p is None:
                time.sleep(1)
                continue
            break
        if p is None:
            self.rec_data['error'] = 'connect failed'
            return False
        self.peripheral = p
        self.getHandles()
        self.enableNotify()
        return True

    def monitorSub(self):
        self.monitoredData = None
        self.monitoredDataLen = 0
        self.monitorFinished = False
        self.write(self.PAYLOAD_REALTIME_MONITORING)
        for i in range(0,6):
            self.peripheral.waitForNotifications(1.0)
            if self.monitorFinished:
                break
            logging.debug('monitor waiting')
        if self.monitorFinished:
            voltage = int.from_bytes(self.monitoredData[1:7], 'little') / (16**6)
            current = int.from_bytes(self.monitoredData[7:13], 'little') / (32**6) * 1000
            wattage = int.from_bytes(self.monitoredData[13:19], 'little') / (16**6)
            timestamp = datetime.datetime(1900+self.monitoredData[24], self.monitoredData[23]+1, *self.monitoredData[22:18:-1])
            self.rec_data['w'] = wattage
            self.rec_data['a_t'] = current / 1000.0
            self.rec_data['a_r'] = current / 1000.0
            self.rec_data['time'] = str(timestamp)
            self.rec_data['done'] = True
            logging.debug('monitored, v=%f, a=%f, w=%f, t=%s' % (voltage, current, wattage, timestamp))
            return True
        else:
            logging.error('notify failed')
            return False

    def monitor(self):
        for i in range(0, 3):
            if self.monitorSub():
                return True
        self.rec_data['error'] = 'notify failed'
        return False
