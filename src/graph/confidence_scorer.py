"""
Confidence Scorer – Bayesian Evidence Propagation Engine

Computes claim confidence scores by propagating evidence strength
through the claim graph using weighted Bayesian updates.

Scoring components:
  - Base prior (claim type default)
  - Source credibility contribution
  - Citation support weight
  - Contradiction penalty
  - Verification bonus
  - Mutation decay (drifted claims lose confidence)

Composite score = weighted combination stored in claim_scores table.
"""

import json
import math
from datetime import datetime, timezone
from dataclasses import dataclass, field

from src.database import insert_row, query_rows, execute_sql, get_connection
from src.graph.claim_graph import ClaimGraph, ClaimNode
from src.logger import get_logger

log = get_logger(__name__)


# ── Priors by claim type ─────────────────────────────────────────────────
TYPE_PRIORS = {
    "observation":  0.60,
    "measurement":  0.65,
    "hypothesis":   0.30,
    "assertion":    0.40,
    "derived":      0.50,
    "prediction":   0.25,
    "historical":   0.45,
    "rebuttal":     0.35,
    "retraction":   0.10,
}

# ── Verification bonuses ────────────────────────────────────────────────
VERIFICATION_BONUSES = {
    "confirmed":    0.30,
    "supported":    0.15,
    "unverified":   0.00,
    "disputed":    -0.10,
    "contradicted":-0.25,
    "retracted":   -0.40,
}

# ── Weights for composite scoring ───────────────────────────────────────
DEFAULT_WEIGHTS = {
    "prior":                0.15,
    "source_credibility":   0.25,
    "citation_support":     0.20,
    "contradiction_penalty":0.15,
    "verification_bonus":   0.15,
    "mutation_decay":       0.10,
}


@dataclass
class ScoreBreakdown:
    """Detailed breakdown of a claim's confidence computation."""
    claim_id: int = 0
    prior: float = 0.0
    source_credibility: float = 0.0
    citation_support: float = 0.0
    contradiction_penalty: float = 0.0
    verification_bonus: float = 0.0
    mutation_decay: float = 0.0
    composite: float = 0.0
    components: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "prior": round(self.prior, 4),
            "source_credibility": round(self.source_credibility, 4),
            "citation_support": round(self.citation_support, 4),
            "contradiction_penalty": round(self.contradiction_penalty, 4),
            "verification_bonus": round(self.verification_bonus, 4),
            "mutation_decay": round(self.mutation_decay, 4),
            "composite": round(self.composite, 4),
            "components": self.components,
        }


class ConfidenceScorer:
    """
    Bayesian confidence scorer for claims in the evidence graph.

    Scores are computed from 6 components and stored in the claim_scores table.
    """

    def __init__(self, weights: dict | None = None):
        self.graph = ClaimGraph()
        self.weights = weights or DEFAULT_WEIGHTS.copy()

    # ── Component Calculators ────────────────────────────────────────────

    def _calc_prior(self, claim: ClaimNode) -> float:
        """Return base prior based on claim type."""
        return TYPE_PRIORS.get(claim.claim_type, 0.35)

    def _calc_source_credibility(self, claim: ClaimNode) -> float:
        """
        Average credibility of all sources linked to this claim via 'supports'.
        Returns 0.5 (neutral) if no supporting sources.
        """
        links = self.graph.get_links_from("claim", claim.id)
        supporting_source_ids = [
            link.to_id for link in links
            if link.to_type == "source" and link.relationship in ("supports", "references")
        ]
        # Also check inbound supports
        inbound = self.graph.get_links_to("claim", claim.id)
        for link in inbound:
            if link.from_type == "source" and link.relationship in ("supports", "references"):
                supporting_source_ids.append(link.from_id)

        if not supporting_source_ids:
            return 0.5  # neutral

        total_cred = 0.0
        count = 0
        for sid in set(supporting_source_ids):
            source = self.graph.get_source(sid)
            if source:
                total_cred += source.credibility
                count += 1

        return total_cred / count if count > 0 else 0.5

    def _calc_citation_support(self, claim: ClaimNode) -> float:
        """
        Normalized count of supporting evidence links.
        Uses sigmoid-like scaling: score = 1 - 1/(1 + support_count).
        """
        outbound = self.graph.get_links_from("claim", claim.id)
        inbound = self.graph.get_links_to("claim", claim.id)

        support_count = 0
        for link in outbound:
            if link.relationship in ("supports", "references", "derives_from"):
                support_count += link.weight
        for link in inbound:
            if link.relationship in ("supports", "references"):
                support_count += link.weight

        # Sigmoid-like normalization: 0 links → 0, 1 → 0.5, 5 → 0.83, etc.
        return 1.0 - (1.0 / (1.0 + support_count))

    def _calc_contradiction_penalty(self, claim: ClaimNode) -> float:
        """
        Penalty based on number and weight of 'contradicts' links.
        Returns value in [0, 1] where 0 = no contradictions (good).
        """
        outbound = self.graph.get_links_from("claim", claim.id)
        inbound = self.graph.get_links_to("claim", claim.id)

        contradiction_weight = 0.0
        for link in outbound + inbound:
            if link.relationship == "contradicts":
                contradiction_weight += link.weight

        # Scale: 0 → 0.0, 1 → 0.5, 3+ → ~1.0
        # We invert for the composite: higher penalty = lower score
        return min(1.0, contradiction_weight / 3.0)

    def _calc_verification_bonus(self, claim: ClaimNode) -> float:
        """
        Score boost/penalty based on verification state.
        Mapped to [0, 1] range centered at 0.5 for 'unverified'.
        """
        raw = VERIFICATION_BONUSES.get(claim.verification, 0.0)
        # Map [-0.4, 0.3] → [0.0, 1.0]
        return max(0.0, min(1.0, 0.5 + raw))

    def _calc_mutation_decay(self, claim: ClaimNode) -> float:
        """
        Confidence decay based on mutation chain depth.
        Root claims get 1.0; heavily mutated claims decay toward 0.
        decay = 1.0 / (1.0 + 0.3 * chain_depth)
        """
        chain = self.graph.get_mutation_chain(claim.id)
        depth = len(chain) - 1  # root = depth 0
        if depth <= 0:
            return 1.0
        return 1.0 / (1.0 + 0.3 * depth)

    # ── Composite Scorer ─────────────────────────────────────────────────

    def score_claim(self, claim_id: int) -> ScoreBreakdown:
        """
        Compute composite confidence score for a single claim.
        Returns detailed ScoreBreakdown.
        """
        claim = self.graph.get_claim(claim_id)
        if not claim:
            log.warning("Claim #%d not found", claim_id)
            return ScoreBreakdown(claim_id=claim_id)

        breakdown = ScoreBreakdown(claim_id=claim_id)
        breakdown.prior = self._calc_prior(claim)
        breakdown.source_credibility = self._calc_source_credibility(claim)
        breakdown.citation_support = self._calc_citation_support(claim)
        breakdown.contradiction_penalty = self._calc_contradiction_penalty(claim)
        breakdown.verification_bonus = self._calc_verification_bonus(claim)
        breakdown.mutation_decay = self._calc_mutation_decay(claim)

        # Composite: weighted sum with contradiction inverted
        w = self.weights
        composite = (
            w["prior"] * breakdown.prior
            + w["source_credibility"] * breakdown.source_credibility
            + w["citation_support"] * breakdown.citation_support
            - w["contradiction_penalty"] * breakdown.contradiction_penalty
            + w["verification_bonus"] * breakdown.verification_bonus
            + w["mutation_decay"] * breakdown.mutation_decay
        )
        # Clamp to [0, 1]
        breakdown.composite = max(0.0, min(1.0, composite))

        breakdown.components = {
            "claim_type": claim.claim_type,
            "verification": claim.verification,
            "mutation_depth": len(self.graph.get_mutation_chain(claim.id)) - 1,
            "weights": self.weights,
        }

        log.info("Claim #%d scored: %.4f (prior=%.2f src=%.2f cite=%.2f "
                 "contra=-%.2f verif=%.2f decay=%.2f)",
                 claim_id, breakdown.composite,
                 breakdown.prior, breakdown.source_credibility,
                 breakdown.citation_support, breakdown.contradiction_penalty,
                 breakdown.verification_bonus, breakdown.mutation_decay)

        return breakdown

    def score_all_claims(self) -> list[ScoreBreakdown]:
        """Score every claim in the graph."""
        claims = self.graph.get_all_claims()
        results = []
        for claim in claims:
            breakdown = self.score_claim(claim.id)
            results.append(breakdown)
        log.info("Scored %d claims total", len(results))
        return results

    # ── Persistence ──────────────────────────────────────────────────────

    def save_score(self, breakdown: ScoreBreakdown) -> int:
        """Persist a score breakdown to claim_scores table."""
        now = datetime.now(timezone.utc).isoformat()
        row_id = insert_row("claim_scores", {
            "claim_id": breakdown.claim_id,
            "score_type": "composite",
            "score_value": breakdown.composite,
            "components_json": json.dumps(breakdown.to_dict()),
            "scored_at": now,
        })
        log.debug("Saved score for claim #%d → row %d", breakdown.claim_id, row_id)
        return row_id

    def save_all_scores(self, breakdowns: list[ScoreBreakdown]) -> int:
        """Persist all score breakdowns. Returns count saved."""
        count = 0
        for b in breakdowns:
            self.save_score(b)
            count += 1
        return count

    def get_scores(self, claim_id: int) -> list[dict]:
        """Retrieve all historical scores for a claim."""
        rows = query_rows("claim_scores", "claim_id = ?", (claim_id,))
        return rows

    def get_latest_score(self, claim_id: int) -> float | None:
        """Get the most recent composite score for a claim."""
        rows = execute_sql(
            "SELECT score_value FROM claim_scores "
            "WHERE claim_id = ? AND score_type = 'composite' "
            "ORDER BY scored_at DESC LIMIT 1",
            (claim_id,),
        )
        return rows[0]["score_value"] if rows else None

    # ── Bayesian Update ──────────────────────────────────────────────────

    def bayesian_update(self, claim_id: int, new_evidence_weight: float = 1.0,
                        direction: str = "support") -> ScoreBreakdown:
        """
        Apply a Bayesian-style update to a claim's confidence.

        direction: "support" (increases confidence) or "contradict" (decreases)
        new_evidence_weight: strength of the new evidence [0, 1]
        """
        current = self.get_latest_score(claim_id) or 0.5
        likelihood_ratio = 1.0 + new_evidence_weight if direction == "support" \
            else 1.0 / (1.0 + new_evidence_weight)

        # Bayesian odds update
        prior_odds = current / (1.0 - current) if current < 1.0 else 100.0
        posterior_odds = prior_odds * likelihood_ratio
        posterior = posterior_odds / (1.0 + posterior_odds)
        posterior = max(0.01, min(0.99, posterior))

        # Re-score with updated prior
        breakdown = self.score_claim(claim_id)
        breakdown.composite = posterior
        breakdown.components["bayesian_update"] = {
            "prior": current,
            "likelihood_ratio": likelihood_ratio,
            "posterior": posterior,
            "direction": direction,
            "evidence_weight": new_evidence_weight,
        }

        self.save_score(breakdown)
        log.info("Bayesian update: claim #%d %.4f → %.4f (%s, w=%.2f)",
                 claim_id, current, posterior, direction, new_evidence_weight)
        return breakdown

    # ── Ranking ──────────────────────────────────────────────────────────

    def rank_claims(self, top_n: int = 20) -> list[tuple[int, float, str]]:
        """
        Return top-N claims ranked by composite confidence score.
        Returns list of (claim_id, score, claim_text_snippet).
        """
        scores = self.score_all_claims()
        scores.sort(key=lambda s: s.composite, reverse=True)

        ranked = []
        for s in scores[:top_n]:
            claim = self.graph.get_claim(s.claim_id)
            text = claim.claim_text[:80] if claim else "?"
            ranked.append((s.claim_id, s.composite, text))
        return ranked
