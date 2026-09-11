from __future__ import annotations

import ctypes


class NvApiError(RuntimeError):
    pass


# ctypes wrapper around NVIDIA's API
class NvApi:
    SHORT_STRING_MAX = 64
    NVAPI_OK = 0

    def __init__(self) -> None:
        dll_name = "nvapi64.dll" if ctypes.sizeof(ctypes.c_void_p) == 8 else "nvapi.dll"
        self.dll = ctypes.WinDLL(dll_name)
        # Query the functions through the nvapi_QueryInterface
        query = self.dll.nvapi_QueryInterface
        query.argtypes = [ctypes.c_uint]
        query.restype = ctypes.c_void_p
        self.query = query
        self._functions: dict[tuple[int, tuple], ctypes._CFuncPtr] = {}
        # 0x0150E828 is NvAPI_Initialize
        self._call(0x0150E828, ctypes.c_int)()

    def _call(self, api_id: int, restype, *argtypes):
        # Cache typed function pointers so each function only has to be looked up once
        key = (api_id, argtypes)
        if key not in self._functions:
            address = self.query(api_id)
            if not address:
                raise NvApiError(f"NVAPI function 0x{api_id:08X} is unavailable")
            self._functions[key] = ctypes.CFUNCTYPE(restype, *argtypes)(address)
        return self._functions[key]

    def _check(self, status: int) -> None:
        # Check NVAPI status codes
        if status != self.NVAPI_OK:
            raise NvApiError(self.error_message(status))

    def error_message(self, status: int) -> str:
        # Convert NVAPI status codes into messages
        try:
            buffer = ctypes.create_string_buffer(self.SHORT_STRING_MAX)
            func = self._call(0x6C2D048C, ctypes.c_int, ctypes.c_int, ctypes.c_char_p)
            func(status, buffer)
            message = buffer.value.decode("mbcs", errors="replace")
            return message or f"NVAPI error {status}"
        except Exception:
            return f"NVAPI error {status}"

    def handle_for_display(self, display_name: str) -> ctypes.c_void_p | None:
        # Convert display name (\\.\DISPLAY1, etc.) into an NVAPI display handle
        handle = ctypes.c_void_p()
        func = self._call(
            0x35C29134,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_void_p),
        )
        status = func(display_name.encode("ascii"), ctypes.byref(handle))
        return handle if status == self.NVAPI_OK else None

    def get_dvc_info(self, handle: ctypes.c_void_p) -> dict[str, int]:
        # Get Digital Vibrance Control info
        data = (ctypes.c_int * 5)()
        data[0] = ctypes.sizeof(data) | 0x10000
        func = self._call(
            0x0E45002D,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_void_p,
        )
        self._check(func(handle, 0, ctypes.byref(data)))
        return {
            "current": int(data[1]),
            "min": int(data[2]),
            "max": int(data[3]),
            "default": int(data[4]),
        }

    def set_dvc_level(self, handle: ctypes.c_void_p, level: int) -> None:
        # Set Digital Vibrance Control for the display handle, level between 0 and 100 set in data[1]
        data = (ctypes.c_int * 5)()
        data[0] = ctypes.sizeof(data) | 0x10000
        data[1] = int(level)
        func = self._call(
            0x4A82C2B1,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_void_p,
        )
        self._check(func(handle, 0, ctypes.byref(data)))
