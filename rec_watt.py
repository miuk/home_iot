import btwattch2
import sys
import json
import logging

def readConf(conf):
    targets = {}
    with open(conf, 'r') as fd:
        lines = fd.readlines()
    for line in lines:
        if line.startswith('#'):
            continue
        args = line.strip().split(' ')
        if len(args) < 3:
            continue
        mac = args[0].lower()
        targets[mac] = {
            'id': args[1],
            'type': args[2],
            'done': False
        }
    return targets

def recordData(fname, data):
    with open(fname, 'a') as fd:
        for (mac, o) in data.items():
            o['mac'] = mac
            fd.write(json.dumps(o) + '\n')

confFile = 'watt_list.dat'
recFile = 'watt_rec.dat'
logFile = '/var/log/watt.log'

logging.basicConfig(level=logging.INFO,
                    filename=logFile,
                    format='[%(asctime)s %(levelname)s %(message)s')

targets = readConf(confFile)
for mac in targets.keys():
    wattChecker = btwattch2.BTWATTChecker(mac)
    if not wattChecker.scanAndConnect():
        continue
    wattChecker.monitor()
    data = wattChecker.get_rec_data()
    wattChecker.disconnect()
    targets[mac].update(data)
    logging.debug(targets[mac])
recordData(recFile, targets)
