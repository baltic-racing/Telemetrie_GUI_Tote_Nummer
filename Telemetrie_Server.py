from Telemetrie_identifier import ID_MAP

import serial       # PySerial fÃ¼r serielle Kommunikation
import serial.tools.list_ports  # FÃ¼r das Auflisten der verfÃ¼gbaren Ports --> NÃ¶tig???
#from Pseudo_Serial_Kommunication import serial  # Pseudo-Serial fÃ¼r Testzwecke

import asyncio 
import os
import time
import threading
from sanic import Sanic, Request
from sanic.response import json, html, file, text

app = Sanic("TY_Interface")

CMD_STX = 0x02
CMD_ETX = 0x55

telemetry_data = {}
latenz = {}
global test_state
test_state = 1
global MAX_LEN
MAX_LEN = 1  # Maximale LÃ¤nge der Telemetriedatenarrays

incoming_data = bytearray()



# ------------------------------------------------------------
# ðŸ”Œ Funktion zum finden des verwendeten USB-Ports
# ------------------------------------------------------------
def find_serial_port(keyword: str = "") -> str | None:
    """
    Sucht automatisch nach einem passenden seriellen Port.
    Optional kann ein 'keyword' (z. B. 'USB', 'CP2102', 'Arduino', 'FTDI', 'CH340') angegeben werden.
    Gibt den Gerätenamen (z. B. 'COM3' oder '/dev/ttyUSB0') zurück oder None, wenn kein Gerät gefunden wurde.
    """
    ports = list(serial.tools.list_ports.comports())
    for p in ports:
        print(p.device, p.description, p.hwid)

    if not ports:
        print("Kein serieller Port gefunden! Bitte Modul anstecken.")
        return None

    forced_port = os.getenv("TELEMETRY_COM_PORT", "").strip()
    if forced_port:
        for port in ports:
            if forced_port.lower() == (port.device or "").lower():
                print(f"Erzwungener Port aus TELEMETRY_COM_PORT: {port.device} ({port.description})")
                return port.device
        print(f"TELEMETRY_COM_PORT={forced_port} nicht gefunden, nutze Auto-Erkennung.")

    if keyword:
        for port in ports:
            description = port.description or ""
            device = port.device or ""
            hwid = port.hwid or ""
            if (keyword.lower() in description.lower()) or (keyword.lower() in device.lower()) or (keyword.lower() in hwid.lower()):
                print(f"USB-Port gefunden: {device} ({description})")
                return device

    preferred_keywords = ("cp210", "ch340", "ftdi", "arduino", "usb serial", "ttyusb", "ttyacm")
    for port in ports:
        haystack = f"{port.description or ''} {port.device or ''} {port.hwid or ''}".lower()
        if any(k in haystack for k in preferred_keywords):
            print(f"Auto-Port gefunden: {port.device} ({port.description})")
            return port.device

    print(f"Kein passender Port gefunden. Nehme Standard: {ports[0].device} ({ports[0].description})")
    return ports[0].device

mode = "serial"  # Standardmodus

# ------------------------------------------------------------
# ðŸ§  Kontinuierlicher USB-Reader in Thread (angepasst an STM-Frame)
# ------------------------------------------------------------
def robust_read_serial(port_keyword="", baudrate=115200):
    global telemetry_data, test_state, latenz

    buffer = bytearray()
    rx_bytes = 0
    rx_frames = 0
    rate_timer = time.perf_counter()

    while True:
        port = find_serial_port(port_keyword)
        if not port:
            print("âŒ Kein USB-Port gefunden, versuche in 1s erneut...")
            time.sleep(1)
            continue

        try:
            with serial.Serial(port, baudrate, timeout=0.1) as ser:
                print(f"âœ… Verbunden mit {port}, starte Leseschleife")
                test_state = 0

                while True:
                    try:
                        incoming = ser.read(ser.in_waiting or 1)
                        print("RAW:", incoming.hex(" "))
                        if not incoming:
                            continue

                        buffer.extend(incoming)
                        rx_bytes += len(incoming)
                        

                        # STM-Format: [TYPE][LEN][PAYLOAD...]
                        CMD_STX = 0x02  # habt ihr oben schon, ist ok

                        # STM-Format: [STX][TYPE][LEN][PAYLOAD...][CHK]
                        while True:
                            # 1) Auf STX synchronisieren
                            stx_pos = buffer.find(bytes([CMD_STX]))
                            if stx_pos == -1:
                                buffer.clear()
                                break
                            if stx_pos > 0:
                                del buffer[:stx_pos]

                            # 2) Minimum: STX, TYPE, LEN
                            if len(buffer) < 3:
                                break

                            msg_type = buffer[1]
                            payload_len = buffer[2]
                            frame_len = 3 + payload_len + 1  # STX+TYPE+LEN + payload + CHK

                            if len(buffer) < frame_len:
                                break

                            frame = buffer[:frame_len]
                            del buffer[:frame_len]

                            # 3) Checksum prÃ¼fen (XOR)
                            chk = 0
                            for b in frame[:-1]:
                                chk ^= b
                            if chk != frame[-1]:
                                print("âš ï¸ Bad CHK, drop frame")
                                continue

                            payload = frame[3:-1]  # nur Payload (ohne STX/TYPE/LEN und ohne CHK)

                            print("TYPE", msg_type, "LEN", payload_len, "PAYLOAD", payload.hex(" "))
                            parse_id_value(payload)
                            rx_frames += 1
                    except serial.SerialException:
                        print("âŒ Fehler beim Lesen, versuche Verbindung neu aufzubauen")
                        test_state = 1
                        break

                    except Exception as e:
                        print("Fehler beim Lesen:", e)
                        test_state = 1
                        break

        except serial.SerialException as e:
            print(f"âŒ Fehler beim Ã–ffnen von {port}: {e}")

        print("â„¹ï¸ Warte 1s und versuche erneut, USB-Verbindung aufzubauen...")
        time.sleep(1)


# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------


def read_tarvos_continuously(port, baudrate=115200):
    global telemetry_data
    buffer = bytearray()

    try:
        with serial.Serial(port, baudrate, timeout=0.1) as ser:
            print(f"ðŸ“¡ Starte kontinuierliches Lesen Ã¼ber Funk von {port} ...")

            while True:  # dauerhaft laufen
                data = ser.read(ser.in_waiting or 1)
                if data:
                    buffer.extend(data)
    except:
        print()
# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------


@app.get("/data")
async def get_data(request):
    global telemetry_data
    return json(telemetry_data)

@app.get("/USB_status")
async def get_usb_status(request, port_keyword="USB"):
    global status
    status = {}
    port = find_serial_port(port_keyword)

    if test_state == 1:
        status = {"USB_Status": "Disconnected"}
    if test_state == 0:
        status = {"USB_Status": "Connected"}
    if port == "Pseudo_USB":
        status = {"USB_Status": "Connected with Pseudo-Serial"}
    return json(status)

@app.get("/Latenz")
async def get_latenz(request):
    global latenz
    return json(latenz)

@app.get("/id_map")
def get_id_map(request):
    return json(ID_MAP)


# ------------------------------------------------------------
# âš™ï¸ Dekodierung Payload: [ID][HIGH][LOW] ...
# ------------------------------------------------------------
def parse_id_value(payload):
    global telemetry_data
    now = time.time()

    # Je Messwert 3 Bytes: ID, High, Low
    for i in range(0, len(payload), 3):
        if i + 2 >= len(payload):
            break

        id_byte = payload[i]
        high = payload[i + 1]
        low = payload[i + 2]
        raw = (high << 8) | low

        # 0x7FFF = LTC6811 Fehlerwert → überspringen
        #if raw == 0x7FFF:
          #  print(f"⚠️ ID {hex(id_byte)}: Fehlerwert 0x7FFF empfangen (REFON nicht gesetzt?)")
           # continue

        # signed 16-bit
        if raw & 0x8000:
            raw -= 0x10000

        # signed 16-bit
        if raw & 0x8000:
            raw -= 0x10000

        info = ID_MAP.get(id_byte)
        if info:
            id_name = info["name"]
            id_group = info["group"]
        else:
            id_name = f"Unknown_ID_{id_byte}"
            id_group = "Unknown_Group"

        if id_group not in telemetry_data:
            telemetry_data[id_group] = {}

        # Standardwert speichern (Rohwert in 0.1 Einheit)
        telemetry_data[id_group][id_name] = {
            "value": raw,
            "ts": now
        }



####################################################################################################################################################################################

# ------------------------------------------------------------
# ðŸŒ Starte Pfad zur API
# ------------------------------------------------------------

@app.get("/")
async def index(request):
    """Statische HTML-Seite als Interface"""
    return await file("Telemetrie_GUI.html")

# ------------------------------------------------------------
# ðŸŒ Beispiel-API-Endpunkt
# ------------------------------------------------------------
@app.get("/status")
async def status(request):
    """Einfacher Test-Endpunkt fÃ¼r Sanic"""
    try:
        port = find_serial_port("USB")  # Port ermitteln
        print(f"ðŸ“¨ Daten werden an API Ã¼bermittet, auch wenn es MÃ¼ll ist :)")
        return json({"status": "ok", "Verwendeter_USB_Port": port})
    except Exception as e:
        return json({"status": "error", "message": str(e)}, status=500)


# ------------------------------------------------------------
# ðŸ§  Startlogik & Hauptlogik â€“ optimiert fÃ¼r Windows
# ------------------------------------------------------------
if __name__ == "__main__":
    import threading

    # Starte den robusten Serial-Reader im Hintergrund
    reader_thread = threading.Thread(target=robust_read_serial, args=("",), daemon=True)
    reader_thread.start()
    print("ðŸðŸš€ Starte Telemetrie-Server...")

    # Sanic im "Single-Process"-Modus starten (keine Worker) - Starte Sanic API
    app.static('/img', './img', '/icon', './icon')  # Statische Dateien fÃ¼r Icons und Bilder
    app.run(
    host="0.0.0.0",
    port=8000,
    debug=True,
    single_process=True  # <- Wichtig fÃ¼r Windows!
    )
