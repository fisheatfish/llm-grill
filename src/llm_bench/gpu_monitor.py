"""Background GPU metrics collection via nvidia-smi over SSH."""

from __future__ import annotations

import bisect
import logging
from collections import defaultdict
from dataclasses import dataclass, field

import anyio
import anyio.abc

from llm_bench.config import BackendConfig

logger = logging.getLogger(__name__)

_NVIDIA_SMI_QUERY = "index,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw"
_MAX_SNAPSHOTS = 500


@dataclass
class GpuSnapshot:
    timestamp: float
    host: str
    gpus: list[dict] = field(default_factory=list)
    mem_used_mib_total: float = 0.0
    mem_total_mib_total: float = 0.0
    util_pct_avg: float = 0.0


class GpuMonitor:
    def __init__(self, backends: list[BackendConfig], poll_interval: float = 2.0) -> None:
        self._backends = [b for b in backends if b.ssh_host]
        self._poll_interval = poll_interval
        self._snapshots: dict[str, list[GpuSnapshot]] = defaultdict(list)
        self._timestamps: dict[str, list[float]] = defaultdict(list)
        self._cancel = anyio.Event()

    async def start(self, task_group: anyio.abc.TaskGroup) -> None:
        for cfg in self._backends:
            task_group.start_soon(self._poll_host, cfg)

    def stop(self) -> None:
        self._cancel.set()

    def get_nearest(self, host: str, timestamp: float) -> dict | None:
        ts_list = self._timestamps.get(host)
        if not ts_list:
            return None
        idx = bisect.bisect_left(ts_list, timestamp)
        candidates = []
        if idx < len(ts_list):
            candidates.append(idx)
        if idx > 0:
            candidates.append(idx - 1)
        best = min(candidates, key=lambda i: abs(ts_list[i] - timestamp))
        snap = self._snapshots[host][best]
        return {
            "gpu_mem_used_mib": snap.mem_used_mib_total,
            "gpu_mem_total_mib": snap.mem_total_mib_total,
            "gpu_util_pct": snap.util_pct_avg,
        }

    async def _poll_host(self, cfg: BackendConfig) -> None:
        host = cfg.ssh_host
        assert host is not None
        user = cfg.ssh_user
        cmd = [
            "ssh",
            "-o",
            "ConnectTimeout=5",
            "-o",
            "StrictHostKeyChecking=no",
            f"{user}@{host}",
            "nvidia-smi",
            f"--query-gpu={_NVIDIA_SMI_QUERY}",
            "--format=csv,noheader,nounits",
        ]
        while not self._cancel.is_set():
            try:
                result = await anyio.run_process(cmd, check=False)
                if result.returncode == 0:
                    snap = _parse_nvidia_csv(result.stdout.decode().strip(), host)
                    snap.timestamp = anyio.current_time()
                    snaps = self._snapshots[host]
                    ts_list = self._timestamps[host]
                    snaps.append(snap)
                    ts_list.append(snap.timestamp)
                    if len(snaps) > _MAX_SNAPSHOTS:
                        snaps.pop(0)
                        ts_list.pop(0)
                else:
                    logger.debug(
                        "nvidia-smi failed on %s: %s", host, result.stderr.decode().strip()
                    )
            except Exception as exc:
                logger.debug("GPU poll error for %s: %s", host, exc)

            with anyio.move_on_after(self._poll_interval):
                await self._cancel.wait()
                return


def _parse_nvidia_csv(output: str, host: str) -> GpuSnapshot:
    gpus: list[dict] = []
    for line in output.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6:
            continue
        try:
            gpus.append(
                {
                    "gpu_index": int(parts[0]),
                    "mem_used_mib": float(parts[1]),
                    "mem_total_mib": float(parts[2]),
                    "util_pct": float(parts[3]),
                    "temp_c": float(parts[4]),
                    "power_w": float(parts[5]),
                }
            )
        except (ValueError, IndexError):
            continue

    mem_used = sum(g["mem_used_mib"] for g in gpus)
    mem_total = sum(g["mem_total_mib"] for g in gpus)
    util_avg = sum(g["util_pct"] for g in gpus) / len(gpus) if gpus else 0.0

    return GpuSnapshot(
        timestamp=0.0,
        host=host,
        gpus=gpus,
        mem_used_mib_total=mem_used,
        mem_total_mib_total=mem_total,
        util_pct_avg=util_avg,
    )
