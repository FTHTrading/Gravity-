"""
Drift Kinematics Engine – Velocity, Acceleration & Jerk Analysis

Analyzes the kinematic properties of claim text drift over time:
  - Drift velocity: rate of textual change per mutation step
  - Drift acceleration: d²(drift)/dt² — detects inflection points
  - Drift jerk: d³(drift)/dt³ — rate of change of acceleration
  - Inflection point detection: where acceleration changes sign
  - Kinematic profile: position/velocity/acceleration/jerk over time

Operates on drift velocity data from mutation_entropy and entropy_timeline.
"""

import math
from datetime import datetime, timezone
from dataclasses import dataclass, field

from src.database import execute_sql
from src.graph.claim_graph import ClaimGraph
from src.graph.mutation_entropy import MutationEntropy
from src.graph.entropy_trend import EntropyTrendEngine
from src.logger import get_logger

log = get_logger(__name__)


@dataclass
class KinematicPoint:
    """Single kinematic measurement at a point in time."""
    timestamp: str = ""
    drift: float = 0.0
    velocity: float = 0.0      # dd/dt
    acceleration: float = 0.0  # d²d/dt²
    jerk: float = 0.0          # d³d/dt³


@dataclass
class DriftKinematics:
    """Full kinematic profile of a claim's drift history."""
    claim_id: int = 0
    current_drift: float = 0.0
    current_velocity: float = 0.0
    current_acceleration: float = 0.0
    current_jerk: float = 0.0
    mean_velocity: float = 0.0
    max_velocity: float = 0.0
    mean_acceleration: float = 0.0
    max_acceleration: float = 0.0
    total_snapshots: int = 0
    inflection_points: list = field(default_factory=list)
    kinematic_profile: list = field(default_factory=list)
    phase: str = "unknown"  # constant, accelerating, decelerating, inflecting

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "current_drift": round(self.current_drift, 6),
            "current_velocity": round(self.current_velocity, 6),
            "current_acceleration": round(self.current_acceleration, 6),
            "current_jerk": round(self.current_jerk, 6),
            "mean_velocity": round(self.mean_velocity, 6),
            "max_velocity": round(self.max_velocity, 6),
            "mean_acceleration": round(self.mean_acceleration, 6),
            "max_acceleration": round(self.max_acceleration, 6),
            "total_snapshots": self.total_snapshots,
            "inflection_count": len(self.inflection_points),
            "phase": self.phase,
        }


class DriftKinematicsEngine:
    """
    Computes kinematic derivatives of claim drift over time.

    Uses entropy timeline snapshots to build velocity, acceleration,
    and jerk profiles. Detects inflection points where drift behavior
    changes character.
    """

    # Minimum number of data points for meaningful analysis
    MIN_POINTS = 3
    # Acceleration threshold for phase classification
    ACCEL_THRESHOLD = 0.001
    # Jerk threshold for inflection detection
    JERK_THRESHOLD = 0.0005

    def __init__(self):
        self.graph = ClaimGraph()
        self.entropy_engine = EntropyTrendEngine()

    # ── Core Analysis ────────────────────────────────────────────────────

    def analyze(self, claim_id: int) -> DriftKinematics:
        """
        Full kinematic analysis of a claim's drift history.

        Computes velocity, acceleration, and jerk from drift timeline data.
        """
        result = DriftKinematics(claim_id=claim_id)

        # Get drift history from entropy timeline
        history = self.entropy_engine.get_history(claim_id, limit=200)
        if not history:
            return result

        # Chronological order (history returns newest-first)
        chronological = list(reversed(history))
        result.total_snapshots = len(chronological)

        # Extract drift series with timestamps
        drift_series = []
        for point in chronological:
            drift_series.append({
                "timestamp": point.snapshot_at,
                "drift": point.drift_velocity,
            })

        if len(drift_series) < 2:
            if drift_series:
                result.current_drift = drift_series[-1]["drift"]
            return result

        # Compute velocities (dd/dt)
        velocities = self._compute_derivatives(drift_series, "drift")

        # Compute accelerations (d²d/dt²)
        accel_input = [
            {"timestamp": v["timestamp"], "drift": v["value"]}
            for v in velocities
        ]
        accelerations = self._compute_derivatives(accel_input, "drift") if len(accel_input) >= 2 else []

        # Compute jerks (d³d/dt³)
        jerk_input = [
            {"timestamp": a["timestamp"], "drift": a["value"]}
            for a in accelerations
        ]
        jerks = self._compute_derivatives(jerk_input, "drift") if len(jerk_input) >= 2 else []

        # Build kinematic profile
        profile = self._build_profile(drift_series, velocities, accelerations, jerks)
        result.kinematic_profile = profile

        # Current values
        result.current_drift = drift_series[-1]["drift"]
        result.current_velocity = velocities[-1]["value"] if velocities else 0.0
        result.current_acceleration = accelerations[-1]["value"] if accelerations else 0.0
        result.current_jerk = jerks[-1]["value"] if jerks else 0.0

        # Statistics
        if velocities:
            vel_vals = [v["value"] for v in velocities]
            result.mean_velocity = sum(abs(v) for v in vel_vals) / len(vel_vals)
            result.max_velocity = max(abs(v) for v in vel_vals)

        if accelerations:
            acc_vals = [a["value"] for a in accelerations]
            result.mean_acceleration = sum(abs(a) for a in acc_vals) / len(acc_vals)
            result.max_acceleration = max(abs(a) for a in acc_vals)

        # Inflection points
        result.inflection_points = self._find_inflection_points(accelerations)

        # Phase classification
        result.phase = self._classify_phase(result)

        return result

    # ── Derivative Computation ───────────────────────────────────────────

    def _compute_derivatives(self, series: list[dict], value_key: str) -> list[dict]:
        """
        Compute finite differences (first derivative) of a time series.
        Returns list of {timestamp, value} where value = d(value_key)/dt.
        """
        if len(series) < 2:
            return []

        derivatives = []
        for i in range(1, len(series)):
            try:
                t0 = datetime.fromisoformat(series[i - 1]["timestamp"])
                t1 = datetime.fromisoformat(series[i]["timestamp"])
                dt_hours = (t1 - t0).total_seconds() / 3600.0
                if dt_hours < 1e-9:
                    dt_hours = 1e-9  # avoid division by zero

                dv = series[i][value_key] - series[i - 1][value_key]
                derivative = dv / dt_hours

                derivatives.append({
                    "timestamp": series[i]["timestamp"],
                    "value": derivative,
                })
            except (ValueError, TypeError, KeyError):
                continue

        return derivatives

    # ── Profile Building ─────────────────────────────────────────────────

    def _build_profile(self, drift_series: list[dict],
                       velocities: list[dict],
                       accelerations: list[dict],
                       jerks: list[dict]) -> list[dict]:
        """Build complete kinematic profile aligned by timestamp."""
        # Index auxiliary data by timestamp
        vel_map = {v["timestamp"]: v["value"] for v in velocities}
        acc_map = {a["timestamp"]: a["value"] for a in accelerations}
        jerk_map = {j["timestamp"]: j["value"] for j in jerks}

        profile = []
        for point in drift_series:
            ts = point["timestamp"]
            profile.append({
                "timestamp": ts,
                "drift": point["drift"],
                "velocity": vel_map.get(ts, 0.0),
                "acceleration": acc_map.get(ts, 0.0),
                "jerk": jerk_map.get(ts, 0.0),
            })
        return profile

    # ── Inflection Point Detection ───────────────────────────────────────

    def _find_inflection_points(self, accelerations: list[dict]) -> list[dict]:
        """
        Detect inflection points where acceleration changes sign.
        These indicate fundamental shifts in drift behavior.
        """
        if len(accelerations) < 2:
            return []

        inflections = []
        for i in range(1, len(accelerations)):
            prev = accelerations[i - 1]["value"]
            curr = accelerations[i]["value"]

            # Sign change = inflection
            if prev * curr < 0 and (abs(prev) > self.JERK_THRESHOLD or abs(curr) > self.JERK_THRESHOLD):
                inflections.append({
                    "timestamp": accelerations[i]["timestamp"],
                    "from_acceleration": round(prev, 6),
                    "to_acceleration": round(curr, 6),
                    "magnitude": round(abs(curr - prev), 6),
                })

        return inflections

    # ── Phase Classification ─────────────────────────────────────────────

    def _classify_phase(self, kinematics: DriftKinematics) -> str:
        """
        Classify the current kinematic phase of drift.

        Phases:
          constant    — minimal velocity and acceleration
          accelerating — positive acceleration (drift speeding up)
          decelerating — negative acceleration (drift slowing down)
          inflecting  — recent inflection point detected
        """
        if kinematics.inflection_points:
            # Check if most recent inflection is "recent" (last in list)
            return "inflecting"

        accel = abs(kinematics.current_acceleration)
        vel = abs(kinematics.current_velocity)

        if accel < self.ACCEL_THRESHOLD and vel < self.ACCEL_THRESHOLD:
            return "constant"

        if kinematics.current_acceleration > self.ACCEL_THRESHOLD:
            return "accelerating"
        elif kinematics.current_acceleration < -self.ACCEL_THRESHOLD:
            return "decelerating"

        return "constant"

    # ── Bulk Analysis ────────────────────────────────────────────────────

    def analyze_all(self) -> list[DriftKinematics]:
        """Analyze drift kinematics for all claims with entropy timeline data."""
        claim_ids = self.entropy_engine.get_claims_with_history()
        results = []
        for cid in claim_ids:
            kinematics = self.analyze(cid)
            results.append(kinematics)
        return results

    def detect_accelerating(self, threshold: float = 0.001) -> list[DriftKinematics]:
        """Find claims with significantly accelerating drift."""
        all_k = self.analyze_all()
        return [k for k in all_k if k.current_acceleration > threshold]

    def detect_inflecting(self) -> list[DriftKinematics]:
        """Find claims currently at inflection points."""
        all_k = self.analyze_all()
        return [k for k in all_k if k.phase == "inflecting"]

    def rank_by_acceleration(self, top_n: int = 20) -> list[DriftKinematics]:
        """Rank claims by absolute acceleration magnitude."""
        all_k = self.analyze_all()
        all_k.sort(key=lambda k: abs(k.current_acceleration), reverse=True)
        return all_k[:top_n]
