import os
import serial
from flask import Flask, Response, jsonify, request


def calcCRC(buf):
    crc = 0
    i = 1
    while i <= buf[1] + 1:
        crc += buf[i]
        i += 1
    return crc & 0xFF


def print_hex(data):
    print(" ".join(f"{b:02x}" for b in data))


def vito_meeting(ser, tx_data):
    tx_data_len = len(tx_data)
    if tx_data_len > 100:
        raise Exception("Payload too large")

    buf = bytearray(200)
    buf[0] = 0x41
    buf[1] = tx_data_len
    buf[2 : 2 + tx_data_len] = tx_data
    buf[tx_data_len + 2] = calcCRC(buf)

    ser.reset_input_buffer()
    if ser.write(buf[: tx_data_len + 3]) < tx_data_len + 3:
        raise Exception("TX: Write to tty failed")

    rec = ser.read(1)
    if not rec:
        raise Exception("RCVD No ACK on Transmission! (got nothing)")

    if rec[0] != 0x06:
        if rec[0] == 0x15:
            raise Exception("CRC ERROR REPORTED BY VITODENS(TX)!\n")
        raise Exception(f"RCVD No ACK on Transmission! (got 0x{rec[0]:02x})\n")

    frame_start = ser.read(1)
    if not frame_start or frame_start[0] != 0x41:
        raise Exception(f"RCVD No Frame Start! (got 0x{frame_start[0]:02x} if any)\n")

    frame_size = ser.read(1)
    if not frame_size:
        raise Exception("RCVD No Frame Size!\n")
    rx_data_len = frame_size[0]

    buf = bytearray(200)
    buf[0] = frame_start[0]
    buf[1] = rx_data_len

    for i in range(rx_data_len + 1):
        byte = ser.read(1)
        if not byte:
            raise Exception(
                f"Answer Frame too short! (received {i} bytes of {rx_data_len+1} expected)\n"
            )
        buf[i + 2] = byte[0]

    if calcCRC(buf[: rx_data_len + 2]) != buf[rx_data_len + 2]:
        print(buf[: rx_data_len + 2])
        print(calcCRC(buf[: rx_data_len + 2]), buf[rx_data_len + 2])
        raise Exception("Bad CRC on RX")

    return buf[2 : 2 + rx_data_len]


def vito_read(ser, location, size):
    command = bytearray(5)
    command[0] = 0x00
    command[1] = 0x01
    command[2] = (location >> 8) & 0xFF
    command[3] = location & 0xFF
    command[4] = size

    result = vito_meeting(ser, command)
    if (
        len(result) != 5 + size
        or result[0] != 0x01
        or result[1] != 0x01
        or result[2] != command[2]
        or result[3] != command[3]
        or result[4] != command[4]
    ):
        raise Exception("Invalid response")

    return result[5 : 5 + size]


def vito_write(ser, location, data):
    command = bytearray(200)

    command[0] = 0x00
    command[1] = 0x02
    command[2] = (location >> 8) & 0xFF
    command[3] = location & 0xFF
    command[4] = len(data)
    command[5:] = data

    result = vito_meeting(ser, command)

    if len(result) != 5:
        raise Exception("WRITE: Wrong RCVD Payload length!")
    elif result[2] != command[2] or result[3] != command[3]:
        raise Exception("WRITE: Wrong Adress received!")
    elif result[0] != 0x01:
        raise Exception("WRITE: Wrong Message Type received!")
    elif result[1] != 0x02:
        raise Exception("WRITE: Wrong Access Type received!")
    elif result[4] != command[4]:
        raise Exception("WRITE: Wrong Memory Size received!")


class SensorF:
    def __init__(self, location, size, divisor):
        self.location = location
        self.size = size
        self.divisor = divisor

    def read_sensor(self, tty):
        r = vito_read(tty, self.location, self.size)
        res = int.from_bytes(r, "little", signed=True)
        return res / self.divisor


class SensorS:
    def __init__(self, location, size):
        self.location = location
        self.size = size

    def read_sensor(self, tty):
        r = vito_read(tty, self.location, self.size)
        return int.from_bytes(r, "little", signed=True)


class SensorU:
    def __init__(self, location, size):
        self.location = location
        self.size = size

    def read_sensor(self, tty):
        r = vito_read(tty, self.location, self.size)
        return int.from_bytes(r, "little", signed=False)

    def write_value(self, tty, value):
        value = int(value)
        data = value.to_bytes(self.size, "little")
        vito_write(tty, self.location, data)


def mode_to_text(mode):
    return {
        0: "OFF",
        1: "Warm Water",
        2: "Heating & Warm Water",
    }.get(mode, "UNKNOWN")


def ventil_to_text(ventil):
    return {0: "Undefined", 1: "Heating", 2: "Mid Position", 3: "Warm Water"}.get(
        ventil, "UNKNOWN"
    )


sensors = {
    "deviceid": SensorU(0x00F8, 2),
    "mode": SensorU(0x2323, 1),
    "outdoor_temp_tp": SensorF(0x5525, 2, 10),
    "outdoor_temp_smooth": SensorF(0x5527, 2, 10),
    "outdoor_temp": SensorF(0x0800, 2, 10),
    "boiler_temp": SensorF(0x0802, 2, 10),
    "boiler_temp_tp": SensorF(0x0810, 2, 10),
    "boiler_target_temp": SensorF(0x555A, 2, 10),
    "flue_gas_temp": SensorF(0x0808, 2, 10),
    "ww_target_temp": SensorU(0x6300, 1),
    "ww_temp": SensorF(0x0804, 2, 10),
    "ww_temp_tp": SensorF(0x0812, 2, 10),
    "ww_offset": SensorF(0x6760, 1, 1),
    "circulation_target_temp": SensorF(0x2544, 2, 10),
    "room_temp": SensorF(0x0896, 2, 10),
    "room_target_temp": SensorF(0x2306, 1, 1),
    "reduced_room_target_temp": SensorF(0x2307, 1, 1),
    "heating_curve_level": SensorS(0x27D4, 1),
    "heating_curve_slope": SensorF(0x27D3, 1, 10),
    "heating_pump_max": SensorF(0x27E6, 1, 1),
    "heating_pump_min": SensorF(0x27E7, 1, 1),
    "starts": SensorU(0x088A, 4),
    "runtime": SensorF(0x0886, 4, 1),
    "power": SensorF(0xA38F, 1, 2),
    "three_way_valve_pos": SensorF(0x0A10, 1, 1),
    "pump_power": SensorF(0x0A3C, 1, 1),
    "flow": SensorF(0x0C24, 2, 1),
    "circ_pump": SensorU(0x6515, 1),
    "h_pump": SensorU(0x7663, 1),
    "ww_pump": SensorU(0x6513, 1),
}


class Optolink:
    def __init__(self, device):
        self.device = device

    def __enter__(self):
        self.tty = serial.Serial(
            port=self.device,
            baudrate=4800,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_EVEN,
            stopbits=serial.STOPBITS_TWO,
            timeout=5.0,
            rtscts=False,
            dsrdtr=False,
            xonxoff=False,
        )

        for _ in range(0, 10):
            self.tty.write(b"\x04")
            r = self.tty.read(1)
            if r == b"\x05":
                break
        else:
            raise Exception("Could not establish optolink connection")

        self.tty.write(b"\x16\x00\x00")
        r = self.tty.read(1)
        assert r == b"\x06", r

        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        self.tty.__exit__(exception_type, exception_value, exception_traceback)

    def get_measurements(self):
        res = {}
        for sensor_name, sensor in sensors.items():
            res[sensor_name] = sensor.read_sensor(self.tty)
        res["mode_text"] = mode_to_text(res["mode"])
        res["three_way_valve_pos_text"] = ventil_to_text(res["three_way_valve_pos"])
        return res

    def write_value(self, sensor, value):
        sensors[sensor].write_value(self.tty, value)


app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def get_measurements():
    device = os.environ.get("VITALK_DEVICE", "/dev/ttyUSB0")
    with Optolink(device) as optolink:
        if request.method == "GET":
            return jsonify(optolink.get_measurements())
        else:
            content = request.json
            optolink.write_value(content["sensor"], content["value"])
            return Response(status=204)
