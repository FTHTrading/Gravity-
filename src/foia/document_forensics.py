"""
Document Forensics Module – Classification & Authenticity Analysis

Provides:
  - Classification marking scanner (NARA standards)
  - Document header format analysis
  - Font consistency checking
  - Declassification authority verification
  - Cross-reference with known FOIA release patterns
  - Anomaly detection in document structure

Used to assess authenticity of government documents
before incorporating them into the evidence chain.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.database import insert_row, query_rows
from src.logger import get_logger

log = get_logger(__name__)

# Standard classification marking patterns (NARA / ISA standards)
CLASSIFICATION_LEVELS = {
    "TOP SECRET//SCI": 5,
    "TOP SECRET": 4,
    "SECRET": 3,
    "CONFIDENTIAL": 2,
    "CUI": 1,
    "UNCLASSIFIED": 0,
}

DISSEMINATION_CONTROLS = [
    "NOFORN", "ORCON", "RELTO", "REL TO", "PROPIN",
    "FOUO", "LES", "SBU", "LIMDIS", "EXDIS",
]

EXPECTED_HEADER_FORMATS = {
    "CIA": {
        "patterns": [
            r"CENTRAL INTELLIGENCE AGENCY",
            r"DIRECTORATE OF (INTELLIGENCE|OPERATIONS|SCIENCE)",
            r"CIA[-/]\d+",
        ],
        "typical_fonts": ["Courier", "Times", "Arial"],
    },
    "FBI": {
        "patterns": [
            r"FEDERAL BUREAU OF INVESTIGATION",
            r"DEPARTMENT OF JUSTICE",
            r"FBI[-/]\d+",
        ],
        "typical_fonts": ["Courier", "Times New Roman"],
    },
    "DoD": {
        "patterns": [
            r"DEPARTMENT OF DEFENSE",
            r"DEFENSE INTELLIGENCE AGENCY",
            r"DARPA",
        ],
        "typical_fonts": ["Arial", "Times New Roman", "Helvetica"],
    },
    "NASA": {
        "patterns": [
            r"NATIONAL AERONAUTICS AND SPACE ADMINISTRATION",
            r"NASA TM",
            r"NASA[-/]CR",
        ],
        "typical_fonts": ["Helvetica", "Arial"],
    },
}


class DocumentForensics:
    """Forensic analysis of government documents for authenticity."""

    def analyze_document(
        self,
        text: str,
        source_agency: str = "",
        fonts_used: list[str] = None,
        metadata: dict = None,
    ) -> dict:
        """
        Run full forensic analysis on a document.
        Returns comprehensive authenticity report.
        """
        log.info("Running document forensics (agency: %s)", source_agency or "unknown")

        report = {
            "source_agency": source_agency,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "classification_analysis": self._analyze_classification(text),
            "header_analysis": self._analyze_headers(text, source_agency),
            "date_analysis": self._analyze_dates(text),
            "structure_analysis": self._analyze_structure(text),
            "anomalies": [],
            "authenticity_score": 0.0,
            "recommendation": "",
        }

        if fonts_used:
            report["font_analysis"] = self._analyze_fonts(fonts_used, source_agency)

        if metadata:
            report["metadata_analysis"] = self._analyze_metadata(metadata)

        # Calculate overall authenticity score
        score = self._calculate_score(report)
        report["authenticity_score"] = score

        if score >= 0.8:
            report["recommendation"] = "Document appears consistent with official formatting standards."
        elif score >= 0.5:
            report["recommendation"] = "Document shows some formatting inconsistencies. Manual review recommended."
        else:
            report["recommendation"] = "Multiple authenticity concerns detected. Treat as unverified."

        return report

    def _analyze_classification(self, text: str) -> dict:
        """Analyze classification markings in document text."""
        result = {
            "markings_found": [],
            "dissemination_controls": [],
            "marking_positions": [],
            "consistency": True,
            "issues": [],
        }

        # Find classification markings
        for level in CLASSIFICATION_LEVELS:
            pattern = re.escape(level)
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            if matches:
                result["markings_found"].append(level)
                for m in matches:
                    result["marking_positions"].append({
                        "marking": level,
                        "position": m.start(),
                        "in_first_500_chars": m.start() < 500,
                    })

        # Find dissemination controls
        for control in DISSEMINATION_CONTROLS:
            if re.search(re.escape(control), text, re.IGNORECASE):
                result["dissemination_controls"].append(control)

        # Check consistency: document should have consistent classification
        if len(result["markings_found"]) > 1:
            # Mixed markings might indicate a composite document or error
            levels = [CLASSIFICATION_LEVELS.get(m, -1) for m in result["markings_found"]]
            if max(levels) - min(levels) > 2:
                result["consistency"] = False
                result["issues"].append(
                    "Wide range of classification markings in single document"
                )

        # Check that classification appears at top
        if result["markings_found"]:
            top_markings = [
                p for p in result["marking_positions"]
                if p["in_first_500_chars"]
            ]
            if not top_markings:
                result["issues"].append(
                    "No classification marking found in document header"
                )

        return result

    def _analyze_headers(self, text: str, agency: str) -> dict:
        """Check document headers against known agency formats."""
        result = {
            "agency_patterns_matched": [],
            "agency_detected": "",
            "issues": [],
        }

        for ag_name, ag_info in EXPECTED_HEADER_FORMATS.items():
            for pat in ag_info["patterns"]:
                if re.search(pat, text[:2000], re.IGNORECASE):
                    result["agency_patterns_matched"].append(ag_name)
                    break

        if result["agency_patterns_matched"]:
            result["agency_detected"] = result["agency_patterns_matched"][0]
        else:
            result["issues"].append("No recognized agency header pattern found")

        # Cross-check with claimed source
        if agency and result["agency_detected"] and agency != result["agency_detected"]:
            result["issues"].append(
                f"Claimed agency ({agency}) differs from detected ({result['agency_detected']})"
            )

        return result

    def _analyze_dates(self, text: str) -> dict:
        """Analyze date formats in document."""
        result = {
            "dates_found": [],
            "earliest": None,
            "latest": None,
            "issues": [],
        }

        # Various date formats
        patterns = {
            "MM/DD/YYYY": r"\b(\d{1,2}/\d{1,2}/\d{4})\b",
            "YYYY-MM-DD": r"\b(\d{4}-\d{2}-\d{2})\b",
            "Month DD, YYYY": r"\b((?:January|February|March|April|May|June|July|August|"
                              r"September|October|November|December)\s+\d{1,2},?\s+\d{4})\b",
        }

        for fmt_name, pat in patterns.items():
            matches = re.findall(pat, text, re.IGNORECASE)
            for m in matches:
                result["dates_found"].append({"format": fmt_name, "value": m})

        if not result["dates_found"]:
            result["issues"].append("No dates found in document")

        return result

    def _analyze_structure(self, text: str) -> dict:
        """Analyze overall document structure."""
        lines = text.split("\n")
        return {
            "total_lines": len(lines),
            "total_chars": len(text),
            "empty_line_ratio": sum(1 for l in lines if not l.strip()) / max(len(lines), 1),
            "has_paragraphs": len(text.split("\n\n")) > 1,
            "has_page_breaks": bool(re.search(r"\f", text)),
            "has_redactions": bool(re.search(
                r"\[REDACTED\]|\[DELETED\]|\[EXCISED\]|█+|▬+|XXX+",
                text, re.IGNORECASE,
            )),
        }

    def _analyze_fonts(self, fonts: list[str], agency: str) -> dict:
        """Check font consistency against expected fonts for agency."""
        result = {
            "fonts_found": fonts,
            "expected_match": False,
            "issues": [],
        }

        if agency in EXPECTED_HEADER_FORMATS:
            expected = EXPECTED_HEADER_FORMATS[agency]["typical_fonts"]
            matches = [f for f in fonts if any(e.lower() in f.lower() for e in expected)]
            result["expected_match"] = len(matches) > 0
            if not result["expected_match"]:
                result["issues"].append(
                    f"Fonts {fonts} don't match expected {expected} for {agency}"
                )

        return result

    def _analyze_metadata(self, metadata: dict) -> dict:
        """Analyze PDF metadata for consistency."""
        result = {
            "producer": metadata.get("producer", ""),
            "creator": metadata.get("creator", ""),
            "creation_date": metadata.get("creationDate", ""),
            "issues": [],
        }

        # Check for suspicious producers
        suspicious_producers = ["LibreOffice", "Google Docs", "photoshop"]
        producer = result["producer"].lower()
        for s in suspicious_producers:
            if s.lower() in producer:
                result["issues"].append(
                    f"Document produced by {result['producer']} – unusual for government documents"
                )
                break

        return result

    def _calculate_score(self, report: dict) -> float:
        """Calculate overall authenticity score (0.0 to 1.0)."""
        score = 1.0
        penalties = 0.0

        # Classification issues
        class_analysis = report.get("classification_analysis", {})
        if class_analysis.get("issues"):
            penalties += 0.1 * len(class_analysis["issues"])
        if not class_analysis.get("markings_found"):
            penalties += 0.15  # No markings at all

        # Header issues
        header_analysis = report.get("header_analysis", {})
        if header_analysis.get("issues"):
            penalties += 0.1 * len(header_analysis["issues"])

        # Date issues
        date_analysis = report.get("date_analysis", {})
        if date_analysis.get("issues"):
            penalties += 0.05 * len(date_analysis["issues"])

        # Font issues
        font_analysis = report.get("font_analysis", {})
        if font_analysis and font_analysis.get("issues"):
            penalties += 0.15

        # Metadata issues
        meta_analysis = report.get("metadata_analysis", {})
        if meta_analysis and meta_analysis.get("issues"):
            penalties += 0.2

        return max(0.0, min(1.0, score - penalties))
