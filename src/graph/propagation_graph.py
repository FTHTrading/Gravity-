"""
Propagation Graph & Origin Trace Module.

Builds and analyzes an information-propagation network:
  - Nodes: individual posts / URLs
  - Edges: repost / share / citation relationships
  - Temporal ordering for origin tracing
  - Cluster detection for amplification analysis
  - Timeline visualization export

Outputs:
  - NetworkX graph object
  - Propagation timeline (chronological)
  - Amplification cluster report
  - GraphML / JSON export for external tools
"""

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.config import REPORTS_DIR
from src.database import query_rows, insert_row, get_connection
from src.logger import get_logger

log = get_logger(__name__)

try:
    import networkx as nx
except ImportError:
    nx = None
    log.warning("NetworkX not installed; graph analysis unavailable.")

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
except ImportError:
    plt = None
    log.warning("Matplotlib not installed; graph visualization unavailable.")


class PropagationGraph:
    """Build and analyze information-spread networks."""

    def __init__(self):
        if nx is None:
            raise ImportError("NetworkX is required: pip install networkx")
        self.graph: nx.DiGraph = nx.DiGraph()

    # ── Build Graph from Database ────────────────────────────────────────
    def build_from_db(self) -> None:
        """
        Load all social_posts and propagation_edges from the database
        to construct the directed graph.
        """
        posts = query_rows("social_posts")
        edges = query_rows("propagation_edges")

        for post in posts:
            self.graph.add_node(
                post["post_url"],
                platform=post["platform"],
                author=post["author"],
                timestamp=post["timestamp_utc"],
                text_preview=(post["post_text"] or "")[:100],
                search_term=post["search_term"],
            )

        for edge in edges:
            self.graph.add_edge(
                edge["source_url"],
                edge["target_url"],
                edge_type=edge["edge_type"],
                source_ts=edge["source_timestamp"],
                target_ts=edge["target_timestamp"],
            )

        log.info(
            "Graph built: %d nodes, %d edges",
            self.graph.number_of_nodes(),
            self.graph.number_of_edges(),
        )

    # ── Add Repost Edge ──────────────────────────────────────────────────
    def add_edge(
        self,
        source_url: str,
        target_url: str,
        source_ts: str = "",
        target_ts: str = "",
        platform: str = "",
        edge_type: str = "repost",
    ) -> None:
        """Register a propagation relationship."""
        self.graph.add_edge(
            source_url, target_url,
            edge_type=edge_type,
            source_ts=source_ts,
            target_ts=target_ts,
        )
        insert_row("propagation_edges", {
            "source_url": source_url,
            "target_url": target_url,
            "source_timestamp": source_ts,
            "target_timestamp": target_ts,
            "platform": platform,
            "edge_type": edge_type,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })

    # ── Origin Identification ────────────────────────────────────────────
    def find_earliest_posts(self, top_n: int = 10) -> list[dict]:
        """Return the N nodes with the earliest timestamps."""
        nodes_with_ts = []
        for node, data in self.graph.nodes(data=True):
            ts = data.get("timestamp")
            if ts:
                nodes_with_ts.append({"url": node, "timestamp": ts, **data})

        nodes_with_ts.sort(key=lambda x: x["timestamp"])
        log.info("Earliest %d posts identified", min(top_n, len(nodes_with_ts)))
        return nodes_with_ts[:top_n]

    # ── Amplification Clusters ───────────────────────────────────────────
    def detect_amplification_clusters(self) -> list[dict]:
        """
        Find clusters of nodes with high repost/share connectivity.
        Uses weakly connected components on the undirected projection.
        """
        undirected = self.graph.to_undirected()
        components = list(nx.connected_components(undirected))
        clusters = []

        for i, comp in enumerate(sorted(components, key=len, reverse=True)):
            sub = self.graph.subgraph(comp)
            clusters.append({
                "cluster_id": i,
                "size": len(comp),
                "density": nx.density(sub),
                "nodes": list(comp)[:20],  # cap for readability
                "platforms": list({
                    self.graph.nodes[n].get("platform", "unknown") for n in comp
                }),
            })

        log.info("Detected %d amplification clusters", len(clusters))
        return clusters

    # ── Propagation Timeline ─────────────────────────────────────────────
    def generate_timeline(self) -> list[dict]:
        """
        Return chronologically ordered list of all events.
        Each entry: {timestamp, url, platform, author, search_term}.
        """
        events = []
        for node, data in self.graph.nodes(data=True):
            if data.get("timestamp"):
                events.append({
                    "timestamp": data["timestamp"],
                    "url": node,
                    "platform": data.get("platform"),
                    "author": data.get("author"),
                    "search_term": data.get("search_term"),
                })

        events.sort(key=lambda x: x["timestamp"])
        log.info("Timeline generated: %d events", len(events))
        return events

    # ── Temporal Distribution ────────────────────────────────────────────
    def temporal_distribution(self) -> dict[str, int]:
        """Count posts per calendar day."""
        day_counts: dict[str, int] = defaultdict(int)
        for _, data in self.graph.nodes(data=True):
            ts = data.get("timestamp", "")
            if ts:
                day = ts[:10]  # YYYY-MM-DD
                day_counts[day] += 1
        return dict(sorted(day_counts.items()))

    # ── Graph Metrics ────────────────────────────────────────────────────
    def compute_metrics(self) -> dict[str, Any]:
        """Return high-level graph statistics."""
        metrics = {
            "num_nodes": self.graph.number_of_nodes(),
            "num_edges": self.graph.number_of_edges(),
            "density": nx.density(self.graph),
            "num_weakly_connected_components": nx.number_weakly_connected_components(self.graph),
            "num_strongly_connected_components": nx.number_strongly_connected_components(self.graph),
        }

        if self.graph.number_of_nodes() > 0:
            in_deg = dict(self.graph.in_degree())
            out_deg = dict(self.graph.out_degree())
            most_cited = max(in_deg, key=in_deg.get) if in_deg else None
            most_sharing = max(out_deg, key=out_deg.get) if out_deg else None
            metrics["most_cited_node"] = {"url": most_cited, "in_degree": in_deg.get(most_cited, 0)}
            metrics["most_sharing_node"] = {"url": most_sharing, "out_degree": out_deg.get(most_sharing, 0)}

        log.info("Graph metrics: %s", json.dumps(metrics, default=str))
        return metrics

    # ── Export ────────────────────────────────────────────────────────────
    def export_graphml(self, filename: str = "propagation_graph.graphml") -> Path:
        """Export graph to GraphML format."""
        path = REPORTS_DIR / filename
        nx.write_graphml(self.graph, str(path))
        log.info("Graph exported to %s", path)
        return path

    def export_json(self, filename: str = "propagation_graph.json") -> Path:
        """Export graph as node-link JSON."""
        path = REPORTS_DIR / filename
        data = nx.node_link_data(self.graph)
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        log.info("Graph JSON exported to %s", path)
        return path

    # ── Visualization ────────────────────────────────────────────────────
    def plot_timeline(self, filename: str = "propagation_timeline.png") -> Optional[Path]:
        """Save a timeline scatter plot of posts over time."""
        if plt is None:
            log.warning("Matplotlib required for plotting.")
            return None

        timeline = self.generate_timeline()
        if not timeline:
            return None

        dates = []
        platforms = []
        for event in timeline:
            try:
                dt = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
                dates.append(dt)
                platforms.append(event.get("platform", "unknown"))
            except (ValueError, TypeError):
                continue

        if not dates:
            return None

        platform_set = sorted(set(platforms))
        color_map = {p: i for i, p in enumerate(platform_set)}
        colors = [color_map[p] for p in platforms]

        fig, ax = plt.subplots(figsize=(14, 5))
        scatter = ax.scatter(dates, [1] * len(dates), c=colors, cmap="tab10", alpha=0.7, s=30)
        ax.set_yticks([])
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.set_title("Propagation Timeline")
        ax.set_xlabel("Date (UTC)")
        fig.autofmt_xdate()

        # Legend
        handles = [
            plt.Line2D([0], [0], marker="o", color="w",
                       markerfacecolor=plt.cm.tab10(color_map[p] / max(len(platform_set), 1)),
                       markersize=8, label=p)
            for p in platform_set
        ]
        ax.legend(handles=handles, loc="upper left", fontsize=8)

        path = REPORTS_DIR / filename
        fig.savefig(str(path), dpi=150, bbox_inches="tight")
        plt.close(fig)
        log.info("Timeline plot saved to %s", path)
        return path
