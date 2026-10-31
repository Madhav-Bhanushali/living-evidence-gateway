# Reproducible synthetic experiment

Run:

```bash
python -m witness_gateway.benchmark
python -m witness_gateway.demo
python -m unittest discover -s tests -v
```

A recorded run is included in [synthetic_results.json](../benchmarks/synthetic_results.json). Times vary by machine and load; correctness checks and generated cases are deterministic.

## Workload

One hundred fictional typed-claim tasks, with a mix of atomic facts, larger records, alternate witnesses and identically named facts in another tenant. Required claim values are known by construction.

The comparator collects every evidence unit passing ownership, source, field and freshness filtering. It intentionally lacks minimization, composition restrictions and bundle budgets. It is a transparent simple comparator, not an optimized RAG system.

The compiler uses the same typed evidence and policies, then selects a sufficient, allowed minimum-cost subset. The synthetic suite checks exact expected claim values and configured minimum cost.

## Recorded results

| Measurement | Collect-all comparator | Compiler |
| --- | ---: | ---: |
| Evidence units selected | 798 | 299 |
| Exposed fact occurrences | 1,497 | 299 |
| Serialized selected-fact payload bytes | 61,342 | 12,600 |
| Cases with exact expected claim values | Not a model-answer evaluation | 100 / 100 |
| Same-claim repairs after witness revocation | Not implemented in comparator | 100 / 100 |

The compiler selected **80.03% fewer fact occurrences** and **79.46% fewer serialized payload bytes** on these constructed tasks. Duplicated facts count as occurrences, so these are not counts of distinct sensitive facts.

Five hundred mutations were rejected, including altered claim content, mismatched scope, changed evidence versions, revoked evidence and changed underlying values. Separate composition checks verify that a forbidden joint tag set is blocked and an allowed alternative can be selected.

The program also reports compiler median/p95/max duration. These are local Python microbenchmarks; they are not model response times, database query times or production throughput measurements.

## What the experiment does not show

- It does not prove a new research algorithm or outperform published systems.
- It does not evaluate arbitrary natural-language interpretation, factual entailment or model hallucination.
- It does not measure database reads; all candidates are already in memory.
- Payload bytes are not model tokens, inference latency or real privacy leakage.
- The candidate set, fact keys, truth values, costs and sensitivity tags are trusted synthetic inputs.
- The exact search is capped at 18 eligible evidence units; no large-corpus scaling result is claimed.
- Receipt integrity does not establish source truth.
- No customer records, private schemas, credentials or operational traces are used.

## How to challenge it

Change the costs, introduce competing permitted values, reduce budgets, revoke witnesses, modify source values, or change the policy version. The compiler should choose a different permitted bundle or reject the request rather than invent support.

Before real integration, evaluate extraction and entity mapping, source authority, concurrent update behavior, retention and key management. A deterministic typed-fact verifier is one component of a gateway, not a complete production security system.
