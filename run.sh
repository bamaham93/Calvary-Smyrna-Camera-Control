#!/bin/zsh -l
# Launched by launchd at login (see com.calvarybaptistchurch.cameracontrol.plist
# in this repo) so the camera control app comes up automatically after every
# reboot, with no terminal needed. Runs as a login shell (-l) so it picks up
# the same PATH as an interactive terminal (Homebrew/python.org python3,
# etc.) - launchd itself starts processes with a minimal environment that
# skips .zshrc, which is the most common reason a launchd script can't find
# a command that works fine when you type it yourself.

cd "$(dirname "$0")"
mkdir -p logs

# EDIT THIS PATH if your virtual environment isn't ./venv (e.g. it's
# ./.venv, or you haven't created one yet: `python3 -m venv venv` from
# this directory, then `venv/bin/pip install -r requirements.txt`).
#
# Calling venv/bin/python3 directly (rather than `source venv/bin/activate`
# then bare `python3`) sidesteps a real case seen in testing: activation
# can leave `python3` on PATH resolving to something outside the venv
# entirely, even though the prompt shows (venv) and pip3 installs land in
# the right place. The explicit path can't be shadowed that way.
VENV_PYTHON="venv/bin/python3"

# Port 3100 matches what's already configured in FreeShow's Emitters -
# changing it here means updating those too.
exec "$VENV_PYTHON" app.py runserver 0.0.0.0:3100 >> logs/app.log 2>&1
