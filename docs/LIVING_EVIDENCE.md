# Living evidence: executable contracts

## Why repair evidence?

An answer can become unsafe even when its text has not changed: an evidence source may be revoked, superseded or corrected.

A citation string cannot resolve that lifecycle by itself. The prototype retains a signed binding between a structured claim contract and its permitted evidence. Rebase searches the current store for a new witness set. It returns a new receipt only if all original typed claim values remain identical.

This is dependency repair under a bounded contract, not semantic verification of arbitrary prose.

## API

```python
from witness_gateway.fixtures import example_system

compiler, store, scope, policy, required = example_system()

receipt = compiler.compile(scope, policy, required)
assert compiler.verify(receipt, scope, policy)

store.revoke("status_primary")
repaired = compiler.rebase(receipt, scope, policy)

assert repaired["claims"] == receipt["claims"]
assert compiler.verify(repaired, scope, policy)
```

Changing a claim value in the receipt without re-signing fails authentication. Changing a selected source version or content invalidates its old receipt. Changing the underlying fact prevents rebase from asserting the old answer as current.

## Typed claim contract

The prototype accepts explicit claim keys, such as `order/42.status`. Keys include entity context so that two records' status fields are not treated as interchangeable. Values are strict JSON values, with exact decimal values expressed as strings. It does not parse free-form questions into facts.

The caller-facing authentication layer is outside this library. The `Scope` instance must be created by trusted application code; constructing a dataclass is not authentication.

## Candidate selection

Before optimization, reject evidence with wrong tenant/KB ownership, unapproved sources or claim fields, future observation times or excessive source age.

Every required claim must have available, nonconflicting values. Among complete permitted subsets, optimize in this order:

1. Total configured disclosure cost.
2. Exposed fact occurrences.
3. Number of evidence units.
4. Stable evidence IDs for deterministic ties.

Enforce maximum cost and evidence count, and reject forbidden combinations of tags across the selected bundle.

The exact subset search is bounded to 18 eligible candidates. General set cover is not cheaply scalable; larger catalogs require a different candidate-generation and optimization strategy. Minimum cost is relative to the supplied candidate set and trusted cost annotations.

## Receipts

A receipt includes the exact scope, policy version and policy digest, requested claims, typed values, selected evidence IDs, versions, content digests, cost and creation time. An HMAC binds the receipt's contents to the issuer key.

HMAC is symmetric authentication, not a public-key signature or proof of truth. The issuer and verifier must trust each other. Anyone holding the key can produce receipts. Real key management, rotation, revocation and multi-process state consistency are outside the prototype.

## Verification and rebase

Verification rechecks the receipt's authenticity and current policy, then validates witnesses against current state. Evidence changes invalidate the old content binding even if a source forgot to increment its version.

Rebase authenticates the old receipt and scope without requiring the old witnesses to remain available. It recompiles under the current permitted evidence and compares typed claim values exactly. Missing, conflicting or changed facts cause rejection rather than silently modifying the old claim contract.

An expired receipt or changed policy does not receive an automatic repair bypass.

## Composition-aware privacy

The prototype can forbid a declared joint tag set—for example, identity plus region—even when each tag is individually allowed. It can choose a different sufficient bundle when available.

This is enforcement of explicit trusted annotations. It does not discover every inference a model might make or guarantee that no sensitive fact can be inferred.

## Boundaries

- All evidence is already in memory; lower selected payload does not imply fewer database reads.
- No large language model is called, so no claim about model accuracy, hallucinations or model latency is established.
- Policy metadata and source semantics must be correct.
- The in-memory store is a single-process snapshot, not an atomic distributed database.
- Contradictions cause abstention; no automatic authority ranking is inferred.
- Raw prose generation and its relationship to typed claims require separate integration and evaluation.
