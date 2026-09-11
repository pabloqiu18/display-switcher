from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from windows_api import DisplayMode, Monitor


def default_config_path() -> Path:
    # Source runs store profiles beside display_switcher.py; frozen builds store them beside the .exe
    if getattr(sys, "frozen", False):
        return Path(sys.executable).with_name("profiles.json")
    return Path(__file__).with_name("profiles.json")


# Profiles stored
CONFIG_PATH = default_config_path()


# Store profiles created and saved by the user for quick applciation
class ProfileStore:
    def __init__(self, path: Path = CONFIG_PATH) -> None:
        self.path = path
        self.data = self.load()

    def load(self) -> dict[str, list[dict[str, Any]]]:
        # Create the file if it doesn't exist yet, otherwise just read the JSON data into memory
        if not self.path.exists():
            return {"profiles": []}
        with self.path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def save(self) -> None:
        # Write the in-memory profile data back to the file
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def all(self) -> list[dict[str, Any]]:
        # List all saved profiles in memory
        return self.data.setdefault("profiles", [])

    def upsert(self, name: str, monitor: Monitor, mode: DisplayMode, digital_vibrance: int | None) -> None:
        # Store a profile's settings in memory, then save the list to the file
        profile = {
            "name": name,
            "monitor_device": monitor.device_name,
            "monitor_name": monitor.display_name,
            "resolution": mode.to_json(),
            "digital_vibrance": digital_vibrance,
        }
        # Profile names should be unique, so saving a profile with the same name overwrites the old one
        self.data["profiles"] = [p for p in self.all() if p["name"] != name]
        self.data["profiles"].append(profile)
        self.save()

    def delete(self, profile: dict[str, Any]) -> None:
        # Delete the selected profile in memory, then save the new list to the file
        self.data["profiles"] = [p for p in self.all() if p is not profile]
        self.save()