"""Hold handles to live, creation-time-checked descendants before terminating a tree."""

import ctypes
from ctypes import wintypes


class ProcessEntry(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]


class WindowsProcessTree:
    def __init__(self, root_pid: int):
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        self.api.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        for name in ("Process32FirstW", "Process32NextW"):
            function = getattr(self.api, name)
            function.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
            function.restype = wintypes.BOOL
        self.api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.api.OpenProcess.restype = wintypes.HANDLE
        self.api.GetProcessTimes.argtypes = [wintypes.HANDLE] + [
            ctypes.POINTER(wintypes.FILETIME)
        ] * 4
        self.api.GetProcessTimes.restype = wintypes.BOOL
        self.api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.api.WaitForSingleObject.restype = wintypes.DWORD
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.api.CloseHandle.restype = wintypes.BOOL
        self.handles = []
        try:
            parents = self._parents()
            root = self._open(root_pid)
            if root is None:
                return  # Already exited, not an authorization to find or kill another PID.
            times = {root_pid: self._created(root)}
            remaining = dict(parents)
            while True:
                selected = [(pid, parent) for pid, parent in remaining.items() if parent in times]
                if not selected:
                    break
                for pid, parent in selected:
                    remaining.pop(pid)
                    if pid in times:
                        continue
                    handle = self._open(pid)
                    if handle is not None:
                        created = self._created(handle)
                        # Parent IDs can outlive the parent and be reused by unrelated processes.
                        if created >= times[parent]:
                            times[pid] = created
                        else:
                            self.handles.remove(handle)
                            self.api.CloseHandle(handle)
        except Exception:
            self.close()
            raise

    def _parents(self):
        snapshot = self.api.CreateToolhelp32Snapshot(2, 0)  # TH32CS_SNAPPROCESS
        if snapshot == ctypes.c_void_p(-1).value:
            raise RuntimeError("Unable to supervise owned subprocess tree")
        try:
            entry = ProcessEntry()
            entry.dwSize = ctypes.sizeof(entry)
            parents = {}
            found = self.api.Process32FirstW(snapshot, ctypes.byref(entry))
            while found:
                parents[entry.th32ProcessID] = entry.th32ParentProcessID
                found = self.api.Process32NextW(snapshot, ctypes.byref(entry))
            if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
                raise RuntimeError("Unable to supervise owned subprocess tree")
            return parents
        finally:
            self.api.CloseHandle(snapshot)

    def _open(self, pid):
        handle = self.api.OpenProcess(
            0x101000, False, pid
        )  # SYNCHRONIZE + QUERY_LIMITED_INFORMATION
        if not handle:
            if ctypes.get_last_error() == 87:  # Gone between enumeration and open.
                return None
            raise RuntimeError("Unable to supervise owned subprocess tree")
        self.handles.append(handle)
        return handle

    def _created(self, handle):
        times = [wintypes.FILETIME() for _ in range(4)]
        if not self.api.GetProcessTimes(handle, *(ctypes.byref(time) for time in times)):
            raise RuntimeError("Unable to supervise owned subprocess tree")
        return times[0].dwHighDateTime << 32 | times[0].dwLowDateTime

    def wait(self):
        for handle in self.handles:
            if self.api.WaitForSingleObject(handle, 5000) != 0:
                raise RuntimeError("Owned subprocess did not finish terminating")

    def close(self):
        for handle in self.handles:
            self.api.CloseHandle(handle)
        self.handles.clear()
