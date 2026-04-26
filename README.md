# Calvary-Smyrna-Camera-Control

A local web app to control the livestream camera.

## Configuration

The app persists preset names and app settings in `config.json` in the project root.

- `preset_names`: persisted labels for presets 1-12.
- `settings.zoom_speed`: default speed used by the zoom in/out buttons.
- `settings.pan_speed`: default pan speed used by directional movement and preset recalls.
- `settings.tilt_speed`: default tilt speed used by directional movement and preset recalls.

You can update both through the web UI:

- **Rename** opens a preset-name modal.
- **Settings** opens a settings modal to update zoom, pan, and tilt speeds.

## Project structure

- `templates/index.html`: Flask template for the control UI.
- `static/css/styles.css`: stylesheet for the UI.
