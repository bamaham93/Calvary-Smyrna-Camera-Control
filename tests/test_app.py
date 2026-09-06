import json
import tempfile
import unittest
from pathlib import Path

import app as camera_app


class FakeCamera:
    def __init__(self):
        self.calls = []
        self.position_feedback = {"pan": 4660, "tilt": 255, "zoom": 3855}

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
        return dict(self.position_feedback)

    def move_to_position(self, pan, tilt, zoom, pan_speed=8, tilt_speed=8):
        self.calls.append(("move_to_position", pan, tilt, zoom, pan_speed, tilt_speed))

    def set_target(self, ip, port=None):
        self.calls.append(("set_target", ip, port))


class FakeAtemInputSlot:
    def __init__(self, value=None):
        self.videoSource = type("FakeVideoSource", (), {"value": value})()


class FakeAtemOnAir:
    def __init__(self, enabled=False):
        self.enabled = enabled


class FakeAtemFillSource:
    def __init__(self, value=None):
        self.value = value


class FakeAtemKeyer:
    def __init__(self):
        self.onAir = FakeAtemOnAir()
        self.fillSource = FakeAtemFillSource()


class FakeAtem:
    def __init__(self):
        self.calls = []
        self.connected = False
        self.atemModel = ""
        self.programInput = {0: FakeAtemInputSlot()}
        self.previewInput = {0: FakeAtemInputSlot()}
        self.keyer = {0: {0: FakeAtemKeyer()}}

    def connect(self, ip):
        self.calls.append(("connect", ip))

    def disconnect(self):
        self.calls.append(("disconnect",))

    def setProgramInputVideoSource(self, mE, source):
        self.calls.append(("setProgramInputVideoSource", mE, source))
        self.programInput[mE].videoSource.value = source

    def execCutME(self, mE):
        self.calls.append(("execCutME", mE))

    def execAutoME(self, mE):
        self.calls.append(("execAutoME", mE))

    def execFadeToBlackME(self, mE):
        self.calls.append(("execFadeToBlackME", mE))

    def setKeyerType(self, mE, keyer, type_):
        self.calls.append(("setKeyerType", mE, keyer, type_))

    def setKeyerMasked(self, mE, keyer, masked):
        self.calls.append(("setKeyerMasked", mE, keyer, masked))

    def setKeyDVESizeX(self, mE, keyer, sizeX):
        self.calls.append(("setKeyDVESizeX", mE, keyer, sizeX))

    def setKeyDVESizeY(self, mE, keyer, sizeY):
        self.calls.append(("setKeyDVESizeY", mE, keyer, sizeY))

    def setKeyDVEPositionX(self, mE, keyer, positionX):
        self.calls.append(("setKeyDVEPositionX", mE, keyer, positionX))

    def setKeyDVEPositionY(self, mE, keyer, positionY):
        self.calls.append(("setKeyDVEPositionY", mE, keyer, positionY))

    def setKeyerFillSource(self, mE, keyer, fillSource):
        self.calls.append(("setKeyerFillSource", mE, keyer, fillSource))
        self.keyer[mE][keyer].fillSource.value = fillSource

    def setKeyerOnAirEnabled(self, mE, keyer, enabled):
        self.calls.append(("setKeyerOnAirEnabled", mE, keyer, enabled))
        self.keyer[mE][keyer].onAir.enabled = enabled


class CameraAppTests(unittest.TestCase):
    def setUp(self):
        self.original_cam = camera_app.cam
        self.original_atem = camera_app.atem
        self.original_config_file = camera_app.CONFIG_FILE
        self.original_preset_names = dict(camera_app.preset_names)
        self.original_settings = dict(camera_app.settings)
        self.original_camera = dict(camera_app.camera)
        self.original_local_positions = dict(camera_app.local_positions)
        self.original_atem_config = dict(camera_app.atem_config)
        self.original_atem_input_names = dict(camera_app.atem_input_names)

        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name) / "config.json"
        camera_app.CONFIG_FILE = self.temp_path
        camera_app.preset_names = camera_app.default_preset_names()
        camera_app.settings = dict(camera_app.DEFAULT_SETTINGS)
        camera_app.camera = dict(camera_app.DEFAULT_CAMERA)
        camera_app.local_positions = {}
        camera_app.atem_config = dict(camera_app.DEFAULT_ATEM)
        camera_app.atem_input_names = camera_app.default_atem_input_names()
        camera_app.cam = FakeCamera()
        camera_app.atem = FakeAtem()
        self.client = camera_app.app.test_client()

    def tearDown(self):
        camera_app.cam = self.original_cam
        camera_app.atem = self.original_atem
        camera_app.CONFIG_FILE = self.original_config_file
        camera_app.preset_names = self.original_preset_names
        camera_app.settings = self.original_settings
        camera_app.camera = self.original_camera
        camera_app.local_positions = self.original_local_positions
        camera_app.atem_config = self.original_atem_config
        camera_app.atem_input_names = self.original_atem_input_names
        self.temp_dir.cleanup()

    def test_load_config_returns_defaults_for_missing_file(self):
        (
            loaded_names,
            loaded_settings,
            loaded_camera,
            loaded_local_positions,
            loaded_atem,
            loaded_atem_names,
        ) = camera_app.load_config(self.temp_path)

        self.assertEqual(loaded_names[1], "Preset 1")
        self.assertEqual(loaded_names[12], "Preset 12")
        self.assertEqual(loaded_settings["zoom_speed"], camera_app.DEFAULT_SETTINGS["zoom_speed"])
        self.assertEqual(loaded_settings["pan_speed"], camera_app.DEFAULT_SETTINGS["pan_speed"])
        self.assertEqual(loaded_settings["tilt_speed"], camera_app.DEFAULT_SETTINGS["tilt_speed"])
        self.assertEqual(loaded_settings["position_speed"], camera_app.DEFAULT_SETTINGS["position_speed"])
        self.assertEqual(loaded_camera, camera_app.DEFAULT_CAMERA)
        self.assertEqual(loaded_local_positions, {})
        self.assertEqual(loaded_atem, camera_app.DEFAULT_ATEM)
        self.assertEqual(loaded_atem_names[1], "Input 1")
        self.assertEqual(loaded_atem_names[4], "Input 4")

    def test_load_config_merges_and_sanitizes_values(self):
        self.temp_path.write_text(
            json.dumps(
                {
                    "preset_names": {"1": "  Stage Left  ", "12": "", "19": "Ignored", "13": "Choir Wide"},
                    "settings": {"zoom_speed": 10, "pan_speed": 40, "tilt_speed": -2, "position_speed": 99},
                    "camera": {"ip": "192.168.1.50", "port": 9999},
                    "local_positions": {
                        "13": {"pan": 100, "tilt": -50, "zoom": 400},
                        "1": {"pan": 1, "tilt": 1, "zoom": 1},
                        "14": {"pan": "bad"},
                    },
                    "atem": {"ip": "10.0.0.99"},
                    "atem_input_names": {"1": "  Pulpit Wide  ", "9": "Ignored"},
                }
            )
        )

        (
            loaded_names,
            loaded_settings,
            loaded_camera,
            loaded_local_positions,
            loaded_atem,
            loaded_atem_names,
        ) = camera_app.load_config(self.temp_path)

        self.assertEqual(loaded_names[1], "Stage Left")
        self.assertEqual(loaded_names[12], "Preset 12")
        self.assertEqual(loaded_settings["zoom_speed"], 7)
        self.assertEqual(loaded_settings["pan_speed"], 24)
        self.assertEqual(loaded_settings["tilt_speed"], 0)
        self.assertEqual(loaded_settings["position_speed"], 20)
        self.assertEqual(loaded_camera, {"ip": "192.168.1.50", "port": 9999})
        self.assertEqual(loaded_atem, {"ip": "10.0.0.99"})
        self.assertEqual(loaded_atem_names[1], "Pulpit Wide")
        self.assertEqual(loaded_atem_names[2], "Input 2")
        self.assertNotIn(9, loaded_atem_names)

        # Local position 13 is valid and merges its name; "1" collides with
        # a camera preset number and is dropped; "14" has malformed fields
        # and is dropped.
        self.assertEqual(loaded_local_positions, {13: {"pan": 100, "tilt": -50, "zoom": 400}})
        self.assertEqual(loaded_names[13], "Choir Wide")
        self.assertNotIn(14, loaded_local_positions)

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
            data={
                "zoom_speed": "5",
                "pan_speed": "12",
                "tilt_speed": "9",
                "position_speed": "3",
                "camera_ip": "192.168.1.50",
                "camera_port": "1259",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Updated settings: zoom speed 5, pan speed 12, tilt speed 9", body)
        self.assertIn("position recall speed 3", body)
        self.assertIn("camera 192.168.1.50:1259", body)

        self.assertEqual(camera_app.settings["zoom_speed"], 5)
        self.assertEqual(camera_app.settings["pan_speed"], 12)
        self.assertEqual(camera_app.settings["tilt_speed"], 9)
        self.assertEqual(camera_app.settings["position_speed"], 3)
        self.assertEqual(camera_app.camera, {"ip": "192.168.1.50", "port": 1259})
        self.assertIn(("set_target", "192.168.1.50", 1259), camera_app.cam.calls)

        stored = json.loads(self.temp_path.read_text())
        self.assertEqual(stored["settings"]["zoom_speed"], 5)
        self.assertEqual(stored["settings"]["pan_speed"], 12)
        self.assertEqual(stored["settings"]["tilt_speed"], 9)
        self.assertEqual(stored["settings"]["position_speed"], 3)
        self.assertEqual(stored["camera"], {"ip": "192.168.1.50", "port": 1259})

    def test_update_settings_requires_all_speed_fields(self):
        base = {
            "zoom_speed": "2",
            "pan_speed": "8",
            "tilt_speed": "8",
            "position_speed": "5",
            "camera_ip": "10.0.0.1",
            "camera_port": "1259",
        }

        def without(key):
            data = dict(base)
            del data[key]
            return data

        response_zoom = self.client.post("/settings", data=without("zoom_speed"))
        response_pan = self.client.post("/settings", data=without("pan_speed"))
        response_tilt = self.client.post("/settings", data=without("tilt_speed"))
        response_position = self.client.post("/settings", data=without("position_speed"))
        response_ip = self.client.post("/settings", data=without("camera_ip"))
        response_port = self.client.post("/settings", data=without("camera_port"))

        self.assertEqual(response_zoom.status_code, 400)
        self.assertIn("zoom_speed is required", response_zoom.get_data(as_text=True))

        self.assertEqual(response_pan.status_code, 400)
        self.assertIn("pan_speed is required", response_pan.get_data(as_text=True))

        self.assertEqual(response_tilt.status_code, 400)
        self.assertIn("tilt_speed is required", response_tilt.get_data(as_text=True))

        self.assertEqual(response_position.status_code, 400)
        self.assertIn("position_speed is required", response_position.get_data(as_text=True))

        self.assertEqual(response_ip.status_code, 400)
        self.assertIn("camera_ip is required", response_ip.get_data(as_text=True))

        self.assertEqual(response_port.status_code, 400)
        self.assertIn("camera_port is required", response_port.get_data(as_text=True))

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
        css = response.get_data(as_text=True)
        self.assertIn(".preset-grid", css)
        self.assertIn("grid-template-columns: repeat(3, minmax(0, 1fr));", css)

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

    def test_create_local_position_captures_current_view_and_assigns_next_number(self):
        camera_app.cam.position_feedback = {"pan": 65243, "tilt": 65460, "zoom": 15134}

        response = self.client.post("/position/local", data={"name": "Choir Wide"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"num": 13, "name": "Choir Wide"})
        self.assertEqual(camera_app.local_positions[13], {"pan": 65243, "tilt": 65460, "zoom": 15134})
        self.assertEqual(camera_app.preset_names[13], "Choir Wide")

        stored = json.loads(self.temp_path.read_text())
        self.assertEqual(stored["local_positions"]["13"], {"pan": 65243, "tilt": 65460, "zoom": 15134})

        # a second one gets the next number, not a reused one
        response2 = self.client.post("/position/local", data={"name": "Piano Wide"})
        self.assertEqual(response2.json["num"], 14)

    def test_recall_local_position_moves_to_stored_coordinates_at_position_speed(self):
        camera_app.local_positions[13] = {"pan": 100, "tilt": -50, "zoom": 400}
        camera_app.preset_names[13] = "Choir Wide"
        camera_app.settings["position_speed"] = 3
        camera_app.settings["pan_speed"] = 11
        camera_app.settings["tilt_speed"] = 7

        response = self.client.get("/preset/13")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Recalled Choir Wide", response.get_data(as_text=True))
        self.assertEqual(
            camera_app.cam.calls,
            [("stop", 11, 7), ("zoom_stop",), ("move_to_position", 100, -50, 400, 3, 3)],
        )

    def test_update_local_position_recaptures_current_view(self):
        camera_app.local_positions[13] = {"pan": 1, "tilt": 1, "zoom": 1}
        camera_app.preset_names[13] = "Choir Wide"
        camera_app.cam.position_feedback = {"pan": 500, "tilt": 600, "zoom": 700}

        response = self.client.post("/preset/13/set")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(camera_app.local_positions[13], {"pan": 500, "tilt": 600, "zoom": 700})

    def test_delete_local_position_removes_it(self):
        camera_app.local_positions[13] = {"pan": 1, "tilt": 1, "zoom": 1}
        camera_app.preset_names[13] = "Choir Wide"

        response = self.client.post("/position/local/13/delete")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(13, camera_app.local_positions)
        self.assertNotIn(13, camera_app.preset_names)

        # it's gone - recalling it now is a 400, not a crash
        recall_response = self.client.get("/preset/13")
        self.assertEqual(recall_response.status_code, 400)

    def test_delete_local_position_rejects_camera_preset_numbers(self):
        response = self.client.post("/position/local/1/delete")

        self.assertEqual(response.status_code, 400)

    def test_goto_position_moves_camera_at_position_speed(self):
        camera_app.settings["position_speed"] = 4

        response = self.client.post(
            "/position/goto",
            json={"pan": 100, "tilt": -50, "zoom": 400},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(camera_app.cam.calls, [("move_to_position", 100, -50, 400, 4, 4)])

    def test_goto_position_requires_integer_values(self):
        response = self.client.post("/position/goto", json={"pan": "abc", "tilt": 1, "zoom": 1})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(camera_app.cam.calls, [])

    def test_atem_state_when_not_connected(self):
        response = self.client.get("/atem/state")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json,
            {
                "connected": False,
                "program": None,
                "preview": None,
                "model": None,
                "pip_on": False,
                "pip_source": None,
            },
        )

    def test_atem_state_when_connected(self):
        camera_app.atem.connected = True
        camera_app.atem.atemModel = "ATEM Mini Pro"
        camera_app.atem.programInput[0].videoSource.value = 2
        camera_app.atem.previewInput[0].videoSource.value = 3

        camera_app.atem.keyer[0][0].onAir.enabled = True
        camera_app.atem.keyer[0][0].fillSource.value = 4

        response = self.client.get("/atem/state")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json,
            {
                "connected": True,
                "program": 2,
                "preview": 3,
                "model": "ATEM Mini Pro",
                "pip_on": True,
                "pip_source": 4,
            },
        )

    def test_atem_set_program_requires_connection(self):
        response = self.client.post("/atem/program/2")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(camera_app.atem.calls, [])

    def test_atem_set_program_calls_switcher(self):
        camera_app.atem.connected = True

        response = self.client.post("/atem/program/2")

        self.assertEqual(response.status_code, 200)
        self.assertIn("Program set to Input 2", response.get_data(as_text=True))
        self.assertIn(("setProgramInputVideoSource", 0, 2), camera_app.atem.calls)

    def test_atem_cut_calls_switcher(self):
        camera_app.atem.connected = True

        response = self.client.post("/atem/cut")

        self.assertEqual(response.status_code, 200)
        self.assertIn(("execCutME", 0), camera_app.atem.calls)

    def test_atem_cut_requires_connection(self):
        response = self.client.post("/atem/cut")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(camera_app.atem.calls, [])

    def test_atem_auto_calls_switcher(self):
        camera_app.atem.connected = True

        response = self.client.post("/atem/auto")

        self.assertEqual(response.status_code, 200)
        self.assertIn(("execAutoME", 0), camera_app.atem.calls)

    def test_atem_ftb_calls_switcher(self):
        camera_app.atem.connected = True

        response = self.client.post("/atem/ftb")

        self.assertEqual(response.status_code, 200)
        self.assertIn(("execFadeToBlackME", 0), camera_app.atem.calls)

    def test_atem_pip_corner_moves_pip(self):
        camera_app.atem.connected = True

        response = self.client.post("/atem/pip/corner/top-left")

        self.assertEqual(response.status_code, 200)
        self.assertIn("top-left", response.get_data(as_text=True))
        self.assertIn(("setKeyerType", 0, 0, camera_app.ATEM_KEYER_TYPE_DVE), camera_app.atem.calls)
        self.assertIn(("setKeyerMasked", 0, 0, False), camera_app.atem.calls)
        self.assertIn(("setKeyDVESizeX", 0, 0, camera_app.ATEM_PIP_SIZE), camera_app.atem.calls)
        self.assertIn(("setKeyDVESizeY", 0, 0, camera_app.ATEM_PIP_SIZE), camera_app.atem.calls)
        expected_x, expected_y = camera_app.ATEM_PIP_CORNERS["top-left"]
        self.assertIn(("setKeyDVEPositionX", 0, 0, expected_x), camera_app.atem.calls)
        self.assertIn(("setKeyDVEPositionY", 0, 0, expected_y), camera_app.atem.calls)

    def test_atem_pip_corner_rejects_invalid_corner(self):
        camera_app.atem.connected = True

        response = self.client.post("/atem/pip/corner/middle")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(camera_app.atem.calls, [])

    def test_atem_pip_corner_requires_connection(self):
        response = self.client.post("/atem/pip/corner/top-left")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(camera_app.atem.calls, [])

    def test_atem_pip_source_sets_fill_source(self):
        camera_app.atem.connected = True

        response = self.client.post("/atem/pip/source/3")

        self.assertEqual(response.status_code, 200)
        self.assertIn(("setKeyerFillSource", 0, 0, 3), camera_app.atem.calls)
        self.assertEqual(camera_app.atem.keyer[0][0].fillSource.value, 3)

    def test_atem_pip_raw_sets_exact_values(self):
        camera_app.atem.connected = True

        response = self.client.post(
            "/atem/pip/raw",
            json={"position_x": -14.5, "position_y": 6.5, "size_x": 0.3, "size_y": 0.35},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(("setKeyDVEPositionX", 0, 0, -14.5), camera_app.atem.calls)
        self.assertIn(("setKeyDVEPositionY", 0, 0, 6.5), camera_app.atem.calls)
        self.assertIn(("setKeyDVESizeX", 0, 0, 0.3), camera_app.atem.calls)
        self.assertIn(("setKeyDVESizeY", 0, 0, 0.35), camera_app.atem.calls)

    def test_atem_pip_raw_defaults_size_when_omitted(self):
        camera_app.atem.connected = True

        response = self.client.post("/atem/pip/raw", json={"position_x": 1, "position_y": 2})

        self.assertEqual(response.status_code, 200)
        self.assertIn(("setKeyDVESizeX", 0, 0, camera_app.ATEM_PIP_SIZE), camera_app.atem.calls)
        self.assertIn(("setKeyDVESizeY", 0, 0, camera_app.ATEM_PIP_SIZE), camera_app.atem.calls)

    def test_atem_pip_raw_requires_numeric_position(self):
        camera_app.atem.connected = True

        response = self.client.post("/atem/pip/raw", json={"position_x": "abc", "position_y": 2})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(camera_app.atem.calls, [])

    def test_atem_pip_on_and_off(self):
        camera_app.atem.connected = True

        response_on = self.client.post("/atem/pip/on")
        self.assertEqual(response_on.status_code, 200)
        self.assertIn(("setKeyerOnAirEnabled", 0, 0, True), camera_app.atem.calls)
        self.assertTrue(camera_app.atem.keyer[0][0].onAir.enabled)

        response_off = self.client.post("/atem/pip/off")
        self.assertEqual(response_off.status_code, 200)
        self.assertIn(("setKeyerOnAirEnabled", 0, 0, False), camera_app.atem.calls)
        self.assertFalse(camera_app.atem.keyer[0][0].onAir.enabled)

    def test_atem_input_name_updates_and_persists(self):
        response = self.client.post("/atem/input/1/name", data={"name": "Pulpit Wide"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(camera_app.atem_input_names[1], "Pulpit Wide")

        stored = json.loads(self.temp_path.read_text())
        self.assertEqual(stored["atem_input_names"]["1"], "Pulpit Wide")

    def test_atem_input_name_rejects_out_of_range(self):
        response = self.client.post("/atem/input/99/name", data={"name": "Whatever"})

        self.assertEqual(response.status_code, 400)

    def test_update_settings_omitting_atem_ip_leaves_it_unchanged(self):
        camera_app.atem_config["ip"] = "10.0.0.5"

        response = self.client.post(
            "/settings",
            data={
                "zoom_speed": "2",
                "pan_speed": "8",
                "tilt_speed": "8",
                "position_speed": "5",
                "camera_ip": "10.0.0.1",
                "camera_port": "1259",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(camera_app.atem_config["ip"], "10.0.0.5")
        self.assertEqual(camera_app.atem.calls, [])

    def test_update_settings_reconnects_atem_when_ip_changes(self):
        response = self.client.post(
            "/settings",
            data={
                "zoom_speed": "2",
                "pan_speed": "8",
                "tilt_speed": "8",
                "position_speed": "5",
                "camera_ip": "10.0.0.1",
                "camera_port": "1259",
                "atem_ip": "10.0.0.99",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("ATEM 10.0.0.99", response.get_data(as_text=True))
        self.assertEqual(camera_app.atem_config["ip"], "10.0.0.99")
        self.assertEqual(camera_app.atem.calls, [("disconnect",), ("connect", "10.0.0.99")])

        stored = json.loads(self.temp_path.read_text())
        self.assertEqual(stored["atem"]["ip"], "10.0.0.99")

    def test_update_settings_blank_atem_ip_disconnects_without_reconnecting(self):
        camera_app.atem_config["ip"] = "10.0.0.5"

        response = self.client.post(
            "/settings",
            data={
                "zoom_speed": "2",
                "pan_speed": "8",
                "tilt_speed": "8",
                "position_speed": "5",
                "camera_ip": "10.0.0.1",
                "camera_port": "1259",
                "atem_ip": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(camera_app.atem_config["ip"], "")
        self.assertEqual(camera_app.atem.calls, [("disconnect",)])


if __name__ == "__main__":
    unittest.main()
