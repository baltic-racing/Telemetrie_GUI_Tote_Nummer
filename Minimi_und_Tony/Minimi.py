from Telemetrie_identifier import ID_MAP, FRONTEND_ID_MAP

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
raw_buffer = bytearray()

STACK_COUNT = 12
CELLS_PER_STACK = 12
USB_RAW_DEBUG = os.getenv("TELEMETRY_RAW_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")

def create_empty_stack_entry(stack_number):
    stack_entry = {
        "stack_index": stack_number,
        "stack_number": stack_number,
        "sum_voltage_v": None,
        "avg_temp_c": None,
        "max_temp_c": None,
        "min_temp_c": None,
        "ltc_temp_c": None,
        "cell_voltages_v": [None] * CELLS_PER_STACK,
        "cell_temperatures_c": [None] * CELLS_PER_STACK,
        "cells": [],
        "ts": None,
    }

    for cell_number in range(1, CELLS_PER_STACK + 1):
        stack_entry[f"cell_{cell_number:02d}_voltage_v"] = None
        stack_entry[f"cell_{cell_number:02d}_temperature_c"] = None
        stack_entry["cells"].append({
            "cell_number": cell_number,
            "voltage_v": None,
            "temperature_c": None,
        })

    return stack_entry


def ensure_stack_placeholders():
    if "Stacks" not in telemetry_data:
        telemetry_data["Stacks"] = {}

    for stack_number in range(STACK_COUNT):
        stack_name = f"Stack_{stack_number:02d}"
        if stack_name not in telemetry_data["Stacks"]:
            telemetry_data["Stacks"][stack_name] = create_empty_stack_entry(stack_number)

ensure_stack_placeholders()


def format_terminal_value(value, unit="", width=9):
    if value is None:
        text_value = "---"
    elif isinstance(value, float):
        text_value = f"{value:.3f}" if unit == "V" else f"{value:.1f}"
    else:
        text_value = str(value)

    if unit:
        text_value = f"{text_value} {unit}"

    return f"{text_value:>{width}}"


def print_stack_terminal(stack_index, stack_entry):
    print(f"\n========== Stack {stack_index:02d} ==========")
    print(f"LTC Temperatur: {format_terminal_value(stack_entry.get('ltc_temp_c'), 'degC')}")
    print(f"Summe Spannung: {format_terminal_value(stack_entry.get('sum_voltage_v'), 'V')}")
    print(
        "Temperatur min/avg/max: "
        f"{format_terminal_value(stack_entry.get('min_temp_c'), 'degC')} / "
        f"{format_terminal_value(stack_entry.get('avg_temp_c'), 'degC')} / "
        f"{format_terminal_value(stack_entry.get('max_temp_c'), 'degC')}"
    )
    print("Zellspannungen und Zelltemperaturen:")

    voltages = stack_entry.get("cell_voltages_v") or []
    temperatures = stack_entry.get("cell_temperatures_c") or []

    for cell_index in range(CELLS_PER_STACK):
        voltage = voltages[cell_index] if cell_index < len(voltages) else None
        temperature = temperatures[cell_index] if cell_index < len(temperatures) else None
        print(
            f"  Zelle {cell_index + 1:02d}: "
            f"{format_terminal_value(voltage, 'V')}   "
            f"{format_terminal_value(temperature, 'degC')}"
        )


def print_ltc_terminal():
    stacks = telemetry_data.get("Stacks", {})
    print("\n========== LTC Temperaturen ==========")
    for stack_index in range(STACK_COUNT):
        stack_name = f"Stack_{stack_index:02d}"
        ltc_temp_c = stacks.get(stack_name, {}).get("ltc_temp_c")
        print(f"  Stack {stack_index:02d}: {format_terminal_value(ltc_temp_c, 'degC')}")


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
                        if USB_RAW_DEBUG and incoming:
                            print("RAW:", incoming.hex(" "))

                        if incoming and len(incoming) > 300:
                            parse_big_stack_raw(incoming)

                        if not incoming:
                            continue

                        buffer.extend(incoming)
                        rx_bytes += len(incoming)
                        

                        # STM-Format: [TYPE][LEN][PAYLOAD...]
                        CMD_STX = 0x02  # habt ihr oben schon, ist ok

                        # STM-Format: [STX][TYPE][LEN][PAYLOAD...][CHK]
                        while True:
                            stx_pos = buffer.find(bytes([CMD_STX]))
                            if stx_pos == -1:
                                buffer.clear()
                                break
                            if stx_pos > 0:
                                del buffer[:stx_pos]

                            # STM-Format:
                            # [STX][CMD_MODE][LEN][DEVICE_SIGNATURE][MESSAGE_ID][DATA...][CHK]
                            if len(buffer) < 5:
                                break

                            cmd_mode = buffer[1]
                            payload_len = buffer[2]      # MESSAGE_ID + DATA
                            device_sig = buffer[3]

                            frame_len = 4 + payload_len + 1

                            if len(buffer) < frame_len:
                                break

                            frame = buffer[:frame_len]
                            del buffer[:frame_len]

                            chk = 0
                            for b in frame[:-1]:
                                chk ^= b

                            if chk != frame[-1]:
                                print("⚠️ Bad CHK, drop frame")
                                continue

                            if device_sig != 0xA1:
                                print("⚠️ Falsche Device Signature:", hex(device_sig))
                                continue

                            msg_type = frame[4]
                            payload = frame[5:-1]

                            if USB_RAW_DEBUG:
                                print("TYPE", hex(msg_type), "LEN", len(payload), "PAYLOAD", payload.hex(" "))

                            if msg_type == 0x40:
                                parse_stack_detail(payload)
                            elif msg_type == 0x90:
                                parse_ltc_all_stacks(payload)
                            else:
                                parse_id_value(bytes([msg_type]) + payload)

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
    return json(FRONTEND_ID_MAP)


# ------------------------------------------------------------
# âš™ï¸ Dekodierung Payload: [ID][HIGH][LOW] ...
# ------------------------------------------------------------
def parse_id_value(payload):
    global telemetry_data
    now = time.time()

    for i in range(0, len(payload), 3):
        if i + 2 >= len(payload):
            break

        id_byte = payload[i]
        high = payload[i + 1]
        low = payload[i + 2]
        raw = (high << 8) | low

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

        telemetry_data[id_group][id_name] = {
            "value": raw,
            "ts": now
        }

        if id_byte == 0x2D:
            telemetry_data[id_group][f"{id_name}_C"] = {
                "value": raw / 10.0,
                "ts": now
            }

        if id_byte == 0x28:
            telemetry_data[id_group][f"{id_name}_C"] = {
                "value": raw / 1000.0,
                "ts": now
            }

        if id_byte == 0x21:
            telemetry_data[id_group][f"{id_name}_C"] = {
                "value": raw / 1000.0,
                "ts": now
            }


def parse_ltc_all_stacks(payload):
    global telemetry_data
    now = time.time()

    expected_len = STACK_COUNT * 2
    if len(payload) != expected_len:
        print(f"⚠️ LTC-AllStacks falsche Länge: {len(payload)} statt {expected_len}")
        return

    ensure_stack_placeholders()

    idx = 0
    for stack_index in range(STACK_COUNT):
        raw = (payload[idx] << 8) | payload[idx + 1]
        idx += 2

        if raw & 0x8000:
            raw -= 0x10000

        if raw in (0x7FFF, -1, -2):
            ltc_temp_c = None
        else:
            ltc_temp_c = round(raw / 10.0, 1)

        stack_name = f"Stack_{stack_index:02d}"
        telemetry_data["Stacks"][stack_name]["ltc_temp_c"] = ltc_temp_c
        telemetry_data["Stacks"][stack_name]["ltc_ts"] = now

    print_ltc_terminal()

def parse_big_stack_raw(payload):
    global telemetry_data
    now = time.time()

    ensure_stack_placeholders()

    # pro Stack: 12 Spannungen à 2 Byte + 2 Trennbytes
    voltage_block_len = 12 * (12 * 2 + 2)

    if len(payload) < voltage_block_len:
        print("⚠️ RAW zu kurz für 12 Spannungs-Stacks:", len(payload))
        return

    v_part = payload[:voltage_block_len]
    t_part = payload[voltage_block_len:]
    temp_block_len = STACK_COUNT * CELLS_PER_STACK
    ltc_part = t_part[temp_block_len:]
    t_part = t_part[:temp_block_len]

    for stack_index in range(12):
        stack_name = f"Stack_{stack_index:02d}"

        v_offset = stack_index * 26
        voltages_raw = []

        for cell in range(12):
            idx = v_offset + cell * 2
            raw = (v_part[idx] << 8) | v_part[idx + 1]
            voltages_raw.append(raw)

        # 2 Trennbytes überspringen
        t_offset = stack_index * 12
        temps_raw = []

        for cell in range(12):
            if t_offset + cell >= len(t_part):
                temps_raw.append(None)
            else:
                raw = t_part[t_offset + cell]
                temps_raw.append(raw)

        voltages_v = [
            None if v in (0, 0xFFFF) else round(v / 1000.0, 3)
            for v in voltages_raw
        ]

        temperatures_c = [
            None if t in (None, 0x41, 0xFF) else t
            for t in temps_raw
        ]
        ltc_temp_c = None
        ltc_idx = stack_index * 2

        if ltc_idx + 1 < len(ltc_part):
            raw = ltc_part[ltc_idx] | (ltc_part[ltc_idx + 1] << 8)

            if raw & 0x8000:
                raw -= 0x10000

            if raw not in (0x7FFF, -1, -2):
                ltc_temp_c = round(raw / 10.0, 1)

        valid_v = [v for v in voltages_v if v is not None]
        valid_t = [t for t in temperatures_c if t is not None]

        stack_entry = telemetry_data["Stacks"][stack_name]
        stack_entry["cell_voltages_v"] = voltages_v
        stack_entry["cell_temperatures_c"] = temperatures_c
        if ltc_temp_c is not None:
            stack_entry["ltc_temp_c"] = ltc_temp_c
            stack_entry["ltc_ts"] = now
        stack_entry["sum_voltage_v"] = round(sum(valid_v), 3) if valid_v else None
        stack_entry["avg_temp_c"] = round(sum(valid_t) / len(valid_t), 1) if valid_t else None
        stack_entry["min_temp_c"] = min(valid_t) if valid_t else None
        stack_entry["max_temp_c"] = max(valid_t) if valid_t else None
        stack_entry["ts"] = now

        stack_entry["cells"] = []
        for i in range(12):
            stack_entry[f"cell_{i+1:02d}_voltage_v"] = voltages_v[i]
            stack_entry[f"cell_{i+1:02d}_temperature_c"] = temperatures_c[i]
            stack_entry["cells"].append({
                "cell_number": i + 1,
                "voltage_v": voltages_v[i],
                "temperature_c": temperatures_c[i],
            })

        print_stack_terminal(stack_index, stack_entry)


def parse_stack_detail(payload):
    global telemetry_data
    now = time.time()

    expected_len_old = 1 + 12 * 2 + 12 * 2      # 49 Byte
    expected_len_new = 1 + 12 * 2 + 12 * 2 + 2  # 51 Byte

    if len(payload) not in (expected_len_old, expected_len_new):
        print(f"⚠️ StackDetail falsche Länge: {len(payload)} statt {expected_len_old} oder {expected_len_new}")
        return

    has_ltc = (len(payload) == expected_len_new)

    stack_index = payload[0]
    if stack_index >= STACK_COUNT:
        print(f"StackDetail ungueltiger Stack: {stack_index}")
        return

    stack_name = f"Stack_{stack_index:02d}"

    if USB_RAW_DEBUG:
        print(f"\n=== STACK DETAIL EMPFANGEN: {stack_name} ===")
        print("RAW PAYLOAD:", payload.hex(" "))

    voltages_raw = []
    temperatures_raw = []

    idx = 1

    # 12 Zellspannungen lesen
    for _ in range(12):
        raw = (payload[idx] << 8) | payload[idx + 1]
        idx += 2
        voltages_raw.append(raw)

    # 12 Zelltemperaturen lesen
    for _ in range(12):
        raw = (payload[idx] << 8) | payload[idx + 1]
        idx += 2
        if raw & 0x8000:
            raw -= 0x10000
        temperatures_raw.append(raw)

    # LTC optional lesen
    ltc_temp_c = None
    if has_ltc:
        ltc_raw = (payload[idx] << 8) | payload[idx + 1]
        if ltc_raw & 0x8000:
            ltc_raw -= 0x10000

        if USB_RAW_DEBUG:
            print("LTC raw:", ltc_raw)

        if ltc_raw not in (0x7FFF, -1, -2):
            ltc_temp_c = round(ltc_raw / 10.0, 1)

    if USB_RAW_DEBUG:
        print("Voltages raw:", voltages_raw)
        print("Temperatures raw:", temperatures_raw)

    # Spannungen umrechnen; 0 oder 0xFFFF lieber als None behandeln
    voltages_v = [
        None if v in (0, 0xFFFF) else round(v / 10000.0, 3)
        for v in voltages_raw
    ]

    # Temperaturen umrechnen; Fehlerwerte unterdrücken
    temperatures_c = [
        None if t in (-1, -2, 0x7FFF) else round(t / 1000.0, 1)
        for t in temperatures_raw
    ]

    if USB_RAW_DEBUG:
        print("Voltages V:", voltages_v)
        print("Temperatures C:", temperatures_c)
        print("LTC C:", ltc_temp_c)

    valid_voltages = [v for v in voltages_v if v is not None]
    valid_temps = [t for t in temperatures_c if t is not None]

    sum_voltage_v = round(sum(valid_voltages), 3) if valid_voltages else None
    avg_temp_c = round(sum(valid_temps) / len(valid_temps), 1) if valid_temps else None
    max_temp_c = max(valid_temps) if valid_temps else None
    min_temp_c = min(valid_temps) if valid_temps else None

    ensure_stack_placeholders()

    old_entry = telemetry_data["Stacks"].get(stack_name, {})

    if not has_ltc:
        ltc_temp_c = old_entry.get("ltc_temp_c")

    stack_entry = {
        "stack_index": stack_index,
        "stack_number": stack_index,
        "sum_voltage_v": sum_voltage_v,
        "avg_temp_c": avg_temp_c,
        "max_temp_c": max_temp_c,
        "min_temp_c": min_temp_c,
        "ltc_temp_c": ltc_temp_c,
        "ltc_ts": now if has_ltc else old_entry.get("ltc_ts"),
        "cell_voltages_v": voltages_v,
        "cell_temperatures_c": temperatures_c,
        "cells": [],
        "ts": now
}

    for cell_idx, (voltage_v, temperature_c) in enumerate(zip(voltages_v, temperatures_c), start=1):
        stack_entry[f"cell_{cell_idx:02d}_voltage_v"] = voltage_v
        stack_entry[f"cell_{cell_idx:02d}_temperature_c"] = temperature_c
        stack_entry["cells"].append({
            "cell_number": cell_idx,
            "voltage_v": voltage_v,
            "temperature_c": temperature_c,
        })

    telemetry_data["Stacks"][stack_name] = stack_entry
    print_stack_terminal(stack_index, stack_entry)

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

@app.get("/stack/<stack_id:int>")
async def get_stack(request, stack_id: int):
    global telemetry_data

    stack_name = f"Stack_{stack_id:02d}"

    stacks = telemetry_data.get("Stacks", {})
    stack = stacks.get(stack_name)

    if not stack:
        return json({"error": f"{stack_name} nicht gefunden"}, status=404)

    compact = {
        "stack": stack_name,
        "stack_index": stack.get("stack_index"),
        "sum_voltage_v": stack.get("sum_voltage_v"),
        "avg_temp_c": stack.get("avg_temp_c"),
        "min_temp_c": stack.get("min_temp_c"),
        "max_temp_c": stack.get("max_temp_c"),
        "ts": stack.get("ts"),
    }

    return json(compact)


@app.get("/stack/detailed/<stack_id:int>")
async def get_stack_detailed(request, stack_id: int):
    global telemetry_data

    stack_name = f"Stack_{stack_id:02d}"

    stacks = telemetry_data.get("Stacks", {})
    stack = stacks.get(stack_name)

    if not stack:
        return json({"error": f"{stack_name} nicht gefunden"}, status=404)

    return json(stack)


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
