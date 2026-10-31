"""Bounded evidence selection and rebasable, authenticated claim receipts.

This is a synthetic reference prototype, not a natural-language truth verifier.
The store, policies, clock and signing key belong to the trusted application.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
from types import MappingProxyType
from itertools import combinations
import hashlib
import hmac
import json
import math
import time


class GatewayError(ValueError):
    """The requested evidence or receipt does not satisfy the contract."""


class AnswerChanged(GatewayError):
    """Current admissible evidence no longer supports the old claim values."""


def _identifier(value, label="identifier"):
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise GatewayError("Invalid " + label)
    return value


def _sequence(values, label, allow_empty=False):
    if not isinstance(values, (tuple, list, set, frozenset)):
        raise GatewayError("Invalid " + label)
    result = tuple(values)
    if (not allow_empty and not result) or len(result) > 128:
        raise GatewayError("Invalid " + label)
    for value in result:
        _identifier(value, label)
    if len(set(result)) != len(result):
        raise GatewayError("Duplicate " + label)
    return result


def _jsonable(value, depth=0):
    """Produce strict JSON values; decimals should be explicit strings."""
    if depth > 16:
        raise GatewayError("JSON nesting budget exceeded")
    if value is None or type(value) in (str, bool, int):
        return value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise GatewayError("JSON object keys must be strings")
        return {key: _jsonable(item, depth + 1) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item, depth + 1) for item in value]
    raise GatewayError("Facts require exact JSON values; use strings for decimals")


def _canonical(value):
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _timestamp(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise GatewayError("Invalid timestamp")
    return value


@dataclass(frozen=True)
class Scope:
    tenant_id: str
    kb_id: str
    principal_id: str
    request_id: str

    def __post_init__(self):
        for value in (self.tenant_id, self.kb_id, self.principal_id, self.request_id):
            _identifier(value)

    def as_dict(self):
        return {"tenant_id": self.tenant_id, "kb_id": self.kb_id,
                "principal_id": self.principal_id, "request_id": self.request_id}


@dataclass(frozen=True)
class EvidenceUnit:
    evidence_id: str
    tenant_id: str
    kb_id: str
    source_id: str
    version: str
    facts: Mapping
    tags: tuple[str, ...] = ()
    disclosure_cost: int = 1
    observed_at: int = 0

    def __post_init__(self):
        for value in (self.evidence_id, self.tenant_id, self.kb_id,
                      self.source_id, self.version):
            _identifier(value)
        if not isinstance(self.facts, Mapping) or not self.facts or len(self.facts) > 128:
            raise GatewayError("Evidence requires bounded nonempty facts")
        for key in self.facts:
            _identifier(key, "claim key")
        facts = _jsonable(self.facts)
        if len(_canonical(facts).encode("utf-8")) > 65536:
            raise GatewayError("Evidence byte budget exceeded")
        object.__setattr__(self, "facts", _freeze(facts))
        object.__setattr__(self, "tags", _sequence(self.tags, "tag", allow_empty=True))
        if type(self.disclosure_cost) is not int or self.disclosure_cost < 0:
            raise GatewayError("Invalid disclosure cost")
        _timestamp(self.observed_at)

    def as_dict(self):
        return {"evidence_id": self.evidence_id, "tenant_id": self.tenant_id,
                "kb_id": self.kb_id, "source_id": self.source_id,
                "version": self.version, "facts": _jsonable(self.facts),
                "tags": list(self.tags), "disclosure_cost": self.disclosure_cost,
                "observed_at": self.observed_at}


@dataclass(frozen=True)
class Policy:
    policy_id: str
    version: str
    allowed_sources: tuple[str, ...]
    allowed_claims: tuple[str, ...]
    forbidden_tag_sets: tuple[tuple[str, ...], ...] = ()
    max_cost: int = 100
    max_units: int = 8
    max_age: int = 3600

    def __post_init__(self):
        _identifier(self.policy_id)
        _identifier(self.version)
        object.__setattr__(self, "allowed_sources",
                           _sequence(self.allowed_sources, "source"))
        object.__setattr__(self, "allowed_claims",
                           _sequence(self.allowed_claims, "claim key"))
        if not isinstance(self.forbidden_tag_sets, (tuple, list)) or len(self.forbidden_tag_sets) > 64:
            raise GatewayError("Invalid forbidden tag combinations")
        combinations_ = tuple(_sequence(group, "forbidden tag")
                              for group in self.forbidden_tag_sets)
        object.__setattr__(self, "forbidden_tag_sets", combinations_)
        if type(self.max_cost) is not int or self.max_cost < 0:
            raise GatewayError("Invalid disclosure budget")
        if type(self.max_units) is not int or not 1 <= self.max_units <= 18:
            raise GatewayError("Invalid unit budget")
        if type(self.max_age) is not int or self.max_age < 0:
            raise GatewayError("Invalid freshness budget")

    def as_dict(self):
        return {"policy_id": self.policy_id, "version": self.version,
                "allowed_sources": sorted(self.allowed_sources),
                "allowed_claims": sorted(self.allowed_claims),
                "forbidden_tag_sets": sorted(sorted(group) for group in self.forbidden_tag_sets),
                "max_cost": self.max_cost, "max_units": self.max_units,
                "max_age": self.max_age}


class Store:
    """Trusted in-memory active evidence snapshot. It contains no connectors."""
    def __init__(self, units=()):
        self._units = {}
        for unit in units:
            if unit.evidence_id in self._units:
                raise GatewayError("Duplicate evidence ID")
            self.put(unit)

    def put(self, unit):
        if not isinstance(unit, EvidenceUnit):
            raise GatewayError("Expected an EvidenceUnit")
        # Facts/tags are already defensively frozen by the dataclass.
        self._units[unit.evidence_id] = unit

    def revoke(self, evidence_id):
        _identifier(evidence_id)
        self._units.pop(evidence_id, None)

    def get(self, evidence_id):
        return self._units.get(evidence_id)

    def units(self):
        return tuple(self._units[key] for key in sorted(self._units))


class Compiler:
    """Exact selection for at most 18 eligible evidence units.

    Objective: minimum total configured disclosure cost, then minimum exposed
    fact occurrences, then minimum units, then deterministic evidence IDs.
    Costs and sensitivity tags are trusted annotations, not measured leakage.
    """
    RECEIPT_FIELDS = frozenset({
        "scope", "policy_id", "policy_version", "policy_digest",
        "required_claims", "claims", "evidence_ids", "versions",
        "evidence_digests", "cost", "created_at", "signature",
    })

    def __init__(self, store, signing_key, clock=time.time):
        if not isinstance(store, Store):
            raise GatewayError("Expected a Store")
        if not isinstance(signing_key, bytes) or len(signing_key) < 16:
            raise GatewayError("Signing key must contain at least 16 bytes")
        if not callable(clock):
            raise GatewayError("Clock must be callable")
        self.store, self._key, self.clock = store, signing_key, clock

    def _now(self):
        # Receipt times use integer seconds; future source times are not accepted.
        return int(_timestamp(self.clock()))

    def _admissible(self, unit, scope, policy, now):
        return ((unit.tenant_id, unit.kb_id) == (scope.tenant_id, scope.kb_id)
                and unit.source_id in policy.allowed_sources
                and set(unit.facts) <= set(policy.allowed_claims)
                and 0 <= now - unit.observed_at <= policy.max_age)

    @staticmethod
    def _composition_allowed(units, policy):
        tags = set(tag for unit in units for tag in unit.tags)
        return not any(set(group) <= tags for group in policy.forbidden_tag_sets)

    def _sign(self, payload):
        return hmac.new(self._key, _canonical(payload).encode("utf-8"),
                        hashlib.sha256).hexdigest()

    def _authenticate(self, receipt, scope, policy):
        if not isinstance(scope, Scope) or not isinstance(policy, Policy):
            raise GatewayError("Trusted scope and policy required")
        if not isinstance(receipt, dict) or set(receipt) != self.RECEIPT_FIELDS:
            raise GatewayError("Invalid receipt shape")
        signature = receipt["signature"]
        payload = {key: value for key, value in receipt.items() if key != "signature"}
        if not isinstance(signature, str) or not hmac.compare_digest(signature, self._sign(payload)):
            raise GatewayError("Invalid receipt signature")
        if receipt["scope"] != scope.as_dict():
            raise GatewayError("Receipt scope mismatch")
        if (receipt["policy_id"] != policy.policy_id
                or receipt["policy_version"] != policy.version
                or receipt["policy_digest"] != _digest(policy.as_dict())):
            raise GatewayError("Receipt policy mismatch")
        created = receipt["created_at"]
        if type(created) is not int or not 0 <= self._now() - created <= policy.max_age:
            raise GatewayError("Receipt expired or has a future timestamp")
        return payload

    def compile(self, scope, policy, required_claims):
        if not isinstance(scope, Scope) or not isinstance(policy, Policy):
            raise GatewayError("Trusted scope and policy required")
        required = tuple(sorted(_sequence(required_claims, "required claim")))
        if not set(required) <= set(policy.allowed_claims):
            raise GatewayError("Requested claim is outside policy")
        now = self._now()
        eligible = [unit for unit in self.store.units()
                    if self._admissible(unit, scope, policy, now)
                    and set(unit.facts).intersection(required)]
        if len(eligible) > 18:
            raise GatewayError("Exact-search candidate budget exceeded (18)")
        if not eligible:
            raise GatewayError("No admissible evidence")
        # Ambiguous current source values fail closed rather than optimizing toward
        # whichever source happens to be cheaper.
        values = {}
        for claim in required:
            by_value = {_canonical(unit.facts[claim]): _jsonable(unit.facts[claim])
                        for unit in eligible if claim in unit.facts}
            if not by_value:
                raise GatewayError("Insufficient evidence for " + claim)
            if len(by_value) != 1:
                raise GatewayError("Conflicting admissible evidence for " + claim)
            values[claim] = next(iter(by_value.values()))
        best = None
        best_units = None
        required_set = set(required)
        for size in range(1, min(policy.max_units, len(eligible)) + 1):
            for selected in combinations(eligible, size):
                cost = sum(unit.disclosure_cost for unit in selected)
                if cost > policy.max_cost or (best is not None and cost > best[0]):
                    continue
                keys = {key for unit in selected for key in unit.facts}
                if not required_set <= keys or not self._composition_allowed(selected, policy):
                    continue
                ids = tuple(unit.evidence_id for unit in selected)
                objective = (cost, sum(len(unit.facts) for unit in selected), size, ids)
                if best is None or objective < best:
                    best, best_units = objective, selected
        if best_units is None:
            raise GatewayError("No complete evidence bundle satisfies privacy and budgets")
        receipt = {
            "scope": scope.as_dict(), "policy_id": policy.policy_id,
            "policy_version": policy.version, "policy_digest": _digest(policy.as_dict()),
            "required_claims": list(required), "claims": values,
            "evidence_ids": [unit.evidence_id for unit in best_units],
            "versions": {unit.evidence_id: unit.version for unit in best_units},
            "evidence_digests": {unit.evidence_id: _digest(unit.as_dict()) for unit in best_units},
            "cost": best[0], "created_at": now,
        }
        receipt["signature"] = self._sign(receipt)
        return receipt

    def verify(self, receipt, scope, policy):
        self._authenticate(receipt, scope, policy)
        required = _sequence(receipt["required_claims"], "required claim")
        ids = _sequence(receipt["evidence_ids"], "evidence ID")
        if not set(required) <= set(policy.allowed_claims) or set(receipt["claims"]) != set(required):
            raise GatewayError("Receipt claim contract mismatch")
        if len(ids) > policy.max_units:
            raise GatewayError("Receipt unit budget exceeded")
        if set(receipt["versions"]) != set(ids) or set(receipt["evidence_digests"]) != set(ids):
            raise GatewayError("Receipt evidence metadata mismatch")
        units, now = [], self._now()
        for evidence_id in ids:
            unit = self.store.get(evidence_id)
            if unit is None or not self._admissible(unit, scope, policy, now):
                raise GatewayError("Evidence revoked, stale or outside scope")
            if (unit.version != receipt["versions"][evidence_id]
                    or _digest(unit.as_dict()) != receipt["evidence_digests"][evidence_id]):
                raise GatewayError("Evidence version or content changed")
            units.append(unit)
        cost = sum(unit.disclosure_cost for unit in units)
        if type(receipt["cost"]) is not int or cost != receipt["cost"] or cost > policy.max_cost:
            raise GatewayError("Receipt disclosure budget mismatch")
        if not self._composition_allowed(units, policy):
            raise GatewayError("Forbidden evidence composition")
        # New conflicting admissible evidence invalidates old receipts too;
        # checking only the originally selected subset would miss corrections.
        for current in self.store.units():
            if not self._admissible(current, scope, policy, now):
                continue
            for claim in required:
                if (claim in current.facts and
                        _canonical(current.facts[claim]) != _canonical(receipt["claims"][claim])):
                    raise GatewayError("Conflicting current evidence invalidates the claim")
        for claim in required:
            witnesses = [unit.facts[claim] for unit in units if claim in unit.facts]
            if not witnesses or any(_canonical(value) != _canonical(receipt["claims"][claim])
                                    for value in witnesses):
                raise GatewayError("Claim is not supported by its witnesses")
        return True

    def rebase(self, receipt, scope, policy):
        # Validate authenticity and original scope/policy/age, but intentionally
        # do not require old witnesses to still be active.
        self._authenticate(receipt, scope, policy)
        current = self.compile(scope, policy, receipt["required_claims"])
        if _canonical(current["claims"]) != _canonical(receipt["claims"]):
            raise AnswerChanged("Current evidence changes the answer; old answer must be invalidated")
        self.verify(current, scope, policy)
        return current
