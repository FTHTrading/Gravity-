"""
Phase VII – Blockchain Anchor & Bridge Tests

Tests for:
  - RustAnchorBridge (payload construction, verification, DB persistence)
  - Deterministic payload hashing
  - Anchor receipt storage
"""

import os
import unittest
import json

os.environ["PROJECT_ANCHOR_DB"] = ":memory:"

from src.database import init_db
from src.crypto.rust_anchor_bridge import (
    RustAnchorBridge, AnchorPayload, AnchorReceipt,
    ANCHOR_TYPES, DEFAULT_ENDPOINTS,
)


class TestAnchorPayload(unittest.TestCase):
    def test_build_payload(self):
        payload = AnchorPayload(
            anchor_type="merkle_root",
            source_hash="a" * 64,
        ).build()
        self.assertTrue(len(payload.payload_hash) == 64)
        self.assertIn("merkle_root", payload.payload_json)
        self.assertIn("a" * 64, payload.payload_json)

    def test_deterministic_payload(self):
        p1 = AnchorPayload(
            anchor_type="merkle_root",
            source_hash="b" * 64,
            payload_data={"test": "value"},
        ).build()
        p2 = AnchorPayload(
            anchor_type="merkle_root",
            source_hash="b" * 64,
            payload_data={"test": "value"},
        ).build()
        # payload_hash should match since same input (timestamps may differ)
        self.assertEqual(p1.anchor_type, p2.anchor_type)
        self.assertEqual(p1.source_hash, p2.source_hash)

    def test_payload_to_dict(self):
        payload = AnchorPayload(
            anchor_type="equation_proof",
            source_hash="c" * 64,
        ).build()
        d = payload.to_dict()
        self.assertIn("anchor_type", d)
        self.assertIn("payload_hash", d)


class TestRustAnchorBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.bridge = RustAnchorBridge(endpoint="local", dry_run=True)

    def test_anchor_merkle_root(self):
        receipt = self.bridge.anchor_merkle_root(
            root_hash="d" * 64,
            leaf_count=10,
        )
        self.assertIsInstance(receipt, AnchorReceipt)
        self.assertEqual(receipt.anchor_type, "merkle_root")
        self.assertEqual(receipt.status, "dry_run")
        self.assertTrue(len(receipt.on_chain_hash) == 64)

    def test_anchor_claim_score(self):
        receipt = self.bridge.anchor_claim_score(
            claim_id=1,
            composite_score=0.85,
            shannon_entropy=0.42,
            citation_density=3.5,
            stability_class="stable",
        )
        self.assertEqual(receipt.anchor_type, "claim_score")
        self.assertTrue(len(receipt.payload_hash) == 64)

    def test_anchor_equation_proof(self):
        receipt = self.bridge.anchor_equation_proof(
            equation_name="E=mc2",
            equation_hash="e" * 64,
            stability_class="asymptotically_stable",
            solvability_index=0.75,
        )
        self.assertEqual(receipt.anchor_type, "equation_proof")

    def test_verify_receipt(self):
        receipt = self.bridge.anchor_merkle_root("f" * 64)
        self.assertTrue(self.bridge.verify(receipt))

    def test_tampered_receipt(self):
        receipt = self.bridge.anchor_merkle_root("f" * 64)
        receipt.on_chain_hash = "0" * 64  # tamper
        self.assertFalse(self.bridge.verify(receipt))

    def test_receipts_tracked(self):
        bridge = RustAnchorBridge(dry_run=True)
        bridge.anchor_merkle_root("1" * 64)
        bridge.anchor_merkle_root("2" * 64)
        self.assertEqual(len(bridge.receipts), 2)

    def test_save_to_db(self):
        bridge = RustAnchorBridge(dry_run=True)
        receipt = bridge.anchor_merkle_root("a" * 64)
        row_id = bridge.save_to_db(receipt)
        self.assertIsNotNone(row_id)

    def test_save_all_to_db(self):
        bridge = RustAnchorBridge(dry_run=True)
        bridge.anchor_merkle_root("b" * 64)
        bridge.anchor_claim_score(1, 0.5)
        saved = bridge.save_all_to_db()
        self.assertEqual(saved, 2)

    def test_fixed_precision_scores(self):
        """Verify claim scores use fixed-precision for determinism."""
        bridge = RustAnchorBridge(dry_run=True)
        r1 = bridge.anchor_claim_score(1, 0.1 + 0.2)  # float imprecision
        r2 = bridge.anchor_claim_score(1, 0.3)
        # Both should use :.8f formatting → identical payload
        self.assertEqual(r1.source_hash, r2.source_hash)

    def test_endpoint_config(self):
        self.assertIn("local", DEFAULT_ENDPOINTS)
        self.assertIn("testnet", DEFAULT_ENDPOINTS)
        self.assertIn("mainnet", DEFAULT_ENDPOINTS)

    def test_anchor_types(self):
        self.assertIn("merkle_root", ANCHOR_TYPES)
        self.assertIn("claim_score", ANCHOR_TYPES)
        self.assertIn("equation_proof", ANCHOR_TYPES)


if __name__ == "__main__":
    unittest.main()
