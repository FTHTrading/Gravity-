"""
Async Executor – Async batch equation analysis for performance-critical paths.

Phase VII: Scalability & Performance

Capabilities:
  - Batch equation analysis with concurrent execution
  - Thread-pool-based parallelism (no external deps required)
  - Progress tracking and error isolation
  - Deterministic result ordering
"""

import time
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

from src.logger import get_logger

log = get_logger(__name__)


@dataclass
class BatchResult:
    """Result of a batch analysis operation."""
    total: int = 0
    completed: int = 0
    failed: int = 0
    results: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    elapsed_sec: float = 0.0
    sha256_hash: str = ""

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "result_count": len(self.results),
            "errors": self.errors,
            "elapsed_sec": round(self.elapsed_sec, 4),
            "sha256_hash": self.sha256_hash,
        }

    def compute_hash(self):
        canonical = json.dumps(self.to_dict(), sort_keys=True, default=str)
        self.sha256_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return self.sha256_hash


class AsyncExecutor:
    """
    Execute batch operations using a thread pool for CPU-bound
    equation analysis. Maintains deterministic result ordering.
    """

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers

    def run_batch(self, items: list, fn: Callable,
                  label: str = "batch") -> BatchResult:
        """
        Process a list of items with a given function using thread pool.

        Args:
            items: List of inputs to process
            fn: Function to apply to each item. Must accept a single arg.
            label: Label for logging

        Returns:
            BatchResult with deterministic ordering (matching input order)
        """
        batch = BatchResult(total=len(items))
        start = time.perf_counter()

        # Map: index → future, to preserve order
        results_by_index = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {}
            for i, item in enumerate(items):
                future = pool.submit(fn, item)
                futures[future] = i

            for future in as_completed(futures):
                idx = futures[future]
                try:
                    result = future.result()
                    results_by_index[idx] = result
                    batch.completed += 1
                except Exception as exc:
                    batch.failed += 1
                    batch.errors.append({
                        "index": idx,
                        "error": str(exc),
                    })
                    results_by_index[idx] = None

        # Reconstruct in original order
        batch.results = [results_by_index.get(i) for i in range(len(items))]
        batch.elapsed_sec = time.perf_counter() - start

        batch.compute_hash()
        log.info("Batch '%s': %d/%d completed in %.2fs (%d errors)",
                 label, batch.completed, batch.total,
                 batch.elapsed_sec, batch.failed)

        return batch

    def run_sequential(self, items: list, fn: Callable,
                       label: str = "sequential") -> BatchResult:
        """
        Process items sequentially (for deterministic benchmarking).
        """
        batch = BatchResult(total=len(items))
        start = time.perf_counter()

        for i, item in enumerate(items):
            try:
                result = fn(item)
                batch.results.append(result)
                batch.completed += 1
            except Exception as exc:
                batch.failed += 1
                batch.errors.append({"index": i, "error": str(exc)})
                batch.results.append(None)

        batch.elapsed_sec = time.perf_counter() - start
        batch.compute_hash()
        log.info("Sequential '%s': %d/%d in %.2fs",
                 label, batch.completed, batch.total, batch.elapsed_sec)

        return batch
