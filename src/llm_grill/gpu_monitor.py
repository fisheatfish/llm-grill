"""Background GPU metrics collection via nvidia-smi over SSH."""

from __future__ import annotations

import bisect
import logging
from collections import defaultdict
from dataclasses import dataclass, field

import anyio
import anyio.abc

from llm_grill.config import BackendConfig

logger = logging.getLogger(__name__)

_NVIDIA_SMI_QUERY = (
    "index,memory.used,memory.total,utilization.gpu,temperature.gpu,"
    "power.draw,pcie.link.gen.current,pcie.link.width.current,"
    "utilization.memory,clocks.current.sm"
)
_MAX_SNAPSHOTS = 500


@dataclass
class GpuSnapshot:
    timestamp: float
    host: str
    gpus: list[dict] = field(default_factory=list)
    mem_used_mib_total: float = 0.0
    mem_total_mib_total: float = 0.0
    util_pct_avg: float = 0.0
    mem_util_pct_avg: float = 0.0


class GpuMonitor:
    def __init__(self, backends: list[BackendConfig], poll_interval: float = 2.0) -> None:
        self._backends = [b for b in backends if b.effective_ssh_host]
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
        result = {
            "gpu_mem_used_mib": snap.mem_used_mib_total,
            "gpu_mem_total_mib": snap.mem_total_mib_total,
            "gpu_util_pct": snap.util_pct_avg,
            "gpu_temp_c_max": max((g["temp_c"] for g in snap.gpus), default=None),
            "gpu_power_w_total": sum(g["power_w"] for g in snap.gpus) if snap.gpus else None,
            "gpu_mem_util_pct_avg": snap.mem_util_pct_avg,
        }
        # Include per-GPU details for multi-GPU setups
        if len(snap.gpus) > 1:
            result["gpu_per_device"] = snap.gpus
        return result

    async def _poll_host(self, cfg: BackendConfig) -> None:
        host = cfg.effective_ssh_host
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
            gpu: dict = {
                "gpu_index": int(parts[0]),
                "mem_used_mib": float(parts[1]),
                "mem_total_mib": float(parts[2]),
                "util_pct": float(parts[3]),
                "temp_c": float(parts[4]),
                "power_w": float(parts[5]),
            }
            # Optional fields — may return [N/A] on some GPUs
            if len(parts) > 6:
                gpu["pcie_gen"] = _safe_int(parts[6])
                gpu["pcie_width"] = _safe_int(parts[7])
            if len(parts) > 8:
                gpu["mem_util_pct"] = _safe_float(parts[8])
            if len(parts) > 9:
                gpu["sm_clock_mhz"] = _safe_float(parts[9])
            gpus.append(gpu)
        except (ValueError, IndexError):
            continue

    mem_used = sum(g["mem_used_mib"] for g in gpus)
    mem_total = sum(g["mem_total_mib"] for g in gpus)
    util_avg = sum(g["util_pct"] for g in gpus) / len(gpus) if gpus else 0.0
    mem_util_avg = sum(g.get("mem_util_pct", 0) for g in gpus) / len(gpus) if gpus else 0.0

    return GpuSnapshot(
        timestamp=0.0,
        host=host,
        gpus=gpus,
        mem_used_mib_total=mem_used,
        mem_total_mib_total=mem_total,
        util_pct_avg=util_avg,
        mem_util_pct_avg=mem_util_avg,
    )


def _safe_float(val: str) -> float | None:
    try:
        return float(val)
    except ValueError:
        return None


def _safe_int(val: str) -> int | None:
    try:
        return int(val)
    except ValueError:
        return None
