"""
Source Forensics Report – Comprehensive Source Intelligence Output

Generates narrative reports combining all Phase VI intelligence:
  - Source reputation profiles (reliability, trends, grades)
  - Influence network topology (gateways, bottlenecks, amplifiers)
  - Coordination detection results (suspicious clusters, patterns)
  - Deep provenance analysis (origin chains, classification)
  - Overall source ecosystem health assessment

Output formats: plaintext narrative, structured dict
"""

import json
import math
from datetime import datetime, timezone
from dataclasses import dataclass, field

from src.database import query_rows
from src.logger import get_logger

log = get_logger(__name__)


@dataclass
class SourceForensicsReport:
    """Container for source forensics report data."""
    source_count: int = 0
    reputation_profiles: list = field(default_factory=list)
    network_profile: dict = field(default_factory=dict)
    coordination_summary: dict = field(default_factory=dict)
    provenance_summary: dict = field(default_factory=dict)
    ecosystem_health: float = 0.0
    ecosystem_grade: str = "C"
    generated_at: str = ""


class SourceForensicsReportEngine:
    """Generate comprehensive source intelligence reports."""

    def generate(self, source_id: int = 0) -> str:
        """
        Generate a narrative source forensics report.

        Args:
            source_id: Specific source (or 0 for full ecosystem report).

        Returns:
            Formatted plaintext report string.
        """
        if source_id > 0:
            return self._generate_single(source_id)
        return self._generate_ecosystem()

    def generate_dict(self, source_id: int = 0) -> dict:
        """Generate report as structured dict."""
        if source_id > 0:
            return self._generate_single_dict(source_id)
        return self._generate_ecosystem_dict()

    # ── Single Source Report ─────────────────────────────────────────────

    def _generate_single(self, source_id: int) -> str:
        """Narrative report for a single source."""
        data = self._generate_single_dict(source_id)
        lines = []

        lines.append("=" * 70)
        lines.append(f"SOURCE FORENSICS REPORT – Source #{source_id}")
        lines.append("=" * 70)
        lines.append("")

        # Metadata
        lines.append("1. SOURCE IDENTITY")
        lines.append("-" * 40)
        lines.append(f"  Title:     {data.get('title', 'Unknown')}")
        lines.append(f"  Type:      {data.get('source_type', 'Unknown')}")
        lines.append(f"  Platform:  {data.get('platform', 'Unknown')}")
        lines.append(f"  Author:    {data.get('author', 'Unknown')}")
        lines.append("")

        # Reputation
        rep = data.get("reputation", {})
        lines.append("2. REPUTATION PROFILE")
        lines.append("-" * 40)
        lines.append(f"  Reliability Index: {rep.get('reliability_index', 0):.4f}")
        lines.append(f"  Grade:             {rep.get('grade', 'N/A')}")
        lines.append(f"  Current EMA:       {rep.get('current_ema', 0):.4f}")
        lines.append(f"  Accuracy Rate:     {rep.get('accuracy_rate', 0):.4f}")
        lines.append(f"  Support Ratio:     {rep.get('support_ratio', 0):.4f}")
        lines.append(f"  Trend:             {rep.get('trend_direction', 'flat')}")
        lines.append(f"  Total Claims:      {rep.get('total_claims', 0)}")
        lines.append(f"  Snapshots:         {rep.get('snapshot_count', 0)}")
        lines.append("")

        # Influence
        inf = data.get("influence", {})
        lines.append("3. INFLUENCE ANALYSIS")
        lines.append("-" * 40)
        lines.append(f"  Outgoing edges:    {inf.get('outgoing', 0)}")
        lines.append(f"  Incoming edges:    {inf.get('incoming', 0)}")
        lines.append(f"  Amplification:     {inf.get('total_amplification', 0):.4f}")
        if inf.get("influences"):
            lines.append("  Influences:")
            for target in inf["influences"][:5]:
                lines.append(f"    -> Source #{target['id']} (shared: {target['shared']})")
        if inf.get("influenced_by"):
            lines.append("  Influenced by:")
            for src in inf["influenced_by"][:5]:
                lines.append(f"    <- Source #{src['id']} (shared: {src['shared']})")
        lines.append("")

        # Coordination
        coord = data.get("coordination", {})
        lines.append("4. COORDINATION FLAGS")
        lines.append("-" * 40)
        lines.append(f"  Events involving this source: {coord.get('event_count', 0)}")
        if coord.get("patterns"):
            lines.append(f"  Pattern types: {', '.join(coord['patterns'])}")
        lines.append("")

        # Provenance
        prov = data.get("provenance", {})
        lines.append("5. PROVENANCE")
        lines.append("-" * 40)
        lines.append(f"  Claims originated:   {prov.get('originated', 0)}")
        lines.append(f"  Claims referenced:   {prov.get('referenced', 0)}")
        lines.append("")

        lines.append("=" * 70)
        lines.append(f"Generated: {data.get('generated_at', '')}")
        lines.append("=" * 70)

        return "\n".join(lines)

    def _generate_single_dict(self, source_id: int) -> dict:
        """Structured data for a single source report."""
        now = datetime.now(timezone.utc).isoformat()

        # Source metadata
        src_rows = query_rows("source_nodes", "id = ?", (source_id,))
        source_meta = src_rows[0] if src_rows else {}

        result = {
            "source_id": source_id,
            "title": source_meta.get("source_title", "Unknown"),
            "source_type": source_meta.get("source_type", "unknown"),
            "platform": source_meta.get("platform", ""),
            "author": source_meta.get("author", ""),
            "generated_at": now,
        }

        # Reputation
        try:
            from src.graph.source_reputation import SourceReputationEngine
            rep_engine = SourceReputationEngine()
            profile = rep_engine.get_profile(source_id)
            result["reputation"] = profile.to_dict()
        except Exception as e:
            log.warning("Reputation engine error: %s", e)
            result["reputation"] = {}

        # Influence
        try:
            from src.graph.influence_network import InfluenceNetworkEngine
            inf_engine = InfluenceNetworkEngine()
            outgoing = inf_engine.get_influence_on(source_id)
            incoming = inf_engine.get_influenced_by(source_id)
            total_amp = sum(e.amplification for e in outgoing)
            result["influence"] = {
                "outgoing": len(outgoing),
                "incoming": len(incoming),
                "total_amplification": total_amp,
                "influences": [
                    {"id": e.to_source_id, "shared": e.shared_claims}
                    for e in outgoing[:10]
                ],
                "influenced_by": [
                    {"id": e.from_source_id, "shared": e.shared_claims}
                    for e in incoming[:10]
                ],
            }
        except Exception as e:
            log.warning("Influence engine error: %s", e)
            result["influence"] = {}

        # Coordination
        try:
            coord_rows = query_rows("coordination_events", "1=1")
            events_involving = []
            patterns = set()
            for row in coord_rows:
                try:
                    sids = json.loads(row["source_ids_json"])
                    if source_id in sids:
                        events_involving.append(row)
                        patterns.add(row["pattern_type"])
                except (json.JSONDecodeError, TypeError):
                    pass
            result["coordination"] = {
                "event_count": len(events_involving),
                "patterns": list(patterns),
            }
        except Exception as e:
            log.warning("Coordination query error: %s", e)
            result["coordination"] = {}

        # Provenance
        try:
            links_from = query_rows(
                "evidence_links",
                "from_type = 'source' AND from_id = ? AND to_type = 'claim'",
                (source_id,),
            )
            links_to = query_rows(
                "evidence_links",
                "to_type = 'source' AND to_id = ? AND from_type = 'claim'",
                (source_id,),
            )
            originated = len([l for l in links_from if l["relationship"] == "supports"])
            referenced = len(links_from) + len(links_to)
            result["provenance"] = {
                "originated": originated,
                "referenced": referenced,
            }
        except Exception as e:
            log.warning("Provenance query error: %s", e)
            result["provenance"] = {}

        return result

    # ── Ecosystem Report ─────────────────────────────────────────────────

    def _generate_ecosystem(self) -> str:
        """Full ecosystem narrative report."""
        data = self._generate_ecosystem_dict()
        lines = []

        lines.append("=" * 70)
        lines.append("SOURCE FORENSICS REPORT – ECOSYSTEM ANALYSIS")
        lines.append("=" * 70)
        lines.append("")

        # Overview
        lines.append("1. ECOSYSTEM OVERVIEW")
        lines.append("-" * 40)
        lines.append(f"  Total sources:     {data.get('source_count', 0)}")
        lines.append(f"  Ecosystem health:  {data.get('ecosystem_health', 0):.1%}")
        lines.append(f"  Ecosystem grade:   {data.get('ecosystem_grade', 'N/A')}")
        lines.append("")

        # Reputation distribution
        rep = data.get("reputation_summary", {})
        lines.append("2. REPUTATION DISTRIBUTION")
        lines.append("-" * 40)
        grade_dist = rep.get("grade_distribution", {})
        for grade in ("A", "B", "C", "D", "F"):
            count = grade_dist.get(grade, 0)
            if count > 0:
                lines.append(f"  Grade {grade}: {count} sources")
        lines.append(f"  Mean reliability:  {rep.get('mean_reliability', 0):.4f}")
        lines.append(f"  Median reliability:{rep.get('median_reliability', 0):.4f}")
        lines.append("")

        # Top sources
        top = data.get("top_sources", [])
        if top:
            lines.append("3. TOP RELIABLE SOURCES")
            lines.append("-" * 40)
            for i, src in enumerate(top[:5], 1):
                lines.append(f"  {i}. [{src.get('grade', '?')}] "
                             f"{src.get('title', 'Unknown')} "
                             f"(idx={src.get('reliability_index', 0):.4f})")
            lines.append("")

        # Bottom sources
        bottom = data.get("bottom_sources", [])
        if bottom:
            lines.append("4. LOWEST RELIABILITY SOURCES")
            lines.append("-" * 40)
            for i, src in enumerate(bottom[:5], 1):
                lines.append(f"  {i}. [{src.get('grade', '?')}] "
                             f"{src.get('title', 'Unknown')} "
                             f"(idx={src.get('reliability_index', 0):.4f})")
            lines.append("")

        # Network
        net = data.get("network", {})
        lines.append("5. INFLUENCE NETWORK")
        lines.append("-" * 40)
        lines.append(f"  Edges:       {net.get('total_edges', 0)}")
        lines.append(f"  Density:     {net.get('density', 0):.4f}")
        lines.append(f"  Components:  {net.get('components', 0)}")
        if net.get("gateways"):
            lines.append("  Gateways:")
            for gw in net["gateways"][:3]:
                lines.append(f"    Source #{gw.get('source_id', '?')}: "
                             f"betweenness={gw.get('betweenness', 0):.4f}")
        if net.get("bottlenecks"):
            lines.append("  Bottlenecks:")
            for bn in net["bottlenecks"][:3]:
                lines.append(f"    Source #{bn.get('source_id', '?')}: "
                             f"removal -> {bn.get('components_if_removed', 0)} components")
        lines.append("")

        # Coordination
        coord = data.get("coordination", {})
        lines.append("6. COORDINATION ANALYSIS")
        lines.append("-" * 40)
        lines.append(f"  Events detected:    {coord.get('total_events', 0)}")
        lines.append(f"  Unique clusters:    {coord.get('total_clusters', 0)}")
        lines.append(f"  Highest score:      {coord.get('highest_score', 0):.4f}")
        pat = coord.get("pattern_distribution", {})
        if pat:
            lines.append(f"  Patterns: {', '.join(f'{k}={v}' for k, v in pat.items())}")
        lines.append("")

        # Provenance
        prov = data.get("provenance", {})
        lines.append("7. PROVENANCE ANALYSIS")
        lines.append("-" * 40)
        lines.append(f"  Traced claims:      {prov.get('total_traced', 0)}")
        lines.append(f"  Avg chain depth:    {prov.get('avg_chain_depth', 0):.2f}")
        lines.append(f"  Max chain depth:    {prov.get('max_chain_depth', 0)}")
        lines.append(f"  Orphan claims:      {prov.get('orphan_count', 0)}")
        orig_dist = prov.get("origin_distribution", {})
        if orig_dist:
            lines.append(f"  Origins: {', '.join(f'{k}={v}' for k, v in orig_dist.items())}")
        lines.append("")

        lines.append("=" * 70)
        lines.append(f"Generated: {data.get('generated_at', '')}")
        lines.append("=" * 70)

        return "\n".join(lines)

    def _generate_ecosystem_dict(self) -> dict:
        """Structured ecosystem report data."""
        now = datetime.now(timezone.utc).isoformat()
        sources = query_rows("source_nodes", "1=1")

        result = {
            "source_count": len(sources),
            "generated_at": now,
        }

        # Reputation profiles
        try:
            from src.graph.source_reputation import SourceReputationEngine
            rep_engine = SourceReputationEngine()
            profiles = rep_engine.rank_sources()

            grade_dist = {}
            reliabilities = []
            for p in profiles:
                grade_dist[p.grade] = grade_dist.get(p.grade, 0) + 1
                reliabilities.append(p.reliability_index)

            mean_rel = sum(reliabilities) / len(reliabilities) if reliabilities else 0
            sorted_rel = sorted(reliabilities)
            median_rel = sorted_rel[len(sorted_rel) // 2] if sorted_rel else 0

            result["reputation_summary"] = {
                "grade_distribution": grade_dist,
                "mean_reliability": mean_rel,
                "median_reliability": median_rel,
            }

            result["top_sources"] = [
                {"source_id": p.source_id, "title": p.source_title,
                 "reliability_index": p.reliability_index, "grade": p.grade}
                for p in profiles[:5]
            ]

            result["bottom_sources"] = [
                {"source_id": p.source_id, "title": p.source_title,
                 "reliability_index": p.reliability_index, "grade": p.grade}
                for p in reversed(profiles[-5:])
            ]
        except Exception as e:
            log.warning("Reputation summary error: %s", e)
            result["reputation_summary"] = {}
            result["top_sources"] = []
            result["bottom_sources"] = []

        # Network
        try:
            from src.graph.influence_network import InfluenceNetworkEngine
            inf_engine = InfluenceNetworkEngine()
            net_profile = inf_engine.analyze_network()
            result["network"] = net_profile.to_dict()
        except Exception as e:
            log.warning("Network analysis error: %s", e)
            result["network"] = {}

        # Coordination
        try:
            from src.graph.coordination_detector import CoordinationDetector
            coord_engine = CoordinationDetector()
            coord_summary = coord_engine.get_summary()
            result["coordination"] = coord_summary.to_dict()
        except Exception as e:
            log.warning("Coordination summary error: %s", e)
            result["coordination"] = {}

        # Provenance
        try:
            from src.graph.provenance_deep import DeepProvenanceEngine
            prov_engine = DeepProvenanceEngine()
            prov_summary = prov_engine.get_summary()
            result["provenance"] = prov_summary.to_dict()
        except Exception as e:
            log.warning("Provenance summary error: %s", e)
            result["provenance"] = {}

        # Ecosystem health: weighted composite
        result["ecosystem_health"] = self._compute_ecosystem_health(result)
        result["ecosystem_grade"] = self._grade(result["ecosystem_health"])

        return result

    # ── Quick Summary ────────────────────────────────────────────────────

    def quick_source(self, source_id: int) -> str:
        """One-line source intelligence summary."""
        try:
            from src.graph.source_reputation import SourceReputationEngine
            rep_engine = SourceReputationEngine()
            profile = rep_engine.get_profile(source_id)

            return (
                f"Source #{source_id} [{profile.grade}] "
                f"reliability={profile.reliability_index:.4f} "
                f"ema={profile.current_ema:.4f} "
                f"accuracy={profile.accuracy_rate:.4f} "
                f"trend={profile.trend_direction} "
                f"claims={profile.total_claims} "
                f"title=\"{profile.source_title[:40]}\""
            )
        except Exception as e:
            return f"Source #{source_id}: error – {e}"

    # ── Internal ─────────────────────────────────────────────────────────

    @staticmethod
    def _compute_ecosystem_health(data: dict) -> float:
        """
        Ecosystem health score (0.0 – 1.0):
          - 40% mean source reliability
          - 25% low orphan rate
          - 20% network connectivity (inverse fragmentation)
          - 15% low coordination suspicion
        """
        # Reliability component
        rep = data.get("reputation_summary", {})
        mean_rel = rep.get("mean_reliability", 0.5)
        rel_component = mean_rel * 0.40

        # Orphan component
        prov = data.get("provenance", {})
        total_traced = prov.get("total_traced", 0)
        orphan_count = prov.get("orphan_count", 0)
        if total_traced > 0:
            orphan_rate = orphan_count / total_traced
            orphan_component = (1.0 - orphan_rate) * 0.25
        else:
            orphan_component = 0.125  # neutral

        # Network component
        net = data.get("network", {})
        components = net.get("components", 1)
        total_sources = data.get("source_count", 1)
        if total_sources > 0:
            fragmentation = components / total_sources
            net_component = (1.0 - fragmentation) * 0.20
        else:
            net_component = 0.10

        # Coordination suspicion: lower is healthier
        coord = data.get("coordination", {})
        highest_score = coord.get("highest_score", 0.0)
        coord_component = (1.0 - highest_score) * 0.15

        health = rel_component + orphan_component + net_component + coord_component
        return max(0.0, min(1.0, health))

    @staticmethod
    def _grade(health: float) -> str:
        if health >= 0.90:
            return "A"
        if health >= 0.75:
            return "B"
        if health >= 0.60:
            return "C"
        if health >= 0.40:
            return "D"
        return "F"
