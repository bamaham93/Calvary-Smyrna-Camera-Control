# Calvary-Smyrna-Camera-Control

A local web app to control the livestream PTZ camera over VISCA (UDP), plus
an HTTP API so other software (FreeShow, a show-control bridge like
Bitfocus Companion, scripts) can trigger the same camera moves.

For how to *use* the app and its API - the web UI, presets vs. local
positions, the full endpoint reference, and how to wire up external
software - see the **Help** page in the running app (`/help`). This file
covers setup and development instead, to avoid the two drifting apart.

## Setup

```bash
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/python app.py runserver 0.0.0.0:3100
```

`app.py` accepts `[runserver] [HOST:PORT|PORT]`, or the `HOST`/`PORT` env
vars, defaulting to `0.0.0.0:5000` if nothing is given.

### Running on boot (macOS)

`run.sh` and `com.calvarybaptistchurch.cameracontrol.plist` set this up as
a `launchd` LaunchAgent that starts at login and restarts itself if it ever
crashes. See the comments in each file - the plist's paths need to match
wherever this repo is actually cloned.

## Configuration

Everything is persisted in `config.json` in the project root:

- `preset_names`: display names for both camera presets (1-12) and local
  positions (13+).
- `settings`: `zoom_speed` / `pan_speed` / `tilt_speed` (manual dpad and
  zoom controls), `position_speed` (used only for local-position recall
  and "Go To", since absolute-position moves are more precise at lower
  speeds than manual panning wants to be).
- `camera`: `ip` / `port` the app sends VISCA commands to. Editable from
  Settings in the UI - no code changes needed when the camera's address
  changes.
- `local_positions`: pan/tilt/zoom coordinates for positions beyond the
  camera's own onboard preset memory, captured from the camera's current
  position and replayed via VISCA's absolute-position commands.

All of the above is editable from the web UI (main page, Manage Positions,
and the Settings modal) - `config.json` isn't meant to be hand-edited
during normal use.

## Project structure

- `app.py`: Flask routes and config load/save.
- `visca.py`: `ViscaCamera` - the VISCA-over-UDP protocol layer.
- `camera_worker.py`: serializes all camera I/O through one background
  thread with per-call timeouts, so a slow or hung camera command can't
  block the web server or freeze the frontend.
- `templates/index.html`: main control page (presets, dpad, zoom,
  position feedback, Settings).
- `templates/positions.html`: "Manage Positions" - the overwrite/create/
  delete actions, deliberately kept off the main page.
- `templates/help.html`: in-app usage and API documentation (`/help`).
- `static/`: shared CSS and JS for the above.
- `run.sh` / `com.calvarybaptistchurch.cameracontrol.plist`: boot-time
  launch on macOS via `launchd`.

## Testing

```bash
venv/bin/pip install -r requirements-dev.txt
venv/bin/pytest tests/ -v
```

`tests/test_visca.py` covers the VISCA command encoding (including the
absolute-position commands and the stale-ACK-skipping in
`send_with_response`); `tests/test_app.py` covers the Flask routes,
config load/save, and the local-positions flow (create/recall/update/
delete), all against a fake camera so nothing here needs real hardware.
Run this after touching `app.py` or `visca.py` - both have had real
regressions slip through before that this suite now catches.
