"""Process memory on Windows without psutil (ctypes GetProcessMemoryInfo). MB = 1024*1024 bytes."""
import ctypes
import ctypes.wintypes as wt
import sys


class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t), ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t), ("PrivateUsage", ctypes.c_size_t)]


def mem_mb() -> dict:
    """working_set ~ RSS; private ~ memory the process alone owns; peak_working_set since start."""
    if sys.platform != "win32":
        import resource
        return {"max_rss": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}
    counters = PROCESS_MEMORY_COUNTERS_EX()
    counters.cb = ctypes.sizeof(counters)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    k32.GetCurrentProcess.restype = wt.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS_EX), wt.DWORD]
    if not psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    mb = 1024 * 1024
    return {"working_set": round(counters.WorkingSetSize / mb, 1),
            "peak_working_set": round(counters.PeakWorkingSetSize / mb, 1),
            "private": round(counters.PrivateUsage / mb, 1)}
