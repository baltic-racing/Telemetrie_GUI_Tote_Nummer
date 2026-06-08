import time
import random

CMD_STX = 0x02
CMD_ETX = 0x55

# -------------------------------------------------
# Fake Serial Klasse wie bei PySerial
# -------------------------------------------------

class serial:
    class Serial:
        def __init__(self, port=None, baudrate=115200, timeout=1):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            pass

        def read(self, num_bytes):
            """
            Simuliert den Empfang eines kompletten USB-Pakets.
            Dein Reader liest ser.read(X), also geben wir ein Paket zurück.
            """
            time.sleep(self.timeout)

            # Beispiel-Payload: 3 IDs mit zufälligen Werten
            payload = bytearray()
            for _ in range(3):
                id_byte = random.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 41, 65, 66, 67, 68, 69, 70, 117])
                if id_byte == 10:
                    value = random.randint(222, 222)  # Spannung in mV
                else:
                    value = random.randint(66, 88)
                payload.extend([id_byte, value])

            packet = bytearray()
            packet.append(CMD_STX)              # Start
            packet.append(0x01)              # msg_type Telemetrie
            packet.append(len(payload))      # Länge
            packet.extend(payload)           # Payload

            payload_len = packet[2]
            checksum = 0
            for b in packet[0:3 + payload_len]:
                checksum ^= b   

            packet.append(checksum)              # End

            return packet

        @property
        def in_waiting(self):
            """
            Gibt vor, dass immer Daten bereitstehen.
            """
            return 1
    
# --------------------------------------------
# Fake list_ports wie PySerial
# --------------------------------------------

class tools:
    class list_ports:
        @staticmethod
        def comports():
            # Liefert Fake-Ports für find_serial_port()
            class Port:
                def __init__(self):
                    self.device = "Pseudo_USB"
                    self.description = "Pseudo: USB Serial Device"
                    self.hwid = "Pseudo: USB_HWID"
            return [Port()]

serial.tools = tools