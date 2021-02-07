import hems
import sys
import datetime
import json
import logging

def readConf(fname):
    rbid = None
    rbpwd = None
    with open(fname, 'r') as fd:
        lines = fd.readlines()
    for line in lines:
        line = line.strip()
        if len(line) <= 0:
            continue
        if line[0] == '#':
            continue
        args = line.split('=')
        if len(args) < 2:
            continue
        name = args[0].strip()
        value = args[1].strip()
        if name == 'rbid':
            rbid = value
        if name == 'rbpwd':
            rbpwd = value
    return (rbid, rbpwd)

def timestamp():
    now = datetime.datetime.now()
    ts = now.strftime('%Y/%m/%d %H:%M:%S')
    return ts

def recordData(fname, data):
    data['id'] = 'tepco'
    data['type'] = 'power'
    data['time'] = timestamp()
    #print(data)
    with open(fname, 'a') as fd:
        fd.write(json.dumps(data) + '\n')

confFile = '/etc/home_iot/hems.conf'
recFile = 'power_meter_rec.dat'
logFile = '/var/log/hems.log'

logging.basicConfig(level=logging.INFO,
                    filename=logFile,
                    format='[%(asctime)s %(levelname)s %(message)s')

(rbid, rbpwd) = readConf(confFile)

data = None
dev = hems.HEMS(rbid, rbpwd)
if dev.connect():
    data = dev.getData()
    if not data is None:
        data['done'] = True
if data is None:
    data = { 'error': 'connect failed',
             'done': False
    }
recordData(recFile, data)
