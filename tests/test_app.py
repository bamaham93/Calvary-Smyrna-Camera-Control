import json
import tempfile
import unittest
from pathlib import Path

import app as camera_app


class FakeCamera:
    def __init__(self):
        self.calls = []

    def stop(self):
        self.calls.append(("stop",))

    def zoom_stop(self):
        self.calls.append(("zoom_stop",))

    def preset_recall(self, preset):
        self.calls.append(("preset_recall", preset))

    def preset_set(self, preset):
        self.calls.append(("preset_set", preset))


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

    def test_load_config_merges_and_sanitizes_values(self):
        self.temp_path.write_text(
            json.dumps(
                {
                    "preset_names": {"1": "  Stage Left  ", "12": "", "19": "Ignored"},
                    "settings": {"zoom_speed": 10},
                }
            )
        )

        loaded_names, loaded_settings = camera_app.load_config(self.temp_path)

        self.assertEqual(loaded_names[1], "Stage Left")
        self.assertEqual(loaded_names[12], "Preset 12")
        self.assertEqual(loaded_settings["zoom_speed"], 7)

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
        response = self.client.post("/settings", data={"zoom_speed": "5"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("Updated settings: zoom speed 5", response.get_data(as_text=True))
        self.assertEqual(camera_app.settings["zoom_speed"], 5)

        stored = json.loads(self.temp_path.read_text())
        self.assertEqual(stored["settings"]["zoom_speed"], 5)

    def test_update_settings_requires_zoom_speed(self):
        response = self.client.post("/settings")

        self.assertEqual(response.status_code, 400)
        self.assertIn("zoom_speed is required", response.get_data(as_text=True))

    def test_set_preset_calls_camera(self):
        response = self.client.post("/preset/3/set")

        self.assertEqual(response.status_code, 200)
        self.assertIn(("preset_set", 3), camera_app.cam.calls)

    def test_recall_preset_uses_safe_recall_flow(self):
        response = self.client.get("/preset/4")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            camera_app.cam.calls,
            [("stop",), ("zoom_stop",), ("preset_recall", 4)],
        )

    def test_home_renders_modals_and_settings_controls(self):
        camera_app.preset_names[1] = "Stage Close"
        camera_app.settings["zoom_speed"] = 4

        response = self.client.get("/")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Stage Close", page)
        self.assertIn("name-modal-overlay", page)
        self.assertIn("settings-modal-overlay", page)
        self.assertIn('/zoom/in/4', page)
        self.assertIn('/zoom/out/4', page)

    def test_invalid_preset_for_set_and_name(self):
        response_set = self.client.post("/preset/99/set")
        response_name = self.client.post("/preset/99/name", data={"name": "Whatever"})

        self.assertEqual(response_set.status_code, 400)
        self.assertEqual(response_name.status_code, 400)


if __name__ == "__main__":
    unittest.main()
