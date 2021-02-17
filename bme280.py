#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Gets information from BME280 with SPI
#
import spidev
import time

class BME280:

    def __init__(self):
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0) # bus 0, cs 0
        self.spi.max_speed_hz = 1000000

    def close(self):
        self.spi.close()

    def configure(self,
                  mode=0,       # 0:sleep, 1:force, 3:normal
                  osrs_h=0,     # 0: skip measurement, otherwise 2^(value-1) oversampling
                  osrs_t=0,
                  osrs_p=0,
                  t_sb=0,       # standby time, 0-7 = 0.5, 62.5, 125, 125, 250, 500, 1000, 10, 20 ms
                  iir_filter=0, # 0: filter off, otherwize 2^value filter coefficient
                  spi3w=0):     # if 1, 3 wire spi
        self.mode = mode
        self.osrs_h = osrs_h
        self.osrs_t = osrs_t
        self.osrs_p = osrs_p
        self.t_sb = t_sb
        self.iir_filter = iir_filter
        self.spi3w = spi3w

    def init(self):
        ctrl_hum = self.osrs_h
        ctrl_meas = (self.osrs_t << 5) | (self.osrs_p << 2) | self.mode
        config = (self.t_sb << 5) | (self.iir_filter << 2) | self.spi3w
        #print(ctrl_hum, ctrl_meas, config)
        self.write_one(0xF2, ctrl_hum)
        self.write_one(0xF4, ctrl_meas)
        self.write_one(0xF5, config)
        self.readTrim()

    def readTrim(self):
        data = self.read(0x88, 24)
        data.extend(self.read(0xA1))
        data.extend(self.read(0xE1, 7))
        #print(data)
        self.digT = []
        self.digT.append((data[1]  << 8) | data[0])
        self.digT.append((data[3]  << 8) | data[2])
        self.digT.append((data[5]  << 8) | data[4])
        self.digP = []
        self.digP.append((data[7]  << 8) | data[6])
        self.digP.append((data[9]  << 8) | data[8])
        self.digP.append((data[11] << 8) | data[10])
        self.digP.append((data[13] << 8) | data[12])
        self.digP.append((data[15] << 8) | data[14])
        self.digP.append((data[17] << 8) | data[16])
        self.digP.append((data[19] << 8) | data[18])
        self.digP.append((data[21] << 8) | data[20])
        self.digP.append((data[23] << 8) | data[22])
        self.digH = []
        self.digH.append(data[24])
        self.digH.append((data[26] << 8) | data[25])
        self.digH.append(data[27])
        self.digH.append((data[28] << 4) | (0x0F & data[29]))
        self.digH.append((data[30] << 4) | ((data[29] >> 4) & 0x0F))
        self.digH.append(data[31])
        for i in range(1, 2):
            if self.digT[i] & 0x8000:
                self.digT[i] = (-self.digT[i] ^ 0xFFFF) + 1
        for i in range(1, 8):
            if self.digP[i] & 0x8000:
                self.digP[i] = (-self.digP[i] ^ 0xFFFF) + 1
        for i in range(0, 6):
            if self.digH[i] & 0x8000:
                self.digH[i] = (-self.digH[i] ^ 0xFFFF) + 1
    
    def read_one(self, addr):
        sdata = [addr, 0x00]
        rdata = self.spi.xfer2(sdata)
        #print(rdata)
        #time.sleep(0.02)
        return rdata[1]
    
    def read(self, addr, num_byte=1):
        ret = []
        for i in range(0, num_byte):
            rdata = self.read_one(addr)
            ret.append(rdata)
            addr += 1
        return ret
        
    def write_one(self, addr, data):
        sdata = [addr & 0x7F, data]
        rdata = self.spi.xfer2(sdata)
        #print(rdata)
        #time.sleep(0.02)
        
    def write(self, addr, data):
        for o in data:
            self.write_one(addr, o)
            addr += 1

    def calibration_T(self, raw):
        var1 = ((((raw >> 3) - (self.digT[0]<<1))) * (self.digT[1])) >> 11
        var2 = (((((raw >> 4) - (self.digT[0])) * ((raw>>4) - (self.digT[0]))) >> 12) * (self.digT[2])) >> 14
        self.t_fine = var1 + var2
        T = (self.t_fine * 5 + 128) >> 8
        return T / 100.0

    def calibration_P(self, raw):
        var1 = (self.t_fine >>1) - 64000
        var2 = (((var1>>2) * (var1>>2)) >> 11) * self.digP[5]
        var2 = var2 + ((var1*(self.digP[4]))<<1)
        var2 = (var2>>2)+((self.digP[3])<<16)
        var1 = (((self.digP[2] * (((var1>>2)*(var1>>2)) >> 13)) >>3) + ((self.digP[1] * var1)>>1))>>18
        var1 = ((32768+var1) * self.digP[0]) >> 15
        if var1 == 0:
            return 0
        P = (((1048576-raw)-(var2>>12)))*3125
        if P < 0x80000000:
            P = int((P << 1) / var1)
        else:
            P = int(P / var1) * 2
        var1 = ((self.digP[8]) * ((((P>>3) * (P>>3))>>13)))>>12
        var2 = (((P>>2)) * (self.digP[7]))>>13
        P = (P + ((var1 + var2 + self.digP[6]) >> 4))
        return P / 100.0

    def calibration_H(self, raw):
        v_x1 = self.t_fine - 76800
        v_x1 = ((((raw << 14) - (self.digH[3] << 20) - (self.digH[4] * v_x1)) + 16384) >> 15) \
                * (((((((v_x1 * self.digH[5]) >> 10) * (((v_x1 * self.digH[2]) >> 11) + 32768)) >> 10) + 2097152) \
                    * self.digH[1] + 8192) >> 14)
        v_x1 = v_x1 - (((((v_x1 >> 15) * (v_x1 >> 15)) >> 7) * self.digH[0]) >> 4)
        if v_x1 < 0:
            v_x1 = 0
        elif v_x1 > 419430400:
            v_x1 = 419430400
        return (v_x1 >> 12) / 1024.0
    
    def readData(self):
        data = self.read(0xF7, 8)
        p_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        t_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        h_raw  = (data[6] << 8) | data[7]
        #print(p_raw, t_raw, h_raw)
        return {
            'temparature': self.calibration_T(t_raw),
            'pressure': self.calibration_P(p_raw),
            'humidity': self.calibration_H(h_raw)
            }

if __name__ == '__main__':
    dev = BME280()
    dev.configure(mode=1, osrs_t=1, osrs_p=1, osrs_h=1)
    dev.init()
    o = dev.readData()
    print(o)
