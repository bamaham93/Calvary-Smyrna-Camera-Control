import json
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from visca import ViscaCamera

app = Flask(__name__)
cam = ViscaCamera("10.238.171.114")
CONFIG_FILE = Path(__file__).with_name("config.json")
DEFAULT_PRESET_RANGE = range(1, 13)
DEFAULT_SETTINGS = {"zoom_speed": 2, "pan_speed": 8, "tilt_speed": 8}


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


def load_config(file_path=None):
    file_path = file_path or CONFIG_FILE
    names = default_preset_names()
    settings = dict(DEFAULT_SETTINGS)

    if not file_path.exists():
        return names, settings

    try:
        persisted = json.loads(file_path.read_text())
    except (json.JSONDecodeError, OSError):
        return names, settings

    if not isinstance(persisted, dict):
        return names, settings

    persisted_names = persisted.get("preset_names", {})
    if isinstance(persisted_names, dict):
        for key, value in persisted_names.items():
            try:
                preset_num = int(key)
            except (TypeError, ValueError):
                continue

            if preset_num not in DEFAULT_PRESET_RANGE:
                continue

            cleaned_name = sanitize_preset_name(value, preset_num)
            names[preset_num] = cleaned_name

    persisted_settings = persisted.get("settings", {})
    if isinstance(persisted_settings, dict):
        settings["zoom_speed"] = sanitize_zoom_speed(persisted_settings.get("zoom_speed"))
        settings["pan_speed"] = sanitize_pan_speed(persisted_settings.get("pan_speed"))
        settings["tilt_speed"] = sanitize_tilt_speed(persisted_settings.get("tilt_speed"))

    return names, settings


def save_config(names, settings, file_path=None):
    file_path = file_path or CONFIG_FILE
    data = {
        "preset_names": {str(preset): name for preset, name in names.items()},
        "settings": {
            "zoom_speed": sanitize_zoom_speed(settings.get("zoom_speed")),
            "pan_speed": sanitize_pan_speed(settings.get("pan_speed")),
            "tilt_speed": sanitize_tilt_speed(settings.get("tilt_speed")),
        },
    }
    file_path.write_text(json.dumps(data, indent=2, sort_keys=True))


def preset_in_range(preset_num):
    return preset_num in DEFAULT_PRESET_RANGE


def safe_recall(preset):
    cam.stop(settings["pan_speed"], settings["tilt_speed"])
    cam.zoom_stop()
    cam.preset_recall(preset)


preset_names, settings = load_config()


@app.route("/preset/<int:num>")
def preset(num):
    if not preset_in_range(num):
        return "Invalid preset", 400

    safe_recall(num)
    return f"Recalled {preset_names.get(num, default_preset_name(num))}"


@app.route("/preset/<int:num>/set", methods=["POST"])
def preset_set(num):
    if not preset_in_range(num):
        return "Invalid preset", 400

    cam.preset_set(num)
    return f"Saved camera position to {preset_names.get(num, default_preset_name(num))}"


@app.route("/preset/<int:num>/name", methods=["POST"])
def preset_name(num):
    if not preset_in_range(num):
        return "Invalid preset", 400

    requested_name = request.form.get("name")
    if requested_name is None and request.is_json:
        payload = request.get_json(silent=True) or {}
        requested_name = payload.get("name")

    if requested_name is None:
        return "Name is required", 400

    cleaned_name = sanitize_preset_name(requested_name, num)
    preset_names[num] = cleaned_name
    save_config(preset_names, settings)
    return f"Updated preset {num} name to {cleaned_name}"


@app.route("/settings", methods=["POST"])
def update_settings():
    requested_zoom_speed = request.form.get("zoom_speed")
    requested_pan_speed = request.form.get("pan_speed")
    requested_tilt_speed = request.form.get("tilt_speed")

    if request.is_json:
        payload = request.get_json(silent=True) or {}
        if requested_zoom_speed is None:
            requested_zoom_speed = payload.get("zoom_speed")
        if requested_pan_speed is None:
            requested_pan_speed = payload.get("pan_speed")
        if requested_tilt_speed is None:
            requested_tilt_speed = payload.get("tilt_speed")

    if requested_zoom_speed is None:
        return "zoom_speed is required", 400
    if requested_pan_speed is None:
        return "pan_speed is required", 400
    if requested_tilt_speed is None:
        return "tilt_speed is required", 400

    settings["zoom_speed"] = sanitize_zoom_speed(requested_zoom_speed)
    settings["pan_speed"] = sanitize_pan_speed(requested_pan_speed)
    settings["tilt_speed"] = sanitize_tilt_speed(requested_tilt_speed)
    save_config(preset_names, settings)
    return (
        "Updated settings: "
        f"zoom speed {settings['zoom_speed']}, "
        f"pan speed {settings['pan_speed']}, "
        f"tilt speed {settings['tilt_speed']}"
    )


@app.route("/zoom/in/<int:speed>")
def zoom_in(speed):
    cam.zoom_in(speed)
    return f"Zoom in {speed}"


@app.route("/zoom/out/<int:speed>")
def zoom_out(speed):
    cam.zoom_out(speed)
    return f"Zoom out {speed}"


@app.route("/zoom/stop")
def zoom_stop():
    cam.zoom_stop()
    return "Zoom stopped"


@app.route("/stop")
def stop():
    cam.stop()
    cam.zoom_stop()
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

    moves[direction]()
    return f"Move {direction}"


@app.route("/position")
def position():
    try:
        return jsonify(cam.get_position_feedback())
    except (OSError, ValueError, TimeoutError):
        return jsonify({"error": "Unable to read camera position"}), 503


@app.route("/")
def home():
    presets = [
        {"num": preset, "name": preset_names.get(preset, default_preset_name(preset))}
        for preset in DEFAULT_PRESET_RANGE
    ]

    return render_template("index.html", presets=presets, settings=settings)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
