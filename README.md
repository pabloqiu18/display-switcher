# display-switcher

> Small Windows-only Python/Tkinter tool to quickly switch resolution and digital vibrance.

[![License](https://img.shields.io/github/license/pabloqiu18/taskbar-player)](https://mit-license.org/)
![Status](https://img.shields.io/badge/Status-Completed-brightgreen)
![Version](https://img.shields.io/badge/Version-v0.1.0-blue)

## Features

- Change resolution and digital vibrance
- Save and load resolution and digital vibrance profiles per monitor
- Only takes 2 clicks to change resolution after a profile is created
- Lightweight

## Tech Stack

- **Python 3.12**
- **Tkinter** - Desktop UI
- **Windows API (WinAPI)** - Resolution control
- **NVIDIA API (NVAPI)** - Digital Vibrance control

## Installation

1. Clone this repository.

```bash
git clone https://github.com/pabloqiu18/display-switcher.git
```

2. (Optional) Create an executable.

```bash
py -3.12 -m PyInstaller --onefile --windowed display_switcher.py
```

## Run

```bash
python .\display_switcher.py
```

If executable was created, navigate to display-switcher\dist and open display_switcher.exe

## Requirements

- Windows
- An NVIDIA GPU and NVAPI, nvapi64.dll to be available to be able to change digital vibrance
- Python 3.12