# Copyright 2025 The ChaosBlade Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""DirectlyInjection executors for CPU burn, memory fill, and process kill.

These execute immediately at create/destroy time without needing method interception.
"""

from __future__ import annotations

import logging
import multiprocessing
import os
import signal
import threading
import time
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from chaosblade.common.model.model import Model

logger = logging.getLogger(__name__)


class CpuBurnExecutor:
    """Burns CPU by running tight loops in worker threads/processes.

    Flags:
      - cpu-count: number of CPU cores to burn (default: all)
      - cpu-percent: target CPU usage percentage (default: 100)
    """

    def __init__(self) -> None:
        self._workers: list[threading.Thread] = []
        self._running = False

    def create_injection(self, uid: str, model: Model) -> None:
        """Start CPU burn workers."""
        cpu_count = self._get_int_flag(model, "cpu-count", multiprocessing.cpu_count())
        cpu_percent = self._get_int_flag(model, "cpu-percent", 100)

        self._running = True
        logger.info("Starting CPU burn: %d cores, %d%% target", cpu_count, cpu_percent)

        for i in range(cpu_count):
            t = threading.Thread(
                target=self._burn_cpu,
                args=(cpu_percent,),
                daemon=True,
                name=f"chaosblade-cpu-{uid}-{i}",
            )
            t.start()
            self._workers.append(t)

    def destroy_injection(self, uid: str, model: Model) -> None:
        """Stop CPU burn workers."""
        self._running = False
        # Wait for threads to finish
        for t in self._workers:
            t.join(timeout=2.0)
        self._workers.clear()
        logger.info("CPU burn stopped for uid=%s", uid)

    def _burn_cpu(self, percent: int) -> None:
        """Burn CPU at the specified percentage."""
        # Simple approach: busy loop for `percent`% of time, sleep for the rest
        interval = 0.1  # 100ms cycles
        burn_time = interval * (percent / 100.0)
        sleep_time = interval - burn_time

        while self._running:
            end = time.perf_counter() + burn_time
            while time.perf_counter() < end:
                pass  # Busy loop
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _get_int_flag(self, model: Model, key: str, default: int) -> int:
        """Get an integer flag from model."""
        if model.action and model.action.get_flag(key):
            try:
                return int(model.action.get_flag(key))
            except (ValueError, TypeError):
                pass
        return default


class MemoryFillExecutor:
    """Fills memory by allocating large byte arrays.

    Flags:
      - mem-percent: percentage of total memory to fill (default: 0)
      - mem-size: specific size in MB to allocate (default: 0, uses percent if 0)
      - mode: "ram" (default) - allocate in memory
    """

    def __init__(self) -> None:
        self._allocated: list[bytearray] = []

    def create_injection(self, uid: str, model: Model) -> None:
        """Allocate memory."""
        size_mb = self._get_target_size_mb(model)
        if size_mb <= 0:
            logger.warning("Memory fill: no valid size specified")
            return

        logger.info("Filling memory: %d MB", size_mb)
        try:
            # Allocate in 64MB chunks to avoid single huge allocation failures
            chunk_size = 64 * 1024 * 1024  # 64MB
            remaining = size_mb * 1024 * 1024

            while remaining > 0:
                alloc_size = min(chunk_size, remaining)
                chunk = bytearray(alloc_size)
                # Touch the memory to ensure it's actually allocated (not just virtual)
                for i in range(0, alloc_size, 4096):
                    chunk[i] = 1
                self._allocated.append(chunk)
                remaining -= alloc_size

            logger.info("Memory fill complete: %d MB allocated", size_mb)
        except MemoryError:
            logger.warning("MemoryError during allocation, allocated partially")

    def destroy_injection(self, uid: str, model: Model) -> None:
        """Release allocated memory."""
        count = len(self._allocated)
        self._allocated.clear()
        logger.info("Memory released: %d chunks freed for uid=%s", count, uid)

    def _get_target_size_mb(self, model: Model) -> int:
        """Determine the target memory size to allocate."""
        # Check mem-size first (explicit MB)
        if model.action:
            size_str = model.action.get_flag("mem-size")
            if size_str:
                try:
                    return int(size_str)
                except (ValueError, TypeError):
                    pass

            # Check mem-percent
            percent_str = model.action.get_flag("mem-percent")
            if percent_str:
                try:
                    percent = int(percent_str)
                    total_mb = self._get_total_memory_mb()
                    return int(total_mb * percent / 100)
                except (ValueError, TypeError):
                    pass

        return 0

    def _get_total_memory_mb(self) -> int:
        """Get total system memory in MB."""
        try:
            import resource
            # Try to get from /proc/meminfo on Linux
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        # Format: "MemTotal:       16384000 kB"
                        parts = line.split()
                        return int(parts[1]) // 1024
        except (ImportError, FileNotFoundError, IOError):
            pass

        # macOS fallback
        try:
            import subprocess
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return int(result.stdout.strip()) // (1024 * 1024)
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
            pass

        # Default 4GB if we can't determine
        return 4096


class ProcessKillExecutor:
    """Kills a process by PID or process name.

    Flags:
      - process: process name pattern to kill
      - process-cmd: command pattern to match
      - signal: signal number to send (default: 9 / SIGKILL)
    """

    def create_injection(self, uid: str, model: Model) -> None:
        """Kill the target process."""
        sig = self._get_signal(model)
        pid = self._find_target_pid(model)

        if pid is None:
            logger.warning("No target process found to kill")
            return

        logger.info("Killing process pid=%d with signal=%d", pid, sig)
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            logger.warning("Process %d not found", pid)
        except PermissionError:
            logger.warning("Permission denied to kill process %d", pid)

    def destroy_injection(self, uid: str, model: Model) -> None:
        """No-op: process kill is not reversible."""
        pass

    def _get_signal(self, model: Model) -> int:
        """Get the signal number from flags."""
        if model.action:
            sig_str = model.action.get_flag("signal")
            if sig_str:
                try:
                    return int(sig_str)
                except (ValueError, TypeError):
                    pass
        return signal.SIGKILL

    def _find_target_pid(self, model: Model) -> int | None:
        """Find the target process PID."""
        if model.action is None:
            return None

        # Direct PID
        pid_str = model.action.get_flag("pid")
        if pid_str:
            try:
                return int(pid_str)
            except (ValueError, TypeError):
                pass

        # By process name
        process_name = model.action.get_flag("process")
        if process_name:
            return self._find_pid_by_name(process_name)

        return None

    def _find_pid_by_name(self, name: str) -> int | None:
        """Find a process PID by its name (best effort)."""
        try:
            import subprocess
            result = subprocess.run(
                ["pgrep", "-f", name],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                pids = result.stdout.strip().split("\n")
                # Return first matching PID that is not ourselves
                my_pid = os.getpid()
                for pid_str in pids:
                    try:
                        pid = int(pid_str.strip())
                        if pid != my_pid:
                            return pid
                    except ValueError:
                        continue
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        return None
