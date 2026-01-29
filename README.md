# hwview — Simple Hardware Viewer

A simple Windows GUI app that displays **CPU, GPU, and RAM** details.

## Run (dev)
```bash
python -m pip install -r requirements.txt
python src/hwview.py
```

## Build Windows EXE
```powershell
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
py -m pip install pyinstaller
py -m PyInstaller --onefile --windowed --name hwview src\hwview.py
```

Output:
- `dist\hwview.exe`

## Notes
- GPU info uses **WMI** on Windows (`Win32_VideoController`).
