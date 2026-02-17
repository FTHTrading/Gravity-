"""
Comprehensive Taxonomy & Knowledge Base for Project Anchor.

Structured reference covering:
  - Anti-gravity device categories (real, experimental, speculative)
  - Core gravitational physics terminology
  - Wave science terminology
  - Advanced propulsion concepts
  - Gravity stabilizer terminology
  - Measurement & experimental terms
  - Research source databases

Each entry stores: term, definition, category, subcategory,
verification_status (verified | theoretical | speculative | debunked),
and related_terms.

The taxonomy is used by:
  - Search modules: rotating through all variant terms
  - NLP module: detecting when collected text references these concepts
  - Dashboard: displaying the full concept map
  - IPFS: pinning the taxonomy as a reference artifact
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional
import json

from src.database import insert_row, query_rows
from src.logger import get_logger

log = get_logger(__name__)


@dataclass
class TaxonomyEntry:
    term: str
    definition: str
    category: str
    subcategory: str
    verification_status: str  # verified | theoretical | speculative | debunked | informal
    related_terms: list[str] = field(default_factory=list)
    search_keywords: list[str] = field(default_factory=list)
    source_ref: str = ""

    def save(self) -> int:
        return insert_row("taxonomy_entries", {
            "term": self.term,
            "definition": self.definition,
            "category": self.category,
            "subcategory": self.subcategory,
            "verification_status": self.verification_status,
            "related_terms_json": json.dumps(self.related_terms),
            "search_keywords_json": json.dumps(self.search_keywords),
            "source_ref": self.source_ref,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })


# ═══════════════════════════════════════════════════════════════════════════
# A) REAL DEVICES LABELED "ANTI-GRAVITY"
# ═══════════════════════════════════════════════════════════════════════════

REAL_DEVICES = [
    TaxonomyEntry(
        term="Ionocraft / Lifter / EHD Thruster",
        definition="High-voltage device creating thrust in air via electrohydrodynamic effects. Often mislabeled as anti-gravity online.",
        category="real_device",
        subcategory="electrohydrodynamic",
        verification_status="verified",
        related_terms=["Biefeld-Brown effect", "electrogravitics", "ionic wind", "corona discharge"],
        search_keywords=["ionocraft", "lifter", "EHD thruster", "EHD propulsion", "ionic wind", "corona wind thrust"],
        source_ref="https://en.wikipedia.org/wiki/Biefeld%E2%80%93Brown_effect",
    ),
    TaxonomyEntry(
        term="Magnetic Levitation (Maglev)",
        definition="Levitation by magnetic forces. Includes maglev trains, superconductor quantum locking demos. Not gravity removal.",
        category="real_device",
        subcategory="magnetic",
        verification_status="verified",
        related_terms=["superconductor", "Meissner effect", "flux pinning", "electromagnetic suspension"],
        search_keywords=["maglev", "magnetic levitation", "quantum locking", "superconducting levitation"],
    ),
    TaxonomyEntry(
        term="Acoustic Levitation",
        definition="Ultrasound standing waves suspend small objects. Used in laboratory and industrial demos.",
        category="real_device",
        subcategory="acoustic",
        verification_status="verified",
        related_terms=["standing wave", "ultrasound", "acoustic radiation pressure"],
        search_keywords=["acoustic levitation", "ultrasonic levitation", "sound levitation"],
    ),
    TaxonomyEntry(
        term="Optical Levitation",
        definition="Laser trapping (optical tweezers) suspending microscopic particles.",
        category="real_device",
        subcategory="optical",
        verification_status="verified",
        related_terms=["optical tweezers", "radiation pressure", "laser trapping"],
        search_keywords=["optical levitation", "optical tweezers", "laser trapping"],
    ),
    TaxonomyEntry(
        term="Buoyancy / Neutral Buoyancy",
        definition="Airships, underwater training tanks, weightlessness rigs. Apparent weightlessness via buoyant forces.",
        category="real_device",
        subcategory="buoyancy",
        verification_status="verified",
        related_terms=["neutral buoyancy", "Archimedes principle"],
        search_keywords=["neutral buoyancy", "buoyancy weightlessness"],
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# B) EXPERIMENTAL / CONTROVERSIAL CLAIMS
# ═══════════════════════════════════════════════════════════════════════════

EXPERIMENTAL_CLAIMS = [
    TaxonomyEntry(
        term="Biefeld-Brown Effect / Electrogravitics",
        definition="Historically framed as gravity interaction. Later lab work attributes thrust to ion wind/corona effects. Modern high-precision testing has null results for EM-gravity coupling.",
        category="experimental_claim",
        subcategory="electrogravitic",
        verification_status="debunked",
        related_terms=["asymmetric capacitor thruster", "corona discharge", "dielectric thrust", "EHD propulsion"],
        search_keywords=["electrogravitics", "Biefeld-Brown effect", "asymmetric capacitor thruster", "dielectric thrust"],
        source_ref="https://en.wikipedia.org/wiki/Biefeld%E2%80%93Brown_effect",
    ),
    TaxonomyEntry(
        term="Rotating Superconductor Gravity Shielding (Podkletnov)",
        definition="Claimed weight reduction above spinning superconductors. Widely debated; replication status contested.",
        category="experimental_claim",
        subcategory="superconductor_rotation",
        verification_status="speculative",
        related_terms=["Podkletnov effect", "gravitational shielding", "rotating superconductor"],
        search_keywords=["Podkletnov effect", "rotating superconductor", "gravity shielding", "superconducting disk", "gravity anomaly"],
    ),
    TaxonomyEntry(
        term="Alzofon-style Weight Reduction",
        definition="Shows up in propulsion-adjacent literature and follow-up measurement studies. Referenced in Tajmar 2024 paper.",
        category="experimental_claim",
        subcategory="weight_reduction",
        verification_status="speculative",
        related_terms=["inertial mass modification", "mass reduction"],
        search_keywords=["Alzofon", "weight reduction experiment", "mass reduction"],
        source_ref="https://www.nature.com/articles/s41598-024-70286-w",
    ),
    TaxonomyEntry(
        term="High-Precision Reactionless Drive Test Programs",
        definition="Real subfield building precision balances to test anomalous thrust claims, isolating thermal drift, EM coupling, outgassing artifacts.",
        category="experimental_claim",
        subcategory="thrust_testing",
        verification_status="verified",
        related_terms=["thrust balance", "null test", "systematic error", "Tajmar group"],
        search_keywords=["reactionless drive test", "thrust balance", "anomalous thrust", "EM gravity coupling"],
        source_ref="https://www.nature.com/articles/s41598-024-70286-w",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# C) SPECULATIVE PROPULSION CONCEPTS
# ═══════════════════════════════════════════════════════════════════════════

SPECULATIVE_PROPULSION = [
    TaxonomyEntry(
        term="Mach Effect Thruster (MEGA drive)",
        definition="NASA NIAC-funded study line around Mach-effect concepts for advanced propulsion.",
        category="speculative_propulsion",
        subcategory="mach_effect",
        verification_status="speculative",
        related_terms=["Mach's principle", "transient mass fluctuation", "NIAC"],
        search_keywords=["Mach effect thruster", "MEGA drive", "Mach effect propulsion", "NIAC advanced propulsion"],
        source_ref="https://www.nasa.gov/general/mach-effect-for-in-space-propulsion-interstellar-mission/",
    ),
    TaxonomyEntry(
        term="EMDrive",
        definition="Propellantless microwave cavity thruster claim. Subsequent high-accuracy tests focus on measurement artifacts.",
        category="speculative_propulsion",
        subcategory="microwave_cavity",
        verification_status="debunked",
        related_terms=["reactionless drive", "microwave cavity", "propellantless thruster"],
        search_keywords=["EMDrive", "EM Drive", "microwave cavity thruster", "propellantless thruster"],
        source_ref="https://www.nature.com/articles/s41598-024-70286-w",
    ),
    TaxonomyEntry(
        term="Warp Drive / Alcubierre Metric",
        definition="Metric engineering concept for faster-than-light travel via spacetime distortion. Requires exotic matter.",
        category="speculative_propulsion",
        subcategory="warp_drive",
        verification_status="theoretical",
        related_terms=["Alcubierre metric", "metric engineering", "exotic matter", "negative energy density"],
        search_keywords=["warp drive", "Alcubierre metric", "metric engineering", "spacetime engineering", "IXS Enterprise"],
        source_ref="https://en.wikipedia.org/wiki/IXS_Enterprise",
    ),
    TaxonomyEntry(
        term="Quantum Vacuum / Casimir Thruster",
        definition="Proposed propulsion tapping vacuum structure. Discussed in advanced propulsion circles.",
        category="speculative_propulsion",
        subcategory="vacuum_energy",
        verification_status="speculative",
        related_terms=["Casimir effect", "vacuum energy", "zero-point energy", "quantum vacuum thruster"],
        search_keywords=["quantum vacuum thruster", "Casimir propulsion", "vacuum energy propulsion", "zero-point energy"],
        source_ref="https://www.wired.com/story/nasas-emdrive-leader-has-a-new-interstellar-project",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# D) AUG 12 RUMOR CLUSTER
# ═══════════════════════════════════════════════════════════════════════════

RUMOR_CLUSTER = [
    TaxonomyEntry(
        term="Aug 12 Weightless / Project Anchor Rumor",
        definition="Internet narrative about Earth losing gravity for seconds, tied to supposed Project Anchor document and black holes. Fact-checked and described as false.",
        category="rumor_cluster",
        subcategory="viral_hoax",
        verification_status="debunked",
        related_terms=["Project Anchor", "Thomas Webb", "gravity cancellation", "Aug 12 gravity"],
        search_keywords=["Project Anchor", "Aug 12 gravity", "August 12 gravity off", "Earth weightless August",
                         "Thomas Webb NASA", "gravity off 2026", "gravity cancellation black hole"],
        source_ref="https://www.yahoo.com/news/articles/fact-check-posts-citing-nasa-110000505.html",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════
# CORE GRAVITATIONAL PHYSICS TERMS
# ═══════════════════════════════════════════════════════════════════════════

GRAVITY_PHYSICS = [
    TaxonomyEntry("Gravity", "Fundamental interaction causing mutual attraction between masses.", "physics", "core_gravity", "verified"),
    TaxonomyEntry("Gravitational Field", "Vector field describing gravitational force per unit mass at each point in space.", "physics", "core_gravity", "verified"),
    TaxonomyEntry("Gravitational Potential", "Scalar quantity representing potential energy per unit mass in a gravitational field.", "physics", "core_gravity", "verified"),
    TaxonomyEntry("Gravitational Acceleration (g)", "Acceleration due to gravity at a given location.", "physics", "core_gravity", "verified"),
    TaxonomyEntry("Newtonian Gravity", "Classical inverse-square law of gravitation.", "physics", "core_gravity", "verified"),
    TaxonomyEntry("General Relativity (GR)", "Einstein's theory describing gravity as curvature of spacetime.", "physics", "core_gravity", "verified"),
    TaxonomyEntry("Spacetime Curvature", "Geometric deformation caused by mass-energy.", "physics", "core_gravity", "verified"),
    TaxonomyEntry("Metric Tensor", "Mathematical object describing spacetime geometry.", "physics", "core_gravity", "verified"),
    TaxonomyEntry("Geodesic", "Path of least action in curved spacetime.", "physics", "core_gravity", "verified"),
    TaxonomyEntry("Gravitational Constant (G)", "Universal constant governing gravitational strength.", "physics", "core_gravity", "verified"),
    TaxonomyEntry("Equivalence Principle", "Principle stating gravitational and inertial mass are equivalent.", "physics", "core_gravity", "verified"),
    TaxonomyEntry("Inertial Mass", "Resistance of an object to acceleration.", "physics", "core_gravity", "verified"),
    TaxonomyEntry("Gravitational Mass", "Mass that determines gravitational attraction.", "physics", "core_gravity", "verified"),
    TaxonomyEntry("Weak Field Approximation", "GR approximation used for small curvature.", "physics", "core_gravity", "verified"),
    TaxonomyEntry("Post-Newtonian Expansion", "Correction framework extending Newtonian gravity.", "physics", "core_gravity", "verified"),
]

GW_RELATIVISTIC = [
    TaxonomyEntry("Gravitational Waves", "Ripples in spacetime produced by accelerating masses.", "physics", "gw_relativistic", "verified"),
    TaxonomyEntry("Strain Amplitude", "Dimensionless measure of gravitational wave distortion.", "physics", "gw_relativistic", "verified"),
    TaxonomyEntry("Binary Black Hole Merger", "Collision event producing gravitational waves.", "physics", "gw_relativistic", "verified"),
    TaxonomyEntry("Frame Dragging", "Spacetime distortion caused by rotating mass.", "physics", "gw_relativistic", "verified"),
    TaxonomyEntry("Lense-Thirring Effect", "Rotational frame-dragging phenomenon.", "physics", "gw_relativistic", "verified"),
    TaxonomyEntry("Gravitomagnetism", "Formal analogy between gravity and magnetism in weak-field GR.", "physics", "gw_relativistic", "verified"),
    TaxonomyEntry("Event Horizon", "Boundary beyond which nothing escapes a black hole.", "physics", "gw_relativistic", "verified"),
    TaxonomyEntry("Singularity", "Region of infinite curvature in spacetime models.", "physics", "gw_relativistic", "verified"),
]

INERTIA_MASS = [
    TaxonomyEntry("Inertia", "Resistance of an object to changes in motion.", "physics", "inertia_mass", "verified"),
    TaxonomyEntry("Mach's Principle", "Hypothesis that inertia arises from interaction with distant mass.", "physics", "inertia_mass", "theoretical"),
    TaxonomyEntry("Inertial Frame", "Reference frame not undergoing acceleration.", "physics", "inertia_mass", "verified"),
    TaxonomyEntry("Inertial Mass Modification", "Hypothetical alteration of inertial mass.", "physics", "inertia_mass", "speculative"),
    TaxonomyEntry("Mass-Energy Equivalence (E=mc²)", "Relationship between mass and energy.", "physics", "inertia_mass", "verified"),
    TaxonomyEntry("Binding Energy", "Energy required to disassemble a system.", "physics", "inertia_mass", "verified"),
    TaxonomyEntry("Gravitational Binding Energy", "Energy required to disperse a gravitationally bound body.", "physics", "inertia_mass", "verified"),
]

EM_GRAVITY_COUPLING = [
    TaxonomyEntry("Electrogravitics", "Proposed coupling between electric fields and gravity.", "physics", "em_gravity", "speculative"),
    TaxonomyEntry("Biefeld-Brown Effect", "Observed thrust in asymmetric capacitors under high voltage.", "physics", "em_gravity", "debunked"),
    TaxonomyEntry("Electrohydrodynamic (EHD) Propulsion", "Ion wind thrust from electric fields.", "physics", "em_gravity", "verified"),
    TaxonomyEntry("Asymmetric Capacitor Thruster", "Device producing thrust via high-voltage field asymmetry.", "physics", "em_gravity", "verified"),
    TaxonomyEntry("Corona Discharge", "Ionization of air near high-voltage electrodes.", "physics", "em_gravity", "verified"),
    TaxonomyEntry("Ionic Wind", "Air movement caused by ion acceleration.", "physics", "em_gravity", "verified"),
    TaxonomyEntry("Dielectric Polarization", "Electric field alignment in insulating material.", "physics", "em_gravity", "verified"),
    TaxonomyEntry("Field Coupling", "Interaction between physical force fields.", "physics", "em_gravity", "verified"),
]

SUPERCONDUCTOR_TERMS = [
    TaxonomyEntry("Superconductivity", "Zero electrical resistance state below critical temperature.", "physics", "superconductor", "verified"),
    TaxonomyEntry("Meissner Effect", "Magnetic field expulsion from superconductors.", "physics", "superconductor", "verified"),
    TaxonomyEntry("Flux Pinning", "Stabilization of magnetic field lines in superconductors.", "physics", "superconductor", "verified"),
    TaxonomyEntry("Rotating Superconductor Effect", "Claimed gravity anomaly in spinning superconductors.", "physics", "superconductor", "speculative"),
    TaxonomyEntry("Gravitational Shielding", "Hypothetical blocking or reduction of gravity.", "physics", "superconductor", "speculative"),
]

ADVANCED_PROPULSION = [
    TaxonomyEntry("Reactionless Drive", "Device claiming thrust without expelled mass.", "propulsion", "advanced", "speculative"),
    TaxonomyEntry("Propellantless Propulsion", "Thrust without reaction mass.", "propulsion", "advanced", "speculative"),
    TaxonomyEntry("Field Propulsion", "Motion via manipulation of force fields.", "propulsion", "advanced", "speculative"),
    TaxonomyEntry("Mach Effect Thruster (MET)", "Device based on transient mass fluctuation theory.", "propulsion", "advanced", "speculative"),
    TaxonomyEntry("EMDrive", "Microwave cavity thruster concept.", "propulsion", "advanced", "debunked"),
    TaxonomyEntry("Quantum Vacuum Thruster", "Propulsion based on vacuum fluctuations.", "propulsion", "advanced", "speculative"),
    TaxonomyEntry("Casimir Effect", "Force between plates due to quantum vacuum fluctuations.", "propulsion", "advanced", "verified"),
    TaxonomyEntry("Vacuum Energy", "Zero-point energy in quantum field theory.", "propulsion", "advanced", "verified"),
    TaxonomyEntry("Zero-Point Energy (ZPE)", "Ground state energy of quantum fields.", "propulsion", "advanced", "verified"),
]

SPACETIME_ENGINEERING = [
    TaxonomyEntry("Metric Engineering", "Alteration of spacetime geometry.", "propulsion", "spacetime", "theoretical"),
    TaxonomyEntry("Warp Drive", "Hypothetical faster-than-light metric distortion.", "propulsion", "spacetime", "theoretical"),
    TaxonomyEntry("Alcubierre Metric", "Proposed spacetime bubble model.", "propulsion", "spacetime", "theoretical"),
    TaxonomyEntry("Negative Energy Density", "Hypothetical exotic matter condition.", "propulsion", "spacetime", "theoretical"),
    TaxonomyEntry("Exotic Matter", "Matter with negative mass or energy density.", "propulsion", "spacetime", "theoretical"),
    TaxonomyEntry("Closed Timelike Curve", "Spacetime path enabling theoretical time loops.", "propulsion", "spacetime", "theoretical"),
]

MEASUREMENT_TERMS = [
    TaxonomyEntry("Torsion Balance", "Instrument measuring weak forces.", "measurement", "instruments", "verified"),
    TaxonomyEntry("Thrust Balance", "Device measuring micro-thrust forces.", "measurement", "instruments", "verified"),
    TaxonomyEntry("Null Test", "Experiment designed to detect absence of effect.", "measurement", "methodology", "verified"),
    TaxonomyEntry("Signal-to-Noise Ratio", "Measurement quality metric.", "measurement", "methodology", "verified"),
    TaxonomyEntry("Thermal Drift", "Measurement deviation due to heat.", "measurement", "artifacts", "verified"),
    TaxonomyEntry("Electromagnetic Interference (EMI)", "Unwanted EM coupling.", "measurement", "artifacts", "verified"),
    TaxonomyEntry("Systematic Error", "Repeatable experimental bias.", "measurement", "artifacts", "verified"),
]

COSMOLOGY_TERMS = [
    TaxonomyEntry("Dark Matter", "Hypothetical mass explaining gravitational anomalies.", "cosmology", "large_scale", "theoretical"),
    TaxonomyEntry("Dark Energy", "Energy causing accelerated expansion of universe.", "cosmology", "large_scale", "theoretical"),
    TaxonomyEntry("Cosmological Constant", "Vacuum energy term in Einstein equations.", "cosmology", "large_scale", "verified"),
    TaxonomyEntry("Modified Newtonian Dynamics (MOND)", "Alternative gravity model.", "cosmology", "large_scale", "theoretical"),
    TaxonomyEntry("Scalar-Tensor Theories", "Gravity models extending GR.", "cosmology", "large_scale", "theoretical"),
    TaxonomyEntry("Brane Cosmology", "Higher-dimensional gravity theory.", "cosmology", "large_scale", "theoretical"),
]

INFORMAL_TERMS = [
    TaxonomyEntry("Anti-Gravity", "Informal term implying gravity cancellation.", "informal", "popular", "informal"),
    TaxonomyEntry("Gravity Cancellation", "Hypothetical elimination of gravitational force.", "informal", "popular", "informal"),
    TaxonomyEntry("Weightlessness", "Condition of free fall, not absence of gravity.", "informal", "popular", "verified"),
    TaxonomyEntry("Mass Reduction", "Hypothetical lowering of gravitational mass.", "informal", "popular", "speculative"),
    TaxonomyEntry("Gravity Anomaly", "Measured deviation in local gravitational field.", "informal", "popular", "verified"),
    TaxonomyEntry("Gravitational Suppression", "Hypothetical reduction of gravity.", "informal", "popular", "speculative"),
    TaxonomyEntry("Gravitational Modulation", "Hypothetical oscillation of gravity strength.", "informal", "popular", "speculative"),
]

# ═══════════════════════════════════════════════════════════════════════════
# GRAVITY STABILIZER TERMS
# ═══════════════════════════════════════════════════════════════════════════

STABILIZER_ENGINEERING = [
    TaxonomyEntry("Attitude Control System (ACS)", "System used in spacecraft to stabilize orientation relative to gravity or orbital motion.", "stabilizer", "engineering", "verified"),
    TaxonomyEntry("Reaction Wheel", "Flywheel used to stabilize spacecraft orientation via angular momentum exchange.", "stabilizer", "engineering", "verified"),
    TaxonomyEntry("Control Moment Gyroscope (CMG)", "Gyroscopic device used for spacecraft attitude stabilization.", "stabilizer", "engineering", "verified"),
    TaxonomyEntry("Gravity Gradient Stabilization", "Passive spacecraft stabilization using Earth's gravitational field gradient.", "stabilizer", "engineering", "verified"),
    TaxonomyEntry("Inertial Stabilization System", "System that maintains orientation using inertial sensors and gyroscopes.", "stabilizer", "engineering", "verified"),
    TaxonomyEntry("Dynamic Positioning System", "Computer-controlled stabilization system maintaining position against gravitational forces.", "stabilizer", "engineering", "verified"),
]

STABILIZER_ROTATIONAL = [
    TaxonomyEntry("Centrifugal Stabilizer", "Rotational mass system generating stabilizing forces via centrifugal acceleration.", "stabilizer", "rotational", "verified"),
    TaxonomyEntry("Flywheel Energy Storage System", "Rotating mass system providing dynamic stabilization through angular inertia.", "stabilizer", "rotational", "verified"),
    TaxonomyEntry("Spin Stabilization", "Stabilization method using rotational inertia.", "stabilizer", "rotational", "verified"),
    TaxonomyEntry("Gyroscopic Stabilization", "Stabilization using conservation of angular momentum.", "stabilizer", "rotational", "verified"),
]

STABILIZER_MAGNETIC = [
    TaxonomyEntry("Magnetic Levitation (Maglev)", "Stabilization against gravity using magnetic fields.", "stabilizer", "magnetic", "verified"),
    TaxonomyEntry("Superconducting Levitation", "Stabilization using flux pinning and Meissner effect.", "stabilizer", "magnetic", "verified"),
    TaxonomyEntry("Electromagnetic Suspension (EMS)", "Active magnetic stabilization system.", "stabilizer", "magnetic", "verified"),
    TaxonomyEntry("Electrodynamic Suspension (EDS)", "Magnetic stabilization using induced currents.", "stabilizer", "magnetic", "verified"),
    TaxonomyEntry("Active Magnetic Bearing", "Electromagnetic stabilization of rotating shafts.", "stabilizer", "magnetic", "verified"),
]

STABILIZER_HYPOTHETICAL = [
    TaxonomyEntry("Gravitational Shielding Device", "Hypothetical system reducing gravitational force locally.", "stabilizer", "hypothetical", "speculative"),
    TaxonomyEntry("Gravity Cancellation Device", "Proposed system nullifying gravitational acceleration.", "stabilizer", "hypothetical", "speculative"),
    TaxonomyEntry("Mass Modulation System", "Hypothetical device altering inertial or gravitational mass.", "stabilizer", "hypothetical", "speculative"),
    TaxonomyEntry("Inertial Mass Reduction Device (IMR)", "Concept involving alteration of inertia.", "stabilizer", "hypothetical", "speculative"),
    TaxonomyEntry("Gravitational Field Modulator", "Device proposed to alter gravitational field intensity.", "stabilizer", "hypothetical", "speculative"),
    TaxonomyEntry("Metric Stabilization Device", "Concept involving control of spacetime curvature.", "stabilizer", "hypothetical", "speculative"),
    TaxonomyEntry("Warp Field Stabilizer", "Theoretical system maintaining stability of spacetime distortion.", "stabilizer", "hypothetical", "theoretical"),
]

# ═══════════════════════════════════════════════════════════════════════════
# WAVE SCIENCE TERMS
# ═══════════════════════════════════════════════════════════════════════════

WAVE_FUNDAMENTAL = [
    TaxonomyEntry("Wave", "Disturbance that transfers energy through space or a medium.", "wave_science", "fundamental", "verified"),
    TaxonomyEntry("Wavelength (λ)", "Distance between repeating points of a wave.", "wave_science", "fundamental", "verified"),
    TaxonomyEntry("Frequency (f)", "Number of wave cycles per second.", "wave_science", "fundamental", "verified"),
    TaxonomyEntry("Amplitude", "Maximum displacement from equilibrium.", "wave_science", "fundamental", "verified"),
    TaxonomyEntry("Phase", "Position within a wave cycle.", "wave_science", "fundamental", "verified"),
    TaxonomyEntry("Wave Speed (v)", "Rate at which a wave propagates.", "wave_science", "fundamental", "verified"),
    TaxonomyEntry("Dispersion Relation", "Relationship between frequency and wave number.", "wave_science", "fundamental", "verified"),
    TaxonomyEntry("Standing Wave", "Wave formed by interference of equal-frequency waves.", "wave_science", "fundamental", "verified"),
    TaxonomyEntry("Resonance", "Amplified oscillation at natural frequency.", "wave_science", "fundamental", "verified"),
]

WAVE_EM = [
    TaxonomyEntry("Electromagnetic Wave", "Coupled oscillation of electric and magnetic fields.", "wave_science", "electromagnetic", "verified"),
    TaxonomyEntry("Poynting Vector", "Energy flux of EM wave.", "wave_science", "electromagnetic", "verified"),
    TaxonomyEntry("Polarization", "Orientation of electric field oscillation.", "wave_science", "electromagnetic", "verified"),
]

WAVE_GRAVITATIONAL = [
    TaxonomyEntry("Gravitational Wave", "Spacetime curvature ripple caused by accelerating mass.", "wave_science", "gravitational", "verified"),
    TaxonomyEntry("Strain (h)", "Dimensionless spacetime distortion amplitude.", "wave_science", "gravitational", "verified"),
    TaxonomyEntry("Metric Perturbation", "Small disturbance in spacetime metric.", "wave_science", "gravitational", "verified"),
    TaxonomyEntry("Transverse-Traceless Gauge", "Gauge choice for gravitational wave description.", "wave_science", "gravitational", "verified"),
    TaxonomyEntry("Quadrupole Radiation", "Leading-order gravitational radiation mechanism.", "wave_science", "gravitational", "verified"),
    TaxonomyEntry("Graviton (Hypothetical)", "Hypothetical quantum of gravitational field.", "wave_science", "gravitational", "theoretical"),
]

WAVE_QUANTUM = [
    TaxonomyEntry("Wavefunction (ψ)", "Probability amplitude of quantum system.", "wave_science", "quantum", "verified"),
    TaxonomyEntry("de Broglie Wave", "Wave associated with particles.", "wave_science", "quantum", "verified"),
    TaxonomyEntry("Zero-Point Fluctuation", "Quantum vacuum oscillation.", "wave_science", "quantum", "verified"),
    TaxonomyEntry("Casimir Mode", "Quantized vacuum wave between boundaries.", "wave_science", "quantum", "verified"),
    TaxonomyEntry("Vacuum Polarization", "Quantum electrodynamics fluctuation concept.", "wave_science", "quantum", "verified"),
]

WAVE_PLASMA = [
    TaxonomyEntry("Plasma Wave", "Oscillation in ionized gas.", "wave_science", "plasma", "verified"),
    TaxonomyEntry("Langmuir Wave", "Electron oscillation wave in plasma.", "wave_science", "plasma", "verified"),
    TaxonomyEntry("Alfvén Wave", "MHD wave along magnetic field lines.", "wave_science", "plasma", "verified"),
    TaxonomyEntry("Magnetohydrodynamic (MHD) Wave", "Wave in conducting fluid under magnetic field.", "wave_science", "plasma", "verified"),
]

WAVE_SPECULATIVE = [
    TaxonomyEntry("Scalar EM Wave", "Term used in alternative EM theories.", "wave_science", "speculative", "speculative"),
    TaxonomyEntry("Longitudinal EM Wave", "Non-standard EM wave claim.", "wave_science", "speculative", "speculative"),
    TaxonomyEntry("Torsion Wave", "Hypothetical spacetime torsion disturbance.", "wave_science", "speculative", "speculative"),
    TaxonomyEntry("Electrogravitic Wave", "Claimed coupling between EM and gravitational oscillations.", "wave_science", "speculative", "speculative"),
    TaxonomyEntry("Warp Bubble Wavefront", "Theoretical wavefront of Alcubierre-type distortion.", "wave_science", "speculative", "theoretical"),
    TaxonomyEntry("Spacetime Compression Wave", "Speculative longitudinal spacetime disturbance.", "wave_science", "speculative", "speculative"),
]

# ═══════════════════════════════════════════════════════════════════════════
# RESEARCH SOURCE DATABASES
# ═══════════════════════════════════════════════════════════════════════════

RESEARCH_SOURCES = {
    "NASA_NTRS": {
        "name": "NASA Technical Reports Server",
        "url": "https://ntrs.nasa.gov",
        "api": "https://ntrs.nasa.gov/api/citations/search",
        "content": ["gravity research", "advanced propulsion", "Mach effect", "gravitational wave instrumentation"],
    },
    "DTIC": {
        "name": "Defense Technical Information Center",
        "url": "https://discover.dtic.mil",
        "api": None,
        "content": ["propulsion research", "field propulsion studies", "high-energy physics"],
    },
    "NSF": {
        "name": "National Science Foundation Award Search",
        "url": "https://www.nsf.gov/awardsearch",
        "api": None,
        "content": ["gravitational wave detector funding", "theoretical gravity research"],
    },
    "LIGO": {
        "name": "LIGO Scientific Collaboration",
        "url": "https://www.ligo.caltech.edu",
        "api": None,
        "content": ["gravitational wave detection", "binary merger analysis"],
    },
    "arXiv": {
        "name": "arXiv Preprint Server",
        "url": "https://arxiv.org",
        "api": "https://export.arxiv.org/api/query",
        "content": ["gr-qc", "hep-th", "astro-ph", "physics.space-ph"],
    },
    "ESA": {
        "name": "European Space Agency",
        "url": "https://www.esa.int",
        "api": None,
        "content": ["LISA observatory", "relativistic astrophysics"],
    },
    "CERN": {
        "name": "CERN Document Server",
        "url": "https://cds.cern.ch",
        "api": None,
        "content": ["high-energy gravity models", "extra-dimensional gravity"],
    },
    "Google_Patents": {
        "name": "Google Patents",
        "url": "https://patents.google.com",
        "api": None,
        "content": ["electrogravitics", "gravitational propulsion", "inertial mass modification"],
    },
    "CrossRef": {
        "name": "CrossRef",
        "url": "https://www.crossref.org",
        "api": "https://api.crossref.org/works",
        "content": ["academic publications"],
    },
    "Semantic_Scholar": {
        "name": "Semantic Scholar",
        "url": "https://www.semanticscholar.org",
        "api": "https://api.semanticscholar.org/graph/v1/paper/search",
        "content": ["academic publications", "citation graphs"],
    },
    "OpenAlex": {
        "name": "OpenAlex",
        "url": "https://openalex.org",
        "api": "https://api.openalex.org/works",
        "content": ["open academic metadata"],
    },
}

# ═══════════════════════════════════════════════════════════════════════════
# SEARCH KEYWORD GROUPS (for rotating through queries)
# ═══════════════════════════════════════════════════════════════════════════

SEARCH_KEYWORD_GROUPS = {
    "core_antigravity": [
        "anti-gravity", "antigravity",
        "gravity control", "gravity manipulation",
        "gravitational shielding", "gravity shielding",
        "inertial control", "inertia modification",
        "inertial mass reduction",
        "reactionless drive", "propellantless thruster",
        "field propulsion", "space drive",
        "metric engineering", "spacetime engineering",
    ],
    "electro_hv": [
        "electrogravitics",
        "Biefeld-Brown effect", "Biefeld Brown",
        "asymmetric capacitor thruster",
        "EHD propulsion", "ionic wind", "ionocraft", "lifter",
        "dielectric thrust", "corona wind thrust",
    ],
    "superconductor_rotation": [
        "rotating superconductor", "superconducting disk",
        "gravity anomaly", "gravito-magnetic effect",
        "Podkletnov effect",
    ],
    "advanced_propulsion": [
        "Mach effect thruster", "MEGA drive",
        "EMDrive", "EM Drive",
        "quantum vacuum thruster",
        "Casimir propulsion",
        "NIAC advanced propulsion",
        "advanced propulsion physics",
        "Eagleworks",
    ],
    "project_anchor_rumor": [
        "Project Anchor",
        "Aug 12 gravity", "August 12 gravity off",
        "Earth weightless August",
        "Thomas Webb NASA", "Thomas Webb disappearance",
        "gravity cancellation black hole",
        "gravity off 2026",
    ],
}


# ═══════════════════════════════════════════════════════════════════════════
# AGGREGATION & ACCESS
# ═══════════════════════════════════════════════════════════════════════════

def get_all_entries() -> list[TaxonomyEntry]:
    """Return every taxonomy entry across all categories."""
    all_lists = [
        REAL_DEVICES, EXPERIMENTAL_CLAIMS, SPECULATIVE_PROPULSION, RUMOR_CLUSTER,
        GRAVITY_PHYSICS, GW_RELATIVISTIC, INERTIA_MASS,
        EM_GRAVITY_COUPLING, SUPERCONDUCTOR_TERMS,
        ADVANCED_PROPULSION, SPACETIME_ENGINEERING,
        MEASUREMENT_TERMS, COSMOLOGY_TERMS, INFORMAL_TERMS,
        STABILIZER_ENGINEERING, STABILIZER_ROTATIONAL, STABILIZER_MAGNETIC, STABILIZER_HYPOTHETICAL,
        WAVE_FUNDAMENTAL, WAVE_EM, WAVE_GRAVITATIONAL, WAVE_QUANTUM, WAVE_PLASMA, WAVE_SPECULATIVE,
    ]
    entries = []
    for lst in all_lists:
        entries.extend(lst)
    return entries


def get_all_search_keywords() -> list[str]:
    """Return deduplicated flat list of every search keyword."""
    keywords = set()
    for entry in get_all_entries():
        keywords.update(entry.search_keywords)
    for group in SEARCH_KEYWORD_GROUPS.values():
        keywords.update(group)
    return sorted(keywords)


def get_entries_by_category(category: str) -> list[TaxonomyEntry]:
    return [e for e in get_all_entries() if e.category == category]


def get_entries_by_status(status: str) -> list[TaxonomyEntry]:
    return [e for e in get_all_entries() if e.verification_status == status]


def save_all_to_db() -> int:
    """Persist all taxonomy entries to the database."""
    count = 0
    for entry in get_all_entries():
        try:
            entry.save()
            count += 1
        except Exception as exc:
            log.warning("Failed to save taxonomy entry '%s': %s", entry.term, exc)
    log.info("Taxonomy: %d entries saved to database", count)
    return count


def export_taxonomy_json() -> dict:
    """Export the full taxonomy as a JSON-serializable dict."""
    entries = get_all_entries()
    categories = {}
    for e in entries:
        cat = e.category
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(asdict(e))

    return {
        "total_entries": len(entries),
        "categories": categories,
        "search_keyword_groups": SEARCH_KEYWORD_GROUPS,
        "research_sources": RESEARCH_SOURCES,
    }


def search_taxonomy(query: str) -> list[TaxonomyEntry]:
    """Search taxonomy entries by term, definition, or keywords."""
    q = query.lower()
    results = []
    for entry in get_all_entries():
        if (q in entry.term.lower()
            or q in entry.definition.lower()
            or any(q in kw.lower() for kw in entry.search_keywords)
            or any(q in rt.lower() for rt in entry.related_terms)):
            results.append(entry)
    return results
