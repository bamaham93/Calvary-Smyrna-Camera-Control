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
        self.original_preset_names_file = camera_app.PRESET_NAMES_FILE
        self.original_preset_names = dict(camera_app.preset_names)

        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name) / "preset_names.json"
        camera_app.PRESET_NAMES_FILE = self.temp_path
        camera_app.preset_names = {
            preset: camera_app.default_preset_name(preset)
            for preset in camera_app.DEFAULT_PRESET_RANGE
        }
        camera_app.cam = FakeCamera()
        self.client = camera_app.app.test_client()

    def tearDown(self):
        camera_app.cam = self.original_cam
        camera_app.PRESET_NAMES_FILE = self.original_preset_names_file
        camera_app.preset_names = self.original_preset_names
        self.temp_dir.cleanup()

    def test_load_preset_names_returns_defaults_for_missing_file(self):
        loaded = camera_app.load_preset_names(self.temp_path)
        self.assertEqual(loaded[1], "Preset 1")
        self.assertEqual(loaded[12], "Preset 12")

    def test_load_preset_names_merges_and_sanitizes_persisted_values(self):
        self.temp_path.write_text(
            json.dumps({"1": "  Stage Left  ", "12": "", "19": "Ignored"})
        )

        loaded = camera_app.load_preset_names(self.temp_path)

        self.assertEqual(loaded[1], "Stage Left")
        self.assertEqual(loaded[12], "Preset 12")

    def test_update_preset_name_saves_to_disk(self):
        response = self.client.post("/preset/2/name", data={"name": " Choir Wide "})

        self.assertEqual(response.status_code, 200)
        self.assertIn("Updated preset 2 name to Choir Wide", response.get_data(as_text=True))
        self.assertEqual(camera_app.preset_names[2], "Choir Wide")

        stored = json.loads(self.temp_path.read_text())
        self.assertEqual(stored["2"], "Choir Wide")

    def test_update_preset_name_requires_name(self):
        response = self.client.post("/preset/2/name")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Name is required", response.get_data(as_text=True))

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

    def test_home_renders_custom_preset_name_and_actions(self):
        camera_app.preset_names[1] = "Stage Close"

        response = self.client.get("/")
        page = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Stage Close", page)
        self.assertIn('/preset/1/name', page)
        self.assertIn('/preset/1/set', page)

    def test_invalid_preset_for_set_and_name(self):
        response_set = self.client.post("/preset/99/set")
        response_name = self.client.post("/preset/99/name", data={"name": "Whatever"})

        self.assertEqual(response_set.status_code, 400)
        self.assertEqual(response_name.status_code, 400)


if __name__ == "__main__":
    unittest.main()
