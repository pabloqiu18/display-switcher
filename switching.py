from __future__ import annotations

import ctypes

from nvapi import NvApi, NvApiError
from windows_api import (
    CDS_TEST,
    CDS_UPDATEREGISTRY,
    DISP_CHANGE_SUCCESSFUL,
    DM_BITSPERPEL,
    DM_DISPLAYFREQUENCY,
    DM_PELSHEIGHT,
    DM_PELSWIDTH,
    ENUM_CURRENT_SETTINGS,
    ChangeDisplaySettingsExW,
    DisplayMode,
    EnumDisplaySettingsExW,
    Monitor,
    enum_windows_monitors,
    new_devmode,
)


# Coordinate resolution and digital vibrance switching
class DisplayController:
    def __init__(self) -> None:
        self.nvapi: NvApi | None = None
        self.nvapi_status = "NVAPI not initialized"
        self.nv_handles: dict[str, ctypes.c_void_p] = {}

    def refresh_monitors(self) -> list[Monitor]:
        # Re-read both Windows display data and NVIDIA metadata to keep the UI in sync with current state
        self._refresh_nvapi()
        monitors = enum_windows_monitors()
        self.nv_handles = {}
        if self.nvapi is not None:
            for monitor in monitors:
                self._attach_nvidia_data(monitor)
        return monitors

    def change_resolution(self, device_name: str, mode: DisplayMode) -> None:
        # Change resolution, starting from the current DEVMODE
        devmode = new_devmode()
        if not EnumDisplaySettingsExW(device_name, ENUM_CURRENT_SETTINGS, ctypes.byref(devmode), 0):
            raise RuntimeError(f"Could not read current settings for {device_name}")

        devmode.dmPelsWidth = mode.width
        devmode.dmPelsHeight = mode.height
        devmode.dmDisplayFrequency = mode.frequency
        devmode.dmBitsPerPel = mode.bits_per_pixel
        devmode.dmFields = DM_PELSWIDTH | DM_PELSHEIGHT | DM_DISPLAYFREQUENCY | DM_BITSPERPEL

        # If test is successful, apply the new mode and don't ask for confirmation to speed up the process
        test = ChangeDisplaySettingsExW(device_name, ctypes.byref(devmode), None, CDS_TEST, None)
        if test != DISP_CHANGE_SUCCESSFUL:
            raise RuntimeError(f"Windows rejected that mode for {device_name} (code {test})")
        result = ChangeDisplaySettingsExW(device_name, ctypes.byref(devmode), None, CDS_UPDATEREGISTRY, None)
        if result != DISP_CHANGE_SUCCESSFUL:
            raise RuntimeError(f"Could not apply mode for {device_name} (code {result})")

    def apply_vibrance(self, device_name: str, level: int) -> None:
        # Change digital vibraance level for the given monitor, unused if the monitor is not NVIDIA or NVAPI is unavailable
        if self.nvapi is None:
            return
        handle = self.nv_handles.get(device_name)
        if handle:
            self.nvapi.set_dvc_level(handle, level)

    def _refresh_nvapi(self) -> None:
        # Keep failures non-fatal so the app can still switch resolutions on non-NVIDIA systems or if the driver API is unavailable
        try:
            self.nvapi = NvApi()
            self.nvapi_status = "NVAPI ready"
        except Exception as exc:
            self.nvapi = None
            self.nvapi_status = f"NVAPI unavailable: {exc}"

    def _attach_nvidia_data(self, monitor: Monitor) -> None:
        # Add NVIDIA runtime data to the Monitor object after the Windows monitor list is collected
        if self.nvapi is None:
            return
        handle = self.nvapi.handle_for_display(monitor.device_name)
        if not handle:
            return
        self.nv_handles[monitor.device_name] = handle
        monitor.nvidia = True
        try:
            monitor.vibrance = self.nvapi.get_dvc_info(handle)
        except NvApiError:
            monitor.vibrance = None
