"""
Benchmark Suite – Performance measurement and logging.

Phase VII: Scalability & Performance

Capabilities:
  - Time any operation with context manager
  - Track memory and CPU usage
  - Log results to performance_metrics table and logs/
  - Generate performance reports
"""

import os
import time
import json
import hashlib
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.logger import get_logger
from src.config import LOGS_DIR

log = get_logger(__name__)


@dataclass
class BenchmarkRecord:
    """A single benchmark measurement."""
    operation: str
    duration_sec: float = 0.0
    memory_bytes: int = 0
    cpu_percent: float = 0.0
    metadata: dict = field(default_factory=dict)
    timestamp: str = ""
    sha256_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "operation": self.operation,
            "duration_sec": round(self.duration_sec, 6),
            "memory_bytes": self.memory_bytes,
            "cpu_percent": round(self.cpu_percent, 2),
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "sha256_hash": self.sha256_hash,
        }

    def compute_hash(self):
        d = self.to_dict()
        d.pop("sha256_hash", None)
        canonical = json.dumps(d, sort_keys=True, default=str)
        self.sha256_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return self.sha256_hash


class BenchmarkSuite:
    """
    Performance benchmarking with DB persistence and log output.
    """

    def __init__(self):
        self._records: list[BenchmarkRecord] = []

    @contextmanager
    def measure(self, operation: str, metadata: dict = None):
        """
        Context manager to measure operation duration.

        Usage:
            suite = BenchmarkSuite()
            with suite.measure("parse_equation", {"name": "E=mc2"}):
                parser.parse_plaintext("m*c**2")
        """
        record = BenchmarkRecord(
            operation=operation,
            metadata=metadata or {},
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        start = time.perf_counter()
        try:
            yield record
        finally:
            record.duration_sec = time.perf_counter() - start
            # Try to get memory usage
            try:
                import psutil
                process = psutil.Process(os.getpid())
                mem = process.memory_info()
                record.memory_bytes = mem.rss
                record.cpu_percent = process.cpu_percent(interval=None)
            except ImportError:
                pass
            except Exception:
                pass

            record.compute_hash()
            self._records.append(record)
            log.info("Benchmark '%s': %.4fs, %d bytes",
                     operation, record.duration_sec, record.memory_bytes)

    def time_function(self, operation: str, fn, *args, **kwargs):
        """
        Time a function call.

        Returns:
            (result, BenchmarkRecord)
        """
        record = BenchmarkRecord(
            operation=operation,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        start = time.perf_counter()
        result = fn(*args, **kwargs)
        record.duration_sec = time.perf_counter() - start
        record.compute_hash()
        self._records.append(record)

        log.info("Benchmark '%s': %.4fs", operation, record.duration_sec)
        return result, record

    @property
    def records(self) -> list[BenchmarkRecord]:
        return list(self._records)

    def summary(self) -> dict:
        """Generate summary statistics."""
        if not self._records:
            return {"total_records": 0}

        durations = [r.duration_sec for r in self._records]
        return {
            "total_records": len(self._records),
            "total_time_sec": round(sum(durations), 6),
            "avg_time_sec": round(sum(durations) / len(durations), 6),
            "min_time_sec": round(min(durations), 6),
            "max_time_sec": round(max(durations), 6),
            "operations": list(set(r.operation for r in self._records)),
        }

    def save_to_db(self) -> int:
        """Save all records to performance_metrics table."""
        from src.database import insert_row
        saved = 0
        for r in self._records:
            try:
                insert_row("performance_metrics", {
                    "operation": r.operation,
                    "duration_sec": r.duration_sec,
                    "memory_bytes": r.memory_bytes,
                    "cpu_percent": r.cpu_percent,
                    "metadata_json": json.dumps(r.metadata, default=str),
                    "result_hash": r.sha256_hash,
                    "measured_at": r.timestamp,
                })
                saved += 1
            except Exception as exc:
                log.debug("Failed to save benchmark: %s", exc)
        log.info("Saved %d benchmark records to database", saved)
        return saved

    def save_to_log(self, filename: str = "benchmarks.json"):
        """Save records to a JSON log file."""
        path = os.path.join(LOGS_DIR, filename)
        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": self.summary(),
            "records": [r.to_dict() for r in self._records],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        log.info("Saved benchmarks to %s", path)

    def clear(self):
        """Clear all recorded benchmarks."""
        self._records.clear()
