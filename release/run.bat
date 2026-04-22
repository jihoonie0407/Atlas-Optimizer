@echo off
cd /d "%~dp0"
py -3 -m pip install pillow numpy pyqt5 --quiet
start "" pyw -3 app.py
