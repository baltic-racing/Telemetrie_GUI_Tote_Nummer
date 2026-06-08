from Telemetrie_identifier import ID_MAP

import serial       # PySerial für serielle Kommunikation
import serial.tools.list_ports  # Für das Auflisten der verfügbaren Ports --> Nötig???
#from Pseudo_Serial_Kommunication import serial  # Pseudo-Serial für Testzwecke

import asyncio
import os
import time
import threading
from sanic import Sanic, Request
from sanic.response import json, html, file, text

app = Sanic("TY_Interface")

telemetry_data = {}
global test_state
test_state = 1
global MAX_LEN
MAX_LEN = 1  # Maximale Länge der Telemetriedatenarrays

incoming_data = bytearray()



# ------------------------------------------------------------
# 🔌 Funktion zum finden des verwendeten USB-Ports
# ------------------------------------------------------------
def find_serial_port(keyword: str = "") -> str | None:
    """
    Sucht automatisch nach einem passenden seriellen Port.
    Optional kann ein 'keyword' (z. B. 'USB', 'CP2102', 'Arduino', 'FTDI', 'CH340') angegeben werden.
    Gibt den Gerätenamen (z. B. 'COM3' oder '/dev/ttyUSB0') zurück oder None, wenn kein Gerät gefunden wurde.
    """
    ports = list(serial.tools.list_ports.comports())

    if not ports:
        print("❌ Kein serieller Port gefunden! Bitte Modul anstecken.")
        return None

    for port in ports:
        description = port.description or ""
        device = port.device or ""
        hwid = port.hwid or ""
        if (keyword.lower() in description.lower()) or (keyword.lower() in device.lower()) or (keyword.lower() in hwid.lower()):
            print(f"✅ USB-Port gefunden: {device} ({description})")
            return device

    print(f"⚠️ Kein passender Port gefunden. Nehme Standard: {ports[0].device} ({ports[0].description})")
    return ports[0].device

mode = "serial"  # Standardmodus

# --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# 🧠 Kontinuierlicher USB-Reader in Thread
# ------------------------------------------------------------
def robust_read_serial(port_keyword="USB", baudrate=115200):
    global telemetry_data
    global test_state

    buffer = bytearray()

    while True:
        port = find_serial_port(port_keyword)
        if not port:
            print("❌ Kein USB-Port gefunden, versuche in 1s erneut...")
            time.sleep(1)
            continue

        try:
            with serial.Serial(port, baudrate, timeout=0.1) as ser:
                print(f"✅ Verbunden mit {port}, starte Leseschleife")
                test_state = 0
                buffer.clear()

                while True:
                    try:
                        incoming = ser.read(ser.in_waiting or 1)

                        if not incoming:
                            continue

                        buffer.extend(incoming)

                        # 🔁 So lange vollständige Frames im Buffer sind
                        while True:
                            if 0x02 not in buffer:
                                print("⚠️ Kein Startbyte im Buffer, verwerfe Müll")
                                break

                            # 1️⃣ Startbyte suchen
                            try:
                                start = buffer.index(0x02)
                            except ValueError:
                                # Kein Startbyte → Müll verwerfen
                                buffer.clear()
                                break

                            # 2️⃣ Alles vor Startbyte verwerfen
                            if start > 0:
                                del buffer[:start]

                            # 3️⃣ Mindestlänge prüfen (AA TYPE LEN)
                            if len(buffer) < 3:
                                break

                            payload_len = buffer[2]
                            frame_len = 3 + payload_len + 1  # Header + Payload + Endbyte

                            # 4️⃣ Warten bis komplettes Frame da ist
                            if len(buffer) < frame_len:
                                break

                            """ # 5️⃣ Endbyte prüfen
                            if buffer[frame_len - 1] != 0x55:
                                # Ungültiges Frame → 1 Byte verwerfen
                                del buffer[0]
                                continue """

                            # 6️⃣ Gültiges Paket extrahieren
                            packet = buffer[:frame_len]
                            del buffer[:frame_len]

                            usb_data = parse_USB_packet(packet)
                            if usb_data is None:
                                continue

                        # 7️⃣ Payload verarbeiten
                        parse_id_value(usb_data["payload"])
                        print("📊 Aktuelle Telemetrie:", telemetry_data)

                    except serial.SerialException:
                        print("❌ Fehler beim Lesen, Verbindung verloren")
                        test_state = 1
                        break

        except serial.SerialException as e:
            print(f"❌ Fehler beim Öffnen von {port}: {e}")

        print("ℹ️ Warte 1s und versuche erneut, USB-Verbindung aufzubauen...")
        time.sleep(1)


def read_tarvos_continuously(port, baudrate=115200):
    global telemetry_data
    buffer = bytearray()

    try:
        with serial.Serial(port, baudrate, timeout=0.1) as ser:
            print(f"📡 Starte kontinuierliches Lesen über Funk von {port} ...")

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
async def get_usb_status(request):
    global status
    status = {}

    if test_state == 1:
        status = {"USB_Status": "Disconnected"}
    else:
        status = {"USB_Status": "Connected"}
    return json(status)

@app.get("/id_map")
def get_id_map(request):
    return json(ID_MAP)


# ------------------------------------------------------------
# ⚙️ Dekodierung der via USB übermittelten Daten
# ------------------------------------------------------------
def parse_USB_packet(packet: bytearray):
    if len(packet) < 5:
        print("💣Datenpacket ist zu kurz")
        return None  # Ungültiges Paket / zu kurz
    
    """ if packet[0] != 0xAA or packet[-1] != 0x55:
        print("💣Daten haben Überprüfung nicht überstanden - Prüfsumme")
        return None  # Ungültiges Start- oder Endbyte """
    
    msg_type = packet[1]
    length = packet[2]
    payload = packet[3:-1]

    """ if len(payload) != length:
        print("💣Daten haben Überprüfung nicht überstanden - Länge")
        return None  # Längenfehler """
    
    return {
        "type": msg_type,
        "length": length,
        "payload": payload
    }

def parse_id_value(payload):
    """
    Wandelt Payload (ID-Value-Paare) in ein Dictionary mit Gruppeninformation um.
    Struktur: telemetry_data[group][name] = value
    """
    global telemetry_data
    data = {}
    
    """ if len(payload) % 2 != 0:
        print("💣Datenfehler - Ungerade Anzahl")
        return data  # Ungerade Anzahl von Bytes """
    
    for i in range(0, len(payload), 2):
        id_byte = payload[i]
        value_byte = payload[i + 1]

        info = ID_MAP.get(id_byte)
        if info:

            id_name = info["name"]
            id_group = info["group"]
        else:
            id_name = f"Unknown_ID_{id_byte}"
            id_group = "Unknown_Group"

        # Falls Gruppe nicht existiert
        if id_group not in telemetry_data:
            telemetry_data[id_group] = {}

        # Speichere Wert in der Gruppe
        if id_name not in telemetry_data[id_group]:
            telemetry_data[id_group][id_name] = []

        telemetry_data[id_group][id_name].append(value_byte)

        # Maximale Länge begrenzen
        if len(telemetry_data[id_group][id_name]) > MAX_LEN:
            telemetry_data[id_group][id_name].pop(0)

    return telemetry_data


####################################################################################################################################################################################

# ------------------------------------------------------------
# 🌐 Starte Pfad zur API
# ------------------------------------------------------------

@app.get("/")
async def index(request):
    """Statische HTML-Seite als Interface"""
    return await file("Telemetrie_GUI.html")

# ------------------------------------------------------------
# 🌐 Beispiel-API-Endpunkt
# ------------------------------------------------------------
@app.get("/status")
async def status(request):
    """Einfacher Test-Endpunkt für Sanic"""
    try:
        port = find_serial_port("USB")  # Port ermitteln
        print(f"📨 Daten werden an API übermittet, auch wenn es Müll ist :)")
        return json({"status": "ok", "Verwendeter_USB_Port": port})
    except Exception as e:
        return json({"status": "error", "message": str(e)}, status=500)


# ------------------------------------------------------------
# 🧠 Startlogik & Hauptlogik – optimiert für Windows
# ------------------------------------------------------------
if __name__ == "__main__":
    import threading

    # Starte den robusten Serial-Reader im Hintergrund
    reader_thread = threading.Thread(target=robust_read_serial, args=("USB",), daemon=True)
    reader_thread.start()
    
    """ port = find_serial_port("USB")  # Port ermitteln

    reader_thread = threading.Thread(target=read_serial_continuously, args=(port,), daemon=True)
    reader_thread.start() """

    # Sanic im "Single-Process"-Modus starten (keine Worker) - Starte Sanic API
    app.run(
    host="0.0.0.0",
    port=8000,
    debug=True,
    single_process=True  # <- Wichtig für Windows!
    )