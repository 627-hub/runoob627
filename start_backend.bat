@echo off
set TDX_PLUGIN_PATH=C:\new_tdx64\PYPlugins\user
echo TDX_PLUGIN_PATH=%TDX_PLUGIN_PATH%
cd /d %~dp0backend
python main.py
pause
