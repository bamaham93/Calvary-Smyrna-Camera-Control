import json
import tempfile
import unittest
from pathlib import Path

import app as camera_app


class FakeCamera:
    def __init__(self):
        self.calls = []

    def stop(self, pan_speed=0, tilt_speed=0):
        self.calls.append(("stop", pan_speed, tilt_speed))

    def zoom_stop(self):
        self.calls.append(("zoom_stop",))

    def preset_recall(self, preset):
        self.calls.append(("preset_recall", preset))

    def preset_set(self, preset):
        self.calls.append(("preset_set", preset))

    def move_up(self, pan_speed=8, tilt_speed=8):
        self.calls.append(("move_up", pan_speed, tilt_speed))

    def get_position_feedback(self):
        self.calls.append(("get_position_feedback",))
        return {"pan": 4660, "tilt": 255, "zoom": 3855}


class CameraAppTests(unittest.TestCase):
    def setUp(self):
        self.original_cam = camera_app.cam
        self.original_config_file = camera_app.CONFIG_FILE
        self.original_preset_names = dict(camera_app.preset_names)
        self.original_settings = dict(camera_app.settings)

        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name) / "config.json"
        camera_app.CONFIG_FILE = self.temp_path
        camera_app.preset_names = camera_app.default_preset_names()
        camera_app.settings = dict(camera_app.DEFAULT_SETTINGS)
        camera_app.cam = FakeCamera()
        self.client = camera_app.app.test_client()

    def tearDown(self):
        camera_app.cam = self.original_cam
        camera_app.CONFIG_FILE = self.original_config_file
        camera_app.preset_names = self.original_preset_names
        camera_app.settings = self.original_settings
        self.temp_dir.cleanup()

    def test_load_config_returns_defaults_for_missing_file(self):
        loaded_names, loaded_settings = camera_app.load_config(self.temp_path)

        self.assertEqual(loaded_names[1], "Preset 1")
        self.assertEqual(loaded_names[12], "Preset 12")
        self.assertEqual(loaded_settings["zoom_speed"], camera_app.DEFAULT_SETTINGS["zoom_speed"])
        self.assertEqual(loaded_settings["pan_speed"], camera_app.DEFAULT_SETTINGS["pan_speed"])
        self.assertEqual(loaded_settings["tilt_speed"], camera_app.DEFAULT_SETTINGS["tilt_speed"])

    def test_load_config_merges_and_sanitizes_values(self):
        self.temp_path.write_text(
            json.dumps(
                {
                    "preset_names": {"1": "  Stage Left  ", "12": "", "19": "Ignored"},
                    "settings": {"zoom_speed": 10, "pan_speed": 40, "tilt_speed": -2},
                }
            )
        )

        loaded_names, loaded_settings = camera_app.load_config(self.temp_path)

        self.assertEqual(loaded_names[1], "Stage Left")
        self.assertEqual(loaded_names[12], "Preset 12")
        self.assertEqual(loaded_settings["zoom_speed"], 7)
        self.assertEqual(loaded_settings["pan_speed"], 24)
        self.assertEqual(loaded_settings["tilt_speed"], 0)

    def test_update_preset_name_saves_to_config_file(self):
        response = self.client.post("/preset/2/name", data={"name": " Choir Wide "})

        self.assertEqual(response.status_code, 200)
        self.assertIn("Updated preset 2 name to Choir Wide", response.get_data(as_text=True))
        self.assertEqual(camera_app.preset_names[2], "Choir Wide")

        stored = json.loads(self.temp_path.read_text())
        self.assertEqual(stored["preset_names"]["2"], "Choir Wide")

    def test_update_preset_name_requires_name(self):
        response = self.client.post("/preset/2/name")

        self.assertEqual(response.status_code, 400)
        self.assertIn("Name is required", response.get_data(as_text=True))

    def test_update_settings_saves_to_config_file(self):
        response = self.client.post(
            "/settings",
            data={"zoom_speed": "5", "pan_speed": "12", "tilt_speed": "9"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "Updated settings: zoom speed 5, pan speed 12, tilt speed 9",
            response.get_data(as_text=True),
        )
        self.assertEqual(camera_app.settings["zoom_speed"], 5)
        self.assertEqual(camera_app.settings["pan_speed"], 12)
        self.assertEqual(camera_app.settings["tilt_speed"], 9)

        stored = json.loads(self.temp_path.read_text())
        self.assertEqual(stored["settings"]["zoom_speed"], 5)
        self.assertEqual(stored["settings"]["pan_speed"], 12)
        self.assertEqual(stored["settings"]["tilt_speed"], 9)

    def test_update_settings_requires_all_speed_fields(self):
        response_zoom = self.client.post("/settings", data={"pan_speed": "8", "tilt_speed": "8"})
        response_pan = self.client.post("/settings", data={"zoom_speed": "2", "tilt_speed": "8"})
        response_tilt = self.client.post("/settings", data={"zoom_speed": "2", "pan_speed": "8"})

        self.assertEqual(response_zoom.status_code, 400)
        self.assertIn("zoom_speed is required", response_zoom.get_data(as_text=True))

        self.assertEqual(response_pan.status_code, 400)
        self.assertIn("pan_speed is required", response_pan.get_data(as_text=True))

        self.assertEqual(response_tilt.status_code, 400)
        self.assertIn("tilt_speed is required", response_tilt.get_data(as_text=True))

    def test_set_preset_calls_camera(self):
        response = self.client.post("/preset/3/set")

        self.assertEqual(response.status_code, 200)
        self.assertIn(("preset_set", 3), camera_app.cam.calls)

    def test_recall_preset_uses_safe_recall_flow_with_configured_speeds(self):
        camera_app.settings["pan_speed"] = 11
        camera_app.settings["tilt_speed"] = 7

        response = self.client.get("/preset/4")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            camera_app.cam.calls,
            [("stop", 11, 7), ("zoom_stop",), ("preset_recall", 4)],
        )

    def test_move_uses_configured_pan_tilt_speeds(self):
        camera_app.settings["pan_speed"] = 14
        camera_app.settings["tilt_speed"] = 6

        response = self.client.get("/move/up")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(camera_app.cam.calls, [("move_up", 14, 6)])

    def test_home_renders_modals_and_settings_controls(self):
        camera_app.preset_names[1] = "Stage Close"
        camera_app.settings["zoom_speed"] = 4
        camera_app.settings["pan_speed"] = 12
        camera_app.settings["tilt_speed"] = 9

        response = self.client.get("/")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Stage Close", page)
        self.assertIn("name-modal-overlay", page)
        self.assertIn("settings-modal-overlay", page)
        self.assertIn('/zoom/in/4', page)
        self.assertIn('/zoom/out/4', page)
        self.assertIn('id="pan-speed-input"', page)
        self.assertIn('id="tilt-speed-input"', page)
        self.assertIn('/static/css/styles.css', page)
        self.assertIn('Position Feedback', page)
        self.assertIn('id="position-pan"', page)
        self.assertIn('refreshPositionFeedback', page)

    def test_static_stylesheet_is_served(self):
        response = self.client.get("/static/css/styles.css")

        self.assertEqual(response.status_code, 200)
        self.assertIn(".preset-grid", response.get_data(as_text=True))

    def test_invalid_preset_for_set_and_name(self):
        response_set = self.client.post("/preset/99/set")
        response_name = self.client.post("/preset/99/name", data={"name": "Whatever"})

        self.assertEqual(response_set.status_code, 400)
        self.assertEqual(response_name.status_code, 400)


    def test_position_feedback_returns_json_payload(self):
        response = self.client.get("/position")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"pan": 4660, "tilt": 255, "zoom": 3855})
        self.assertIn(("get_position_feedback",), camera_app.cam.calls)

    def test_position_feedback_returns_503_when_camera_errors(self):
        class BrokenCamera(FakeCamera):
            def get_position_feedback(self):
                raise TimeoutError("camera timeout")

        camera_app.cam = BrokenCamera()

        response = self.client.get("/position")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json, {"error": "Unable to read camera position"})


if __name__ == "__main__":
    unittest.main()
