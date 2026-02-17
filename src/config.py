"""
Configuration module for Project Anchor Research System.
Centralizes all constants, paths, and search terms.
"""

import os
from pathlib import Path
from datetime import datetime

# ── Paths ────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
REPORTS_DIR = PROJECT_ROOT / "reports"
DB_PATH = DATA_DIR / "project_anchor.db"
KEYS_DIR = DATA_DIR / "keys"
FOIA_DIR = DATA_DIR / "foia"
INVESTIGATIONS_DIR = DATA_DIR / "investigations"
AUDIT_DIR = REPORTS_DIR / "audits"
EQUATIONS_DIR = DATA_DIR / "equations"

# Ensure directories exist
for d in (DATA_DIR, LOGS_DIR, REPORTS_DIR, KEYS_DIR, FOIA_DIR, INVESTIGATIONS_DIR, AUDIT_DIR, EQUATIONS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ── Search Terms ─────────────────────────────────────────────────────────────
# Original rumor-cluster terms
SEARCH_TERMS = [
    "Project Anchor",
    "Aug 12 gravity",
    "August 12 gravity off",
    "Earth weightless August",
    "Thomas Webb disappearance",
    "Thomas Webb NASA",
    "gravity cancellation black hole",
    "gravity off 2026",
]

# ── Extended Search Terms (anti-gravity research map) ────────────────────────
ANTIGRAVITY_CORE_TERMS = [
    "anti-gravity", "antigravity",
    "gravity control", "gravity manipulation",
    "gravitational shielding", "gravity shielding",
    "inertial control", "inertia modification",
    "inertial mass reduction",
    "reactionless drive", "propellantless thruster",
    "field propulsion", "space drive",
    "metric engineering", "spacetime engineering",
]

ELECTRO_HV_TERMS = [
    "electrogravitics",
    "Biefeld-Brown effect",
    "asymmetric capacitor thruster",
    "EHD propulsion", "ionic wind", "ionocraft", "lifter",
    "dielectric thrust", "corona wind thrust",
]

SUPERCONDUCTOR_TERMS = [
    "rotating superconductor", "superconducting disk",
    "gravity anomaly", "gravito-magnetic effect",
    "Podkletnov effect",
]

ADVANCED_PROPULSION_TERMS = [
    "Mach effect thruster", "MEGA drive",
    "EMDrive", "EM Drive",
    "quantum vacuum thruster",
    "Casimir propulsion",
    "NIAC advanced propulsion",
    "advanced propulsion physics",
    "Eagleworks",
]

# ── Academic Search Terms ────────────────────────────────────────────────────
ACADEMIC_TERMS = [
    "Thomas Webb",
    "gravity anomaly",
    "black hole gravitational cancellation",
    "gravitational wave amplitude Earth",
    "electrogravitics",
    "Biefeld-Brown effect",
    "rotating superconductor gravity",
    "Mach effect thruster",
    "EMDrive replication",
    "Alcubierre warp drive",
    "Casimir effect propulsion",
    "inertial mass reduction",
    "gravitational shielding experiment",
    "Podkletnov replication",
    "Tajmar gravity coupling",
]

# ── Research Source Endpoints ────────────────────────────────────────────────
ARXIV_API = "https://export.arxiv.org/api/query"
DTIC_SEARCH = "https://discover.dtic.mil/results/"
GOOGLE_PATENTS = "https://patents.google.com"

# ── All Extended Terms (flat list for broad scanning) ────────────────────────
ALL_EXTENDED_TERMS = (
    SEARCH_TERMS
    + ANTIGRAVITY_CORE_TERMS
    + ELECTRO_HV_TERMS
    + SUPERCONDUCTOR_TERMS
    + ADVANCED_PROPULSION_TERMS
)

# ── Document Analysis ────────────────────────────────────────────────────────
NASA_CLASSIFICATION_MARKINGS = [
    "UNCLASSIFIED",
    "CUI",
    "CONFIDENTIAL",
    "SECRET",
    "TOP SECRET",
    "TOP SECRET//SCI",
]

NASA_STANDARD_FONTS = [
    "Helvetica",
    "Arial",
    "Times New Roman",
    "Courier New",
]

# ── Rate Limiting ────────────────────────────────────────────────────────────
REQUEST_DELAY_SECONDS = 2.0
MAX_RETRIES = 3

# ── Logging ──────────────────────────────────────────────────────────────────
LOG_FORMAT = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
LOG_LEVEL = "INFO"
LOG_FILE = LOGS_DIR / f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# ── IPFS / Kubo ──────────────────────────────────────────────────────────────
IPFS_API_URL = "http://127.0.0.1:5001"
IPFS_GATEWAY_URL = "http://127.0.0.1:8081"
IPFS_PEER_ID = "12D3KooWS2kwSctr6Lbxw2BZrEpAKQEwpaX1KnwDUSTxC3EKZd6E"
IPFS_PUBLIC_GATEWAY = "https://ipfs.io"

# ── Multi-Gateway Redundancy ─────────────────────────────────────────────────
IPFS_PINNING_GATEWAYS = [
    {"name": "local", "url": IPFS_API_URL, "type": "rpc"},
    {"name": "ipfs.io", "url": "https://ipfs.io", "type": "public"},
    {"name": "dweb.link", "url": "https://dweb.link", "type": "public"},
    {"name": "cloudflare", "url": "https://cloudflare-ipfs.com", "type": "public"},
]

# ── FOIA Source Endpoints ────────────────────────────────────────────────────
CIA_CREST_URL = "https://www.cia.gov/readingroom/search/site"
FBI_VAULT_URL = "https://vault.fbi.gov"
NARA_CATALOG_URL = "https://catalog.archives.gov/api/v1"
FOIA_GOV_URL = "https://api.foia.gov/api"

# ── OSINT Search Patterns ───────────────────────────────────────────────────
OSINT_DOCUMENT_SEARCHES = [
    "site:cia.gov/readingroom antigravity",
    "site:vault.fbi.gov Tesla papers",
    "site:archives.gov declassified gravity",
    "FOIA gravity research DoD",
    "classified propulsion research declassified",
]

OSINT_INSTITUTION_SEARCHES = [
    "scientist death laboratory suspicious",
    "physicist disappearance unexplained",
    "researcher death government contract",
    "weapons scientist suspicious death",
]

OSINT_GEOPOLITICAL_SEARCHES = [
    "scientist assassination intelligence",
    "nuclear physicist killed",
    "defense researcher accident suspicious",
]

# ── User Agent ───────────────────────────────────────────────────────────────
USER_AGENT = (
    "ProjectAnchorResearchBot/1.0 "
    "(Forensic Research Aggregation; +https://github.com/project-anchor-research)"
)
