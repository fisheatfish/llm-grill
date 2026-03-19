"""Shared Prometheus text format parser for backend clients."""

from __future__ import annotations


def parse_prometheus(text: str, prefixes: list[str] | None = None) -> dict:
    """Extract metric values from Prometheus text exposition format.

    Args:
        text: Raw Prometheus text response.
        prefixes: If provided, only return metrics whose name starts with one of these prefixes.
                  If None, return all metrics.
    """
    result: dict[str, float] = {}
    for line in text.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        if prefixes and not any(line.startswith(p) for p in prefixes):
            continue
        parts = line.rsplit(" ", 1)
        if len(parts) == 2:
            key = parts[0].split("{")[0].strip()
            try:
                result[key] = float(parts[1])
            except ValueError:
                pass
    return result
