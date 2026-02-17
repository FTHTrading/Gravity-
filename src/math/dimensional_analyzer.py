"""
Dimensional Analyzer – SI Unit Consistency Validation

Provides:
  - Dimensional analysis of symbolic expressions
  - Unit mismatch detection
  - Missing constant detection
  - Non-physical expression flagging
  - SI base dimension tracking (M, L, T, Θ, I, N, J)
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from src.logger import get_logger

log = get_logger(__name__)


# ── SI Base Dimensions ───────────────────────────────────────────────────────
# Represented as tuples: (M, L, T, Θ, I, N, J)
# Mass, Length, Time, Temperature, Current, Amount, Luminosity

@dataclass(frozen=True)
class Dimension:
    """SI base dimension vector."""
    M: float = 0  # mass (kg)
    L: float = 0  # length (m)
    T: float = 0  # time (s)
    Theta: float = 0  # temperature (K)
    I: float = 0  # current (A)
    N: float = 0  # amount (mol)
    J: float = 0  # luminosity (cd)

    def __mul__(self, other: "Dimension") -> "Dimension":
        return Dimension(
            M=self.M + other.M, L=self.L + other.L, T=self.T + other.T,
            Theta=self.Theta + other.Theta, I=self.I + other.I,
            N=self.N + other.N, J=self.J + other.J,
        )

    def __truediv__(self, other: "Dimension") -> "Dimension":
        return Dimension(
            M=self.M - other.M, L=self.L - other.L, T=self.T - other.T,
            Theta=self.Theta - other.Theta, I=self.I - other.I,
            N=self.N - other.N, J=self.J - other.J,
        )

    def __pow__(self, exp: float) -> "Dimension":
        return Dimension(
            M=self.M * exp, L=self.L * exp, T=self.T * exp,
            Theta=self.Theta * exp, I=self.I * exp,
            N=self.N * exp, J=self.J * exp,
        )

    def is_dimensionless(self) -> bool:
        return all(v == 0 for v in (self.M, self.L, self.T,
                                     self.Theta, self.I, self.N, self.J))

    def to_str(self) -> str:
        parts = []
        labels = [("M", self.M), ("L", self.L), ("T", self.T),
                  ("Θ", self.Theta), ("I", self.I), ("N", self.N), ("J", self.J)]
        for label, val in labels:
            if val != 0:
                if val == 1:
                    parts.append(label)
                else:
                    parts.append(f"{label}^{val:g}")
        return " ".join(parts) if parts else "dimensionless"

    def to_tuple(self) -> tuple:
        return (self.M, self.L, self.T, self.Theta, self.I, self.N, self.J)


# ── Known Dimension Maps ────────────────────────────────────────────────────
DIMENSIONLESS = Dimension()

# Base quantities
DIM_MASS = Dimension(M=1)
DIM_LENGTH = Dimension(L=1)
DIM_TIME = Dimension(T=1)
DIM_TEMP = Dimension(Theta=1)
DIM_CURRENT = Dimension(I=1)

# Derived quantities
DIM_VELOCITY = Dimension(L=1, T=-1)
DIM_ACCELERATION = Dimension(L=1, T=-2)
DIM_FORCE = Dimension(M=1, L=1, T=-2)
DIM_ENERGY = Dimension(M=1, L=2, T=-2)
DIM_POWER = Dimension(M=1, L=2, T=-3)
DIM_PRESSURE = Dimension(M=1, L=-1, T=-2)
DIM_FREQUENCY = Dimension(T=-1)
DIM_MOMENTUM = Dimension(M=1, L=1, T=-1)
DIM_ANGULAR_MOMENTUM = Dimension(M=1, L=2, T=-1)
DIM_CHARGE = Dimension(I=1, T=1)

# Physical constants dimensions
SYMBOL_DIMENSIONS = {
    # Constants
    "G": Dimension(M=-1, L=3, T=-2),       # m³ kg⁻¹ s⁻²
    "c": DIM_VELOCITY,                      # m s⁻¹
    "h": Dimension(M=1, L=2, T=-1),        # J·s = kg m² s⁻¹
    "hbar": Dimension(M=1, L=2, T=-1),     # J·s
    "k_B": Dimension(M=1, L=2, T=-2, Theta=-1),  # J K⁻¹
    "e_charge": DIM_CHARGE,                 # C = A·s
    "m_e": DIM_MASS,
    "m_p": DIM_MASS,
    "epsilon_0": Dimension(M=-1, L=-3, T=4, I=2),  # F/m
    "mu_0": Dimension(M=1, L=1, T=-2, I=-2),       # H/m
    "g_surface": DIM_ACCELERATION,

    # Common physics variables
    "m": DIM_MASS,
    "M": DIM_MASS,
    "r": DIM_LENGTH,
    "R": DIM_LENGTH,
    "d": DIM_LENGTH,
    "x": DIM_LENGTH,
    "y": DIM_LENGTH,
    "z": DIM_LENGTH,
    "t": DIM_TIME,
    "v": DIM_VELOCITY,
    "a": DIM_ACCELERATION,
    "F": DIM_FORCE,
    "E": DIM_ENERGY,
    "T": DIM_TIME,
    "P": DIM_POWER,
    "V": Dimension(M=1, L=2, T=-3, I=-1),  # voltage
    "omega": DIM_FREQUENCY,
    "nu": DIM_FREQUENCY,
    "rho": Dimension(M=1, L=-3),            # density
    "sigma": DIM_PRESSURE,                   # stress
    "L": DIM_ANGULAR_MOMENTUM,
}

# Named unit dimensions
NAMED_DIMENSIONS = {
    "joule": DIM_ENERGY, "J": DIM_ENERGY,
    "newton": DIM_FORCE, "N": DIM_FORCE,
    "watt": DIM_POWER, "W": DIM_POWER,
    "pascal": DIM_PRESSURE, "Pa": DIM_PRESSURE,
    "hertz": DIM_FREQUENCY, "Hz": DIM_FREQUENCY,
    "meter": DIM_LENGTH, "m": DIM_LENGTH,
    "kilogram": DIM_MASS, "kg": DIM_MASS,
    "second": DIM_TIME, "s": DIM_TIME,
    "kelvin": DIM_TEMP, "K": DIM_TEMP,
    "ampere": DIM_CURRENT, "A": DIM_CURRENT,
}


@dataclass
class DimensionalReport:
    """Result of dimensional analysis."""
    equation_name: str
    status: str = "unknown"  # valid, invalid, partial, unknown
    lhs_dimension: str = ""
    rhs_dimension: str = ""
    dimensions_match: bool = False
    missing_dimensions: list = field(default_factory=list)
    unknown_symbols: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "equation_name": self.equation_name,
            "status": self.status,
            "lhs_dimension": self.lhs_dimension,
            "rhs_dimension": self.rhs_dimension,
            "dimensions_match": self.dimensions_match,
            "missing_dimensions": self.missing_dimensions,
            "unknown_symbols": self.unknown_symbols,
            "warnings": self.warnings,
            "errors": self.errors,
        }


class DimensionalAnalyzer:
    """
    Validates dimensional consistency of equations.

    Uses a registry of known symbol dimensions to track
    SI base dimensions through algebraic expressions.
    """

    def __init__(self, custom_dimensions: Optional[dict] = None):
        self.dimensions = dict(SYMBOL_DIMENSIONS)
        if custom_dimensions:
            for sym, dim in custom_dimensions.items():
                self.dimensions[sym] = dim

    def register_symbol(self, symbol_name: str, dimension: Dimension):
        """Register a new symbol with its dimension."""
        self.dimensions[symbol_name] = dimension

    def analyze(
        self,
        parsed_eq,
        dimension_hints: Optional[dict] = None,
    ) -> DimensionalReport:
        """
        Analyze an equation for dimensional consistency.

        Args:
            parsed_eq: ParsedEquation from equation_parser
            dimension_hints: Optional dict mapping symbol names to Dimension objects

        Returns:
            DimensionalReport
        """
        report = DimensionalReport(equation_name=parsed_eq.name)

        if dimension_hints:
            for sym, dim in dimension_hints.items():
                self.dimensions[sym] = dim

        # Identify unknown symbols
        for sym_name in parsed_eq.symbols_found:
            if sym_name not in self.dimensions:
                report.unknown_symbols.append(sym_name)
                report.warnings.append(
                    f"Symbol '{sym_name}' has no registered dimension"
                )

        if parsed_eq.is_equation and parsed_eq.lhs and parsed_eq.rhs:
            # Analyze both sides
            lhs_dim = self._infer_dimension(parsed_eq.lhs, report)
            rhs_dim = self._infer_dimension(parsed_eq.rhs, report)

            if lhs_dim and rhs_dim:
                report.lhs_dimension = lhs_dim.to_str()
                report.rhs_dimension = rhs_dim.to_str()
                report.dimensions_match = (lhs_dim.to_tuple() == rhs_dim.to_tuple())

                if report.dimensions_match:
                    report.status = "valid"
                    log.info("Dimensional analysis '%s': VALID (%s = %s)",
                             parsed_eq.name, report.lhs_dimension, report.rhs_dimension)
                else:
                    report.status = "invalid"
                    report.errors.append(
                        f"Dimension mismatch: LHS={report.lhs_dimension} "
                        f"≠ RHS={report.rhs_dimension}"
                    )
                    log.warning("Dimensional analysis '%s': MISMATCH", parsed_eq.name)
            else:
                report.status = "partial"
                if lhs_dim:
                    report.lhs_dimension = lhs_dim.to_str()
                if rhs_dim:
                    report.rhs_dimension = rhs_dim.to_str()
        else:
            # Expression only — just report its dimension
            expr = parsed_eq.sympy_expr
            dim = self._infer_dimension(expr, report)
            if dim:
                report.rhs_dimension = dim.to_str()
                report.status = "valid"
            else:
                report.status = "partial"

        if report.unknown_symbols:
            report.missing_dimensions = report.unknown_symbols[:]

        return report

    def _infer_dimension(self, expr, report: DimensionalReport) -> Optional[Dimension]:
        """
        Recursively infer the dimension of a SymPy expression.

        Returns Dimension or None if unable to determine.
        """
        import sympy

        if expr is None:
            return None

        # Numeric constant → dimensionless
        if expr.is_number:
            return DIMENSIONLESS

        # Symbol → look up dimension
        if isinstance(expr, sympy.Symbol):
            name = str(expr)
            if name in self.dimensions:
                return self.dimensions[name]
            return None  # Unknown

        # Addition/Subtraction: all terms must have same dimension
        if isinstance(expr, sympy.Add):
            dims = []
            for arg in expr.args:
                d = self._infer_dimension(arg, report)
                if d is not None:
                    dims.append(d)
            if not dims:
                return None
            # Check all same
            ref = dims[0]
            for d in dims[1:]:
                if d.to_tuple() != ref.to_tuple():
                    report.errors.append(
                        f"Addition of incompatible dimensions: "
                        f"{ref.to_str()} + {d.to_str()}"
                    )
                    return ref  # Return first but flag error
            return ref

        # Multiplication
        if isinstance(expr, sympy.Mul):
            result = DIMENSIONLESS
            for arg in expr.args:
                d = self._infer_dimension(arg, report)
                if d is not None:
                    result = result * d
                elif not arg.is_number:
                    return None  # Can't determine
            return result

        # Power
        if isinstance(expr, sympy.Pow):
            base, exp = expr.args
            base_dim = self._infer_dimension(base, report)
            if base_dim is None:
                return None
            if exp.is_number:
                return base_dim ** float(exp)
            else:
                # Non-numeric exponent: base must be dimensionless
                if not base_dim.is_dimensionless():
                    report.errors.append(
                        f"Non-numeric exponent on dimensioned quantity: "
                        f"({base_dim.to_str()})^({exp})"
                    )
                return DIMENSIONLESS

        # Function calls (sin, cos, exp, log) → dimensionless out, require dimensionless in
        if isinstance(expr, sympy.Function):
            func_name = type(expr).__name__
            for arg in expr.args:
                arg_dim = self._infer_dimension(arg, report)
                if arg_dim and not arg_dim.is_dimensionless():
                    report.warnings.append(
                        f"Function {func_name}() applied to dimensioned argument: "
                        f"{arg_dim.to_str()}"
                    )
            return DIMENSIONLESS

        # Derivative
        if isinstance(expr, sympy.Derivative):
            # d(f)/dx has dimension [f]/[x]
            func_expr = expr.args[0]
            func_dim = self._infer_dimension(func_expr, report)
            if func_dim is None:
                return None
            result = func_dim
            for var_tuple in expr.args[1:]:
                var = var_tuple[0] if isinstance(var_tuple, tuple) else var_tuple
                order = var_tuple[1] if isinstance(var_tuple, tuple) and len(var_tuple) > 1 else 1
                var_dim = self._infer_dimension(var, report)
                if var_dim:
                    result = result / (var_dim ** order)
            return result

        # Integral — too complex for general case, return None
        if isinstance(expr, sympy.Integral):
            report.warnings.append("Integral dimensional analysis not fully supported")
            return None

        # Default: try to recurse
        return None

    def check_known_equation(self, name: str) -> Optional[DimensionalReport]:
        """
        Run dimensional analysis on a well-known equation.

        Args:
            name: One of 'newton_gravity', 'einstein_energy', 'coulomb',
                  'schrodinger', 'friedmann', 'gravitational_wave_power'
        """
        from src.math.equation_parser import EquationParser
        parser = EquationParser()

        known_equations = {
            "newton_gravity": ("F = G*M*m/r**2", "Newton's Law of Gravitation"),
            "einstein_energy": ("E = m*c**2", "Einstein Mass-Energy Equivalence"),
            "coulomb": ("F = e_charge**2/(4*pi*epsilon_0*r**2)", "Coulomb's Law"),
            "gravitational_pe": ("E = -G*M*m/r", "Gravitational Potential Energy"),
            "kinetic_energy": ("E = m*v**2/2", "Kinetic Energy"),
            "escape_velocity": ("v = (2*G*M/r)**(1/2)", "Escape Velocity"),
        }

        if name not in known_equations:
            return None

        text, desc = known_equations[name]
        parsed = parser.parse_plaintext(text, name=desc)
        return self.analyze(parsed)
