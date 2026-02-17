"""
Claim Graph Engine – Evidence Linking & Narrative Propagation Intelligence

Provides:
  - Claim node CRUD (typed: hypothesis, observation, assertion, derived, rebuttal)
  - Source node management (documents, CIDs, URLs, archives, witness)
  - Evidence link edges with confidence scoring
  - Entity nodes for co-occurrence tracking
  - Mutation detection (claim drift / revision tracking)
  - Narrative cluster extraction using connected components
  - Contradiction detection between linked claims
  - Provenance chain traversal
  - NetworkX integration for graph analysis

DB tables used: claim_nodes, source_nodes, evidence_links, entity_nodes
"""

import json
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional
from difflib import unified_diff

from src.database import insert_row, query_rows, get_connection
from src.logger import get_logger

log = get_logger(__name__)


# ── Claim Types ──────────────────────────────────────────────────────────
CLAIM_TYPES = {
    "hypothesis",
    "observation",
    "assertion",
    "derived",
    "rebuttal",
    "retraction",
    "prediction",
    "historical",
}

SOURCE_TYPES = {
    "document",
    "ipfs_cid",
    "url",
    "archive",
    "foia_response",
    "academic_paper",
    "patent",
    "testimony",
    "measurement",
    "calculation",
}

VERIFICATION_STATES = {
    "unverified",
    "supported",
    "contradicted",
    "disputed",
    "retracted",
    "confirmed",
}


@dataclass
class ClaimNode:
    """A single claim in the evidence graph."""
    id: int = 0
    claim_text: str = ""
    claim_type: str = "assertion"
    first_source: str = ""
    confidence: float = 0.0
    verification: str = "unverified"
    mutation_parent: Optional[int] = None
    mutation_diff: str = ""
    tags: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "claim_text": self.claim_text,
            "claim_type": self.claim_type,
            "first_source": self.first_source,
            "confidence": self.confidence,
            "verification": self.verification,
            "mutation_parent": self.mutation_parent,
            "mutation_diff": self.mutation_diff,
            "tags": self.tags,
            "created_at": self.created_at,
        }


@dataclass
class SourceNode:
    """A source of evidence."""
    id: int = 0
    source_type: str = "document"
    source_title: str = ""
    source_url: str = ""
    document_cid: str = ""
    author: str = ""
    published_at: str = ""
    credibility: float = 0.5
    platform: str = ""
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_title": self.source_title,
            "source_url": self.source_url,
            "document_cid": self.document_cid,
            "author": self.author,
            "published_at": self.published_at,
            "credibility": self.credibility,
            "platform": self.platform,
            "created_at": self.created_at,
        }


@dataclass
class EvidenceLink:
    """A weighted edge in the of evidence graph."""
    id: int = 0
    from_type: str = ""  # "claim" or "source" or "entity"
    from_id: int = 0
    to_type: str = ""
    to_id: int = 0
    relationship: str = ""  # supports, contradicts, derives_from, references, etc.
    weight: float = 1.0
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "from_type": self.from_type,
            "from_id": self.from_id,
            "to_type": self.to_type,
            "to_id": self.to_id,
            "relationship": self.relationship,
            "weight": self.weight,
            "created_at": self.created_at,
        }


class ClaimGraph:
    """
    Evidence graph engine for forensic narrative analysis.

    Manages claim nodes, source nodes, entity nodes, and evidence links.
    Supports mutation tracking, contradiction detection, and provenance chains.
    """

    # ── Claim Nodes ──────────────────────────────────────────────────────
    def add_claim(
        self,
        claim_text: str,
        claim_type: str = "assertion",
        source_reference: str = "",
        confidence: float = 0.5,
        tags: str = "",
        parent_claim_id: Optional[int] = None,
    ) -> int:
        """
        Add a claim to the graph.

        If parent_claim_id is provided, mutation tracking engages:
        the new claim is recorded as a mutation of the parent, and
        a diff is stored.
        """
        if claim_type not in CLAIM_TYPES:
            log.warning("Unknown claim_type '%s', defaulting to 'assertion'", claim_type)
            claim_type = "assertion"

        now = datetime.now(timezone.utc).isoformat()

        mutation_diff = ""
        if parent_claim_id:
            parent_rows = query_rows("claim_nodes", "id = ?", (parent_claim_id,))
            if parent_rows:
                parent_text = parent_rows[0]["claim_text"]
                diff_lines = list(unified_diff(
                    parent_text.splitlines(keepends=True),
                    claim_text.splitlines(keepends=True),
                    fromfile="parent",
                    tofile="mutation",
                ))
                mutation_diff = "".join(diff_lines)

        claim_id = insert_row("claim_nodes", {
            "claim_text": claim_text,
            "claim_type": claim_type,
            "first_source": source_reference,
            "confidence": confidence,
            "verification": "unverified",
            "mutation_parent": parent_claim_id,
            "mutation_diff": mutation_diff,
            "tags": tags,
            "created_at": now,
        })

        log.info("Added claim #%d [%s] confidence=%.2f", claim_id, claim_type, confidence)
        return claim_id

    def get_claim(self, claim_id: int) -> Optional[ClaimNode]:
        rows = query_rows("claim_nodes", "id = ?", (claim_id,))
        if not rows:
            return None
        return self._row_to_claim(rows[0])

    def update_claim_status(self, claim_id: int, status: str) -> bool:
        if status not in VERIFICATION_STATES:
            log.warning("Invalid verification status: %s", status)
            return False
        with get_connection() as conn:
            conn.execute(
                "UPDATE claim_nodes SET verification = ? WHERE id = ?",
                (status, claim_id),
            )
        log.info("Claim #%d status → %s", claim_id, status)
        return True

    def search_claims(self, keyword: str) -> list[ClaimNode]:
        rows = query_rows("claim_nodes", "claim_text LIKE ?", (f"%{keyword}%",))
        return [self._row_to_claim(r) for r in rows]

    def get_all_claims(self) -> list[ClaimNode]:
        rows = query_rows("claim_nodes", "1=1")
        return [self._row_to_claim(r) for r in rows]

    # ── Source Nodes ─────────────────────────────────────────────────────
    def add_source(
        self,
        title: str,
        source_type: str = "document",
        url: str = "",
        document_cid: str = "",
        author: str = "",
        date_published: str = "",
        credibility: float = 0.5,
    ) -> int:
        if source_type not in SOURCE_TYPES:
            log.warning("Unknown source_type '%s', defaulting to 'document'", source_type)
            source_type = "document"

        now = datetime.now(timezone.utc).isoformat()

        source_id = insert_row("source_nodes", {
            "source_type": source_type,
            "source_title": title,
            "source_url": url,
            "document_cid": document_cid,
            "author": author,
            "published_at": date_published,
            "credibility": credibility,
            "platform": "",
            "created_at": now,
        })

        log.info("Added source #%d [%s]: %s", source_id, source_type, title)
        return source_id

    def get_source(self, source_id: int) -> Optional[SourceNode]:
        rows = query_rows("source_nodes", "id = ?", (source_id,))
        if not rows:
            return None
        return self._row_to_source(rows[0])

    def get_all_sources(self) -> list[SourceNode]:
        rows = query_rows("source_nodes", "1=1")
        return [self._row_to_source(r) for r in rows]

    # ── Entity Nodes ─────────────────────────────────────────────────────
    def add_entity(
        self,
        entity_name: str,
        entity_type: str = "person",
        description: str = "",
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        entity_id = insert_row("entity_nodes", {
            "entity_name": entity_name,
            "entity_type": entity_type,
            "description": description,
            "created_at": now,
        })
        log.info("Added entity #%d [%s]: %s", entity_id, entity_type, entity_name)
        return entity_id

    def get_entity(self, entity_id: int) -> Optional[dict]:
        rows = query_rows("entity_nodes", "id = ?", (entity_id,))
        return dict(rows[0]) if rows else None

    def increment_entity_mentions(self, entity_id: int):
        """No-op placeholder — entity_nodes schema is minimal."""
        pass

    # ── Evidence Links ───────────────────────────────────────────────────
    def link(
        self,
        from_type: str,
        from_id: int,
        to_type: str,
        to_id: int,
        relationship: str = "supports",
        weight: float = 1.0,
    ) -> int:
        """
        Create a weighted edge between two nodes.

        from_type/to_type: "claim", "source", "entity"
        relationship: "supports", "contradicts", "derives_from",
                      "references", "co_occurs", "supersedes"
        """
        now = datetime.now(timezone.utc).isoformat()
        link_id = insert_row("evidence_links", {
            "from_type": from_type,
            "from_id": from_id,
            "to_type": to_type,
            "to_id": to_id,
            "relationship": relationship,
            "weight": weight,
            "created_at": now,
        })
        log.info("Linked %s#%d → %s#%d [%s] w=%.2f",
                 from_type, from_id, to_type, to_id, relationship, weight)
        return link_id

    def get_links_from(self, node_type: str, node_id: int) -> list[EvidenceLink]:
        rows = query_rows(
            "evidence_links",
            "from_type = ? AND from_id = ?",
            (node_type, node_id),
        )
        return [self._row_to_link(r) for r in rows]

    def get_links_to(self, node_type: str, node_id: int) -> list[EvidenceLink]:
        rows = query_rows(
            "evidence_links",
            "to_type = ? AND to_id = ?",
            (node_type, node_id),
        )
        return [self._row_to_link(r) for r in rows]

    def get_all_links(self) -> list[EvidenceLink]:
        rows = query_rows("evidence_links", "1=1")
        return [self._row_to_link(r) for r in rows]

    # ── Mutation Detection ───────────────────────────────────────────────
    def get_mutation_chain(self, claim_id: int) -> list[ClaimNode]:
        """
        Trace back through mutation_parent_id links
        to reconstruct how a claim evolved over time.
        """
        chain = []
        current_id = claim_id

        while current_id:
            claim = self.get_claim(current_id)
            if not claim:
                break
            chain.append(claim)
            current_id = claim.mutation_parent

        chain.reverse()
        return chain

    def detect_mutations(self, claim_id: int) -> list[dict]:
        """
        Find all claims that are derived (mutated) from a given claim.
        Returns list of mutation records.
        """
        descendants = query_rows(
            "claim_nodes",
            "mutation_parent = ?",
            (claim_id,),
        )
        results = []
        for row in descendants:
            results.append({
                "child_id": row["id"],
                "child_text": row["claim_text"],
                "diff": row["mutation_diff"],
                "created_at": row["created_at"],
            })
        return results

    # ── Contradiction Detection ──────────────────────────────────────────
    def find_contradictions(self) -> list[dict]:
        """
        Find all evidence links typed 'contradicts' and return
        the connected claim pairs with details.
        """
        rows = query_rows("evidence_links", "relationship = ?", ("contradicts",))
        contradictions = []
        for row in rows:
            entry = {
                "link_id": row["id"],
                "from_type": row["from_type"],
                "from_id": row["from_id"],
                "to_type": row["to_type"],
                "to_id": row["to_id"],
                "weight": row["weight"],
            }
            # Load claim texts
            if row["from_type"] == "claim":
                c = self.get_claim(row["from_id"])
                if c:
                    entry["from_text"] = c.claim_text
            if row["to_type"] == "claim":
                c = self.get_claim(row["to_id"])
                if c:
                    entry["to_text"] = c.claim_text
            contradictions.append(entry)
        return contradictions

    # ── Provenance Chain ─────────────────────────────────────────────────
    def get_provenance(self, claim_id: int, max_depth: int = 10) -> list[dict]:
        """
        BFS traversal from a claim outward through evidence links.
        Returns traversal path showing how the claim is supported.
        """
        visited = set()
        queue = [("claim", claim_id, 0)]
        path = []

        while queue and len(path) < 100:
            node_type, node_id, depth = queue.pop(0)
            key = (node_type, node_id)
            if key in visited or depth > max_depth:
                continue
            visited.add(key)

            # Get node info
            node_info = {"type": node_type, "id": node_id, "depth": depth}
            if node_type == "claim":
                c = self.get_claim(node_id)
                if c:
                    node_info["text"] = c.claim_text[:100]
                    node_info["confidence"] = c.confidence
                    node_info["status"] = c.verification
            elif node_type == "source":
                s = self.get_source(node_id)
                if s:
                    node_info["title"] = s.source_title
                    node_info["credibility"] = s.credibility
            path.append(node_info)

            # Follow outgoing links
            links = self.get_links_from(node_type, node_id)
            for link in links:
                queue.append((link.to_type, link.to_id, depth + 1))

            # Follow incoming links
            links = self.get_links_to(node_type, node_id)
            for link in links:
                queue.append((link.from_type, link.from_id, depth + 1))

        return path

    # ── NetworkX Integration ─────────────────────────────────────────────
    def to_networkx(self):
        """
        Export the full claim graph to a NetworkX DiGraph.

        Node IDs are formatted as "claim_1", "source_3", "entity_5".
        Edge attributes include relationship and weight.
        """
        try:
            import networkx as nx
        except ImportError:
            log.error("NetworkX not installed")
            return None

        G = nx.DiGraph()

        # Add claim nodes
        for claim in self.get_all_claims():
            nid = f"claim_{claim.id}"
            G.add_node(nid, node_type="claim", label=claim.claim_text[:50],
                       claim_type=claim.claim_type, confidence=claim.confidence,
                       status=claim.verification)

        # Add source nodes
        for source in self.get_all_sources():
            nid = f"source_{source.id}"
            G.add_node(nid, node_type="source", label=source.source_title[:50],
                       source_type=source.source_type, credibility=source.credibility)

        # Add entity nodes
        entity_rows = query_rows("entity_nodes", "1=1")
        for row in entity_rows:
            nid = f"entity_{row['id']}"
            G.add_node(nid, node_type="entity", label=row["entity_name"],
                       entity_type=row["entity_type"])

        # Add edges
        for link in self.get_all_links():
            src = f"{link.from_type}_{link.from_id}"
            dst = f"{link.to_type}_{link.to_id}"
            G.add_edge(src, dst, relationship=link.relationship,
                       weight=link.weight)

        log.info("Exported claim graph: %d nodes, %d edges",
                 G.number_of_nodes(), G.number_of_edges())
        return G

    def get_clusters(self) -> list[set]:
        """
        Extract narrative clusters using weakly connected components
        from the evidence graph.
        """
        G = self.to_networkx()
        if not G:
            return []
        components = list(G.subgraph(c) for c in
                          __import__("networkx").weakly_connected_components(G))
        clusters = [set(comp.nodes()) for comp in components]
        log.info("Found %d narrative clusters", len(clusters))
        return clusters

    def get_statistics(self) -> dict:
        """Summary statistics for the claim graph."""
        claims = self.get_all_claims()
        sources = self.get_all_sources()
        links = self.get_all_links()
        contradictions = self.find_contradictions()

        by_type = {}
        for c in claims:
            by_type[c.claim_type] = by_type.get(c.claim_type, 0) + 1

        by_status = {}
        for c in claims:
            by_status[c.verification] = by_status.get(c.verification, 0) + 1

        return {
            "total_claims": len(claims),
            "total_sources": len(sources),
            "total_links": len(links),
            "total_contradictions": len(contradictions),
            "claims_by_type": by_type,
            "claims_by_status": by_status,
            "avg_confidence": (
                sum(c.confidence for c in claims) / len(claims) if claims else 0
            ),
        }

    # ── Row Converters ───────────────────────────────────────────────────
    @staticmethod
    def _row_to_claim(row) -> ClaimNode:
        return ClaimNode(
            id=row["id"],
            claim_text=row["claim_text"],
            claim_type=row["claim_type"],
            first_source=row["first_source"],
            confidence=row["confidence"],
            verification=row["verification"],
            mutation_parent=row["mutation_parent"],
            mutation_diff=row["mutation_diff"],
            tags=row["tags"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_source(row) -> SourceNode:
        return SourceNode(
            id=row["id"],
            source_type=row["source_type"],
            source_title=row["source_title"],
            source_url=row["source_url"],
            document_cid=row["document_cid"],
            author=row["author"],
            published_at=row["published_at"],
            credibility=row["credibility"],
            platform=row["platform"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_link(row) -> EvidenceLink:
        return EvidenceLink(
            id=row["id"],
            from_type=row["from_type"],
            from_id=row["from_id"],
            to_type=row["to_type"],
            to_id=row["to_id"],
            relationship=row["relationship"],
            weight=row["weight"],
            created_at=row["created_at"],
        )
