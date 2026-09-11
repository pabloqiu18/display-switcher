from __future__ import annotations

import ctypes
import re
import winreg
from ctypes import wintypes
from dataclasses import dataclass


# Current settings constant for EnumDisplaySettingsExW and ChangeDisplaySettingsExW
ENUM_CURRENT_SETTINGS = -1
# Flags for ChangeDisplaySettingsExW
CDS_TEST = 0x00000002
CDS_UPDATEREGISTRY = 0x00000001
# Success code for ChangeDisplaySettingsExW
DISP_CHANGE_SUCCESSFUL = 0
# Bit mask for DISPLAY_DEVICEW StateFlags, used to filter active monitors
DISPLAY_DEVICE_ACTIVE = 0x00000001
# Bit masks for DEVMODEW dmFields, used to change resolution, color depth, and refresh rate
DM_BITSPERPEL = 0x00040000
DM_PELSWIDTH = 0x00080000
DM_PELSHEIGHT = 0x00100000
DM_DISPLAYFREQUENCY = 0x00400000
# Bit mask for DEVMODEW dmDisplayFlags, used to filter out interlaced modes
DM_INTERLACED = 0x00000002
# Flag for EnumDisplayDevicesW to get the device interface name
EDD_GET_DEVICE_INTERFACE_NAME = 0x00000001
# Fallback names for monitors that do not provide a proper name through the Windows API
GENERIC_MONITOR_NAMES = {"", "Generic PnP Monitor", "Generic Non-PnP Monitor"}


# Python versions of Windows C structs so Windows can read and write to them properly
class POINTL(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class DEVMODEW(ctypes.Structure):
    # Main struct for Windows display settings
    _fields_ = [
        ("dmDeviceName", wintypes.WCHAR * 32),
        ("dmSpecVersion", wintypes.WORD),
        ("dmDriverVersion", wintypes.WORD),
        ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD),
        ("dmFields", wintypes.DWORD),
        ("dmPosition", POINTL),
        ("dmDisplayOrientation", wintypes.DWORD),
        ("dmDisplayFixedOutput", wintypes.DWORD),
        ("dmColor", wintypes.SHORT),
        ("dmDuplex", wintypes.SHORT),
        ("dmYResolution", wintypes.SHORT),
        ("dmTTOption", wintypes.SHORT),
        ("dmCollate", wintypes.SHORT),
        ("dmFormName", wintypes.WCHAR * 32),
        ("dmLogPixels", wintypes.WORD),
        ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),
        ("dmDisplayFlags", wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),
        ("dmICMMethod", wintypes.DWORD),
        ("dmICMIntent", wintypes.DWORD),
        ("dmMediaType", wintypes.DWORD),
        ("dmDitherType", wintypes.DWORD),
        ("dmReserved1", wintypes.DWORD),
        ("dmReserved2", wintypes.DWORD),
        ("dmPanningWidth", wintypes.DWORD),
        ("dmPanningHeight", wintypes.DWORD),
    ]


class DISPLAY_DEVICEW(ctypes.Structure):
    # Describes a display device, such as a monitor or graphics card
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("DeviceName", wintypes.WCHAR * 32),
        ("DeviceString", wintypes.WCHAR * 128),
        ("StateFlags", wintypes.DWORD),
        ("DeviceID", wintypes.WCHAR * 128),
        ("DeviceKey", wintypes.WCHAR * 128),
    ]


# Load user32.dll and describe the argument/return types for the functions we call
# ctypes does not know the Win32 signatures unless we define them
user32 = ctypes.WinDLL("user32", use_last_error=True)
EnumDisplayDevicesW = user32.EnumDisplayDevicesW
EnumDisplayDevicesW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.POINTER(DISPLAY_DEVICEW),
    wintypes.DWORD,
]
EnumDisplayDevicesW.restype = wintypes.BOOL

EnumDisplaySettingsExW = user32.EnumDisplaySettingsExW
EnumDisplaySettingsExW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.POINTER(DEVMODEW),
    wintypes.DWORD,
]
EnumDisplaySettingsExW.restype = wintypes.BOOL

ChangeDisplaySettingsExW = user32.ChangeDisplaySettingsExW
ChangeDisplaySettingsExW.argtypes = [
    wintypes.LPCWSTR,
    ctypes.POINTER(DEVMODEW),
    wintypes.HWND,
    wintypes.DWORD,
    wintypes.LPVOID,
]
ChangeDisplaySettingsExW.restype = wintypes.LONG


# App-level data class for one usable display mode
@dataclass(frozen=True)
class DisplayMode:
    width: int
    height: int
    frequency: int
    bits_per_pixel: int

    @property
    def label(self) -> str:
        # Easily readable label (width x height @ refresh rate) for the dropdown menu
        return f"{self.width} x {self.height} @ {self.frequency} Hz"

    def to_json(self) -> dict[str, int]:
        # Simple dict for profiles.json, only store the fields we care about
        return {
            "width": self.width,
            "height": self.height,
            "frequency": self.frequency,
            "bits_per_pixel": self.bits_per_pixel,
        }

    @classmethod
    def from_json(cls, data: dict) -> "DisplayMode":
        # Rebuild a DisplayMode from profiles.json data
        return cls(
            int(data["width"]),
            int(data["height"]),
            int(data.get("frequency", 60)),
            int(data.get("bits_per_pixel", 32)),
        )


# App-level data class for one monitor and the modes available on that monitor
@dataclass
class Monitor:
    device_name: str
    display_name: str
    monitor_id: str
    current_mode: DisplayMode
    modes: list[DisplayMode]
    nvidia: bool = False
    vibrance: dict[str, int] | None = None

    @property
    def label(self) -> str:
        # Lead with real monitor name, then show the Windows display number for debugging
        vendor = "NVIDIA" if self.nvidia else "Windows"
        display_number = self.device_name.rsplit("\\", 1)[-1]
        return f"{self.display_name} ({display_number}, {vendor})"


# Create a DEVMODEW with dmSize to use in EnumDisplaySettingsExW and ChangeDisplaySettingsExW
def new_devmode() -> DEVMODEW:
    mode = DEVMODEW()
    mode.dmSize = ctypes.sizeof(DEVMODEW)
    return mode


# Enumerate all active Windows displays and convert raw Win32 data into our dataclasses
def enum_windows_monitors() -> list[Monitor]:
    monitors: list[Monitor] = []
    index = 0
    while True:
        device = DISPLAY_DEVICEW()
        device.cb = ctypes.sizeof(DISPLAY_DEVICEW)
        if not EnumDisplayDevicesW(None, index, ctypes.byref(device), 0):
            break
        index += 1
        if not device.StateFlags & DISPLAY_DEVICE_ACTIVE:
            continue

        current = new_devmode()
        # Get current settings for this display
        if not EnumDisplaySettingsExW(device.DeviceName, ENUM_CURRENT_SETTINGS, ctypes.byref(current), 0):
            continue

        monitor_name, monitor_id = monitor_details(device.DeviceName, device.DeviceString)
        monitors.append(
            Monitor(
                device_name=device.DeviceName,
                display_name=monitor_name,
                monitor_id=monitor_id,
                current_mode=DisplayMode(
                    int(current.dmPelsWidth),
                    int(current.dmPelsHeight),
                    int(current.dmDisplayFrequency),
                    int(current.dmBitsPerPel),
                ),
                modes=enum_modes(device.DeviceName),
            )
        )
    apply_edid_fallback_names(monitors)
    return monitors


# Check child monitor devices first for monitor name, otherwise fall back to EDID
def monitor_details(adapter_name: str, fallback_name: str) -> tuple[str, str]:
    for monitor in child_monitor_devices(adapter_name):
        edid_name = edid_name_for_monitor_id(monitor.DeviceID)
        if edid_name:
            return edid_name, monitor.DeviceID
        if monitor.DeviceString not in GENERIC_MONITOR_NAMES:
            return monitor.DeviceString, monitor.DeviceID

    edid_names = all_edid_monitor_names()
    # If there is only one EDID name, use that one
    if len(edid_names) == 1:
        return edid_names[0], ""
    return fallback_name, ""


# Enumerate all monitors under a display adapter
def child_monitor_devices(adapter_name: str) -> list[DISPLAY_DEVICEW]:
    devices: list[DISPLAY_DEVICEW] = []
    seen: set[tuple[str, str]] = set()
    for flags in (0, EDD_GET_DEVICE_INTERFACE_NAME):
        index = 0
        while True:
            monitor = DISPLAY_DEVICEW()
            monitor.cb = ctypes.sizeof(DISPLAY_DEVICEW)
            if not EnumDisplayDevicesW(adapter_name, index, ctypes.byref(monitor), flags):
                break
            index += 1
            key = (monitor.DeviceString, monitor.DeviceID)
            if key not in seen and monitor.StateFlags & DISPLAY_DEVICE_ACTIVE:
                seen.add(key)
                devices.append(monitor)
    return devices


# Look up the EDID display name for a monitor ID
def edid_name_for_monitor_id(monitor_id: str) -> str | None:
    display_id = display_registry_id(monitor_id)
    if not display_id:
        return None
    for path in display_registry_paths(display_id):
        name = edid_name_from_registry_path(path)
        if name:
            return name
    return None


def display_registry_id(monitor_id: str) -> str | None:
    # Regex to find the key from the Device ID
    match = re.search(r"(?:MONITOR|DISPLAY)[\\#]([^\\#]+)", monitor_id, re.IGNORECASE)
    return match.group(1) if match else None


def display_registry_paths(display_id: str) -> list[str]:
    # Return the paths to the Device Parameters keys for all instances of this display ID
    base = f"SYSTEM\\CurrentControlSet\\Enum\\DISPLAY\\{display_id}"
    return [f"{base}\\{instance}\\Device Parameters" for instance in registry_subkeys(base)]


def edid_name_from_registry_path(path: str) -> str | None:
    # Get the EDID value and decode the display name from it, if present
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            edid, _ = winreg.QueryValueEx(key, "EDID")
    except OSError:
        return None
    return decode_edid_display_name(bytes(edid))


def all_edid_monitor_names() -> list[str]:
    # Fallback scan for any devices not in the Windows API, but present in the registry
    names: list[str] = []
    seen: set[str] = set()
    for display_id in registry_subkeys("SYSTEM\\CurrentControlSet\\Enum\\DISPLAY"):
        for path in display_registry_paths(display_id):
            name = edid_name_from_registry_path(path)
            if name and name not in seen:
                seen.add(name)
                names.append(name)
    return names


def registry_subkeys(path: str) -> list[str]:
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            subkeys: list[str] = []
            index = 0
            while True:
                try:
                    subkeys.append(winreg.EnumKey(key, index))
                except OSError:
                    return subkeys
                index += 1
    except OSError:
        return []


def decode_edid_display_name(edid: bytes) -> str | None:
    # Decode display name from EDID data if present
    if len(edid) < 128:
        return None
    for offset in (54, 72, 90, 108):
        descriptor = edid[offset : offset + 18]
        if descriptor[:3] == b"\x00\x00\x00" and descriptor[3] in (0xFC, 0xFE):
            name = descriptor[5:18].decode("ascii", errors="ignore").strip(" \t\r\n\x00")
            if name:
                return name
    return None


def apply_edid_fallback_names(monitors: list[Monitor]) -> None:
    # Fallback names if Windows API does not provide a monitor ID, but EDID did
    unnamed_monitors = [monitor for monitor in monitors if not monitor.monitor_id]
    edid_names = all_edid_monitor_names()
    if len(unnamed_monitors) != len(edid_names):
        return
    for monitor, edid_name in zip(unnamed_monitors, edid_names):
        monitor.display_name = edid_name


def enum_modes(device_name: str) -> list[DisplayMode]:
    # Enumerate all display modes for the given device, ignoring interlaced modes (Usually TV modes) and dupes
    seen: set[tuple[int, int, int]] = set()
    modes: list[DisplayMode] = []
    index = 0
    while True:
        mode = new_devmode()
        if not EnumDisplaySettingsExW(device_name, index, ctypes.byref(mode), 0):
            break
        index += 1
        if mode.dmBitsPerPel < 32:
            continue
        if mode.dmDisplayFlags & DM_INTERLACED:
            continue
        if mode.dmPelsWidth < 640 or mode.dmPelsHeight < 480:
            continue
        key = (int(mode.dmPelsWidth), int(mode.dmPelsHeight), int(mode.dmDisplayFrequency))
        if key in seen:
            continue
        seen.add(key)
        modes.append(
            DisplayMode(
                int(mode.dmPelsWidth),
                int(mode.dmPelsHeight),
                int(mode.dmDisplayFrequency),
                int(mode.dmBitsPerPel),
            )
        )
    return sorted(modes, key=lambda m: (m.width * m.height, m.frequency), reverse=True)
