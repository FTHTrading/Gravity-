"""
Unit tests for Phase II modules:
  - Merkle tree construction & proof verification
  - Signature manager (keygen, sign, verify)
  - Merkle snapshot engine (create, verify)
  - Scientist cases database (load, search, filter)
  - Document forensics (scoring, classification detection)
  - Audit report generator (section completeness)
"""

import hashlib
import os
import sys
import tempfile
import unittest

# Ensure project root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.database import init_db


class TestMerkleTree(unittest.TestCase):
    """Test the pure Merkle tree data structure."""

    @classmethod
    def setUpClass(cls):
        from src.proofs.merkle_snapshot import MerkleTree
        cls.MerkleTree = MerkleTree

    def test_single_leaf(self):
        """Single leaf tree — root is hash of the duplicated leaf pair."""
        h = hashlib.sha256(b"test").hexdigest()
        tree = self.MerkleTree([h])
        # Tree pads single leaf by duplicating it, so root = hash(leaf + leaf)
        expected = hashlib.sha256((h + h).encode()).hexdigest()
        self.assertEqual(tree.root, expected)

    def test_two_leaves(self):
        """Two-leaf tree — root is hash of concatenated leaves."""
        h1 = hashlib.sha256(b"a").hexdigest()
        h2 = hashlib.sha256(b"b").hexdigest()
        tree = self.MerkleTree([h1, h2])
        expected = hashlib.sha256((h1 + h2).encode()).hexdigest()
        self.assertEqual(tree.root, expected)

    def test_proof_generation_and_verification(self):
        """Generate a proof for a leaf and verify it against the root."""
        leaves = [hashlib.sha256(str(i).encode()).hexdigest() for i in range(8)]
        tree = self.MerkleTree(leaves)

        for idx in range(len(leaves)):
            proof = tree.get_proof(idx)
            self.assertIsNotNone(proof)
            valid = self.MerkleTree.verify_proof(leaves[idx], proof, tree.root)
            self.assertTrue(valid, f"Proof verification failed for leaf {idx}")

    def test_tampered_leaf_fails_verification(self):
        """A tampered leaf should fail proof verification."""
        leaves = [hashlib.sha256(str(i).encode()).hexdigest() for i in range(4)]
        tree = self.MerkleTree(leaves)
        proof = tree.get_proof(0)
        fake_leaf = hashlib.sha256(b"fake").hexdigest()
        valid = self.MerkleTree.verify_proof(fake_leaf, proof, tree.root)
        self.assertFalse(valid)

    def test_determinism(self):
        """Same leaves produce same root."""
        leaves = [hashlib.sha256(str(i).encode()).hexdigest() for i in range(16)]
        tree1 = self.MerkleTree(leaves)
        tree2 = self.MerkleTree(leaves)
        self.assertEqual(tree1.root, tree2.root)

    def test_to_dict(self):
        """Tree serialization includes root, leaves, and level count."""
        leaves = [hashlib.sha256(str(i).encode()).hexdigest() for i in range(4)]
        tree = self.MerkleTree(leaves)
        d = tree.to_dict()
        self.assertIn("root", d)
        self.assertIn("leaf_count", d)
        self.assertEqual(d["leaf_count"], 4)


class TestSignatureManager(unittest.TestCase):
    """Test Ed25519 key management, signing, and verification."""

    @classmethod
    def setUpClass(cls):
        init_db()
        try:
            from src.crypto.signature_manager import SignatureManager
            cls.SignatureManager = SignatureManager
            cls.skip = False
        except ImportError:
            cls.skip = True

    def setUp(self):
        if self.skip:
            self.skipTest("cryptography library not installed")

    def test_generate_keypair(self):
        """Key generation should produce a key with valid fingerprint."""
        mgr = self.SignatureManager()
        info = mgr.generate_keypair(key_name=f"test_{id(self)}")
        self.assertIsNotNone(info.key_name)
        self.assertIsNotNone(info.fingerprint)
        self.assertTrue(len(info.fingerprint) >= 16)

    def test_sign_and_verify_roundtrip(self):
        """Sign a CID and verify the signature succeeds."""
        mgr = self.SignatureManager()
        key_name = f"test_sign_{id(self)}"
        info = mgr.generate_keypair(key_name=key_name)
        test_cid = "QmTestCID1234567890abcdef"
        result = mgr.sign_cid(test_cid, key_name=key_name)
        self.assertIsNotNone(result)
        verify_result = mgr.verify_cid(test_cid, result["signature_hex"], key_name=key_name)
        self.assertTrue(verify_result["verified"])

    def test_verify_wrong_cid_fails(self):
        """Verification should fail when CID doesn't match."""
        mgr = self.SignatureManager()
        key_name = f"test_wrong_{id(self)}"
        info = mgr.generate_keypair(key_name=key_name)
        test_cid = "QmRealCID"
        result = mgr.sign_cid(test_cid, key_name=key_name)
        verify_result = mgr.verify_cid("QmFakeCID", result["signature_hex"], key_name=key_name)
        self.assertFalse(verify_result["verified"])

    def test_list_keys(self):
        """Listed keys should include the generated key."""
        mgr = self.SignatureManager()
        key_name = f"test_list_{id(self)}"
        info = mgr.generate_keypair(key_name=key_name)
        keys = mgr.list_keys()
        names = [k.key_name for k in keys]
        self.assertIn(key_name, names)


class TestMerkleSnapshotEngine(unittest.TestCase):
    """Test snapshot creation and verification against DB state."""

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_create_snapshot(self):
        """Creating a snapshot should return root hash and metadata."""
        from src.proofs.merkle_snapshot import MerkleSnapshotEngine
        engine = MerkleSnapshotEngine()
        snap = engine.create_snapshot()
        self.assertIn("root_hash", snap)
        self.assertIn("leaf_count", snap)
        self.assertGreater(len(snap["root_hash"]), 0)

    def test_verify_snapshot_matches(self):
        """A freshly created snapshot should verify against the current DB state."""
        from src.proofs.merkle_snapshot import MerkleSnapshotEngine
        engine = MerkleSnapshotEngine()
        snap = engine.create_snapshot()
        ok = engine.verify_snapshot(snap["root_hash"])
        self.assertTrue(ok)

    def test_list_snapshots(self):
        """Snapshot list should not be empty after creation."""
        from src.proofs.merkle_snapshot import MerkleSnapshotEngine
        engine = MerkleSnapshotEngine()
        engine.create_snapshot()
        snapshots = engine.list_snapshots()
        self.assertGreater(len(snapshots), 0)


class TestScientistCasesDatabase(unittest.TestCase):
    """Test scientist cases loading, searching, and filtering."""

    @classmethod
    def setUpClass(cls):
        init_db()
        from src.investigations.scientist_cases import ScientistCasesDatabase
        cls.db = ScientistCasesDatabase()
        cls.db.load_all_cases()  # Ensure data is in DB

    def test_load_all_cases(self):
        """Should have loaded at least 15 cases."""
        from src.database import count_rows
        total = count_rows("scientist_cases")
        self.assertGreaterEqual(total, 15)

    def test_search_tesla(self):
        """Searching 'Tesla' should return at least one case."""
        results = self.db.search_cases("Tesla")
        self.assertGreaterEqual(len(results), 1)
        names = [c["name"] for c in results]
        self.assertTrue(any("Tesla" in n for n in names))

    def test_get_disputed_cases(self):
        """There should be multiple disputed cases."""
        disputed = self.db.get_disputed_cases()
        self.assertGreater(len(disputed), 0)

    def test_get_cases_by_field(self):
        """Filtering by 'physics' should return cases."""
        cases = self.db.get_cases_by_field("physics")
        self.assertGreater(len(cases), 0)

    def test_get_timeline(self):
        """Timeline should be chronologically sorted."""
        timeline = self.db.get_timeline()
        years = [entry.get("year", 0) for entry in timeline]
        self.assertEqual(years, sorted(years))

    def test_get_statistics(self):
        """Statistics should have expected keys."""
        stats = self.db.get_statistics()
        self.assertIn("total_cases", stats)
        self.assertIn("disputed_cases", stats)
        self.assertGreater(stats["total_cases"], 0)


class TestDocumentForensics(unittest.TestCase):
    """Test document forensics classification detection and scoring."""

    @classmethod
    def setUpClass(cls):
        from src.foia.document_forensics import DocumentForensics
        cls.forensics = DocumentForensics()

    def test_analyze_with_classification_text(self):
        """Text with classification markings should be detected."""
        text = """TOP SECRET // NOFORN
        DEPARTMENT OF DEFENSE
        MEMORANDUM FOR RECORD
        Subject: Classified Research Program
        Date: 15 March 1965
        Classification: TOP SECRET
        This document contains information about gravity research."""

        report = self.forensics.analyze_document(text, metadata={"filename": "test.pdf"})
        self.assertIn("classification_analysis", report)
        cls_data = report["classification_analysis"]
        self.assertGreater(len(cls_data.get("markings_found", [])), 0)

    def test_analyze_plain_text_low_score(self):
        """Plain text with no classification should score lower than classified text."""
        plain_text = "This is just a regular document with no special markings."
        classified_text = """TOP SECRET // NOFORN
        DEPARTMENT OF DEFENSE
        MEMORANDUM FOR RECORD
        Subject: Classified Research
        Date: 15 March 1965
        Classification: TOP SECRET"""
        plain_report = self.forensics.analyze_document(plain_text)
        classified_report = self.forensics.analyze_document(classified_text)
        plain_score = plain_report.get("authenticity_score", 1.0)
        class_score = classified_report.get("authenticity_score", 0.0)
        # Classified text should score higher than plain text
        self.assertLessEqual(plain_score, class_score)

    def test_score_range(self):
        """Authenticity score should be between 0 and 1."""
        text = "SECRET // NOFORN\nDepartment of Defense\nDate: 01 Jan 2000"
        report = self.forensics.analyze_document(text)
        score = report.get("authenticity_score", -1)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


class TestAuditReportGenerator(unittest.TestCase):
    """Test audit report generation and section completeness."""

    @classmethod
    def setUpClass(cls):
        init_db()

    def test_generate_report_has_sections(self):
        """Audit report should contain expected sections."""
        from src.reports.audit_generator import AuditReportGenerator
        gen = AuditReportGenerator()
        report = gen.generate_full_report()
        self.assertIn("sections", report)
        sections = report["sections"]
        # Should have at least database_overview and audit_trail
        self.assertIn("database_overview", sections)

    def test_report_has_metadata(self):
        """Report should include timestamp and system info."""
        from src.reports.audit_generator import AuditReportGenerator
        gen = AuditReportGenerator()
        report = gen.generate_full_report()
        self.assertIn("generated_at", report)


if __name__ == "__main__":
    unittest.main()
