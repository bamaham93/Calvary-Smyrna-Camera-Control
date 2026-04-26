import json
from pathlib import Path

from flask import Flask, render_template_string, request
from visca import ViscaCamera

app = Flask(__name__)
cam = ViscaCamera("10.238.171.114")
PRESET_NAMES_FILE = Path(__file__).with_name("preset_names.json")
DEFAULT_PRESET_RANGE = range(1, 13)


def default_preset_name(preset_num):
    return f"Preset {preset_num}"


def load_preset_names(file_path=None):
    file_path = file_path or PRESET_NAMES_FILE
    names = {preset: default_preset_name(preset) for preset in DEFAULT_PRESET_RANGE}

    if not file_path.exists():
        return names

    try:
        persisted_names = json.loads(file_path.read_text())
    except (json.JSONDecodeError, OSError):
        return names

    if not isinstance(persisted_names, dict):
        return names

    for key, value in persisted_names.items():
        try:
            preset_num = int(key)
        except (TypeError, ValueError):
            continue

        if preset_num not in DEFAULT_PRESET_RANGE:
            continue

        cleaned_value = str(value).strip()
        if cleaned_value:
            names[preset_num] = cleaned_value

    return names


def save_preset_names(names, file_path=None):
    file_path = file_path or PRESET_NAMES_FILE
    data = {str(preset): name for preset, name in names.items()}
    file_path.write_text(json.dumps(data, indent=2, sort_keys=True))


def sanitize_preset_name(name, preset_num):
    cleaned_name = name.strip()[:40]
    if not cleaned_name:
        return default_preset_name(preset_num)
    return cleaned_name


def preset_in_range(preset_num):
    return preset_num in DEFAULT_PRESET_RANGE


def safe_recall(preset):
    cam.stop()
    cam.zoom_stop()
    cam.preset_recall(preset)


preset_names = load_preset_names()


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

    cleaned_name = sanitize_preset_name(str(requested_name), num)
    preset_names[num] = cleaned_name
    save_preset_names(preset_names)
    return f"Updated preset {num} name to {cleaned_name}"


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
        "up": cam.move_up,
        "down": cam.move_down,
        "left": cam.move_left,
        "right": cam.move_right,
        "up-left": cam.move_up_left,
        "up-right": cam.move_up_right,
        "down-left": cam.move_down_left,
        "down-right": cam.move_down_right,
        "stop": cam.stop,
    }

    if direction not in moves:
        return "Invalid direction", 400

    moves[direction]()
    return f"Move {direction}"


@app.route("/")
def home():
    presets = [
        {"num": preset, "name": preset_names.get(preset, default_preset_name(preset))}
        for preset in DEFAULT_PRESET_RANGE
    ]

    return render_template_string(
        """
<!DOCTYPE html>
<html>
<head>
    <title>Camera Control</title>
    <script src="https://unpkg.com/htmx.org@1.9.12"></script>
    <style>
        body {
            font-family: sans-serif;
            background: #0f0f0f;
            color: #eee;
            margin: 0;
            padding: 16px;
        }

        h1 { margin-bottom: 10px; }

        h2 {
            margin: 12px 0 8px;
            font-size: 16px;
            color: #aaa;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .container {
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
        }

        .panel {
            background: #1a1a1a;
            border-radius: 12px;
            padding: 12px;
            flex: 1 1 280px;
            min-width: 260px;
        }

        button {
            border: none;
            border-radius: 8px;
            background: #2a2a2a;
            color: white;
            font-size: 16px;
            padding: 14px;
            cursor: pointer;
            transition: background 0.15s;
        }

        button:hover { background: #444; }
        button:active { background: #666; }

        .preset-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
            gap: 8px;
        }

        .preset-card {
            background: #111;
            border-radius: 8px;
            padding: 8px;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .preset-recall {
            height: 70px;
            font-size: 14px;
        }

        .preset-actions {
            display: grid;
            grid-template-columns: 1fr auto;
            gap: 6px;
        }

        .preset-actions input {
            background: #222;
            color: #fff;
            border: 1px solid #444;
            border-radius: 6px;
            padding: 6px;
            min-width: 0;
        }

        .preset-actions button {
            padding: 8px;
            font-size: 14px;
        }

        .preset-set-btn {
            width: 100%;
            font-size: 14px;
            padding: 8px;
            background: #305a8a;
        }

        .zoom-controls {
            display: flex;
            gap: 8px;
        }

        .zoom-controls button { flex: 1; }

        .dpad {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 8px;
            justify-items: center;
        }

        .dpad button {
            width: 70px;
            height: 70px;
            font-size: 26px;
            touch-action: none;
        }

        .center-stop { background: #aa3333; }

        #status {
            margin-top: 12px;
            font-size: 13px;
            color: #888;
        }

        @media (max-width: 600px) {
            button {
                font-size: 18px;
                padding: 18px;
            }

            .dpad button {
                width: 80px;
                height: 80px;
            }
        }
    </style>
</head>
<body>

<h1>Camera Control</h1>

<div class="container">

    <div class="panel">
        <h2>Presets</h2>
        <div class="preset-grid">
            {% for preset in presets %}
            <div class="preset-card">
                <button class="preset-recall" hx-get="/preset/{{ preset.num }}" hx-target="#status" hx-swap="innerText">{{ preset.name }}</button>
                <form class="preset-actions" hx-post="/preset/{{ preset.num }}/name" hx-target="#status" hx-swap="innerText">
                    <input type="text" name="name" value="{{ preset.name }}" maxlength="40">
                    <button type="submit">Save</button>
                </form>
                <button class="preset-set-btn" hx-post="/preset/{{ preset.num }}/set" hx-target="#status" hx-swap="innerText">Set Current View</button>
            </div>
            {% endfor %}
        </div>
    </div>

    <div class="panel">
        <h2>Pan / Tilt</h2>
        <div class="dpad">
            <button hx-get="/move/up-left" hx-trigger="mousedown, touchstart" hx-target="#status" hx-swap="innerText"
                onmouseup="htmx.ajax('GET','/move/stop',{target:'#status', swap:'innerText'})"
                ontouchend="htmx.ajax('GET','/move/stop',{target:'#status', swap:'innerText'})">↖</button>

            <button hx-get="/move/up" hx-trigger="mousedown, touchstart" hx-target="#status" hx-swap="innerText"
                onmouseup="htmx.ajax('GET','/move/stop',{target:'#status', swap:'innerText'})"
                ontouchend="htmx.ajax('GET','/move/stop',{target:'#status', swap:'innerText'})">↑</button>

            <button hx-get="/move/up-right" hx-trigger="mousedown, touchstart" hx-target="#status" hx-swap="innerText"
                onmouseup="htmx.ajax('GET','/move/stop',{target:'#status', swap:'innerText'})"
                ontouchend="htmx.ajax('GET','/move/stop',{target:'#status', swap:'innerText'})">↗</button>

            <button hx-get="/move/left" hx-trigger="mousedown, touchstart" hx-target="#status" hx-swap="innerText"
                onmouseup="htmx.ajax('GET','/move/stop',{target:'#status', swap:'innerText'})"
                ontouchend="htmx.ajax('GET','/move/stop',{target:'#status', swap:'innerText'})">←</button>

            <button class="center-stop" hx-get="/stop" hx-target="#status" hx-swap="innerText">■</button>

            <button hx-get="/move/right" hx-trigger="mousedown, touchstart" hx-target="#status" hx-swap="innerText"
                onmouseup="htmx.ajax('GET','/move/stop',{target:'#status', swap:'innerText'})"
                ontouchend="htmx.ajax('GET','/move/stop',{target:'#status', swap:'innerText'})">→</button>

            <button hx-get="/move/down-left" hx-trigger="mousedown, touchstart" hx-target="#status" hx-swap="innerText"
                onmouseup="htmx.ajax('GET','/move/stop',{target:'#status', swap:'innerText'})"
                ontouchend="htmx.ajax('GET','/move/stop',{target:'#status', swap:'innerText'})">↙</button>

            <button hx-get="/move/down" hx-trigger="mousedown, touchstart" hx-target="#status" hx-swap="innerText"
                onmouseup="htmx.ajax('GET','/move/stop',{target:'#status', swap:'innerText'})"
                ontouchend="htmx.ajax('GET','/move/stop',{target:'#status', swap:'innerText'})">↓</button>

            <button hx-get="/move/down-right" hx-trigger="mousedown, touchstart" hx-target="#status" hx-swap="innerText"
                onmouseup="htmx.ajax('GET','/move/stop',{target:'#status', swap:'innerText'})"
                ontouchend="htmx.ajax('GET','/move/stop',{target:'#status', swap:'innerText'})">↘</button>
        </div>
    </div>

    <div class="panel">
        <h2>Zoom</h2>
        <div class="zoom-controls">
            <button hx-get="/zoom/in/2" hx-target="#status" hx-swap="innerText">＋</button>
            <button hx-get="/zoom/stop" hx-target="#status" hx-swap="innerText">■</button>
            <button hx-get="/zoom/out/2" hx-target="#status" hx-swap="innerText">－</button>
        </div>
    </div>

</div>

<div id="status">Ready</div>

</body>
</html>
""",
        presets=presets,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
