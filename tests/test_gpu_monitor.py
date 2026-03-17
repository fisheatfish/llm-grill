"""
Tests for gpu_monitor.py.
Tests nvidia-smi CSV parsing and bisect-based nearest snapshot lookup.
"""

from __future__ import annotations

from llm_bench.gpu_monitor import GpuMonitor, GpuSnapshot, _parse_nvidia_csv


class TestParseNvidiaCsv:
    """Tests for nvidia-smi CSV output parsing."""

    def test_should_parse_single_gpu(self):
        """
        Should extract GPU metrics from a single-GPU CSV line.

        Given: A single-line nvidia-smi CSV output
        When: Parsing the CSV
        Then: One GPU is parsed with correct memory and utilization values
        """
        # Given
        csv_output = "0, 4096, 8192, 85, 62, 250.0"

        # When
        snap = _parse_nvidia_csv(csv_output, "host1")

        # Then
        assert len(snap.gpus) == 1
        assert snap.gpus[0]["gpu_index"] == 0
        assert snap.gpus[0]["mem_used_mib"] == 4096.0
        assert snap.mem_used_mib_total == 4096.0
        assert snap.mem_total_mib_total == 8192.0
        assert snap.util_pct_avg == 85.0

    def test_should_aggregate_multi_gpu(self):
        """
        Should sum memory and average utilization across multiple GPUs.

        Given: Two-line nvidia-smi CSV output (2 GPUs)
        When: Parsing the CSV
        Then: Memory is summed and utilization is averaged
        """
        # Given
        csv_output = "0, 4000, 8000, 80, 60, 200\n1, 6000, 8000, 90, 65, 220"

        # When
        snap = _parse_nvidia_csv(csv_output, "host1")

        # Then
        assert len(snap.gpus) == 2
        assert snap.mem_used_mib_total == 10000.0
        assert snap.util_pct_avg == 85.0

    def test_should_handle_empty_output(self):
        """
        Should return empty snapshot when nvidia-smi output is empty.

        Given: An empty string
        When: Parsing the CSV
        Then: No GPUs and zero utilization
        """
        # When
        snap = _parse_nvidia_csv("", "host1")

        # Then
        assert len(snap.gpus) == 0
        assert snap.util_pct_avg == 0.0

    def test_should_skip_malformed_lines(self):
        """
        Should skip unparseable lines and parse valid ones.

        Given: CSV with a malformed line between two valid lines
        When: Parsing the CSV
        Then: Two GPUs are parsed, malformed line is skipped
        """
        # Given
        csv_output = "0, 4096, 8192, 85, 62, 250\nbad line\n1, 2048, 4096, 50, 55, 150"

        # When
        snap = _parse_nvidia_csv(csv_output, "host1")

        # Then
        assert len(snap.gpus) == 2


class TestGetNearest:
    """Tests for GpuMonitor.get_nearest() bisect lookup."""

    def test_should_find_exact_timestamp_match(self):
        """
        Should return the snapshot at the exact requested timestamp.

        Given: A monitor with one snapshot at t=10.0
        When: Querying get_nearest("h1", 10.0)
        Then: Returns the snapshot with correct utilization
        """
        # Given
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

        # When
        result = monitor.get_nearest("h1", 10.0)

        # Then
        assert result is not None
        assert result["gpu_util_pct"] == 80.0

    def test_should_return_nearest_snapshot_before_timestamp(self):
        """
        Should return the closest snapshot before the requested time.

        Given: Two snapshots at t=10.0 (util=80) and t=20.0 (util=90)
        When: Querying get_nearest("h1", 12.0)
        Then: Returns the t=10.0 snapshot (util=80)
        """
        # Given
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

        # When
        result = monitor.get_nearest("h1", 12.0)

        # Then
        assert result is not None
        assert result["gpu_util_pct"] == 80.0

    def test_should_return_none_for_unknown_host(self):
        """
        Should return None when the host has no recorded snapshots.

        Given: An empty monitor
        When: Querying get_nearest("unknown", 10.0)
        Then: Returns None
        """
        # Given
        monitor = GpuMonitor([], poll_interval=1.0)

        # When / Then
        assert monitor.get_nearest("unknown", 10.0) is None
