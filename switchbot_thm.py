#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Gets information from SwitchBot MeterTH S1
#
import datetime
import json
import binascii
import bluepy.btle
import logging

class Device(bluepy.btle.DefaultDelegate):

    def __init__(self):
        bluepy.btle.DefaultDelegate.__init__(self)

    def handleDiscovery(self, dev, isNewDev, isNewData):
        mac = dev.addr.lower()
        if not mac in self.targets:
            logging.debug('not target, mac=%s', mac)
            return
        if mac in self.results and self.results[mac]['done']:
            logging.debug('already scanned, mac=%s', mac)
            return
        for (adtype, desc, value) in dev.getScanData():
            if adtype != 22:
                continue
            servicedata = binascii.unhexlify(value[4:])
            battery = servicedata[2] & 0b01111111
            isTemperatureAboveFreezing = servicedata[4] & 0b10000000
            temperature = (servicedata[3] & 0b00001111) / 10 + (servicedata[4] & 0b01111111)
            if not isTemperatureAboveFreezing:
                temperature = -temperature
            humidity = servicedata[5] & 0b01111111
            now = datetime.datetime.now()
            self.results[mac] = {
                'battery': battery,
                'temperature': temperature,
                'humidity': humidity,
                'done': True,
                'time': now.strftime('%Y/%m/%d %H:%M:%S')
                }
            logging.debug(self.results[mac])

    def getData(self, targets, nretry):
        self.targets = list(map(lambda target: target.lower(), targets))
        self.results = {}
        scanner = bluepy.btle.Scanner().withDelegate(self)
        for i in range(0, nretry):
            scanner.scan(1.0)
            if len(self.results) >= len(targets):
                break
        return self.results
