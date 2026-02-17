"""
Wave Science Computation Module for Project Anchor.

Numerical tools for wave physics relevant to gravity-anomaly claims:
  - Electromagnetic wave equations
  - Gravitational wave characteristics
  - Resonance and interference analysis
  - Dispersion relations
  - Standing wave / cavity modes
  - Plasma frequency
  - Quantum wave-particle relations

All outputs are numerical — no interpretive conclusions.
Constants sourced from NIST CODATA 2018.
"""

import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

from src.database import insert_row
from src.logger import get_logger

log = get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
c = 2.99792458e8            # speed of light [m/s]
h_PLANCK = 6.62607015e-34   # Planck constant [J s]
hbar = h_PLANCK / (2 * math.pi)
k_B = 1.380649e-23          # Boltzmann constant [J/K]
e_charge = 1.602176634e-19  # elementary charge [C]
m_e = 9.1093837015e-31      # electron mass [kg]
epsilon_0 = 8.854187817e-12 # vacuum permittivity [F/m]
mu_0 = 4 * math.pi * 1e-7  # vacuum permeability [H/m]
G = 6.67430e-11             # gravitational constant


@dataclass
class WaveResult:
    """Container for a wave-physics computed quantity."""
    description: str
    equation: str
    value: float
    units: str
    source_ref: str

    def save(self) -> int:
        return insert_row("physics_comparisons", {
            **asdict(self),
            "computed_at": datetime.now(timezone.utc).isoformat(),
        })


class WaveScienceEngine:
    """Numerical wave physics computations."""

    # ── 1. Wavelength-Frequency Relation ─────────────────────────────────
    def wavelength_from_frequency(
        self, frequency: float, v_phase: float = c
    ) -> WaveResult:
        """
        λ = v / f  (applies to any wave in a medium with phase velocity v).
        Default: EM wave in vacuum.
        """
        lam = v_phase / frequency
        result = WaveResult(
            description=f"Wavelength for f={frequency:.3e} Hz (v={v_phase:.3e} m/s)",
            equation="λ = v / f",
            value=lam,
            units="metres",
            source_ref="Fundamental wave relation",
        )
        result.save()
        log.info("λ = %.6e m for f = %.3e Hz", lam, frequency)
        return result

    # ── 2. EM Wave Energy (Photon) ───────────────────────────────────────
    def photon_energy(self, frequency: float) -> WaveResult:
        """
        E = h f  (Planck-Einstein relation)
        """
        E = h_PLANCK * frequency
        result = WaveResult(
            description=f"Photon energy at f={frequency:.3e} Hz",
            equation="E = h * f",
            value=E,
            units="joules",
            source_ref="Planck 1900; Einstein 1905",
        )
        result.save()
        log.info("Photon energy: %.6e J (%.6e eV)", E, E / e_charge)
        return result

    # ── 3. de Broglie Wavelength ─────────────────────────────────────────
    def de_broglie_wavelength(
        self, mass: float = m_e, velocity: float = 1e6
    ) -> WaveResult:
        """
        λ_dB = h / (m v)  (matter wave wavelength)
        Default: electron at 1e6 m/s.
        """
        lam = h_PLANCK / (mass * velocity)
        result = WaveResult(
            description=f"de Broglie wavelength (m={mass:.3e} kg, v={velocity:.3e} m/s)",
            equation="λ_dB = h / (m * v)",
            value=lam,
            units="metres",
            source_ref="de Broglie 1924; wave-particle duality",
        )
        result.save()
        log.info("de Broglie λ: %.6e m", lam)
        return result

    # ── 4. Plasma Frequency ──────────────────────────────────────────────
    def plasma_frequency(
        self, n_e: float = 1e18
    ) -> WaveResult:
        """
        Electron plasma frequency:
        ω_p = sqrt(n_e e^2 / (ε_0 m_e))
        f_p = ω_p / (2π)

        Default: n_e = 1e18 m^-3 (typical lab plasma).
        """
        omega_p = math.sqrt(n_e * e_charge**2 / (epsilon_0 * m_e))
        f_p = omega_p / (2 * math.pi)
        result = WaveResult(
            description=f"Plasma frequency (n_e={n_e:.2e} m^-3)",
            equation="f_p = (1/2π) sqrt(n_e e^2 / (ε₀ m_e))",
            value=f_p,
            units="Hz",
            source_ref="Plasma physics; Langmuir 1928",
        )
        result.save()
        log.info("Plasma frequency: %.4e Hz (%.4e GHz)", f_p, f_p / 1e9)
        return result

    # ── 5. Standing Wave Cavity Modes ────────────────────────────────────
    def cavity_resonance(
        self, L: float = 1.0, n: int = 1, v_phase: float = c
    ) -> WaveResult:
        """
        Resonant frequencies of a 1D cavity:
        f_n = n * v / (2 L)

        Default: 1-metre cavity, fundamental mode, EM wave.
        """
        f_n = n * v_phase / (2 * L)
        result = WaveResult(
            description=f"Cavity resonance mode n={n} (L={L} m, v={v_phase:.3e} m/s)",
            equation="f_n = n * v / (2 * L)",
            value=f_n,
            units="Hz",
            source_ref="Standing wave theory; Fabry-Pérot cavity",
        )
        result.save()
        log.info("Cavity mode %d: %.4e Hz", n, f_n)
        return result

    # ── 6. Interference: Two-Source Path Difference ──────────────────────
    def interference_condition(
        self, wavelength: float, path_diff: float
    ) -> WaveResult:
        """
        Determine constructive/destructive interference:
        phase_diff = 2π * Δd / λ
        If phase ≈ 2nπ → constructive; (2n+1)π → destructive.
        Returns the phase difference in radians.
        """
        phase = 2 * math.pi * path_diff / wavelength
        n_half = phase / math.pi
        result = WaveResult(
            description=f"Interference phase (λ={wavelength:.4e} m, Δd={path_diff:.4e} m)",
            equation="Δφ = 2π Δd / λ",
            value=phase,
            units="radians",
            source_ref="Young's double-slit; superposition principle",
        )
        result.save()
        log.info("Phase diff: %.4f rad (%.2f × π)", phase, n_half)
        return result

    # ── 7. Doppler Shift (Relativistic) ──────────────────────────────────
    def relativistic_doppler(
        self, f_source: float, v_relative: float
    ) -> WaveResult:
        """
        Relativistic Doppler shift (source approaching):
        f_obs = f_source * sqrt((1 + β) / (1 - β))
        where β = v / c
        """
        beta = v_relative / c
        if abs(beta) >= 1.0:
            log.warning("β >= 1 is unphysical; clamping to 0.9999")
            beta = 0.9999 if beta > 0 else -0.9999
        f_obs = f_source * math.sqrt((1 + beta) / (1 - beta))
        result = WaveResult(
            description=f"Relativistic Doppler shift (f_src={f_source:.3e} Hz, v={v_relative:.3e} m/s)",
            equation="f_obs = f_src * sqrt((1+β)/(1-β))",
            value=f_obs,
            units="Hz",
            source_ref="Special Relativity; Einstein 1905",
        )
        result.save()
        log.info("Doppler: f_obs = %.4e Hz (shift ratio: %.6f)", f_obs, f_obs / f_source)
        return result

    # ── 8. GW Characteristic Strain Sensitivity ─────────────────────────
    def gw_strain_sensitivity(
        self, arm_length: float = 4000.0,  # LIGO arm
        displacement_m: float = 1e-18,     # detectable displacement
    ) -> WaveResult:
        """
        Minimum detectable strain from an interferometer:
        h_min = Δx / L
        Default: LIGO (4 km arms, ~1e-18 m displacement sensitivity).
        """
        h_min = displacement_m / arm_length
        result = WaveResult(
            description=f"Detector strain sensitivity (L={arm_length} m, Δx={displacement_m:.1e} m)",
            equation="h_min = Δx / L",
            value=h_min,
            units="dimensionless strain",
            source_ref="LIGO design sensitivity; Abramovici et al. 1992",
        )
        result.save()
        log.info("Strain sensitivity: %.4e", h_min)
        return result

    # ── 9. Dispersion Relation (Deep Water Gravity Waves) ────────────────
    def deep_water_dispersion(
        self, wavelength: float = 100.0, g: float = 9.80665
    ) -> WaveResult:
        """
        Deep water surface gravity wave dispersion:
        ω^2 = g k,  where k = 2π/λ
        f = (1/2π) * sqrt(g * 2π / λ)
        """
        k = 2 * math.pi / wavelength
        omega = math.sqrt(g * k)
        f = omega / (2 * math.pi)
        v_phase = omega / k
        result = WaveResult(
            description=f"Deep water wave (λ={wavelength} m): frequency & phase velocity",
            equation="ω² = g k;  v_phase = sqrt(g λ / 2π)",
            value=f,
            units="Hz",
            source_ref="Airy wave theory; ocean surface waves",
        )
        result.save()
        log.info("Deep water wave f=%.4f Hz, v_phase=%.2f m/s", f, v_phase)
        return result

    # ── 10. Schumann Resonance Frequencies ───────────────────────────────
    def schumann_resonance(self, n: int = 1) -> WaveResult:
        """
        Earth-ionosphere cavity Schumann resonances:
        f_n ≈ (c / (2π R_Earth)) * sqrt(n(n+1))

        n=1 fundamental ≈ 7.83 Hz
        """
        R = 6.371e6  # Earth radius
        f_n = (c / (2 * math.pi * R)) * math.sqrt(n * (n + 1))
        result = WaveResult(
            description=f"Schumann resonance mode n={n}",
            equation="f_n = (c / 2πR) * sqrt(n(n+1))",
            value=f_n,
            units="Hz",
            source_ref="Schumann 1952; Earth-ionosphere EM cavity",
        )
        result.save()
        log.info("Schumann mode %d: %.2f Hz", n, f_n)
        return result

    # ── 11. Electromagnetic Skin Depth ───────────────────────────────────
    def em_skin_depth(
        self, frequency: float = 1e6, conductivity: float = 5.96e7
    ) -> WaveResult:
        """
        EM skin depth in a conductor:
        δ = sqrt(2 / (ω μ₀ σ))
        Default: copper at 1 MHz.
        """
        omega = 2 * math.pi * frequency
        delta = math.sqrt(2.0 / (omega * mu_0 * conductivity))
        result = WaveResult(
            description=f"EM skin depth (f={frequency:.2e} Hz, σ={conductivity:.2e} S/m)",
            equation="δ = sqrt(2 / (ω μ₀ σ))",
            value=delta,
            units="metres",
            source_ref="Maxwell's equations; conductor wave penetration",
        )
        result.save()
        log.info("Skin depth: %.6e m (%.4f μm)", delta, delta * 1e6)
        return result

    # ── Run Full Wave Suite ──────────────────────────────────────────────
    def run_full_suite(self) -> list[dict[str, Any]]:
        """Execute all wave physics computations with default parameters."""
        computations = [
            lambda: self.wavelength_from_frequency(1e9),           # 1 GHz EM
            lambda: self.photon_energy(5e14),                       # visible light
            lambda: self.de_broglie_wavelength(),                   # electron
            lambda: self.plasma_frequency(),                        # lab plasma
            lambda: self.cavity_resonance(),                        # 1m cavity
            lambda: self.interference_condition(500e-9, 250e-9),    # visible λ
            lambda: self.relativistic_doppler(1e9, 1e7),           # 1 GHz, 10 km/s
            lambda: self.gw_strain_sensitivity(),                   # LIGO
            lambda: self.deep_water_dispersion(),                   # 100m ocean wave
            lambda: self.schumann_resonance(1),                     # fundamental
            lambda: self.em_skin_depth(),                           # copper 1 MHz
        ]
        results = []
        for fn in computations:
            try:
                r = fn()
                results.append(asdict(r))
            except Exception as exc:
                log.error("Wave computation failed: %s", exc)

        log.info("Wave science suite complete: %d results", len(results))
        return results
