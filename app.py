import json
from pathlib import Path

from flask import Flask, render_template_string, request
from visca import ViscaCamera

app = Flask(__name__)
cam = ViscaCamera("10.238.171.114")
CONFIG_FILE = Path(__file__).with_name("config.json")
DEFAULT_PRESET_RANGE = range(1, 13)
DEFAULT_SETTINGS = {"zoom_speed": 2}


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

    return names, settings


def save_config(names, settings, file_path=None):
    file_path = file_path or CONFIG_FILE
    data = {
        "preset_names": {str(preset): name for preset, name in names.items()},
        "settings": {"zoom_speed": sanitize_zoom_speed(settings.get("zoom_speed"))},
    }
    file_path.write_text(json.dumps(data, indent=2, sort_keys=True))


def preset_in_range(preset_num):
    return preset_num in DEFAULT_PRESET_RANGE


def safe_recall(preset):
    cam.stop()
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
    if requested_zoom_speed is None and request.is_json:
        payload = request.get_json(silent=True) or {}
        requested_zoom_speed = payload.get("zoom_speed")

    if requested_zoom_speed is None:
        return "zoom_speed is required", 400

    settings["zoom_speed"] = sanitize_zoom_speed(requested_zoom_speed)
    save_config(preset_names, settings)
    return f"Updated settings: zoom speed {settings['zoom_speed']}"


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

        .header-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
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

        .preset-edit-btn {
            width: 100%;
            font-size: 13px;
            padding: 8px;
            background: #424242;
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

        .modal-overlay {
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.7);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 100;
        }

        .modal-overlay.open { display: flex; }

        .modal {
            width: min(90vw, 420px);
            background: #1b1b1b;
            border: 1px solid #333;
            border-radius: 10px;
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .modal label {
            color: #ccc;
            font-size: 14px;
        }

        .modal input {
            background: #222;
            color: #fff;
            border: 1px solid #444;
            border-radius: 6px;
            padding: 10px;
            width: 100%;
            box-sizing: border-box;
            font-size: 15px;
        }

        .modal-actions {
            display: flex;
            justify-content: flex-end;
            gap: 8px;
        }

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

<div class="header-row">
    <h1>Camera Control</h1>
    <button type="button" onclick="openSettingsModal()">Settings</button>
</div>

<div class="container">

    <div class="panel">
        <h2>Presets</h2>
        <div class="preset-grid">
            {% for preset in presets %}
            <div class="preset-card">
                <button id="preset-label-{{ preset.num }}" class="preset-recall" hx-get="/preset/{{ preset.num }}" hx-target="#status" hx-swap="innerText">{{ preset.name }}</button>
                <button
                    class="preset-edit-btn"
                    type="button"
                    onclick="openNameModal({{ preset.num }}, '{{ preset.name|replace("'", "&#39;") }}')"
                >Rename</button>
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
            <button hx-get="/zoom/in/{{ settings.zoom_speed }}" hx-target="#status" hx-swap="innerText">＋</button>
            <button hx-get="/zoom/stop" hx-target="#status" hx-swap="innerText">■</button>
            <button hx-get="/zoom/out/{{ settings.zoom_speed }}" hx-target="#status" hx-swap="innerText">－</button>
        </div>
    </div>

</div>

<div id="name-modal-overlay" class="modal-overlay" onclick="closeModal(event, 'name-modal-overlay')">
    <div class="modal">
        <h2>Rename Preset</h2>
        <form id="name-modal-form" onsubmit="submitPresetName(event)">
            <input type="hidden" id="name-modal-preset-num" value="">
            <label for="name-modal-input">Name</label>
            <input id="name-modal-input" type="text" maxlength="40" required>
            <div class="modal-actions">
                <button type="button" onclick="closeModal(event, 'name-modal-overlay')">Cancel</button>
                <button type="submit">Save</button>
            </div>
        </form>
    </div>
</div>

<div id="settings-modal-overlay" class="modal-overlay" onclick="closeModal(event, 'settings-modal-overlay')">
    <div class="modal">
        <h2>Settings</h2>
        <form id="settings-form" onsubmit="submitSettings(event)">
            <label for="zoom-speed-input">Default Zoom Speed (0-7)</label>
            <input id="zoom-speed-input" type="number" min="0" max="7" value="{{ settings.zoom_speed }}" required>
            <div class="modal-actions">
                <button type="button" onclick="closeModal(event, 'settings-modal-overlay')">Cancel</button>
                <button type="submit">Save</button>
            </div>
        </form>
    </div>
</div>

<div id="status">Ready</div>

<script>
    function closeModal(event, modalId) {
        if (event && event.target.id !== modalId && event.target.tagName !== 'BUTTON') {
            return;
        }
        document.getElementById(modalId).classList.remove('open');
    }

    function openNameModal(presetNum, currentName) {
        document.getElementById('name-modal-preset-num').value = presetNum;
        document.getElementById('name-modal-input').value = currentName;
        document.getElementById('name-modal-overlay').classList.add('open');
    }

    function openSettingsModal() {
        document.getElementById('settings-modal-overlay').classList.add('open');
    }

    async function submitPresetName(event) {
        event.preventDefault();
        const presetNum = document.getElementById('name-modal-preset-num').value;
        const input = document.getElementById('name-modal-input');
        const params = new URLSearchParams();
        params.append('name', input.value);

        const response = await fetch(`/preset/${presetNum}/name`, {
            method: 'POST',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: params,
        });

        const text = await response.text();
        document.getElementById('status').innerText = text;

        if (response.ok) {
            document.getElementById(`preset-label-${presetNum}`).innerText = input.value.trim() || `Preset ${presetNum}`;
            document.getElementById('name-modal-overlay').classList.remove('open');
        }
    }

    async function submitSettings(event) {
        event.preventDefault();
        const zoomSpeed = document.getElementById('zoom-speed-input').value;
        const params = new URLSearchParams();
        params.append('zoom_speed', zoomSpeed);

        const response = await fetch('/settings', {
            method: 'POST',
            headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            body: params,
        });

        const text = await response.text();
        document.getElementById('status').innerText = text;

        if (response.ok) {
            window.location.reload();
        }
    }
</script>

</body>
</html>
""",
        presets=presets,
        settings=settings,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
