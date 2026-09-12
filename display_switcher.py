from __future__ import annotations

import os

from frontend import DisplaySwitcherApp


# Small launcher kept separate from the UI so imports and startup stay obvious
def main() -> int:
    if os.name != "nt":
        print("This tool is Windows-only because it uses the Windows display APIs.")
        return 1
    app = DisplaySwitcherApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
