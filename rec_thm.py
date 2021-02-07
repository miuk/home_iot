import switchbot_thm
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

confFile = 'thm_list.dat'
recFile = 'thm_rec.dat'
logFile = '/var/log/thm.log'

logging.basicConfig(level=logging.INFO,
                    filename=logFile,
                    format='[%(asctime)s %(levelname)s %(message)s')


targets = readConf(confFile)
dev = switchbot_thm.Device()
results = dev.getData(targets.keys(), 30)
for mac in targets.keys():
    if mac in results:
        targets[mac].update(results[mac])
recordData(recFile, targets)
