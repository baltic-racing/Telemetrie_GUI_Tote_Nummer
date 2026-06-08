import serial
import time

ser = serial.Serial('COM3', 115200, timeout=1)  # Port anpassen
time.sleep(2)  # warten, bis Verbindung steht

try:
    while True:
        data = ser.read(ser.in_waiting or 1)
        if data:
            print(data)  # zeigt Bytes als Hex/ASCII
except KeyboardInterrupt:
    ser.close()