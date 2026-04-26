"""
ViscaCamera class to control a camera using the VISCA protocol over UDP.
"""

import socket
import time


class ViscaCamera:
    def __init__(self, ip, port=1259, delay=0.05, timeout=1.0):
        self.addr = (ip, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.delay = delay  # command spacing
        self.timeout = timeout

    def send(self, hex_string):
        command = bytes.fromhex(hex_string)
        self.sock.sendto(command, self.addr)
        time.sleep(self.delay)

    def send_with_response(self, hex_string):
        command = bytes.fromhex(hex_string)
        self.sock.settimeout(self.timeout)
        self.sock.sendto(command, self.addr)
        data, _ = self.sock.recvfrom(1024)
        time.sleep(self.delay)
        return data

    @staticmethod
    def _decode_position_nibbles(nibbles):
        value = 0
        for nibble in nibbles:
            value = (value << 4) | (nibble & 0x0F)
        return value

    # --- Core VISCA Commands ---

    def preset_recall(self, preset):
        if not (0 <= preset <= 255):
            raise ValueError("Preset must be between 0 and 255")
        self.send(f"81 01 04 3F 02 {preset:02X} FF")

    def preset_set(self, preset):
        if not (0 <= preset <= 255):
            raise ValueError("Preset must be between 0 and 255")
        self.send(f"81 01 04 3F 01 {preset:02X} FF")

    def zoom_in(self, speed=2):
        if not (0 <= speed <= 7):
            raise ValueError("Zoom speed must be between 0 and 7")
        self.send(f"81 01 04 07 2{speed:X} FF")

    def zoom_out(self, speed=2):
        if not (0 <= speed <= 7):
            raise ValueError("Zoom speed must be between 0 and 7")
        self.send(f"81 01 04 07 3{speed:X} FF")

    def zoom_stop(self):
        self.send("81 01 04 07 00 FF")

    def stop(self, pan_speed=0, tilt_speed=0):
        self.move(pan_speed=pan_speed, tilt_speed=tilt_speed, pan="stop", tilt="stop")

    def get_pan_tilt_position(self):
        response = self.send_with_response("81 09 06 12 FF")

        if len(response) < 11 or response[0] != 0x90 or response[1] != 0x50:
            raise ValueError("Invalid pan/tilt response from camera")

        pan = self._decode_position_nibbles(response[2:6])
        tilt = self._decode_position_nibbles(response[6:10])
        return {"pan": pan, "tilt": tilt}

    def get_zoom_position(self):
        response = self.send_with_response("81 09 04 47 FF")

        if len(response) < 7 or response[0] != 0x90 or response[1] != 0x50:
            raise ValueError("Invalid zoom response from camera")

        zoom = self._decode_position_nibbles(response[2:6])
        return {"zoom": zoom}

    def get_position_feedback(self):
        pan_tilt = self.get_pan_tilt_position()
        zoom = self.get_zoom_position()
        return {
            "pan": pan_tilt["pan"],
            "tilt": pan_tilt["tilt"],
            "zoom": zoom["zoom"],
        }

    # --- Named Shots (your workflow layer) ---

    def pulpit_close(self):
        self.preset_recall(1)

    def pulpit_medium(self):
        self.preset_recall(2)

    def pulpit_wide(self):
        self.preset_recall(3)

    def piano_close(self):
        self.preset_recall(4)

    # --- Camera Movement ---

    def move(self, pan_speed=8, tilt_speed=8, pan="stop", tilt="stop"):
        pan_dirs = {
            "left": "01",
            "right": "02",
            "stop": "03",
        }

        tilt_dirs = {
            "up": "01",
            "down": "02",
            "stop": "03",
        }

        if not (0 <= pan_speed <= 24):
            raise ValueError("Pan speed must be between 0 and 24")

        if not (0 <= tilt_speed <= 20):
            raise ValueError("Tilt speed must be between 0 and 20")

        self.send(
            f"81 01 06 01 "
            f"{pan_speed:02X} {tilt_speed:02X} "
            f"{pan_dirs[pan]} {tilt_dirs[tilt]} FF"
        )

    def move_up(self, pan_speed=8, tilt_speed=8):
        self.move(pan_speed=pan_speed, tilt_speed=tilt_speed, tilt="up")

    def move_down(self, pan_speed=8, tilt_speed=8):
        self.move(pan_speed=pan_speed, tilt_speed=tilt_speed, tilt="down")

    def move_left(self, pan_speed=8, tilt_speed=8):
        self.move(pan_speed=pan_speed, tilt_speed=tilt_speed, pan="left")

    def move_right(self, pan_speed=8, tilt_speed=8):
        self.move(pan_speed=pan_speed, tilt_speed=tilt_speed, pan="right")

    def move_up_left(self, pan_speed=8, tilt_speed=8):
        self.move(pan_speed=pan_speed, tilt_speed=tilt_speed, pan="left", tilt="up")

    def move_up_right(self, pan_speed=8, tilt_speed=8):
        self.move(pan_speed=pan_speed, tilt_speed=tilt_speed, pan="right", tilt="up")

    def move_down_left(self, pan_speed=8, tilt_speed=8):
        self.move(pan_speed=pan_speed, tilt_speed=tilt_speed, pan="left", tilt="down")

    def move_down_right(self, pan_speed=8, tilt_speed=8):
        self.move(pan_speed=pan_speed, tilt_speed=tilt_speed, pan="right", tilt="down")

    # --- Cleanup ---

    def close(self):
        self.sock.close()


if __name__ == "__main__":
    cam = ViscaCamera("10.238.171.114")

    try:
        cam.pulpit_close()
    finally:
        cam.close()
