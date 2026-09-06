import json
import os
import sys
from pathlib import Path

import PyATEMMax
from flask import Flask, jsonify, render_template, request
from camera_worker import CameraWorker, TimedOut
from visca import ViscaCamera

app = Flask(__name__)
worker = CameraWorker()
atem_worker = CameraWorker()
CAMERA_TIMEOUT = 2.0
ATEM_TIMEOUT = 2.0
CONFIG_FILE = Path(__file__).with_name("config.json")
DEFAULT_PRESET_RANGE = range(1, 13)
DEFAULT_SETTINGS = {"zoom_speed": 2, "pan_speed": 8, "tilt_speed": 8, "position_speed": 5}
DEFAULT_CAMERA = {"ip": "10.238.171.114", "port": 1259}
DEFAULT_ATEM = {"ip": ""}
DEFAULT_ATEM_INPUT_RANGE = range(1, 5)
ATEM_KEYER_TYPE_DVE = 3  # PyATEMMax's ATEMKeyerTypes.dVE
# Size (0.0-1.0 fraction of frame) and position for each PIP corner,
# confirmed on real hardware via the "PIP Position Tuning" panel on
# Manage Positions (position_x=11.5, position_y=6.5 for Top Right - the
# ATEM's DVE coordinate space isn't a simple -1..1 range like size is, and
# isn't documented anywhere, so this came from direct observation rather
# than the library's docs). Mirrored across the other three corners since
# the frame is symmetric around (0, 0).
ATEM_PIP_SIZE = 0.25
ATEM_PIP_CORNERS = {
    "top-left": (-11.5, 6.5),
    "top-right": (11.5, 6.5),
    "bottom-left": (-11.5, -6.5),
    "bottom-right": (11.5, -6.5),
}
ATEM_PIP_CORNER_TOLERANCE = 0.5  # position units - for matching live state back to a named corner


def match_pip_corner(position_x, position_y):
    for corner, (target_x, target_y) in ATEM_PIP_CORNERS.items():
        if abs(position_x - target_x) <= ATEM_PIP_CORNER_TOLERANCE and abs(position_y - target_y) <= ATEM_PIP_CORNER_TOLERANCE:
            return corner
    return None


def default_preset_name(preset_num):
    return f"Preset {preset_num}"


def default_preset_names():
    return {preset: default_preset_name(preset) for preset in DEFAULT_PRESET_RANGE}


def sanitize_preset_name(name, preset_num):
    cleaned_name = str(name).strip()[:40]
    if not cleaned_name:
        return default_preset_name(preset_num)
    return cleaned_name


def sanitize_zoom_speed(speed):
    try:
        cleaned_speed = int(speed)
    except (TypeError, ValueError):
        return DEFAULT_SETTINGS["zoom_speed"]

    return max(0, min(7, cleaned_speed))


def sanitize_pan_speed(speed):
    try:
        cleaned_speed = int(speed)
    except (TypeError, ValueError):
        return DEFAULT_SETTINGS["pan_speed"]

    return max(0, min(24, cleaned_speed))


def sanitize_tilt_speed(speed):
    try:
        cleaned_speed = int(speed)
    except (TypeError, ValueError):
        return DEFAULT_SETTINGS["tilt_speed"]

    return max(0, min(20, cleaned_speed))


def sanitize_position_speed(speed):
    try:
        cleaned_speed = int(speed)
    except (TypeError, ValueError):
        return DEFAULT_SETTINGS["position_speed"]

    # Shared between the pan (0-24) and tilt (0-20) speed bytes of the
    # absolute-position command, so clamp to the tighter of the two.
    return max(0, min(20, cleaned_speed))


def sanitize_camera_ip(ip):
    cleaned_ip = str(ip).strip()
    return cleaned_ip or DEFAULT_CAMERA["ip"]


def sanitize_camera_port(port):
    try:
        cleaned_port = int(port)
    except (TypeError, ValueError):
        return DEFAULT_CAMERA["port"]

    return max(1, min(65535, cleaned_port))


def default_atem_input_name(num):
    return f"Input {num}"


def default_atem_input_names():
    return {num: default_atem_input_name(num) for num in DEFAULT_ATEM_INPUT_RANGE}


def sanitize_atem_input_name(name, num):
    cleaned_name = str(name).strip()[:40]
    return cleaned_name or default_atem_input_name(num)


def sanitize_atem_ip(ip):
    # Empty string is a valid, meaningful value here: "no ATEM configured".
    return str(ip).strip()


def load_config(file_path=None):
    file_path = file_path or CONFIG_FILE
    names = default_preset_names()
    settings = dict(DEFAULT_SETTINGS)
    camera = dict(DEFAULT_CAMERA)
    local_positions = {}
    atem_config = dict(DEFAULT_ATEM)
    atem_input_names = default_atem_input_names()

    if not file_path.exists():
        return names, settings, camera, local_positions, atem_config, atem_input_names

    try:
        persisted = json.loads(file_path.read_text())
    except (json.JSONDecodeError, OSError):
        return names, settings, camera, local_positions, atem_config, atem_input_names

    if not isinstance(persisted, dict):
        return names, settings, camera, local_positions, atem_config, atem_input_names

    persisted_local_positions = persisted.get("local_positions", {})
    if isinstance(persisted_local_positions, dict):
        for key, value in persisted_local_positions.items():
            try:
                position_num = int(key)
            except (TypeError, ValueError):
                continue

            if position_num in DEFAULT_PRESET_RANGE or not isinstance(value, dict):
                continue

            try:
                local_positions[position_num] = {
                    "pan": int(value["pan"]),
                    "tilt": int(value["tilt"]),
                    "zoom": int(value["zoom"]),
                }
            except (KeyError, TypeError, ValueError):
                continue

    persisted_names = persisted.get("preset_names", {})
    if isinstance(persisted_names, dict):
        for key, value in persisted_names.items():
            try:
                preset_num = int(key)
            except (TypeError, ValueError):
                continue

            if preset_num not in DEFAULT_PRESET_RANGE and preset_num not in local_positions:
                continue

            cleaned_name = sanitize_preset_name(value, preset_num)
            names[preset_num] = cleaned_name

    persisted_settings = persisted.get("settings", {})
    if isinstance(persisted_settings, dict):
        settings["zoom_speed"] = sanitize_zoom_speed(persisted_settings.get("zoom_speed"))
        settings["pan_speed"] = sanitize_pan_speed(persisted_settings.get("pan_speed"))
        settings["tilt_speed"] = sanitize_tilt_speed(persisted_settings.get("tilt_speed"))
        settings["position_speed"] = sanitize_position_speed(persisted_settings.get("position_speed"))

    persisted_camera = persisted.get("camera", {})
    if isinstance(persisted_camera, dict):
        camera["ip"] = sanitize_camera_ip(persisted_camera.get("ip", camera["ip"]))
        camera["port"] = sanitize_camera_port(persisted_camera.get("port", camera["port"]))

    persisted_atem = persisted.get("atem", {})
    if isinstance(persisted_atem, dict):
        atem_config["ip"] = sanitize_atem_ip(persisted_atem.get("ip", atem_config["ip"]))

    persisted_atem_names = persisted.get("atem_input_names", {})
    if isinstance(persisted_atem_names, dict):
        for key, value in persisted_atem_names.items():
            try:
                input_num = int(key)
            except (TypeError, ValueError):
                continue

            if input_num not in DEFAULT_ATEM_INPUT_RANGE:
                continue

            atem_input_names[input_num] = sanitize_atem_input_name(value, input_num)

    return names, settings, camera, local_positions, atem_config, atem_input_names


def save_config(names, settings, camera, local_positions, atem_config, atem_input_names, file_path=None):
    file_path = file_path or CONFIG_FILE
    data = {
        "preset_names": {str(preset): name for preset, name in names.items()},
        "settings": {
            "zoom_speed": sanitize_zoom_speed(settings.get("zoom_speed")),
            "pan_speed": sanitize_pan_speed(settings.get("pan_speed")),
            "tilt_speed": sanitize_tilt_speed(settings.get("tilt_speed")),
            "position_speed": sanitize_position_speed(settings.get("position_speed")),
        },
        "camera": {
            "ip": sanitize_camera_ip(camera.get("ip")),
            "port": sanitize_camera_port(camera.get("port")),
        },
        "local_positions": {
            str(num): {"pan": position["pan"], "tilt": position["tilt"], "zoom": position["zoom"]}
            for num, position in local_positions.items()
        },
        "atem": {
            "ip": sanitize_atem_ip(atem_config.get("ip")),
        },
        "atem_input_names": {str(num): name for num, name in atem_input_names.items()},
    }
    file_path.write_text(json.dumps(data, indent=2, sort_keys=True))


def is_camera_preset(num):
    return num in DEFAULT_PRESET_RANGE


def is_local_position(num):
    return num in local_positions


def preset_exists(num):
    return is_camera_preset(num) or is_local_position(num)


def next_local_position_number():
    existing = list(DEFAULT_PRESET_RANGE) + list(local_positions.keys())
    return max(existing) + 1


def safe_recall(preset):
    cam.stop(settings["pan_speed"], settings["tilt_speed"])
    cam.zoom_stop()
    cam.preset_recall(preset)


def recall_local_position(num):
    position = local_positions[num]
    cam.stop(settings["pan_speed"], settings["tilt_speed"])
    cam.zoom_stop()
    cam.move_to_position(
        position["pan"],
        position["tilt"],
        position["zoom"],
        pan_speed=settings["position_speed"],
        tilt_speed=settings["position_speed"],
    )


def capture_local_position(num):
    feedback = cam.get_position_feedback()
    local_positions[num] = {
        "pan": feedback["pan"],
        "tilt": feedback["tilt"],
        "zoom": feedback["zoom"],
    }
    save_config(preset_names, settings, camera, local_positions, atem_config, atem_input_names)


def create_and_capture_local_position(requested_name):
    # Assigning the number and capturing the position happen together on
    # the worker thread so two concurrent "Add Position" requests can't
    # race and grab the same number.
    num = next_local_position_number()
    capture_local_position(num)
    preset_names[num] = sanitize_preset_name(requested_name or default_preset_name(num), num)
    save_config(preset_names, settings, camera, local_positions, atem_config, atem_input_names)
    return num


preset_names, settings, camera, local_positions, atem_config, atem_input_names = load_config()
cam = ViscaCamera(camera["ip"], port=camera["port"])

atem = PyATEMMax.ATEMMax()


def connect_atem(ip):
    """(Re)connect to the ATEM switcher. A blank IP means "not configured" -
    skip connecting entirely rather than pointing at a meaningless address.
    connect() itself is non-blocking; PyATEMMax manages its own background
    threads and automatic reconnection from here on."""
    atem.disconnect()
    if ip:
        atem.connect(ip)


connect_atem(atem_config["ip"])


@app.route("/preset/<int:num>")
def preset(num):
    if not preset_exists(num):
        return "Invalid preset", 400

    recall_job = recall_local_position if is_local_position(num) else safe_recall
    try:
        worker.submit(recall_job, num, timeout=CAMERA_TIMEOUT)
    except TimedOut:
        return jsonify({"error": "Camera did not respond in time"}), 503

    return f"Recalled {preset_names.get(num, default_preset_name(num))}"


@app.route("/preset/<int:num>/set", methods=["POST"])
def preset_set(num):
    if not preset_exists(num):
        return "Invalid preset", 400

    try:
        if is_local_position(num):
            worker.submit(capture_local_position, num, timeout=CAMERA_TIMEOUT)
        else:
            worker.submit(cam.preset_set, num, timeout=CAMERA_TIMEOUT)
    except TimedOut:
        return jsonify({"error": "Camera did not respond in time"}), 503

    return f"Saved camera position to {preset_names.get(num, default_preset_name(num))}"


@app.route("/preset/<int:num>/name", methods=["POST"])
def preset_name(num):
    if not preset_exists(num):
        return "Invalid preset", 400

    requested_name = request.form.get("name")
    if requested_name is None and request.is_json:
        payload = request.get_json(silent=True) or {}
        requested_name = payload.get("name")

    if requested_name is None:
        return "Name is required", 400

    cleaned_name = sanitize_preset_name(requested_name, num)
    preset_names[num] = cleaned_name
    save_config(preset_names, settings, camera, local_positions, atem_config, atem_input_names)
    return f"Updated preset {num} name to {cleaned_name}"


@app.route("/position/local", methods=["POST"])
def create_local_position():
    requested_name = request.form.get("name")
    if requested_name is None and request.is_json:
        payload = request.get_json(silent=True) or {}
        requested_name = payload.get("name")

    try:
        num = worker.submit(create_and_capture_local_position, requested_name, timeout=CAMERA_TIMEOUT)
    except TimedOut:
        return jsonify({"error": "Camera did not respond in time"}), 503
    except (OSError, ValueError, TimeoutError):
        return jsonify({"error": "Unable to read camera position"}), 503

    return jsonify({"num": num, "name": preset_names[num]})


@app.route("/position/local/<int:num>/delete", methods=["POST"])
def delete_local_position(num):
    if not is_local_position(num):
        return "Invalid local position", 400

    del local_positions[num]
    preset_names.pop(num, None)
    save_config(preset_names, settings, camera, local_positions, atem_config, atem_input_names)
    return f"Deleted position {num}"


@app.route("/position/goto", methods=["POST"])
def goto_position():
    payload = request.get_json(silent=True) if request.is_json else None
    payload = payload or request.form

    try:
        pan = int(payload.get("pan"))
        tilt = int(payload.get("tilt"))
        zoom = int(payload.get("zoom"))
    except (TypeError, ValueError):
        return "pan, tilt, and zoom are required integers", 400

    def move():
        cam.move_to_position(pan, tilt, zoom, settings["position_speed"], settings["position_speed"])

    try:
        worker.submit(move, timeout=CAMERA_TIMEOUT)
    except TimedOut:
        return jsonify({"error": "Camera did not respond in time"}), 503
    except ValueError as exc:
        return str(exc), 400

    return f"Moving to pan={pan}, tilt={tilt}, zoom={zoom}"


@app.route("/settings", methods=["POST"])
def update_settings():
    requested_zoom_speed = request.form.get("zoom_speed")
    requested_pan_speed = request.form.get("pan_speed")
    requested_tilt_speed = request.form.get("tilt_speed")
    requested_position_speed = request.form.get("position_speed")
    requested_camera_ip = request.form.get("camera_ip")
    requested_camera_port = request.form.get("camera_port")
    requested_atem_ip = request.form.get("atem_ip")

    if request.is_json:
        payload = request.get_json(silent=True) or {}
        if requested_zoom_speed is None:
            requested_zoom_speed = payload.get("zoom_speed")
        if requested_pan_speed is None:
            requested_pan_speed = payload.get("pan_speed")
        if requested_tilt_speed is None:
            requested_tilt_speed = payload.get("tilt_speed")
        if requested_position_speed is None:
            requested_position_speed = payload.get("position_speed")
        if requested_camera_ip is None:
            requested_camera_ip = payload.get("camera_ip")
        if requested_camera_port is None:
            requested_camera_port = payload.get("camera_port")
        if requested_atem_ip is None:
            requested_atem_ip = payload.get("atem_ip")

    if requested_zoom_speed is None:
        return "zoom_speed is required", 400
    if requested_pan_speed is None:
        return "pan_speed is required", 400
    if requested_tilt_speed is None:
        return "tilt_speed is required", 400
    if requested_position_speed is None:
        return "position_speed is required", 400
    if requested_camera_ip is None:
        return "camera_ip is required", 400
    if requested_camera_port is None:
        return "camera_port is required", 400

    settings["zoom_speed"] = sanitize_zoom_speed(requested_zoom_speed)
    settings["pan_speed"] = sanitize_pan_speed(requested_pan_speed)
    settings["tilt_speed"] = sanitize_tilt_speed(requested_tilt_speed)
    settings["position_speed"] = sanitize_position_speed(requested_position_speed)
    camera["ip"] = sanitize_camera_ip(requested_camera_ip)
    camera["port"] = sanitize_camera_port(requested_camera_port)
    cam.set_target(camera["ip"], camera["port"])

    # atem_ip is optional - a missing field leaves the current value alone,
    # rather than resetting an already-configured switcher's address.
    new_atem_ip = sanitize_atem_ip(requested_atem_ip if requested_atem_ip is not None else atem_config["ip"])
    if new_atem_ip != atem_config["ip"]:
        atem_config["ip"] = new_atem_ip
        connect_atem(new_atem_ip)

    save_config(preset_names, settings, camera, local_positions, atem_config, atem_input_names)
    return (
        "Updated settings: "
        f"zoom speed {settings['zoom_speed']}, "
        f"pan speed {settings['pan_speed']}, "
        f"tilt speed {settings['tilt_speed']}, "
        f"position recall speed {settings['position_speed']}, "
        f"camera {camera['ip']}:{camera['port']}, "
        f"ATEM {atem_config['ip'] or '(not configured)'}"
    )


@app.route("/atem/state")
def atem_state():
    if not atem.connected:
        return jsonify(
            {
                "connected": False,
                "program": None,
                "preview": None,
                "model": None,
                "pip_on": False,
                "pip_source": None,
                "pip_corner": None,
            }
        )

    pip_keyer = atem.keyer[0][0]
    pip_dve = atem.key[0][0].dVE
    return jsonify(
        {
            "connected": True,
            "program": atem.programInput[0].videoSource.value,
            "preview": atem.previewInput[0].videoSource.value,
            "model": atem.atemModel or None,
            "pip_on": pip_keyer.onAir.enabled,
            "pip_source": pip_keyer.fillSource.value,
            "pip_corner": match_pip_corner(pip_dve.position.x, pip_dve.position.y),
        }
    )


@app.route("/atem/program/<int:source>", methods=["POST"])
def atem_set_program(source):
    if not atem.connected:
        return jsonify({"error": "ATEM switcher is not connected"}), 503

    try:
        atem_worker.submit(atem.setProgramInputVideoSource, 0, source, timeout=ATEM_TIMEOUT)
    except TimedOut:
        return jsonify({"error": "ATEM did not respond in time"}), 503

    return f"Program set to {atem_input_names.get(source, default_atem_input_name(source))}"


@app.route("/atem/cut", methods=["POST"])
def atem_cut():
    if not atem.connected:
        return jsonify({"error": "ATEM switcher is not connected"}), 503

    try:
        atem_worker.submit(atem.execCutME, 0, timeout=ATEM_TIMEOUT)
    except TimedOut:
        return jsonify({"error": "ATEM did not respond in time"}), 503

    return "Cut"


@app.route("/atem/auto", methods=["POST"])
def atem_auto():
    if not atem.connected:
        return jsonify({"error": "ATEM switcher is not connected"}), 503

    try:
        atem_worker.submit(atem.execAutoME, 0, timeout=ATEM_TIMEOUT)
    except TimedOut:
        return jsonify({"error": "ATEM did not respond in time"}), 503

    return "Auto transition"


@app.route("/atem/ftb", methods=["POST"])
def atem_ftb():
    if not atem.connected:
        return jsonify({"error": "ATEM switcher is not connected"}), 503

    try:
        atem_worker.submit(atem.execFadeToBlackME, 0, timeout=ATEM_TIMEOUT)
    except TimedOut:
        return jsonify({"error": "ATEM did not respond in time"}), 503

    return "Fade to black"


def set_pip_dve(position_x, position_y, size_x, size_y):
    atem.setKeyerType(0, 0, ATEM_KEYER_TYPE_DVE)
    atem.setKeyerMasked(0, 0, False)
    atem.setKeyDVESizeX(0, 0, size_x)
    atem.setKeyDVESizeY(0, 0, size_y)
    atem.setKeyDVEPositionX(0, 0, position_x)
    atem.setKeyDVEPositionY(0, 0, position_y)


def move_pip_to_corner(position_x, position_y):
    set_pip_dve(position_x, position_y, ATEM_PIP_SIZE, ATEM_PIP_SIZE)


@app.route("/atem/pip/raw", methods=["POST"])
def atem_pip_raw():
    """Set arbitrary PIP position/size directly - a tuning tool for finding
    the right numbers for ATEM_PIP_CORNERS, not needed for normal use."""
    payload = request.get_json(silent=True) if request.is_json else None
    payload = payload or request.form

    try:
        position_x = float(payload.get("position_x"))
        position_y = float(payload.get("position_y"))
        size_x = float(payload.get("size_x", ATEM_PIP_SIZE))
        size_y = float(payload.get("size_y", ATEM_PIP_SIZE))
    except (TypeError, ValueError):
        return "position_x and position_y are required numbers (size_x/size_y optional)", 400

    if not atem.connected:
        return jsonify({"error": "ATEM switcher is not connected"}), 503

    try:
        atem_worker.submit(set_pip_dve, position_x, position_y, size_x, size_y, timeout=ATEM_TIMEOUT)
    except TimedOut:
        return jsonify({"error": "ATEM did not respond in time"}), 503

    return f"PIP set to position=({position_x}, {position_y}) size=({size_x}, {size_y})"


@app.route("/atem/pip/corner/<corner>", methods=["POST"])
def atem_pip_corner(corner):
    if corner not in ATEM_PIP_CORNERS:
        return "Invalid corner", 400
    if not atem.connected:
        return jsonify({"error": "ATEM switcher is not connected"}), 503

    position_x, position_y = ATEM_PIP_CORNERS[corner]
    try:
        atem_worker.submit(move_pip_to_corner, position_x, position_y, timeout=ATEM_TIMEOUT)
    except TimedOut:
        return jsonify({"error": "ATEM did not respond in time"}), 503

    return f"PIP moved to {corner}"


@app.route("/atem/pip/source/<int:source>", methods=["POST"])
def atem_pip_source(source):
    if not atem.connected:
        return jsonify({"error": "ATEM switcher is not connected"}), 503

    try:
        atem_worker.submit(atem.setKeyerFillSource, 0, 0, source, timeout=ATEM_TIMEOUT)
    except TimedOut:
        return jsonify({"error": "ATEM did not respond in time"}), 503

    return f"PIP source set to {atem_input_names.get(source, default_atem_input_name(source))}"


@app.route("/atem/pip/on", methods=["POST"])
def atem_pip_on():
    if not atem.connected:
        return jsonify({"error": "ATEM switcher is not connected"}), 503

    try:
        atem_worker.submit(atem.setKeyerOnAirEnabled, 0, 0, True, timeout=ATEM_TIMEOUT)
    except TimedOut:
        return jsonify({"error": "ATEM did not respond in time"}), 503

    return "PIP on"


@app.route("/atem/pip/off", methods=["POST"])
def atem_pip_off():
    if not atem.connected:
        return jsonify({"error": "ATEM switcher is not connected"}), 503

    try:
        atem_worker.submit(atem.setKeyerOnAirEnabled, 0, 0, False, timeout=ATEM_TIMEOUT)
    except TimedOut:
        return jsonify({"error": "ATEM did not respond in time"}), 503

    return "PIP off"


@app.route("/atem/input/<int:num>/name", methods=["POST"])
def atem_input_name(num):
    if num not in DEFAULT_ATEM_INPUT_RANGE:
        return "Invalid input", 400

    requested_name = request.form.get("name")
    if requested_name is None and request.is_json:
        payload = request.get_json(silent=True) or {}
        requested_name = payload.get("name")

    if requested_name is None:
        return "Name is required", 400

    cleaned_name = sanitize_atem_input_name(requested_name, num)
    atem_input_names[num] = cleaned_name
    save_config(preset_names, settings, camera, local_positions, atem_config, atem_input_names)
    return f"Updated input {num} name to {cleaned_name}"


@app.route("/zoom/in/<int:speed>")
def zoom_in(speed):
    try:
        worker.submit(cam.zoom_in, speed, timeout=CAMERA_TIMEOUT)
    except TimedOut:
        return jsonify({"error": "Camera did not respond in time"}), 503
    return f"Zoom in {speed}"


@app.route("/zoom/out/<int:speed>")
def zoom_out(speed):
    try:
        worker.submit(cam.zoom_out, speed, timeout=CAMERA_TIMEOUT)
    except TimedOut:
        return jsonify({"error": "Camera did not respond in time"}), 503
    return f"Zoom out {speed}"


@app.route("/zoom/stop")
def zoom_stop():
    try:
        worker.submit(cam.zoom_stop, timeout=CAMERA_TIMEOUT)
    except TimedOut:
        return jsonify({"error": "Camera did not respond in time"}), 503
    return "Zoom stopped"


@app.route("/stop")
def stop():
    def stop_all():
        cam.stop()
        cam.zoom_stop()

    try:
        worker.submit(stop_all, timeout=CAMERA_TIMEOUT)
    except TimedOut:
        return jsonify({"error": "Camera did not respond in time"}), 503
    return "Stopped all"


@app.route("/move/<direction>")
def move(direction):
    moves = {
        "up": lambda: cam.move_up(settings["pan_speed"], settings["tilt_speed"]),
        "down": lambda: cam.move_down(settings["pan_speed"], settings["tilt_speed"]),
        "left": lambda: cam.move_left(settings["pan_speed"], settings["tilt_speed"]),
        "right": lambda: cam.move_right(settings["pan_speed"], settings["tilt_speed"]),
        "up-left": lambda: cam.move_up_left(settings["pan_speed"], settings["tilt_speed"]),
        "up-right": lambda: cam.move_up_right(settings["pan_speed"], settings["tilt_speed"]),
        "down-left": lambda: cam.move_down_left(settings["pan_speed"], settings["tilt_speed"]),
        "down-right": lambda: cam.move_down_right(settings["pan_speed"], settings["tilt_speed"]),
        "stop": cam.stop,
    }

    if direction not in moves:
        return "Invalid direction", 400

    try:
        worker.submit(moves[direction], timeout=CAMERA_TIMEOUT)
    except TimedOut:
        return jsonify({"error": "Camera did not respond in time"}), 503
    return f"Move {direction}"


@app.route("/position")
def position():
    try:
        result = worker.submit(cam.get_position_feedback, timeout=CAMERA_TIMEOUT)
    except TimedOut:
        return jsonify({"error": "Unable to read camera position"}), 503
    except (OSError, ValueError, TimeoutError):
        return jsonify({"error": "Unable to read camera position"}), 503
    return jsonify(result)


@app.route("/")
def home():
    all_preset_numbers = list(DEFAULT_PRESET_RANGE) + sorted(local_positions)
    presets = [
        {"num": num, "name": preset_names.get(num, default_preset_name(num))}
        for num in all_preset_numbers
    ]
    atem_inputs = [
        {"num": num, "name": atem_input_names.get(num, default_atem_input_name(num))}
        for num in DEFAULT_ATEM_INPUT_RANGE
    ]

    return render_template(
        "index.html",
        presets=presets,
        settings=settings,
        camera=camera,
        atem_config=atem_config,
        atem_inputs=atem_inputs,
    )


@app.route("/positions")
def positions_page():
    camera_presets = [
        {"num": num, "name": preset_names.get(num, default_preset_name(num))}
        for num in DEFAULT_PRESET_RANGE
    ]
    local_position_list = [
        {"num": num, "name": preset_names.get(num, default_preset_name(num)), **local_positions[num]}
        for num in sorted(local_positions)
    ]

    return render_template(
        "positions.html",
        camera_presets=camera_presets,
        local_positions=local_position_list,
        settings=settings,
    )


@app.route("/help")
def help_page():
    return render_template("help.html", base_url=request.host_url.rstrip("/"))


def parse_host_port(argv):
    """Accept `app.py [runserver] [HOST:PORT|PORT]`, falling back to the
    HOST/PORT env vars and finally 0.0.0.0:5000."""
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 5000))

    args = argv[1:]
    if args and args[0] == "runserver":
        args = args[1:]

    if args:
        addr = args[0]
        if ":" in addr:
            host, port_str = addr.rsplit(":", 1)
            port = int(port_str)
        else:
            port = int(addr)

    return host, port


if __name__ == "__main__":
    host, port = parse_host_port(sys.argv)
    # use_reloader=False avoids Werkzeug's debug-mode child process, which
    # can outlive a killed/closed terminal and keep the port bound.
    # threaded=True lets Flask accept requests concurrently; actual camera
    # I/O is still serialized through CameraWorker's single queue.
    app.run(host=host, port=port, debug=True, use_reloader=False, threaded=True)
