"""Bound one fixed, already-staged Ledgerly Raider receiver; no installation or dispatch."""
import base64
import ctypes as c
from ctypes import wintypes as w
import datetime
import hashlib
import json
import msvcrt
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import threading
import time
import _winapi

ROOT = Path(r"D:\hamon-autonomous-e3a41d2b3368-ledgerly-status-20261009")
PYTHON = Path(r"C:\Python314\python.exe")
NODE = Path(r"C:\Program Files\nodejs\node.exe")
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
DRIVER = ROOT / "receive-status.mjs"
ARGV = [str(NODE), "--max-old-space-size=192", str(DRIVER), "--run"]
PINS = [
    (PYTHON, None, "cce21c0e8710e304273e98ac4b2b0f5aceb639acbcd2343cbaa5c4e81619c45b"),
    (NODE, 91380224, "63c259c81e5d472b5f11c8d506070130cb04a1ecf84b80377a34ed6ec9048088"),
    (CHROME, 4496024, "977d6483df6c457eab24a3241b44645c66067f52b73bc2c8dbd7e6469bf15d1f"),
    (DRIVER, 29567, "c57bd3d34d6a2146e98ac2188712e1e9a7ca6189423a39c93c6f9d0c77f6a780"),
]
JOB_MEMORY = 1610612736
ACTIVE_LIMIT = 16
MEMORY_FLOOR = 2147483648
DISK_FLOOR = 268435456
WALL_SECONDS = 100.0
CHILD_STOP_RESERVE = 5.0
STREAM_LIMITS = {"stdout": 65536, "stderr": 32768}
OUTPUTS = ("SUPERVISOR-CHILD-START.json", "SUPERVISOR.json", "node.stdout.txt", "node.stderr.txt")
started = time.monotonic()
deadline = started + WALL_SECONDS
k32 = c.WinDLL("kernel32", use_last_error=True)

class Basic(c.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", c.c_longlong), ("PerJobUserTimeLimit", c.c_longlong),
        ("LimitFlags", w.DWORD), ("MinimumWorkingSetSize", c.c_size_t),
        ("MaximumWorkingSetSize", c.c_size_t), ("ActiveProcessLimit", w.DWORD),
        ("Affinity", c.c_size_t), ("PriorityClass", w.DWORD), ("SchedulingClass", w.DWORD),
    ]

class Io(c.Structure):
    _fields_ = [(name, c.c_ulonglong) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

class Extended(c.Structure):
    _fields_ = [
        ("BasicLimitInformation", Basic), ("IoInfo", Io),
        ("ProcessMemoryLimit", c.c_size_t), ("JobMemoryLimit", c.c_size_t),
        ("PeakProcessMemoryUsed", c.c_size_t), ("PeakJobMemoryUsed", c.c_size_t),
    ]

class Accounting(c.Structure):
    _fields_ = [(name, c.c_longlong) for name in (
        "TotalUserTime", "TotalKernelTime", "ThisPeriodTotalUserTime", "ThisPeriodTotalKernelTime")]
    _fields_ += [(name, w.DWORD) for name in (
        "TotalPageFaultCount", "TotalProcesses", "ActiveProcesses", "TotalTerminatedProcesses")]

class MemoryStatus(c.Structure):
    _fields_ = [("dwLength", w.DWORD), ("dwMemoryLoad", w.DWORD)]
    _fields_ += [(name, c.c_ulonglong) for name in (
        "ullTotalPhys", "ullAvailPhys", "ullTotalPageFile", "ullAvailPageFile",
        "ullTotalVirtual", "ullAvailVirtual", "ullAvailExtendedVirtual")]

def api(name, restype, args):
    f = getattr(k32, name)
    f.restype = restype
    f.argtypes = args
    return f

create_job = api("CreateJobObjectW", w.HANDLE, [c.c_void_p, w.LPCWSTR])
set_job = api("SetInformationJobObject", w.BOOL, [w.HANDLE, c.c_int, c.c_void_p, w.DWORD])
query_job = api("QueryInformationJobObject", w.BOOL, [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.c_void_p])
assign_job = api("AssignProcessToJobObject", w.BOOL, [w.HANDLE, w.HANDLE])
terminate_job = api("TerminateJobObject", w.BOOL, [w.HANDLE, w.UINT])
resume_thread = api("ResumeThread", w.DWORD, [w.HANDLE])
close_handle = api("CloseHandle", w.BOOL, [w.HANDLE])
memory_status = api("GlobalMemoryStatusEx", w.BOOL, [c.POINTER(MemoryStatus)])

class ProcessIds(c.Structure):
    _fields_ = [("NumberOfAssignedProcesses", w.DWORD),
                ("NumberOfProcessIdsInList", w.DWORD),
                ("ProcessIdList", c.c_size_t * ACTIVE_LIMIT)]

get_times = api("GetProcessTimes", w.BOOL,
    [w.HANDLE, c.POINTER(w.FILETIME), c.POINTER(w.FILETIME), c.POINTER(w.FILETIME), c.POINTER(w.FILETIME)])

def require(value, operation):
    if not value:
        raise c.WinError(c.get_last_error(), operation)
    return value

def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def known_directory(path):
    s = path.lstat()
    if not stat.S_ISDIR(s.st_mode) or getattr(s, "st_file_attributes", 0) & 0x400:
        raise RuntimeError("known owned directory type differs: " + str(path))
    return s

def file_pin(path, expected_bytes=None, expected_sha=None):
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or getattr(before, "st_file_attributes", 0) & 0x400:
        raise RuntimeError("pinned file type differs: " + str(path))
    if before.st_size > 134217728 or (expected_bytes is not None and before.st_size != expected_bytes):
        raise RuntimeError("pinned file size differs: " + str(path))
    h = hashlib.sha256()
    count = 0
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(1048576)
            if not chunk:
                break
            count += len(chunk)
            if count > 134217728:
                raise RuntimeError("pinned file read bound")
            h.update(chunk)
    after = path.lstat()
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino) or count != before.st_size:
        raise RuntimeError("pinned file changed during read: " + str(path))
    actual = h.hexdigest()
    if expected_sha is not None and actual != expected_sha:
        raise RuntimeError("pinned file digest differs: " + str(path))
    return {"path": str(path), "bytes": count, "sha256": actual,
            "mtime_ns": before.st_mtime_ns, "creation_ns": getattr(before, "st_birthtime_ns", None),
            "file_id": before.st_ino, "mode": before.st_mode,
            "attributes": getattr(before, "st_file_attributes", None)}

def save(name, raw):
    if name not in OUTPUTS or len(raw) > 524288:
        raise RuntimeError("fixed owned receipt path/size bound")
    path = ROOT / name
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    if path.read_bytes() != raw:
        raise RuntimeError("owned receipt readback differs")
    return {"path": str(path), "bytes": len(raw), "sha256": digest(raw)}

def save_json(name, value):
    return save(name, (json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode("ascii"))

def times(handle):
    values = [w.FILETIME() for _ in range(4)]
    require(get_times(handle, *(c.byref(x) for x in values)), "GetProcessTimes own child")
    return {key: (value.dwHighDateTime << 32) | value.dwLowDateTime
            for key, value in zip(("creation_filetime", "exit_filetime", "kernel_100ns", "user_100ns"), values)}

result = {
    "schema": "hamon-e3-ledgerly-raider-fixed-supervisor/1",
    "started_utc": utc(), "supervisor_pid": os.getpid(), "python": sys.version,
    "python_executable": sys.executable, "argv": ARGV, "cwd": str(ROOT),
    "job_memory_limit_bytes": JOB_MEMORY, "active_process_limit": ACTIVE_LIMIT,
    "memory_floor_bytes": MEMORY_FLOOR, "disk_floor_bytes": DISK_FLOOR,
    "wall_seconds": WALL_SECONDS, "termination_reserve_seconds": CHILD_STOP_RESERVE,
    "stream_limits": STREAM_LIMITS, "created_children": 0, "resume_attempted": False,
    "resume_previous_suspend_count": None, "node_exit_code": None,
    "node_handle_signaled": False, "node_process_handle_closed": False,
    "primary_thread_handle_closed": False, "job_closed": False,
    "pins_unchanged": False, "error": None, "cleanup_errors": [], "receipts": [],
    "supervision_passed": False,
    "descendant_closure": "Separate scoped post-close observation required; job accounting is an observation.",
    "application_qualification": "Not evaluated by this supervisor; preserve the driver's original result.",
}
job = hp = ht = None
assigned = False
fds = set()
readers = []
streams = {"stdout": bytearray(), "stderr": bytearray()}
stream_errors = []
overflow = threading.Event()
write_admitted = False

def read_pipe(fd, name):
    try:
        while True:
            remaining = STREAM_LIMITS[name] - len(streams[name])
            chunk = os.read(fd, min(4096, remaining + 1))
            if not chunk:
                return
            streams[name].extend(chunk[:remaining])
            if len(chunk) > remaining:
                stream_errors.append(name + " byte limit exceeded")
                overflow.set()
                return
    except Exception as exc:
        stream_errors.append(type(exc).__name__ + ": " + str(exc))
        overflow.set()
    finally:
        os.close(fd)

try:
    if os.name != "nt" or c.sizeof(c.c_void_p) != 8 or c.sizeof(Extended) != 144 or c.sizeof(Accounting) != 48 or c.sizeof(ProcessIds) != 136:
        raise RuntimeError("native platform/Win32 structure layout differs")
    if os.path.normcase(sys.executable) != os.path.normcase(str(PYTHON)) or not sys.dont_write_bytecode or sys.version_info[:3] != (3, 14, 3):
        raise RuntimeError("existing pinned Python/-B/version differs")
    if Path.cwd() != ROOT:
        raise RuntimeError("fixed owned working directory differs")
    known_directory(ROOT)
    known_directory(ROOT / "temp")
    if any(os.path.lexists(ROOT / name) for name in OUTPUTS):
        raise RuntimeError("existing supervisor output refused unchanged")
    mem = MemoryStatus()
    mem.dwLength = c.sizeof(mem)
    require(memory_status(c.byref(mem)), "GlobalMemoryStatusEx")
    result["available_memory_before_child_bytes"] = mem.ullAvailPhys
    result["free_owned_volume_bytes"] = shutil.disk_usage(ROOT).free
    if mem.ullAvailPhys < MEMORY_FLOOR or result["free_owned_volume_bytes"] < DISK_FLOOR:
        raise RuntimeError("fresh 2 GiB RAM / 256 MiB disk floor refused")
    write_admitted = True
    result["pins_before"] = [file_pin(*p) for p in PINS]
    result["supervisor_source"] = file_pin(Path(__file__))
    if time.monotonic() >= deadline - CHILD_STOP_RESERVE:
        raise TimeoutError("supervisor admission exhausted wall bound")
    job = require(create_job(None, None), "CreateJobObjectW anonymous own job")
    info = Extended()
    info.BasicLimitInformation.LimitFlags = 0x2000 | 0x0200 | 0x0008
    info.BasicLimitInformation.ActiveProcessLimit = ACTIVE_LIMIT
    info.JobMemoryLimit = JOB_MEMORY
    require(set_job(job, 9, c.byref(info), c.sizeof(info)), "SetInformationJobObject")
    observed = Extended()
    require(query_job(job, 9, c.byref(observed), c.sizeof(observed), None), "QueryInformationJobObject limits")
    if observed.JobMemoryLimit != JOB_MEMORY or observed.BasicLimitInformation.ActiveProcessLimit != ACTIVE_LIMIT or observed.BasicLimitInformation.LimitFlags != info.BasicLimitInformation.LimitFlags:
        raise RuntimeError("own job limits were not established")
    result["job_limits_before_process"] = {
        "limit_flags": observed.BasicLimitInformation.LimitFlags,
        "job_memory_limit_bytes": observed.JobMemoryLimit,
        "active_process_limit": observed.BasicLimitInformation.ActiveProcessLimit,
        "anonymous": True, "breakaway_requested": False,
    }
    stdin_fd = os.open(os.devnull, os.O_RDONLY | os.O_BINARY)
    fds.add(stdin_fd)
    stdout_r, stdout_w = os.pipe()
    fds.update((stdout_r, stdout_w))
    stderr_r, stderr_w = os.pipe()
    fds.update((stderr_r, stderr_w))
    handles = [msvcrt.get_osfhandle(fd) for fd in (stdin_fd, stdout_w, stderr_w)]
    for handle in handles:
        os.set_handle_inheritable(handle, True)
    si = subprocess.STARTUPINFO(dwFlags=_winapi.STARTF_USESTDHANDLES,
        hStdInput=handles[0], hStdOutput=handles[1], hStdError=handles[2],
        lpAttributeList={"handle_list": handles})
    child_env = os.environ.copy()
    child_env["TEMP"] = str(ROOT / "temp")
    child_env["TMP"] = str(ROOT / "temp")
    hp, ht, pid, tid = _winapi.CreateProcess(
        str(NODE), subprocess.list2cmdline(ARGV), None, None, True,
        0x00000004 | 0x08000000, child_env, str(ROOT), si)
    result["created_children"] = 1
    result["node_pid"] = pid
    result["node_thread_id"] = tid
    result["node_times_before_resume"] = times(hp)
    for fd in (stdin_fd, stdout_w, stderr_w):
        os.close(fd)
        fds.remove(fd)
    require(assign_job(job, hp), "AssignProcessToJobObject suspended own Node")
    assigned = True
    result["job_assigned_before_resume"] = True
    result["receipts"].append(save_json("SUPERVISOR-CHILD-START.json", {
        "utc": utc(), "pid": pid, "thread_id": tid, "argv": ARGV,
        "times": result["node_times_before_resume"], "state": "created-suspended",
        "job_limits": result["job_limits_before_process"],
    }))
    for fd, name in ((stdout_r, "stdout"), (stderr_r, "stderr")):
        t = threading.Thread(target=read_pipe, args=(fd, name), daemon=True)
        t.start()
        fds.remove(fd)
        readers.append(t)
    result["resume_attempted"] = True
    previous = resume_thread(ht)
    result["resume_previous_suspend_count"] = previous
    if previous == 0xFFFFFFFF:
        raise c.WinError(c.get_last_error(), "ResumeThread")
    if previous != 1:
        raise RuntimeError("unexpected suspension count; execution state uncertain")
    result["resumed_at_utc"] = utc()
    while True:
        waited = _winapi.WaitForSingleObject(hp, 25)
        result["last_node_wait_result"] = waited
        if waited == _winapi.WAIT_OBJECT_0:
            result["node_handle_signaled"] = True
            result["node_exit_code"] = _winapi.GetExitCodeProcess(hp)
            break
        if waited != _winapi.WAIT_TIMEOUT:
            raise RuntimeError("unexpected own Node wait result")
        if overflow.is_set():
            raise RuntimeError("bounded Node stream refused: " + "; ".join(stream_errors))
        if time.monotonic() >= deadline - CHILD_STOP_RESERVE:
            raise TimeoutError("supervisor wall bound; reserve time for own child/job closure")
except Exception as exc:
    result["error"] = {"type": type(exc).__name__, "message": str(exc)}
finally:
    if hp is not None:
        try:
            waited = _winapi.WaitForSingleObject(hp, 0)
            result["node_wait_before_cleanup"] = waited
            if waited == _winapi.WAIT_TIMEOUT:
                result["termination_requested"] = True
                if assigned:
                    if not terminate_job(job, 125):
                        result["cleanup_errors"].append("TerminateJobObject failed: " + str(c.get_last_error()))
                        _winapi.TerminateProcess(hp, 125)
                else:
                    _winapi.TerminateProcess(hp, 125)
                waited = _winapi.WaitForSingleObject(hp, 2000)
            if waited == _winapi.WAIT_OBJECT_0:
                result["node_handle_signaled"] = True
                result["node_exit_code"] = _winapi.GetExitCodeProcess(hp)
            else:
                result["cleanup_errors"].append("own Node handle not observed signaled: " + str(waited))
            result["node_times_at_cleanup"] = times(hp)
        except Exception as exc:
            result["cleanup_errors"].append("own Node wait/times: " + type(exc).__name__ + ": " + str(exc))
    for fd in tuple(fds):
        try:
            os.close(fd)
        except Exception as exc:
            result["cleanup_errors"].append("owned pipe close: " + str(exc))
    for label, handle in (("primary_thread_handle_closed", ht), ("node_process_handle_closed", hp)):
        if handle is not None:
            try:
                _winapi.CloseHandle(handle)
                result[label] = True
            except Exception as exc:
                result["cleanup_errors"].append(label + ": " + str(exc))
    if job is not None:
        try:
            observed = Extended()
            require(query_job(job, 9, c.byref(observed), c.sizeof(observed), None), "own job memory observation")
            result["peak_process_committed_bytes"] = observed.PeakProcessMemoryUsed
            result["peak_job_committed_bytes"] = observed.PeakJobMemoryUsed
            accounting = Accounting()
            require(query_job(job, 1, c.byref(accounting), c.sizeof(accounting), None), "own job accounting observation")
            result["job_accounting_before_close"] = {
                "total_processes": accounting.TotalProcesses,
                "active_processes": accounting.ActiveProcesses,
                "terminated_processes": accounting.TotalTerminatedProcesses,
                "meaning": "Observed association counts after closing the Node/thread handles; no total==1 requirement and no descendant-closure proof.",
            }
            ids = ProcessIds()
            ok = query_job(job, 3, c.byref(ids), c.sizeof(ids), None)
            result["job_process_ids_before_close"] = {
                "query_succeeded": bool(ok), "winerror": None if ok else c.get_last_error(),
                "assigned_count": ids.NumberOfAssignedProcesses,
                "returned_count": ids.NumberOfProcessIdsInList,
                "pids": list(ids.ProcessIdList[:min(ids.NumberOfProcessIdsInList, ACTIVE_LIMIT)]),
                "complete": bool(ok and ids.NumberOfAssignedProcesses == ids.NumberOfProcessIdsInList and ids.NumberOfProcessIdsInList <= ACTIVE_LIMIT),
            }
        except Exception as exc:
            result["cleanup_errors"].append("own job observation: " + type(exc).__name__ + ": " + str(exc))
        finally:
            result["job_close_attempted_at_utc"] = utc()
            result["job_closed"] = bool(close_handle(job))
            if not result["job_closed"]:
                result["cleanup_errors"].append("CloseHandle own job failed: " + str(c.get_last_error()))
    for t in readers:
        t.join(1.0)
    if any(t.is_alive() for t in readers):
        result["cleanup_errors"].append("owned pipe reader not observed closed")
    if stream_errors:
        result["stream_errors"] = stream_errors

if write_admitted:
    try:
        result["pins_after"] = [file_pin(*p) for p in PINS]
        result["pins_unchanged"] = result.get("pins_before") == result["pins_after"]
        result["supervisor_source_unchanged"] = result.get("supervisor_source") == file_pin(Path(__file__))
    except Exception as exc:
        result["preservation_error"] = {"type": type(exc).__name__, "message": str(exc)}
for name in ("stdout", "stderr"):
    raw = bytes(streams[name])
    result[name + "_bytes"] = len(raw)
    result[name + "_sha256"] = digest(raw)
    result[name + "_base64"] = base64.b64encode(raw).decode("ascii")
    if write_admitted:
        try:
            result["receipts"].append(save("node." + name + ".txt", raw))
        except Exception as exc:
            result["cleanup_errors"].append("owned stream receipt: " + str(exc))
result["finished_utc"] = utc()
result["elapsed_seconds"] = time.monotonic() - started
result["wall_bound_observed"] = result["elapsed_seconds"] <= WALL_SECONDS
result["supervision_passed"] = bool(
    result["created_children"] == 1 and result["resume_previous_suspend_count"] == 1
    and result["node_exit_code"] == 0 and result["node_handle_signaled"]
    and result["node_process_handle_closed"] and result["primary_thread_handle_closed"]
    and result["job_closed"] and result["pins_unchanged"]
    and result.get("supervisor_source_unchanged") and result["wall_bound_observed"]
    and result.get("peak_job_committed_bytes", JOB_MEMORY + 1) <= JOB_MEMORY
    and not result["error"] and not result["cleanup_errors"] and not stream_errors
    and not result.get("preservation_error")
)
if write_admitted:
    try:
        result["supervisor_receipt"] = save_json("SUPERVISOR.json", result)
    except Exception as exc:
        result["supervision_passed"] = False
        result["receipt_error"] = {"type": type(exc).__name__, "message": str(exc)}
summary = {key: result.get(key) for key in (
    "schema", "supervisor_pid", "node_pid", "node_exit_code", "node_handle_signaled",
    "node_process_handle_closed", "job_closed", "job_accounting_before_close",
    "job_process_ids_before_close", "pins_unchanged", "supervision_passed",
    "descendant_closure", "application_qualification", "elapsed_seconds", "wall_bound_observed",
    "stdout_bytes", "stdout_sha256", "stderr_bytes", "stderr_sha256",
    "supervisor_receipt", "error", "cleanup_errors", "preservation_error", "receipt_error")}
out = (json.dumps(summary, ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")
if len(out) > 32768:
    raise RuntimeError("supervisor final capture bound")
sys.stdout.buffer.write(out)
sys.stdout.buffer.flush()
raise SystemExit(0 if result["supervision_passed"] else 3)
