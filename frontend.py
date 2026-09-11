from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from profiles import ProfileStore
from switching import DisplayController
from windows_api import DisplayMode, Monitor


APP_NAME = "Display Switcher"


# Tkinter frontend
# It knows how to show controls and gather user selections,
# while DisplayController and ProfileStore do the actual work
class DisplaySwitcherApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.minsize(720, 420)
        # Utilities for runtime display control and profile persistence
        self.controller = DisplayController()
        self.profile_store = ProfileStore()
        self.monitors: list[Monitor] = []

        self.monitor_var = tk.StringVar()
        self.mode_var = tk.StringVar()
        self.vibrance_var = tk.IntVar(value=50)
        self.status_var = tk.StringVar(value="Ready")

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        # Main layout with fixed-width current monitor controls on the left and growing profiles list on the right
        root = ttk.Frame(self, padding=14)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(0, weight=0)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(1, weight=1)

        ttk.Label(root, text="Monitor").grid(row=0, column=0, sticky="w")
        self.monitor_combo = ttk.Combobox(root, textvariable=self.monitor_var, state="readonly")
        self.monitor_combo.grid(row=0, column=0, sticky="ew", pady=(22, 12), padx=(0, 12))
        self.monitor_combo.bind("<<ComboboxSelected>>", lambda _: self.on_monitor_changed())

        ttk.Button(root, text="Refresh", command=self.refresh).grid(row=0, column=1, sticky="ne")

        # Current monitor controls
        settings = ttk.LabelFrame(root, text="Current Monitor", padding=12)
        settings.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        settings.columnconfigure(1, weight=1)

        ttk.Label(settings, text="Resolution").grid(row=0, column=0, sticky="w", pady=6)
        self.mode_combo = ttk.Combobox(settings, textvariable=self.mode_var, state="readonly")
        self.mode_combo.grid(row=0, column=1, sticky="ew", pady=6)

        ttk.Label(settings, text="Digital Vibrance").grid(row=1, column=0, sticky="w", pady=6)
        self.vibrance_scale = ttk.Scale(
            settings,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.vibrance_var,
            command=lambda value: self.vibrance_var.set(round(float(value))),
        )
        self.vibrance_scale.grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Label(settings, textvariable=self.vibrance_var, width=4).grid(row=1, column=2, sticky="e", padx=(8, 0))

        actions = ttk.Frame(settings)
        actions.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(16, 0))
        ttk.Button(actions, text="Apply", command=self.apply_current).pack(side=tk.LEFT)
        ttk.Button(actions, text="Save Profile", command=self.save_current_profile).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="Default Vibrance", command=self.reset_vibrance).pack(side=tk.LEFT, padx=(8, 0))

        # Saved profile controls
        profiles = ttk.LabelFrame(root, text="Profiles", padding=12)
        profiles.grid(row=1, column=1, sticky="nsew")
        profiles.rowconfigure(0, weight=1)
        profiles.columnconfigure(0, weight=1)
        self.profile_list = tk.Listbox(profiles, activestyle="dotbox")
        self.profile_list.grid(row=0, column=0, sticky="nsew")
        profile_buttons = ttk.Frame(profiles)
        profile_buttons.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(profile_buttons, text="Apply Profile", command=self.apply_selected_profile).pack(side=tk.LEFT)
        ttk.Button(profile_buttons, text="Delete", command=self.delete_selected_profile).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Label(root, textvariable=self.status_var).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))

    def refresh(self, selected_device_name: str | None = None) -> None:
        # Re-enumerate monitors and keep the same monitor selected when possible
        previous_monitor = self.selected_monitor()
        preferred_device_name = selected_device_name or (previous_monitor.device_name if previous_monitor else None)

        self.monitors = self.controller.refresh_monitors()
        self.monitor_combo["values"] = [m.label for m in self.monitors]
        if self.monitors:
            selected_index = 0
            if preferred_device_name:
                selected_index = next(
                    (index for index, monitor in enumerate(self.monitors) if monitor.device_name == preferred_device_name),
                    0,
                )
            self.monitor_combo.current(selected_index)
        self.on_monitor_changed()
        self.reload_profiles_list()
        self.status_var.set(f"{len(self.monitors)} active monitor(s). {self.controller.nvapi_status}")

    def selected_monitor(self) -> Monitor | None:
        # Convert the selected combobox index back into the Monitor object
        index = self.monitor_combo.current()
        if index < 0 or index >= len(self.monitors):
            return None
        return self.monitors[index]

    def selected_mode(self) -> DisplayMode | None:
        # Convert the selected resolution label back into the DisplayMode object
        monitor = self.selected_monitor()
        if not monitor:
            return None
        label = self.mode_var.get()
        return next((mode for mode in monitor.modes if mode.label == label), None)

    def on_monitor_changed(self) -> None:
        # Repopulate resolution and vibrance controls for the newly selected monitor
        monitor = self.selected_monitor()
        if not monitor:
            return
        self.mode_combo["values"] = [mode.label for mode in monitor.modes]
        current_label = monitor.current_mode.label
        if current_label in self.mode_combo["values"]:
            self.mode_var.set(current_label)
        elif monitor.modes:
            self.mode_combo.current(0)

        if monitor.vibrance:
            self.vibrance_scale.state(["!disabled"])
            self.vibrance_scale.configure(from_=monitor.vibrance["min"], to=monitor.vibrance["max"])
            self.vibrance_var.set(monitor.vibrance["current"])
        else:
            self.vibrance_scale.state(["disabled"])
            self.vibrance_var.set(50)

    def apply_current(self) -> None:
        # Apply the currently selected resolution and vibrance directly without saving a profile
        monitor = self.selected_monitor()
        mode = self.selected_mode()
        if not monitor or not mode:
            return
        try:
            self.controller.change_resolution(monitor.device_name, mode)
            self.controller.apply_vibrance(monitor.device_name, self.vibrance_var.get())
            self.status_var.set(f"Applied {mode.label} to {monitor.device_name}")
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def reset_vibrance(self) -> None:
        # Use the default vibrance value reported by NVAPI for this monitor
        monitor = self.selected_monitor()
        if not monitor or not monitor.vibrance:
            return
        self.vibrance_var.set(monitor.vibrance["default"])
        try:
            self.controller.apply_vibrance(monitor.device_name, monitor.vibrance["default"])
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def save_current_profile(self) -> None:
        # Ask the user for a profile name, then persist the current UI selection
        monitor = self.selected_monitor()
        mode = self.selected_mode()
        if not monitor or not mode:
            return
        name = simpledialog.askstring(APP_NAME, "Profile name", parent=self)
        if not name:
            return
        vibrance = self.vibrance_var.get() if monitor.vibrance else None
        self.profile_store.upsert(name, monitor, mode, vibrance)
        self.reload_profiles_list()

    def reload_profiles_list(self) -> None:
        # Rebuild the visible profile list from the saved JSON data
        self.profile_list.delete(0, tk.END)
        monitor_names = {monitor.device_name: monitor.display_name for monitor in self.monitors}
        for profile in self.profile_store.all():
            vib = profile.get("digital_vibrance")
            vib_label = f", vibrance {vib}" if vib is not None else ""
            mode = DisplayMode.from_json(profile["resolution"])
            monitor_label = (
                monitor_names.get(profile["monitor_device"])
                or profile.get("monitor_name")
                or profile["monitor_device"]
            )
            self.profile_list.insert(
                tk.END,
                f"{profile['name']} - {monitor_label} - {mode.label}{vib_label}",
            )

    def selected_profile(self) -> dict | None:
        # Convert the selected listbox row back into the profile dictionary
        selection = self.profile_list.curselection()
        if not selection:
            return None
        return self.profile_store.all()[selection[0]]

    def apply_selected_profile(self) -> None:
        # Apply a saved profile, then refresh so the UI shows the new live state
        profile = self.selected_profile()
        if not profile:
            return
        try:
            mode = DisplayMode.from_json(profile["resolution"])
            device_name = profile["monitor_device"]
            self.controller.change_resolution(device_name, mode)
            if profile.get("digital_vibrance") is not None:
                self.controller.apply_vibrance(device_name, int(profile["digital_vibrance"]))
            self.refresh(selected_device_name=device_name)
            self.status_var.set(f"Applied profile {profile['name']}")
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def delete_selected_profile(self) -> None:
        # Remove the selected profile from storage
        profile = self.selected_profile()
        if not profile:
            return
        self.profile_store.delete(profile)
        self.reload_profiles_list()
