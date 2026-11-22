"""Point the app at a throwaway config file *before* app.py is imported, so
running the tests never reads, creates, or migrates a real config in the
user's app data folder."""

import os
import tempfile
from pathlib import Path

_test_config_dir = tempfile.mkdtemp(prefix="camera-control-tests-")
os.environ["CAMERA_CONTROL_CONFIG"] = str(Path(_test_config_dir) / "config.json")
