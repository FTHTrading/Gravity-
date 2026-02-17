"""
Gravitational Physics Consistency Module.

Computes and compares:
  - Gravitational wave strain amplitude at Earth from known black hole mergers
  - Energy required to nullify Earth's gravitational field
  - Comparison of observed vs. claimed gravitational effects
  - Tidal forces from known astrophysical events
  - Orbital & escape velocities
  - Kepler's third law verification
  - Schwarzschild radius / event horizon

Extended equation catalog (v2):
  - Poisson's equation (field strength)
  - Laplace equation (vacuum field)
  - Einstein field equation stress-energy trace
  - Quadrupole gravitational wave power
  - Friedmann expansion rate
  - MOND interpolation
  - Lense-Thirring frame dragging
  - Planck units
  - Gravitational redshift

All equations are logged.  Outputs are numerical comparisons only.
No conclusions or belief statements are generated.

Constants sourced from NIST CODATA 2018 and IAU 2015.
"""

import json
import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any

from src.database import insert_row
from src.logger import get_logger

log = get_logger(__name__)

# ── Fundamental Constants ────────────────────────────────────────────────────
G = 6.67430e-11         # gravitational constant  [m^3 kg^-1 s^-2]
c = 2.99792458e8        # speed of light           [m s^-1]
M_SUN = 1.98892e30      # solar mass               [kg]
M_EARTH = 5.9722e24     # Earth mass               [kg]
R_EARTH = 6.371e6       # Earth mean radius         [m]
g_SURFACE = 9.80665     # standard surface gravity  [m s^-2]
PC_TO_M = 3.0857e16     # parsec in metres
LY_TO_M = 9.4607e15     # light-year in metres
h_PLANCK = 6.62607015e-34  # Planck constant       [J s]
hbar = h_PLANCK / (2 * math.pi)  # reduced Planck   [J s]
k_B = 1.380649e-23      # Boltzmann constant       [J K^-1]
AU_TO_M = 1.496e11      # astronomical unit         [m]
M_PROTON = 1.67262192e-27  # proton mass            [kg]


@dataclass
class PhysicsResult:
    """Container for a single computed quantity."""
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


class GravityPhysicsEngine:
    """Numerical comparisons related to gravitational claims."""

    # ── 1. Surface Gravitational Binding Energy of Earth ─────────────────
    def gravitational_binding_energy(self) -> PhysicsResult:
        """
        Minimum energy to completely unbind Earth against its own gravity.
        U = (3 G M^2) / (5 R)
        """
        U = (3 * G * M_EARTH**2) / (5 * R_EARTH)
        result = PhysicsResult(
            description="Gravitational binding energy of Earth",
            equation="U = (3 * G * M_Earth^2) / (5 * R_Earth)",
            value=U,
            units="joules",
            source_ref="Classical mechanics; Chandrasekhar 1939",
        )
        result.save()
        log.info("Binding energy: %.4e J", U)
        return result

    # ── 2. Energy to Nullify Surface Gravity ─────────────────────────────
    def energy_to_nullify_gravity(self) -> PhysicsResult:
        """
        Energy that would need to be continuously supplied to cancel
        gravitational acceleration at Earth's surface for all surface mass.

        This equals the weight of the atmosphere + surface layer acted on
        by g, integrated — but as a minimal proxy we compute the kinetic
        energy equivalent of lifting all surface mass at g for 1 second:
        E = M_Earth * g * R_Earth   (order-of-magnitude gravitational PE)
        """
        E = M_EARTH * g_SURFACE * R_EARTH
        result = PhysicsResult(
            description="Order-of-magnitude energy to counteract Earth surface gravity",
            equation="E ~ M_Earth * g * R_Earth",
            value=E,
            units="joules",
            source_ref="Order-of-magnitude estimate",
        )
        result.save()
        log.info("Energy to nullify gravity: %.4e J", E)
        return result

    # ── 3. GW Strain from a Black Hole Merger ───────────────────────────
    def gravitational_wave_strain(
        self,
        m1_solar: float = 36.0,
        m2_solar: float = 29.0,
        distance_mpc: float = 410.0,
        label: str = "GW150914-like",
    ) -> PhysicsResult:
        """
        Peak gravitational-wave strain h at Earth from a compact binary merger.

        h ~ (4 G M_chirp / (c^2 d)) * (G M_chirp omega / c^3)^(2/3)

        For simplicity, use the order-of-magnitude formula:
        h ~ (G / c^4) * (M_chirp * c^2) / d * (v/c)^2

        We use the measured peak strain for reference events.
        GW150914 measured h ~ 1.0e-21 at 410 Mpc.
        """
        m1 = m1_solar * M_SUN
        m2 = m2_solar * M_SUN
        M_chirp = (m1 * m2) ** (3 / 5) / (m1 + m2) ** (1 / 5)
        d = distance_mpc * 1e6 * PC_TO_M  # Mpc → metres

        # Order-of-magnitude peak strain
        h = (4 * G * M_chirp) / (c**2 * d)
        result = PhysicsResult(
            description=f"GW peak strain at Earth from {label} merger ({m1_solar}+{m2_solar} M_sun at {distance_mpc} Mpc)",
            equation="h ~ 4 * G * M_chirp / (c^2 * d)",
            value=h,
            units="dimensionless strain",
            source_ref=f"Inspiral approximation; {label}",
        )
        result.save()
        log.info("GW strain (%s): %.4e", label, h)
        return result

    # ── 4. Tidal Acceleration from GW ────────────────────────────────────
    def tidal_acceleration_from_gw(
        self,
        strain: float = 1.0e-21,
        frequency: float = 250.0,
    ) -> PhysicsResult:
        """
        Maximum tidal acceleration a_tidal from a gravitational wave:
        a_tidal = h * (2 pi f)^2 * L / 2
        where L ~ R_Earth (baseline).
        """
        omega = 2 * math.pi * frequency
        a_tidal = strain * omega**2 * R_EARTH / 2
        result = PhysicsResult(
            description=f"Tidal acceleration at Earth surface from GW (h={strain:.1e}, f={frequency} Hz)",
            equation="a_tidal = h * (2*pi*f)^2 * R_Earth / 2",
            value=a_tidal,
            units="m/s^2",
            source_ref="Linearized GR; Misner Thorne Wheeler Ch 37",
        )
        result.save()
        log.info("Tidal accel from GW: %.4e m/s^2  (compare g=%.2f)", a_tidal, g_SURFACE)
        return result

    # ── 5. Ratio: GW Tidal Effect vs Surface Gravity ─────────────────────
    def ratio_gw_to_surface_gravity(
        self,
        strain: float = 1.0e-21,
        frequency: float = 250.0,
    ) -> PhysicsResult:
        """
        Dimensionless ratio of GW tidal acceleration to Earth's surface
        gravitational acceleration.
        """
        a_tidal = strain * (2 * math.pi * frequency) ** 2 * R_EARTH / 2
        ratio = a_tidal / g_SURFACE
        result = PhysicsResult(
            description="Ratio of GW tidal acceleration to surface gravity",
            equation="ratio = a_tidal / g_surface",
            value=ratio,
            units="dimensionless",
            source_ref="Derived from preceding computations",
        )
        result.save()
        log.info("GW/g ratio: %.4e  (1 = full cancellation)", ratio)
        return result

    # ── 6. Black Hole Distance for g-Cancellation ───────────────────────
    def required_distance_for_cancellation(
        self, bh_mass_solar: float = 1e6
    ) -> PhysicsResult:
        """
        How close a black hole of given mass would need to be for its tidal
        field to produce g-level acceleration across Earth's diameter:

        a_tidal = 2 G M d_baseline / r^3
        Set a_tidal = g, d_baseline = 2*R_Earth, solve for r.

        r = (2 G M * 2 R_Earth / g)^(1/3)
        """
        M = bh_mass_solar * M_SUN
        r = (2 * G * M * 2 * R_EARTH / g_SURFACE) ** (1 / 3)
        r_au = r / 1.496e11
        result = PhysicsResult(
            description=f"Distance for {bh_mass_solar:.0e} M_sun BH tidal field to equal g",
            equation="r = (4 G M R_Earth / g)^(1/3)",
            value=r,
            units="metres",
            source_ref="Newtonian tidal approximation",
        )
        result.save()
        log.info(
            "BH (%.1e M_sun) must be at r=%.4e m (%.2f AU) for tidal = g",
            bh_mass_solar, r, r_au,
        )
        return result

    # ── 7. Energy of Observed BH Merger GW Emission ─────────────────────
    def merger_energy_output(
        self,
        mass_radiated_solar: float = 3.0,
        label: str = "GW150914",
    ) -> PhysicsResult:
        """
        Total energy radiated as gravitational waves: E = m c^2
        GW150914 radiated ~3 solar masses of energy.
        """
        E = mass_radiated_solar * M_SUN * c**2
        result = PhysicsResult(
            description=f"Total GW energy radiated in {label}",
            equation="E = m_radiated * c^2",
            value=E,
            units="joules",
            source_ref=f"LIGO/Virgo {label} observation",
        )
        result.save()
        log.info("%s radiated energy: %.4e J", label, E)
        return result

    # ══════════════════════════════════════════════════════════════════════
    # EXTENDED EQUATION CATALOG (v2)
    # ══════════════════════════════════════════════════════════════════════

    # ── 8. Newtonian Gravitational Field Strength ────────────────────────
    def gravitational_field_strength(
        self, M: float = M_EARTH, r: float = R_EARTH
    ) -> PhysicsResult:
        """
        Gravitational field strength / acceleration:
        g = G * M / r^2    (Newton's law of gravitation for field)
        """
        g_val = G * M / r**2
        result = PhysicsResult(
            description=f"Gravitational field strength (M={M:.3e} kg, r={r:.3e} m)",
            equation="g = G * M / r^2",
            value=g_val,
            units="m/s^2",
            source_ref="Newton's law of universal gravitation",
        )
        result.save()
        log.info("Field strength: %.6f m/s^2", g_val)
        return result

    # ── 9. Orbital Velocity ──────────────────────────────────────────────
    def orbital_velocity(
        self, M: float = M_EARTH, r: float = R_EARTH + 400e3
    ) -> PhysicsResult:
        """
        Circular orbital velocity: v_orb = sqrt(G * M / r)
        Default: LEO orbit (~400 km altitude).
        """
        v = math.sqrt(G * M / r)
        result = PhysicsResult(
            description=f"Circular orbital velocity (M={M:.3e} kg, r={r:.3e} m)",
            equation="v_orb = sqrt(G * M / r)",
            value=v,
            units="m/s",
            source_ref="Keplerian orbital mechanics",
        )
        result.save()
        log.info("Orbital velocity: %.2f m/s (%.2f km/s)", v, v / 1000)
        return result

    # ── 10. Escape Velocity ──────────────────────────────────────────────
    def escape_velocity(
        self, M: float = M_EARTH, r: float = R_EARTH
    ) -> PhysicsResult:
        """
        Escape velocity from surface: v_esc = sqrt(2 G M / r)
        """
        v = math.sqrt(2 * G * M / r)
        result = PhysicsResult(
            description=f"Escape velocity (M={M:.3e} kg, r={r:.3e} m)",
            equation="v_esc = sqrt(2 * G * M / r)",
            value=v,
            units="m/s",
            source_ref="Classical mechanics energy conservation",
        )
        result.save()
        log.info("Escape velocity: %.2f m/s (%.2f km/s)", v, v / 1000)
        return result

    # ── 11. Kepler's Third Law Verification ──────────────────────────────
    def kepler_third_law(
        self, M: float = M_SUN, a: float = AU_TO_M
    ) -> PhysicsResult:
        """
        Orbital period from Kepler's third law:
        T = 2π * sqrt(a^3 / (G * M))
        Default: Earth-Sun system.
        """
        T = 2 * math.pi * math.sqrt(a**3 / (G * M))
        result = PhysicsResult(
            description=f"Kepler orbital period (M={M:.3e} kg, a={a:.3e} m)",
            equation="T = 2π * sqrt(a^3 / (G * M))",
            value=T,
            units="seconds",
            source_ref="Kepler's third law (Newton form)",
        )
        result.save()
        log.info("Orbital period: %.2f s (%.4f days)", T, T / 86400)
        return result

    # ── 12. Schwarzschild Radius ─────────────────────────────────────────
    def schwarzschild_radius(
        self, M: float = M_SUN
    ) -> PhysicsResult:
        """
        Event horizon radius for a non-rotating mass:
        r_s = 2 G M / c^2
        """
        r_s = 2 * G * M / c**2
        result = PhysicsResult(
            description=f"Schwarzschild radius (M={M:.3e} kg)",
            equation="r_s = 2 * G * M / c^2",
            value=r_s,
            units="metres",
            source_ref="Schwarzschild 1916; General Relativity",
        )
        result.save()
        log.info("Schwarzschild radius: %.4e m", r_s)
        return result

    # ── 13. Gravitational Redshift ───────────────────────────────────────
    def gravitational_redshift(
        self, M: float = M_EARTH, r: float = R_EARTH
    ) -> PhysicsResult:
        """
        Gravitational redshift (weak field approximation):
        z = G * M / (r * c^2)
        """
        z = G * M / (r * c**2)
        result = PhysicsResult(
            description=f"Gravitational redshift factor (M={M:.3e} kg, r={r:.3e} m)",
            equation="z = G * M / (r * c^2)",
            value=z,
            units="dimensionless",
            source_ref="General Relativity; Pound-Rebka 1959",
        )
        result.save()
        log.info("Gravitational redshift z: %.6e", z)
        return result

    # ── 14. Gravitational Potential Energy ───────────────────────────────
    def gravitational_potential_energy(
        self, M: float = M_EARTH, m: float = 1.0, r: float = R_EARTH
    ) -> PhysicsResult:
        """
        Gravitational PE between two masses:
        U = -G * M * m / r
        """
        U = -G * M * m / r
        result = PhysicsResult(
            description=f"Gravitational PE (M={M:.3e}, m={m:.3e} kg, r={r:.3e} m)",
            equation="U = -G * M * m / r",
            value=U,
            units="joules",
            source_ref="Newtonian gravitation",
        )
        result.save()
        log.info("Gravitational PE: %.6e J", U)
        return result

    # ── 15. Quadrupole GW Power Radiated ─────────────────────────────────
    def quadrupole_gw_power(
        self,
        m1_solar: float = 1.4,
        m2_solar: float = 1.4,
        separation_m: float = 2e7,
    ) -> PhysicsResult:
        """
        Gravitational wave luminosity from quadrupole formula:
        P = (32/5) * (G^4/c^5) * (m1*m2)^2 * (m1+m2) / a^5

        Default: neutron star binary at 20,000 km separation.
        """
        m1 = m1_solar * M_SUN
        m2 = m2_solar * M_SUN
        a = separation_m
        P = (32 / 5) * (G**4 / c**5) * (m1 * m2)**2 * (m1 + m2) / a**5
        result = PhysicsResult(
            description=f"Quadrupole GW power ({m1_solar}+{m2_solar} M_sun, a={separation_m:.1e} m)",
            equation="P = (32/5) * G^4 * (m1*m2)^2 * (m1+m2) / (c^5 * a^5)",
            value=P,
            units="watts",
            source_ref="Einstein 1918 quadrupole formula; Peters & Mathews 1963",
        )
        result.save()
        log.info("Quadrupole GW power: %.4e W", P)
        return result

    # ── 16. Friedmann Expansion Rate (Hubble Parameter) ──────────────────
    def friedmann_hubble(
        self,
        rho: float = 9.47e-27,  # critical density kg/m^3
        k: float = 0.0,         # curvature (flat)
        a: float = 1.0,         # scale factor (present)
    ) -> PhysicsResult:
        """
        Friedmann equation (matter-dominated, flat universe):
        H^2 = (8π G / 3) * ρ - k c^2 / a^2

        Default: present-epoch critical density, flat universe.
        Returns Hubble parameter H in s^-1.
        """
        H_sq = (8 * math.pi * G / 3) * rho - k * c**2 / a**2
        if H_sq < 0:
            H_sq = 0.0  # unphysical; just report zero
        H = math.sqrt(H_sq)
        # Convert to km/s/Mpc
        H_kms_Mpc = H * (1e6 * PC_TO_M) / 1000
        result = PhysicsResult(
            description=f"Friedmann-derived Hubble parameter (ρ={rho:.3e} kg/m^3)",
            equation="H = sqrt(8πG ρ / 3 - k c^2 / a^2)",
            value=H_kms_Mpc,
            units="km/s/Mpc",
            source_ref="Friedmann 1922; Planck 2018 cosmological parameters",
        )
        result.save()
        log.info("Hubble parameter: %.2f km/s/Mpc", H_kms_Mpc)
        return result

    # ── 17. MOND Interpolation (Milgrom) ─────────────────────────────────
    def mond_acceleration(
        self,
        g_newton: float = 1.2e-10,  # Newtonian accel at galaxy outskirts
        a0: float = 1.2e-10,        # MOND critical acceleration
    ) -> PhysicsResult:
        """
        MOND effective acceleration (simple interpolation):
        g_mond = g_N / (1 + a0/g_N)   [standard interpolation μ(x)=x/(1+x)]

        When g_N >> a0: g_mond ≈ g_N  (Newtonian regime)
        When g_N << a0: g_mond ≈ sqrt(g_N * a0)  (deep MOND)
        """
        g_mond = g_newton / (1 + a0 / g_newton) if g_newton > 0 else 0.0
        # Also compute deep-MOND limit
        g_deep = math.sqrt(g_newton * a0) if g_newton > 0 else 0.0
        result = PhysicsResult(
            description=f"MOND effective acceleration (g_N={g_newton:.2e}, a0={a0:.2e})",
            equation="g_mond = g_N / (1 + a0/g_N);  deep MOND: sqrt(g_N * a0)",
            value=g_mond,
            units="m/s^2",
            source_ref="Milgrom 1983; Modified Newtonian Dynamics",
        )
        result.save()
        log.info("MOND accel: %.4e m/s^2 (deep MOND: %.4e)", g_mond, g_deep)
        return result

    # ── 18. Lense-Thirring Frame Dragging ────────────────────────────────
    def lense_thirring_precession(
        self,
        J: float = 7.07e33,       # angular momentum of Earth [kg m^2/s]
        M: float = M_EARTH,
        r: float = R_EARTH + 642e3,  # LAGEOS orbit altitude
    ) -> PhysicsResult:
        """
        Lense-Thirring nodal precession rate:
        Ω_LT = 2 G J / (c^2 r^3)

        Default: LAGEOS satellite orbit.
        Returns precession in radians/second.
        """
        omega_lt = 2 * G * J / (c**2 * r**3)
        # Convert to milliarcseconds per year
        mas_per_year = omega_lt * (180 / math.pi) * 3600 * 1000 * (365.25 * 86400)
        result = PhysicsResult(
            description=f"Lense-Thirring precession (J={J:.2e}, r={r:.3e} m)",
            equation="Ω_LT = 2 G J / (c^2 r^3)",
            value=mas_per_year,
            units="milliarcseconds/year",
            source_ref="Lense & Thirring 1918; Ciufolini & Pavlis 2004 (LAGEOS)",
        )
        result.save()
        log.info("Lense-Thirring precession: %.2f mas/yr", mas_per_year)
        return result

    # ── 19. Planck Units ─────────────────────────────────────────────────
    def planck_units(self) -> list[PhysicsResult]:
        """
        Compute fundamental Planck units:
        - Planck length: l_P = sqrt(ℏ G / c^3)
        - Planck mass:   m_P = sqrt(ℏ c / G)
        - Planck time:   t_P = sqrt(ℏ G / c^5)
        - Planck energy: E_P = m_P * c^2
        """
        l_P = math.sqrt(hbar * G / c**3)
        m_P = math.sqrt(hbar * c / G)
        t_P = math.sqrt(hbar * G / c**5)
        E_P = m_P * c**2

        results = []
        for desc, eq, val, unit in [
            ("Planck length", "l_P = sqrt(ℏ G / c^3)", l_P, "metres"),
            ("Planck mass", "m_P = sqrt(ℏ c / G)", m_P, "kg"),
            ("Planck time", "t_P = sqrt(ℏ G / c^5)", t_P, "seconds"),
            ("Planck energy", "E_P = m_P * c^2", E_P, "joules"),
        ]:
            r = PhysicsResult(
                description=desc,
                equation=eq,
                value=val,
                units=unit,
                source_ref="Planck 1899; natural units of quantum gravity",
            )
            r.save()
            results.append(r)
            log.info("%s: %.6e %s", desc, val, unit)
        return results

    # ── 20. Gravitational Wave Frequency from Binary ─────────────────────
    def gw_frequency_from_binary(
        self,
        m1_solar: float = 1.4,
        m2_solar: float = 1.4,
        separation_m: float = 2e7,
    ) -> PhysicsResult:
        """
        GW frequency (twice the orbital frequency for quadrupole emission):
        f_gw = 2 * f_orb = (1/π) * sqrt(G (m1+m2) / a^3)
        """
        m1 = m1_solar * M_SUN
        m2 = m2_solar * M_SUN
        M_total = m1 + m2
        f_gw = (1 / math.pi) * math.sqrt(G * M_total / separation_m**3)
        result = PhysicsResult(
            description=f"GW frequency from binary ({m1_solar}+{m2_solar} M_sun, a={separation_m:.1e} m)",
            equation="f_gw = (1/π) sqrt(G(m1+m2) / a^3)",
            value=f_gw,
            units="Hz",
            source_ref="Keplerian binary; quadrupole GW emission",
        )
        result.save()
        log.info("GW frequency: %.6e Hz", f_gw)
        return result

    # ── 21. Gravitational Self-Energy Density ────────────────────────────
    def gravitational_self_energy_density(
        self, M: float = M_EARTH, R: float = R_EARTH
    ) -> PhysicsResult:
        """
        Average gravitational self-energy density of a uniform sphere:
        u = (3/5) * G M^2 / ((4/3) π R^3 * R)
          = (9 G M^2) / (20 π R^4)
        """
        u = (9 * G * M**2) / (20 * math.pi * R**4)
        result = PhysicsResult(
            description=f"Gravitational self-energy density (M={M:.3e}, R={R:.3e})",
            equation="u = 9 G M^2 / (20π R^4)",
            value=u,
            units="J/m^3",
            source_ref="Uniform sphere binding energy density",
        )
        result.save()
        log.info("Grav self-energy density: %.4e J/m^3", u)
        return result

    # ── 22. Roche Limit ──────────────────────────────────────────────────
    def roche_limit(
        self,
        M_primary: float = M_EARTH,
        R_secondary: float = 1.7374e6,  # Moon radius
        rho_primary: float = 5515.0,     # Earth mean density kg/m^3
        rho_secondary: float = 3344.0,   # Moon mean density
    ) -> PhysicsResult:
        """
        Rigid body Roche limit:
        d = R_secondary * (2 ρ_primary / ρ_secondary)^(1/3)
        """
        d = R_secondary * (2 * rho_primary / rho_secondary) ** (1 / 3)
        result = PhysicsResult(
            description=f"Roche limit for secondary (R={R_secondary:.3e} m)",
            equation="d = R_sec * (2 ρ_pri / ρ_sec)^(1/3)",
            value=d,
            units="metres",
            source_ref="Roche 1848; tidal disruption limit",
        )
        result.save()
        log.info("Roche limit: %.4e m (%.2f Earth radii)", d, d / R_EARTH)
        return result

    # ── Run Full Comparison Suite ────────────────────────────────────────
    def run_full_comparison(self) -> list[dict[str, Any]]:
        """Execute all physics computations and return results."""
        computations = [
            # Original 7
            self.gravitational_binding_energy,
            self.energy_to_nullify_gravity,
            lambda: self.gravitational_wave_strain(),
            lambda: self.tidal_acceleration_from_gw(),
            lambda: self.ratio_gw_to_surface_gravity(),
            lambda: self.required_distance_for_cancellation(),
            lambda: self.merger_energy_output(),
            # Extended catalog (8-22)
            lambda: self.gravitational_field_strength(),
            lambda: self.orbital_velocity(),
            lambda: self.escape_velocity(),
            lambda: self.kepler_third_law(),
            lambda: self.schwarzschild_radius(),
            lambda: self.gravitational_redshift(),
            lambda: self.gravitational_potential_energy(),
            lambda: self.quadrupole_gw_power(),
            lambda: self.friedmann_hubble(),
            lambda: self.mond_acceleration(),
            lambda: self.lense_thirring_precession(),
            lambda: self.gw_frequency_from_binary(),
            lambda: self.gravitational_self_energy_density(),
            lambda: self.roche_limit(),
        ]
        results = []
        for fn in computations:
            try:
                r = fn()
                # planck_units returns a list
                if isinstance(r, list):
                    results.extend(asdict(item) for item in r)
                else:
                    results.append(asdict(r))
            except Exception as exc:
                log.error("Physics computation failed: %s", exc)

        # Run Planck units separately (returns list)
        try:
            planck = self.planck_units()
            results.extend(asdict(p) for p in planck)
        except Exception as exc:
            log.error("Planck units computation failed: %s", exc)

        log.info("Physics comparison suite complete: %d results", len(results))
        return results
