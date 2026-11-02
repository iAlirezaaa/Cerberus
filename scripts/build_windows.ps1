# Build an unsigned, standalone Windows executable for the current Python version.
# Run from the repository root in PowerShell.
$ErrorActionPreference = "Stop"
python -m pip install --upgrade pip
python -m pip install -e ".[gui]"
python -m pip install "pyinstaller>=6,<7"
python -m PyInstaller --noconfirm --clean --onefile --windowed --collect-data cerberus --name Cerberus scripts/run_desktop.py
Write-Host "Built: dist\Cerberus.exe"
