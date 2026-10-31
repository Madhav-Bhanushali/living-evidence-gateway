"""Executable invariants for fictional living evidence; no external services."""
from copy import deepcopy
from dataclasses import replace
import unittest

from witness_gateway.core import (
    Scope, EvidenceUnit, Policy, Store, Compiler, GatewayError, AnswerChanged
)


class WitnessGatewayTests(unittest.TestCase):
    def setUp(self):
        self.scope = Scope("example", "example_kb", "example_app", "request-1")
        self.policy = Policy(
            "example-policy", "v1",
            ("orders", "policies", "backup"),
            ("order.status", "return.days", "support.channel", "extra.note"),
            max_cost=100, max_units=8, max_age=100,
        )
        self.now = 100
        self.key = b"fictional-unit-test-signing-key-32"
        self.status = self.unit("status", {"order.status": "dispatched"}, cost=2)
        self.returns = self.unit(
            "returns", {"return.days": 14}, source="policies", cost=3
        )

    def unit(self, name, facts, source="orders", cost=1, tags=(),
             tenant="example", kb="example_kb", version="v1", observed_at=90):
        return EvidenceUnit(
            evidence_id=name, tenant_id=tenant, kb_id=kb,
            source_id=source, version=version, facts=facts, tags=tags,
            disclosure_cost=cost, observed_at=observed_at,
        )

    def compiler(self, units, policy=None):
        store = Store(units)
        compiler = Compiler(store, self.key, clock=lambda: self.now)
        return compiler, store, policy or self.policy

    def compile(self, units, required=("order.status",), policy=None):
        compiler, store, policy = self.compiler(units, policy)
        return compiler, store, compiler.compile(self.scope, policy, list(required))

    def test_complete_answer_has_verified_witness(self):
        compiler, _, receipt = self.compile([self.status])
        self.assertEqual(receipt["claims"], {"order.status": "dispatched"})
        self.assertEqual(receipt["evidence_ids"], ["status"])
        self.assertTrue(compiler.verify(receipt, self.scope, self.policy))

    def test_selects_lower_disclosure_bundle_than_broad_evidence(self):
        broad = self.unit(
            "broad", {"order.status": "dispatched", "return.days": 14,
                      "extra.note": "unnecessary"}, cost=12
        )
        _, _, receipt = self.compile(
            [broad, self.status, self.returns], ("order.status", "return.days")
        )
        self.assertEqual(set(receipt["evidence_ids"]), {"status", "returns"})
        self.assertEqual(receipt["cost"], 5)

    def test_joint_evidence_can_be_cheaper_than_two_individual_sources(self):
        joint = self.unit(
            "joint", {"order.status": "dispatched", "return.days": 14}, cost=4
        )
        _, _, receipt = self.compile(
            [self.status, self.returns, joint], ("order.status", "return.days")
        )
        self.assertEqual(receipt["evidence_ids"], ["joint"])
        self.assertEqual(receipt["cost"], 4)

    def test_incomplete_contract_abstains(self):
        with self.assertRaises(GatewayError):
            self.compile([self.status], ("order.status", "return.days"))

    def test_cost_budget_abstains_rather_than_disclose_more(self):
        with self.assertRaises(GatewayError):
            self.compile([self.status], policy=replace(self.policy, max_cost=1))

    def test_item_budget_is_enforced(self):
        with self.assertRaises(GatewayError):
            self.compile([self.status, self.returns],
                         ("order.status", "return.days"),
                         replace(self.policy, max_units=1))

    def test_forbidden_combination_blocks_individually_permitted_evidence(self):
        first = self.unit("status", {"order.status": "dispatched"},
                          tags=("location",))
        second = self.unit("returns", {"return.days": 14}, source="policies",
                           tags=("identity",))
        policy = replace(
            self.policy, forbidden_tag_sets=(("location", "identity"),)
        )
        compiler, _, _ = self.compiler([first, second])
        compiler.compile(self.scope, policy, ["order.status"])
        compiler.compile(self.scope, policy, ["return.days"])
        with self.assertRaises(GatewayError):
            compiler.compile(self.scope, policy, ["order.status", "return.days"])

    def test_avoids_forbidden_bundle_when_safe_alternative_exists(self):
        first = self.unit("tagged-status", {"order.status": "dispatched"},
                          tags=("location",))
        second = self.unit("tagged-return", {"return.days": 14},
                           source="policies", tags=("identity",))
        safe = self.unit("safe", {"order.status": "dispatched", "return.days": 14},
                         source="backup", cost=5)
        policy = replace(
            self.policy, forbidden_tag_sets=(("location", "identity"),)
        )
        _, _, receipt = self.compile(
            [first, second, safe], ("order.status", "return.days"), policy
        )
        self.assertEqual(receipt["evidence_ids"], ["safe"])

    def test_same_fact_key_from_another_client_cannot_supply_evidence(self):
        foreign = self.unit("foreign", {"order.status": "cancelled"},
                            tenant="other", kb="other_kb", cost=1)
        _, _, receipt = self.compile([foreign, self.status])
        self.assertEqual(receipt["claims"]["order.status"], "dispatched")
        self.assertNotIn("foreign", receipt["evidence_ids"])

    def test_other_kb_in_same_client_is_excluded(self):
        foreign = self.unit("foreign", {"order.status": "cancelled"},
                            kb="other_kb")
        with self.assertRaises(GatewayError):
            self.compile([foreign])

    def test_unapproved_source_is_excluded(self):
        private = self.unit("private", {"order.status": "dispatched"},
                            source="unapproved")
        with self.assertRaises(GatewayError):
            self.compile([private])

    def test_unauthorized_requested_claim_is_rejected(self):
        with self.assertRaises(GatewayError):
            self.compile([self.status], ("unknown.claim",))

    def test_stale_source_is_rejected(self):
        self.now = 101
        old = replace(self.status, observed_at=0)
        with self.assertRaises(GatewayError):
            self.compile([old])

    def test_conflicting_authorized_values_do_not_choose_convenient_answer(self):
        alternative = self.unit(
            "contradiction", {"order.status": "cancelled"}, source="backup"
        )
        with self.assertRaises(GatewayError):
            self.compile([self.status, alternative])

    def test_new_conflicting_source_invalidates_a_previously_valid_receipt(self):
        compiler, store, policy = self.compiler([self.status])
        receipt = compiler.compile(self.scope, policy, ["order.status"])
        store.put(self.unit("new_conflict", {"order.status": "returned"}, source="backup"))
        with self.assertRaises(GatewayError):
            compiler.verify(receipt, self.scope, policy)

    def test_eighteen_candidate_budget_is_explicit(self):
        candidates = [self.unit("unit-"+str(i), {"order.status": "dispatched"})
                      for i in range(19)]
        with self.assertRaises(GatewayError):
            self.compile(candidates)

    def test_integer_and_boolean_are_not_equivalent_claim_values(self):
        first = self.unit("integer", {"return.days": 1}, source="policies")
        second = self.unit("boolean", {"return.days": True}, source="backup")
        with self.assertRaises(GatewayError):
            self.compile([first, second], ("return.days",))

    def test_signature_rejects_modified_answer_value(self):
        compiler, _, receipt = self.compile([self.status])
        changed = deepcopy(receipt)
        changed["claims"]["order.status"] = "cancelled"
        with self.assertRaises(GatewayError):
            compiler.verify(changed, self.scope, self.policy)

    def test_signature_rejects_modified_evidence_identifier(self):
        compiler, _, receipt = self.compile([self.status])
        changed = deepcopy(receipt)
        changed["evidence_ids"] = ["invented"]
        with self.assertRaises(GatewayError):
            compiler.verify(changed, self.scope, self.policy)

    def test_policy_revision_invalidates_old_receipt(self):
        compiler, _, receipt = self.compile([self.status])
        with self.assertRaises(GatewayError):
            compiler.verify(receipt, self.scope, replace(self.policy, version="v2"))

    def test_request_scope_is_bound_to_receipt(self):
        compiler, _, receipt = self.compile([self.status])
        for scope in (
            replace(self.scope, request_id="other-request"),
            replace(self.scope, principal_id="other-principal"),
            replace(self.scope, tenant_id="other"),
            replace(self.scope, kb_id="other"),
        ):
            with self.subTest(scope=scope):
                with self.assertRaises(GatewayError):
                    compiler.verify(receipt, scope, self.policy)

    def test_source_revocation_invalidates_receipt(self):
        compiler, store, receipt = self.compile([self.status])
        store.revoke("status")
        with self.assertRaises(GatewayError):
            compiler.verify(receipt, self.scope, self.policy)

    def test_version_change_invalidates_original_receipt(self):
        compiler, store, receipt = self.compile([self.status])
        store.put(replace(self.status, version="v2"))
        with self.assertRaises(GatewayError):
            compiler.verify(receipt, self.scope, self.policy)

    def test_value_change_without_version_change_invalidates_digest(self):
        compiler, store, receipt = self.compile([self.status])
        store.put(replace(self.status, facts={"order.status": "cancelled"}))
        with self.assertRaises(GatewayError):
            compiler.verify(receipt, self.scope, self.policy)

    def test_rebase_can_repair_revoked_witness_without_changing_claim(self):
        backup = self.unit("backup", {"order.status": "dispatched"},
                           source="backup", cost=4)
        compiler, store, receipt = self.compile([self.status, backup])
        self.assertEqual(receipt["evidence_ids"], ["status"])
        store.revoke("status")
        repaired = compiler.rebase(receipt, self.scope, self.policy)
        self.assertEqual(repaired["claims"], receipt["claims"])
        self.assertEqual(repaired["evidence_ids"], ["backup"])
        self.assertTrue(compiler.verify(repaired, self.scope, self.policy))

    def test_rebase_rejects_changed_current_fact(self):
        compiler, store, receipt = self.compile([self.status])
        store.put(replace(self.status, version="v2",
                          facts={"order.status": "cancelled"}))
        with self.assertRaises(AnswerChanged):
            compiler.rebase(receipt, self.scope, self.policy)

    def test_rebase_does_not_resurrect_tampered_receipt(self):
        backup = self.unit("backup", {"order.status": "dispatched"},
                           source="backup", cost=4)
        compiler, store, receipt = self.compile([self.status, backup])
        store.revoke("status")
        tampered = deepcopy(receipt)
        tampered["claims"]["order.status"] = "cancelled"
        with self.assertRaises(GatewayError):
            compiler.rebase(tampered, self.scope, self.policy)

    def test_expired_receipt_is_not_verified(self):
        compiler, _, receipt = self.compile([self.status])
        self.now = 250
        with self.assertRaises(GatewayError):
            compiler.verify(receipt, self.scope, self.policy)

    def test_store_snapshot_does_not_follow_input_dict_mutation(self):
        facts = {"order.status": "dispatched"}
        unit = self.unit("mutable-input", facts)
        compiler, store, receipt = self.compile([unit])
        facts["order.status"] = "cancelled"
        self.assertTrue(compiler.verify(receipt, self.scope, self.policy))
        self.assertEqual(receipt["claims"]["order.status"], "dispatched")

    def test_nan_fact_is_rejected(self):
        with self.assertRaises((GatewayError, ValueError, TypeError)):
            self.compile([self.unit("nan", {"return.days": float("nan")})],
                         ("return.days",))

    def test_infinite_fact_is_rejected(self):
        with self.assertRaises((GatewayError, ValueError, TypeError)):
            self.compile([self.unit("infinite", {"return.days": float("inf")})],
                         ("return.days",))

    def test_empty_claim_contract_is_rejected(self):
        with self.assertRaises(GatewayError):
            self.compile([self.status], ())


    def test_unit_with_an_unauthorized_extra_fact_is_ineligible(self):
        unit = self.unit("broad-secret", {
            "order.status": "dispatched", "private.contact": "fictional"
        })
        with self.assertRaises(GatewayError):
            self.compile([unit])

    def test_changed_policy_definition_invalidates_same_version_receipt(self):
        compiler, _, receipt = self.compile([self.status])
        changed = replace(self.policy, allowed_sources=("policies",))
        with self.assertRaises(GatewayError):
            compiler.verify(receipt, self.scope, changed)

    def test_rebase_cannot_cross_client_scope(self):
        compiler, _, receipt = self.compile([self.status])
        with self.assertRaises(GatewayError):
            compiler.rebase(
                receipt, replace(self.scope, tenant_id="other"), self.policy
            )


if __name__ == "__main__":
    unittest.main()
