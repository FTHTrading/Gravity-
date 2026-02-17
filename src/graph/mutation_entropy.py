"""
Mutation Entropy Engine – Shannon Entropy & Drift Analysis

Quantifies the information-theoretic properties of claim mutation chains:
  - Shannon entropy of character distributions across mutations
  - Drift velocity: rate of textual change per mutation step
  - Max diff ratio: largest single-step change
  - Semantic stability: inverse of cumulative drift
  - Chain statistics: depth, breadth, branching factor

Results stored in mutation_metrics table.
"""

import math
import hashlib
from collections import Counter
from datetime import datetime, timezone
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from src.database import insert_row, query_rows
from src.graph.claim_graph import ClaimGraph, ClaimNode
from src.logger import get_logger

log = get_logger(__name__)


@dataclass
class MutationMetrics:
    """Quantified mutation analysis for a single claim chain."""
    claim_id: int = 0
    chain_length: int = 0
    shannon_entropy: float = 0.0
    drift_velocity: float = 0.0
    max_diff_ratio: float = 0.0
    semantic_stability: float = 1.0
    step_diffs: list = field(default_factory=list)
    char_distribution: dict = field(default_factory=dict)
    computed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "chain_length": self.chain_length,
            "shannon_entropy": round(self.shannon_entropy, 6),
            "drift_velocity": round(self.drift_velocity, 6),
            "max_diff_ratio": round(self.max_diff_ratio, 6),
            "semantic_stability": round(self.semantic_stability, 6),
            "step_diffs": [round(d, 4) for d in self.step_diffs],
        }


class MutationEntropy:
    """
    Computes information-theoretic metrics for claim mutation chains.

    Higher entropy → more chaotic mutations (potential disinformation).
    Lower entropy → stable / minor editorial changes.
    """

    def __init__(self):
        self.graph = ClaimGraph()

    # ── Core Metrics ─────────────────────────────────────────────────────

    @staticmethod
    def shannon_entropy(text: str) -> float:
        """
        Compute Shannon entropy of character distribution in text.
        H = -Σ p(c) * log2(p(c))
        """
        if not text:
            return 0.0
        freq = Counter(text.lower())
        total = len(text)
        entropy = 0.0
        for count in freq.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy

    @staticmethod
    def text_similarity(text_a: str, text_b: str) -> float:
        """
        SequenceMatcher ratio between two texts.
        Returns value in [0, 1] where 1.0 = identical.
        """
        if not text_a and not text_b:
            return 1.0
        return SequenceMatcher(None, text_a, text_b).ratio()

    @staticmethod
    def diff_ratio(text_a: str, text_b: str) -> float:
        """
        Fraction of characters that changed between two texts.
        Returns value in [0, 1] where 0.0 = identical.
        """
        return 1.0 - MutationEntropy.text_similarity(text_a, text_b)

    # ── Chain Analysis ───────────────────────────────────────────────────

    def analyze_chain(self, claim_id: int) -> MutationMetrics:
        """
        Full mutation analysis for a claim's entire ancestry chain.
        """
        chain = self.graph.get_mutation_chain(claim_id)
        metrics = MutationMetrics(
            claim_id=claim_id,
            chain_length=len(chain),
            computed_at=datetime.now(timezone.utc).isoformat(),
        )

        if len(chain) < 2:
            # No mutations — pure root claim
            if chain:
                metrics.shannon_entropy = self.shannon_entropy(chain[0].claim_text)
                metrics.semantic_stability = 1.0
            return metrics

        # Compute step-by-step diffs
        step_diffs = []
        all_text = ""
        for i in range(len(chain)):
            all_text += chain[i].claim_text
            if i > 0:
                dr = self.diff_ratio(chain[i - 1].claim_text, chain[i].claim_text)
                step_diffs.append(dr)

        metrics.step_diffs = step_diffs
        metrics.max_diff_ratio = max(step_diffs) if step_diffs else 0.0

        # Shannon entropy of concatenated chain text
        metrics.shannon_entropy = self.shannon_entropy(all_text)

        # Character frequency distribution
        freq = Counter(all_text.lower())
        total = len(all_text)
        metrics.char_distribution = {
            c: round(cnt / total, 4) for c, cnt in freq.most_common(20)
        }

        # Drift velocity: average diff per step
        metrics.drift_velocity = (
            sum(step_diffs) / len(step_diffs) if step_diffs else 0.0
        )

        # Semantic stability: 1 - cumulative drift (clamped to [0, 1])
        cumulative_drift = sum(step_diffs)
        metrics.semantic_stability = max(0.0, min(1.0, 1.0 - cumulative_drift / len(chain)))

        log.info("Chain analysis for claim #%d: len=%d entropy=%.4f "
                 "drift=%.4f max_diff=%.4f stability=%.4f",
                 claim_id, metrics.chain_length, metrics.shannon_entropy,
                 metrics.drift_velocity, metrics.max_diff_ratio,
                 metrics.semantic_stability)

        return metrics

    def analyze_all_chains(self) -> list[MutationMetrics]:
        """
        Analyze mutation chains for every claim that has mutations.
        Returns metrics for claims that are chain endpoints (leaf mutations
        or root claims with descendants).
        """
        all_claims = self.graph.get_all_claims()
        results = []
        analyzed_ids = set()

        for claim in all_claims:
            if claim.id in analyzed_ids:
                continue
            chain = self.graph.get_mutation_chain(claim.id)
            if len(chain) >= 2:
                metrics = self.analyze_chain(claim.id)
                results.append(metrics)
                for c in chain:
                    analyzed_ids.add(c.id)
            else:
                # Single claim, still worth analyzing entropy
                metrics = self.analyze_chain(claim.id)
                results.append(metrics)
                analyzed_ids.add(claim.id)

        log.info("Analyzed %d mutation chains", len(results))
        return results

    # ── Anomaly Detection ────────────────────────────────────────────────

    def detect_high_drift(self, threshold: float = 0.5) -> list[MutationMetrics]:
        """
        Find claims with unusually high mutation drift velocity.
        These may indicate semantic manipulation or disinformation.
        """
        all_metrics = self.analyze_all_chains()
        anomalies = [m for m in all_metrics if m.drift_velocity > threshold]
        log.info("High-drift anomalies (threshold=%.2f): %d found",
                 threshold, len(anomalies))
        return anomalies

    def detect_entropy_anomalies(self, z_score_threshold: float = 2.0) -> list[MutationMetrics]:
        """
        Find claims whose Shannon entropy deviates significantly
        from the population mean. Uses z-score detection.
        """
        all_metrics = self.analyze_all_chains()
        if len(all_metrics) < 3:
            return []

        entropies = [m.shannon_entropy for m in all_metrics]
        mean_e = sum(entropies) / len(entropies)
        variance = sum((e - mean_e) ** 2 for e in entropies) / len(entropies)
        std_e = math.sqrt(variance) if variance > 0 else 1.0

        anomalies = []
        for m in all_metrics:
            z_score = abs(m.shannon_entropy - mean_e) / std_e
            if z_score > z_score_threshold:
                anomalies.append(m)

        log.info("Entropy anomalies (z>%.1f): %d found",
                 z_score_threshold, len(anomalies))
        return anomalies

    # ── Branching Analysis ───────────────────────────────────────────────

    def get_branching_factor(self, claim_id: int) -> dict:
        """
        Compute branching analysis for a claim: how many direct
        mutations spawned from it.
        """
        descendants = query_rows(
            "claim_nodes", "mutation_parent = ?", (claim_id,)
        )
        child_ids = [d["id"] for d in descendants]

        # Recursive depth
        total_tree_size = 0
        queue = list(child_ids)
        visited = {claim_id}
        while queue:
            cid = queue.pop(0)
            if cid in visited:
                continue
            visited.add(cid)
            total_tree_size += 1
            sub = query_rows("claim_nodes", "mutation_parent = ?", (cid,))
            queue.extend(d["id"] for d in sub)

        return {
            "claim_id": claim_id,
            "direct_children": len(child_ids),
            "total_tree_size": total_tree_size,
            "child_ids": child_ids,
        }

    # ── Persistence ──────────────────────────────────────────────────────

    def save_metrics(self, metrics: MutationMetrics) -> int:
        """Persist mutation metrics to DB."""
        row_id = insert_row("mutation_metrics", {
            "claim_id": metrics.claim_id,
            "chain_length": metrics.chain_length,
            "shannon_entropy": metrics.shannon_entropy,
            "drift_velocity": metrics.drift_velocity,
            "max_diff_ratio": metrics.max_diff_ratio,
            "semantic_stability": metrics.semantic_stability,
            "computed_at": metrics.computed_at or datetime.now(timezone.utc).isoformat(),
        })
        log.debug("Saved mutation metrics for claim #%d → row %d",
                  metrics.claim_id, row_id)
        return row_id

    def save_all_metrics(self, metrics_list: list[MutationMetrics]) -> int:
        """Persist all metrics. Returns count saved."""
        count = 0
        for m in metrics_list:
            self.save_metrics(m)
            count += 1
        return count
