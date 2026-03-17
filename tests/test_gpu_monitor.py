"""Tests for gpu_monitor.py — CSV parsing and bisect lookup."""

from __future__ import annotations

from llm_bench.gpu_monitor import GpuMonitor, GpuSnapshot, _parse_nvidia_csv


class TestParseNvidiaCsv:
    def test_single_gpu(self) -> None:
        csv = "0, 4096, 8192, 85, 62, 250.0"
        snap = _parse_nvidia_csv(csv, "host1")
        assert len(snap.gpus) == 1
        assert snap.gpus[0]["gpu_index"] == 0
        assert snap.gpus[0]["mem_used_mib"] == 4096.0
        assert snap.mem_used_mib_total == 4096.0
        assert snap.mem_total_mib_total == 8192.0
        assert snap.util_pct_avg == 85.0

    def test_multi_gpu(self) -> None:
        csv = "0, 4000, 8000, 80, 60, 200\n1, 6000, 8000, 90, 65, 220"
        snap = _parse_nvidia_csv(csv, "host1")
        assert len(snap.gpus) == 2
        assert snap.mem_used_mib_total == 10000.0
        assert snap.util_pct_avg == 85.0

    def test_empty_output(self) -> None:
        snap = _parse_nvidia_csv("", "host1")
        assert len(snap.gpus) == 0
        assert snap.util_pct_avg == 0.0

    def test_malformed_line_skipped(self) -> None:
        csv = "0, 4096, 8192, 85, 62, 250\nbad line\n1, 2048, 4096, 50, 55, 150"
        snap = _parse_nvidia_csv(csv, "host1")
        assert len(snap.gpus) == 2


class TestGetNearest:
    def test_exact_match(self) -> None:
        monitor = GpuMonitor([], poll_interval=1.0)
        snap = GpuSnapshot(
            timestamp=10.0,
            host="h1",
            mem_used_mib_total=4000,
            mem_total_mib_total=8000,
            util_pct_avg=80,
        )
        monitor._snapshots["h1"] = [snap]
        monitor._timestamps["h1"] = [10.0]
        result = monitor.get_nearest("h1", 10.0)
        assert result is not None
        assert result["gpu_util_pct"] == 80.0

    def test_nearest_before(self) -> None:
        monitor = GpuMonitor([], poll_interval=1.0)
        snap1 = GpuSnapshot(
            timestamp=10.0,
            host="h1",
            mem_used_mib_total=4000,
            mem_total_mib_total=8000,
            util_pct_avg=80,
        )
        snap2 = GpuSnapshot(
            timestamp=20.0,
            host="h1",
            mem_used_mib_total=5000,
            mem_total_mib_total=8000,
            util_pct_avg=90,
        )
        monitor._snapshots["h1"] = [snap1, snap2]
        monitor._timestamps["h1"] = [10.0, 20.0]
        result = monitor.get_nearest("h1", 12.0)
        assert result is not None
        assert result["gpu_util_pct"] == 80.0

    def test_unknown_host_returns_none(self) -> None:
        monitor = GpuMonitor([], poll_interval=1.0)
        assert monitor.get_nearest("unknown", 10.0) is None
