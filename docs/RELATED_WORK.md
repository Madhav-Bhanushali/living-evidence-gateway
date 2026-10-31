# Related work and contribution boundary

This project is a new implementation of an engineering experiment. It is not presented as a new retrieval algorithm, a formal privacy proof, a reproduction of the papers below, or a claim of being the first system with evidence receipts.

## Minimal sufficient evidence

[Minimal Evidence Group Identification for Claim Verification](https://aclanthology.org/2025.trustnlp-main.8/) studies identifying nonredundant groups of evidence and relates the problem to set cover. Our bounded typed-fact optimizer uses a familiar combinatorial formulation; minimum evidence selection itself is not new.

## Counterfactual evidence analysis

[RAGE Against the Machine: Retrieval-Augmented LLM Explanations](https://arxiv.org/abs/2405.13000) analyzes how removing retrieved context can change model answers. Our mutation tests exercise a deterministic receipt verifier, not an LLM attribution method or a reproduction of RAGE.

## Context sufficiency and abstention

[Sufficient Context: A New Lens on Retrieval Augmented Generation Systems](https://research.google/pubs/sufficient-context-a-new-lens-on-retrieval-augmented-generation-systems/) examines whether retrieved context is sufficient. This prototype's sufficiency notion is narrower: exact coverage of explicitly requested typed claim keys under a trusted policy.

## Structure-aware document retrieval

[STAIR](https://arxiv.org/abs/2609.03874) explores table-of-contents structure for generative retrieval. The living-evidence compiler does not implement STAIR training and does not require a document retriever.

## What this repository contributes

An inspectable, executable combination of:

- Policy-scoped typed evidence selection with configured disclosure costs.
- Explicit restrictions on combinations of sensitivity tags.
- Authenticated receipts bound to policy and evidence versions.
- Repairing a revoked witness set only when the original claim values remain unchanged.
- Reproducible synthetic benchmarks and adversarial tests.

Related systems in provenance, truth maintenance, policy enforcement and authenticated data structures contain overlapping ideas. A broader literature review would be needed before making any research-novelty claim.
