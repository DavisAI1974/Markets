"""Safe operational resource observations for Frankie/BOSS native execution.

This module observes host/process resources only. It never reads market evidence,
model tensors, prompts, credentials, or optimizer contents. Diagnostics are
advisory and must never become scientific authority.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import platform


def _linux_kib(path, names):
    result = {}
    try:
        for line in Path(path).read_text(encoding='utf-8').splitlines():
            key, _, tail = line.partition(':')
            if key in names:
                pieces = tail.strip().split()
                if pieces and pieces[0].isdigit():
                    result[key] = int(pieces[0]) * 1024
    except (OSError, UnicodeError):
        pass
    return result


def _windows_memory():
    if os.name != 'nt':
        return {}
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
        status = MEMORYSTATUSEX(); status.dwLength = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return {}

        class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
            _fields_ = [('cb', ctypes.c_ulong), ('PageFaultCount', ctypes.c_ulong),
                ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t),
                ('PrivateUsage', ctypes.c_size_t)]
        counters = PROCESS_MEMORY_COUNTERS_EX(); counters.cb = ctypes.sizeof(counters)
        kernel32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
        # GetCurrentProcess returns the pseudo-handle (HANDLE)-1. Left untyped, ctypes hands it
        # back as a 32-bit int and GetProcessMemoryInfo rejects it, so every process field was
        # silently absent on 64-bit Windows (measured 2026-09-15: only the two system fields came
        # back). Type the handle and the call.
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESS_MEMORY_COUNTERS_EX), ctypes.c_ulong]
        process = {}
        if psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            process = dict(process_rss_bytes=int(counters.WorkingSetSize),
                process_peak_rss_bytes=int(counters.PeakWorkingSetSize),
                process_private_bytes=int(counters.PrivateUsage))
        return dict(system_memory_total_bytes=int(status.ullTotalPhys),
            system_memory_available_bytes=int(status.ullAvailPhys), **process)
    except (AttributeError, OSError, ValueError):
        return {}


def memory_snapshot():
    """Return bounded scalar memory observations; missing fields are simply absent."""
    if os.name == 'nt':
        return _windows_memory()
    status = _linux_kib('/proc/self/status', {'VmRSS', 'VmHWM'})
    memory = _linux_kib('/proc/meminfo', {'MemTotal', 'MemAvailable'})
    result = {}
    if 'VmRSS' in status: result['process_rss_bytes'] = status['VmRSS']
    if 'VmHWM' in status: result['process_peak_rss_bytes'] = status['VmHWM']
    if 'MemTotal' in memory: result['system_memory_total_bytes'] = memory['MemTotal']
    if 'MemAvailable' in memory: result['system_memory_available_bytes'] = memory['MemAvailable']
    return result


def cpu_model():
    """Best-effort non-secret CPU model string for numeric-runtime provenance."""
    if os.name == 'nt':
        return os.environ.get('PROCESSOR_IDENTIFIER') or platform.processor() or 'unknown'
    try:
        for line in Path('/proc/cpuinfo').read_text(encoding='utf-8').splitlines():
            if line.lower().startswith('model name'):
                return line.partition(':')[2].strip() or 'unknown'
    except (OSError, UnicodeError):
        pass
    return platform.processor() or platform.machine() or 'unknown'


def host_snapshot():
    """Safe host facts that may be persisted beside run diagnostics."""
    return dict(platform_system=platform.system(), platform_release=platform.release(),
        platform_machine=platform.machine(), logical_cpus=os.cpu_count(), cpu_model=cpu_model(),
        **memory_snapshot())
