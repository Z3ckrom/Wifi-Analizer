Baseline notes

Install the folowing

UV
Powershell CMD: powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

Then "uv run wifi-analizer"

UV installs all the needed on uv run so no npm install.

To make a EXE:
uv run python -m PyInstaller --onefile --console --name wifi-analizer --paths src src/wifi_analizer/**init**.py
