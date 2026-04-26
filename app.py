from flask import Flask, render_template_string
from visca import ViscaCamera

app = Flask(__name__)
cam = ViscaCamera("10.238.171.114")


def safe_recall(preset):
    cam.stop()
    cam.zoom_stop()
    cam.preset_recall(preset)


@app.route("/preset/<int:num>")
def preset(num):
    safe_recall(num)
    return f"Preset {num}"


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
    return render_template_string("""
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
            grid-template-columns: repeat(auto-fill, minmax(70px, 1fr));
            gap: 8px;
        }

        .preset-grid button {
            height: 70px;
            font-size: 14px;
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
            <button hx-get="/preset/1" hx-target="#status" hx-swap="innerText">1</button>
            <button hx-get="/preset/2" hx-target="#status" hx-swap="innerText">2</button>
            <button hx-get="/preset/3" hx-target="#status" hx-swap="innerText">3</button>
            <button hx-get="/preset/4" hx-target="#status" hx-swap="innerText">4</button>
            <button hx-get="/preset/5" hx-target="#status" hx-swap="innerText">5</button>
            <button hx-get="/preset/6" hx-target="#status" hx-swap="innerText">6</button>
            <button hx-get="/preset/7" hx-target="#status" hx-swap="innerText">7</button>
            <button hx-get="/preset/8" hx-target="#status" hx-swap="innerText">8</button>
            <button hx-get="/preset/9" hx-target="#status" hx-swap="innerText">9</button>
            <button hx-get="/preset/10" hx-target="#status" hx-swap="innerText">10</button>
            <button hx-get="/preset/11" hx-target="#status" hx-swap="innerText">11</button>
            <button hx-get="/preset/12" hx-target="#status" hx-swap="innerText">12</button>
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
""")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)