"""Deterministic fictional benchmark for the bounded witness compiler.

No model, database, customer data or external network is used.
The baseline only applies ownership/source/field/freshness filtering; it does NOT
implement minimization, composition exclusions or bundle budgets.
"""
from __future__ import annotations

import argparse
import copy
from dataclasses import replace
import json
import math
from pathlib import Path
import statistics
import time

from .core import Compiler, EvidenceUnit, GatewayError, Policy, Scope, Store

NOW = 1000
FIXTURE_KEY = b"public-synthetic-benchmark-key-not-for-deployment"


def _case(case_id: int):
    width = 2 + case_id % 3
    tenant = f"fictional_company_{case_id}"
    scope = Scope(tenant, f"fictional_kb_{case_id}", "fictional_app", f"request_{case_id}")
    keys = [f"item/{case_id}/fact_{index}" for index in range(width)]
    facts = {key: f"synthetic_value_{case_id}_{index}" for index, key in enumerate(keys)}
    noise = {f"item/{case_id}/unused_{index}": f"unused_synthetic_{index}" for index in range(3)}
    units = []
    for index, key in enumerate(keys):
        for prefix, cost, source in [("primary", 1, "primary_records"), ("alternate", 2, "replica_records")]:
            units.append(EvidenceUnit(f"{prefix}_{index}", tenant, scope.kb_id, source,
                                      "v1", {key: facts[key]}, (), cost, NOW))
    units.extend([
        EvidenceUnit("broad", tenant, scope.kb_id, "broad_records", "v1",
                     {**facts, **noise}, (), width + 4, NOW),
        EvidenceUnit("noise", tenant, scope.kb_id, "broad_records", "v1",
                     noise, (), 2, NOW),
        EvidenceUnit("foreign", "unrelated_company", "unrelated_kb", "primary_records",
                     "v1", {keys[0]: "wrong_foreign_value"}, (), 1, NOW),
    ])
    policy = Policy("fictional_policy", "v1",
                    ("primary_records", "replica_records", "broad_records"),
                    tuple([*facts, *noise]), (), 100, 8, 3600)
    store = Store(units)
    compiler = Compiler(store, FIXTURE_KEY, clock=lambda: NOW)
    return compiler, store, scope, policy, keys, units, facts


def _filtered_collect_all(units, scope, policy):
    # A deliberately simple collect-all comparator, NOT an optimized RAG system.
    return [
        unit for unit in units
        if unit.tenant_id == scope.tenant_id and unit.kb_id == scope.kb_id
        and unit.source_id in policy.allowed_sources
        and set(unit.facts) <= set(policy.allowed_claims)
        and 0 <= NOW - unit.observed_at <= policy.max_age
    ]


def _payload_bytes(units):
    # A transparent serialization proxy, not a tokenizer or a database-read metric.
    return len(json.dumps([dict(unit.facts) for unit in units],
                          sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _rejects(call):
    try:
        call()
    except GatewayError:
        return True
    return False


def _percentile(values, percentile):
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, math.ceil(len(ordered) * percentile) - 1))]


def _composition_checks():
    scope = Scope("fictional_company", "fictional_kb", "fictional_app", "composition_request")
    policy = Policy("composition_policy", "v1", ("example_records",), ("claim/a", "claim/b"),
                    (("identity_hint", "region_hint"),), 20, 8, 3600)
    first = EvidenceUnit("identity", scope.tenant_id, scope.kb_id, "example_records",
                         "v1", {"claim/a": 1}, ("identity_hint",), 1, NOW)
    second = EvidenceUnit("region", scope.tenant_id, scope.kb_id, "example_records",
                          "v1", {"claim/b": 2}, ("region_hint",), 1, NOW)
    compiler = Compiler(Store([first, second]), FIXTURE_KEY, clock=lambda: NOW)
    individual_allowed = bool(compiler.compile(scope, policy, ["claim/a"]))
    individual_allowed = individual_allowed and bool(compiler.compile(scope, policy, ["claim/b"]))
    combination_rejected = _rejects(lambda: compiler.compile(scope, policy, ["claim/a", "claim/b"]))
    alternate = EvidenceUnit("approved_aggregate", scope.tenant_id, scope.kb_id,
                             "example_records", "v1", {"claim/a": 1, "claim/b": 2},
                             ("approved_summary",), 3, NOW)
    other = Compiler(Store([first, second, alternate]), FIXTURE_KEY, clock=lambda: NOW)
    repaired_selection = other.compile(scope, policy, ["claim/a", "claim/b"])
    return {
        "individually_permitted_units_available": individual_allowed,
        "forbidden_joint_disclosure_rejected": combination_rejected,
        "approved_alternative_selected": repaired_selection["evidence_ids"] == ["approved_aggregate"],
        "limit": "Tags and exclusions are trusted policy metadata; no automatic inference of all privacy risks.",
    }


def run_benchmark(cases=100):
    if type(cases) is not int or not 1 <= cases <= 100:
        raise ValueError("Benchmark case count must be between 1 and 100")
    totals = {"baseline_units": 0, "selected_units": 0, "baseline_fact_cells": 0,
              "selected_fact_cells": 0, "baseline_payload_bytes": 0,
              "selected_payload_bytes": 0, "exact_claim_cases": 0,
              "minimum_declared_cost_cases": 0, "rebases_preserving_claims": 0,
              "mutations_attempted": 0, "mutations_rejected": 0}
    latencies = []
    for case_id in range(cases):
        compiler, store, scope, policy, keys, units, expected = _case(case_id)
        baseline = _filtered_collect_all(units, scope, policy)
        started = time.perf_counter()
        receipt = compiler.compile(scope, policy, keys)
        latencies.append((time.perf_counter() - started) * 1000)
        compiler.verify(receipt, scope, policy)
        selected = [store.get(identifier) for identifier in receipt["evidence_ids"]]
        totals["baseline_units"] += len(baseline)
        totals["selected_units"] += len(selected)
        totals["baseline_fact_cells"] += sum(len(unit.facts) for unit in baseline)
        totals["selected_fact_cells"] += sum(len(unit.facts) for unit in selected)
        totals["baseline_payload_bytes"] += _payload_bytes(baseline)
        totals["selected_payload_bytes"] += _payload_bytes(selected)
        totals["exact_claim_cases"] += receipt["claims"] == expected
        # In this generated family, each primary witness costs one and covers one
        # required claim; every alternative is more expensive. The optimum is known.
        totals["minimum_declared_cost_cases"] += receipt["cost"] == len(keys)

        tampered = copy.deepcopy(receipt)
        tampered["claims"][keys[0]] = "invented"
        mutations = [
            lambda: compiler.verify(tampered, scope, policy),
            lambda: compiler.verify(receipt, replace(scope, tenant_id="unrelated_company"), policy),
        ]
        for mutation in mutations:
            totals["mutations_attempted"] += 1
            totals["mutations_rejected"] += _rejects(mutation)

        original = store.get("primary_0")
        store.put(replace(original, version="v2"))
        totals["mutations_attempted"] += 1
        totals["mutations_rejected"] += _rejects(lambda: compiler.verify(receipt, scope, policy))
        store.put(original)
        store.revoke("primary_0")
        totals["mutations_attempted"] += 1
        totals["mutations_rejected"] += _rejects(lambda: compiler.verify(receipt, scope, policy))
        rebased = compiler.rebase(receipt, scope, policy)
        compiler.verify(rebased, scope, policy)
        totals["rebases_preserving_claims"] += rebased["claims"] == receipt["claims"]

        # Remove the old-value broad witness, then change the sole remaining
        # witness for this claim. Repairing the old answer must now fail.
        store.revoke("broad")
        alternate = store.get("alternate_0")
        store.put(replace(alternate, version="v2", facts={keys[0]: "changed_source_value"}))
        totals["mutations_attempted"] += 1
        totals["mutations_rejected"] += _rejects(lambda: compiler.rebase(rebased, scope, policy))

    composition = _composition_checks()
    passed = (totals["exact_claim_cases"] == cases
              and totals["minimum_declared_cost_cases"] == cases
              and totals["rebases_preserving_claims"] == cases
              and totals["mutations_attempted"] == totals["mutations_rejected"]
              and all(composition[key] for key in (
                  "individually_permitted_units_available",
                  "forbidden_joint_disclosure_rejected",
                  "approved_alternative_selected")))
    return {
        "benchmark": "bounded synthetic living-evidence experiment",
        "case_count": cases,
        "all_checks_passed": passed,
        "baseline": {
            "name": "ownership/source/field/freshness-filtered collect-all",
            "does_not_implement": ["minimum-disclosure selection", "composition exclusions", "bundle budgets"],
            "fairness_note": "This is a transparent simple comparator, not an optimized RAG baseline.",
        },
        "results": {
            **totals,
            "fact_cell_reduction_percent": round(100 * (1 - totals["selected_fact_cells"] / totals["baseline_fact_cells"]), 2),
            "payload_byte_reduction_percent": round(100 * (1 - totals["selected_payload_bytes"] / totals["baseline_payload_bytes"]), 2),
            "compiler_latency_ms": {
                "median": round(statistics.median(latencies), 4),
                "p95": round(_percentile(latencies, .95), 4),
                "max": round(max(latencies), 4),
            },
        },
        "composition_checks": composition,
        "limits": [
            "All records, keys, companies and mutations are fictional.",
            "Claims are explicit structured keys and values, not unrestricted natural-language statements.",
            "Serialized payload bytes are not tokens, database reads, real privacy leakage or model latency.",
            "Declared cost is a trusted policy input, not an inferred privacy guarantee.",
            "Exact selection is bounded by the compiler candidate limit, not a scalable global optimality claim.",
            "No model quality, production throughput or real-corpus accuracy is measured.",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=int, default=100)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_benchmark(args.cases)
    rendered = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")
    print(rendered)
    if not report["all_checks_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
