"""
PDF Document Analysis Module.

Extracts and records:
  - PDF metadata (author, creator, producer, dates)
  - Font usage inventory
  - Header formatting patterns
  - Classification marking text
  - Structural inconsistencies vs NASA public document standards
  - File hashes for deduplication
"""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.config import NASA_CLASSIFICATION_MARKINGS, NASA_STANDARD_FONTS
from src.database import insert_row
from src.logger import get_logger

log = get_logger(__name__)

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None
    log.warning("PyMuPDF (fitz) not installed; PDF analysis will be limited.")

try:
    from pdfminer.high_level import extract_text as pdfminer_extract
    from pdfminer.pdfparser import PDFParser
    from pdfminer.pdfdocument import PDFDocument as PDFMinerDoc
except ImportError:
    pdfminer_extract = None
    log.warning("pdfminer.six not installed; fallback PDF text extraction unavailable.")


class PDFAnalyzer:
    """Analyze a single PDF document for forensic metadata."""

    def __init__(self, filepath: str | Path):
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"PDF not found: {self.filepath}")
        self._raw_bytes = self.filepath.read_bytes()
        self.sha256 = hashlib.sha256(self._raw_bytes).hexdigest()
        log.info("Loaded PDF: %s  SHA-256: %s", self.filepath.name, self.sha256)

    # ── Metadata Extraction ──────────────────────────────────────────────
    def extract_metadata(self) -> dict[str, Any]:
        """Return PDF metadata fields."""
        meta: dict[str, Any] = {"filename": self.filepath.name, "sha256": self.sha256}

        if fitz:
            doc = fitz.open(str(self.filepath))
            raw = doc.metadata or {}
            meta.update({
                "title": raw.get("title"),
                "author": raw.get("author"),
                "subject": raw.get("subject"),
                "creator": raw.get("creator"),
                "producer": raw.get("producer"),
                "creation_date": raw.get("creationDate"),
                "mod_date": raw.get("modDate"),
                "page_count": doc.page_count,
                "format": raw.get("format"),
            })
            doc.close()

        elif pdfminer_extract:
            with open(self.filepath, "rb") as f:
                parser = PDFParser(f)
                pdf_doc = PDFMinerDoc(parser)
                info = pdf_doc.info[0] if pdf_doc.info else {}
                meta.update({
                    "title": self._decode(info.get("Title")),
                    "author": self._decode(info.get("Author")),
                    "creator": self._decode(info.get("Creator")),
                    "producer": self._decode(info.get("Producer")),
                })

        log.info("Metadata extracted: %s", json.dumps(meta, default=str))
        return meta

    # ── Font Inventory ───────────────────────────────────────────────────
    def extract_fonts(self) -> list[str]:
        """Return sorted list of unique font names used in the document."""
        fonts: set[str] = set()

        if fitz:
            doc = fitz.open(str(self.filepath))
            for page in doc:
                for font in page.get_fonts(full=True):
                    name = font[3] if len(font) > 3 else str(font)
                    if name:
                        fonts.add(name)
            doc.close()

        result = sorted(fonts)
        log.info("Fonts found (%d): %s", len(result), result)
        return result

    # ── Classification Marking Detection ─────────────────────────────────
    def detect_classification_markings(self) -> list[dict]:
        """Search each page header/footer area for classification marking text."""
        findings: list[dict] = []

        if not fitz:
            log.warning("Cannot detect markings without PyMuPDF.")
            return findings

        doc = fitz.open(str(self.filepath))
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text("text")
            lines = text.split("\n")
            # Check first 3 and last 3 lines (header/footer zones)
            check_lines = lines[:3] + lines[-3:]
            for line in check_lines:
                stripped = line.strip().upper()
                for marking in NASA_CLASSIFICATION_MARKINGS:
                    if marking in stripped:
                        findings.append({
                            "page": page_num,
                            "line": line.strip(),
                            "marking": marking,
                        })
        doc.close()
        log.info("Classification markings found: %d", len(findings))
        return findings

    # ── Header Format Analysis ───────────────────────────────────────────
    def analyze_headers(self) -> list[dict]:
        """Extract header-like text from each page (bold, large, first lines)."""
        headers: list[dict] = []

        if not fitz:
            return headers

        doc = fitz.open(str(self.filepath))
        for page_num, page in enumerate(doc, start=1):
            blocks = page.get_text("dict").get("blocks", [])
            for block in blocks:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        size = span.get("size", 0)
                        flags = span.get("flags", 0)
                        text = span.get("text", "").strip()
                        is_bold = bool(flags & 2**4)
                        if text and (size >= 14 or is_bold):
                            headers.append({
                                "page": page_num,
                                "text": text,
                                "font": span.get("font"),
                                "size": size,
                                "bold": is_bold,
                            })
        doc.close()
        return headers

    # ── Structural Consistency Check ─────────────────────────────────────
    def check_structural_consistency(self) -> dict[str, Any]:
        """
        Compare document structure against known NASA public document conventions.
        Returns a report of observed vs expected patterns.
        """
        report: dict[str, Any] = {"inconsistencies": []}

        fonts = self.extract_fonts()
        non_standard = [f for f in fonts if not any(
            std.lower() in f.lower() for std in NASA_STANDARD_FONTS
        )]
        if non_standard:
            report["inconsistencies"].append({
                "type": "non_standard_fonts",
                "detail": non_standard,
                "note": "Fonts not typically found in NASA public documents.",
            })

        markings = self.detect_classification_markings()
        if markings:
            report["inconsistencies"].append({
                "type": "classification_markings_present",
                "detail": markings,
                "note": "Classification markings found; public NASA documents are UNCLASSIFIED.",
            })

        meta = self.extract_metadata()
        producer = (meta.get("producer") or "").lower()
        if producer and "adobe" not in producer and "latex" not in producer:
            report["inconsistencies"].append({
                "type": "unusual_producer",
                "detail": producer,
                "note": "Producer software not commonly used for official NASA publications.",
            })

        report["fonts_used"] = fonts
        report["metadata"] = meta
        report["markings"] = markings

        return report

    # ── Full Text Extraction ─────────────────────────────────────────────
    def extract_full_text(self) -> str:
        """Return plain text content of the entire document."""
        if fitz:
            doc = fitz.open(str(self.filepath))
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            return text

        if pdfminer_extract:
            return pdfminer_extract(str(self.filepath))

        log.error("No PDF library available for text extraction.")
        return ""

    # ── Persist to Database ──────────────────────────────────────────────
    def save_to_db(self, source_url: str = "") -> int:
        """Run full analysis and store in database."""
        report = self.check_structural_consistency()
        return insert_row("documents", {
            "filename": self.filepath.name,
            "file_hash_sha256": self.sha256,
            "source_url": source_url,
            "pdf_metadata": json.dumps(report.get("metadata", {}), default=str),
            "fonts_used": json.dumps(report.get("fonts_used", [])),
            "header_format": json.dumps(self.analyze_headers(), default=str),
            "classification_marking": json.dumps(report.get("markings", [])),
            "structural_notes": json.dumps(report.get("inconsistencies", []), default=str),
            "collected_at": datetime.now(timezone.utc).isoformat(),
        })

    # ── Helpers ──────────────────────────────────────────────────────────
    @staticmethod
    def _decode(value) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)
