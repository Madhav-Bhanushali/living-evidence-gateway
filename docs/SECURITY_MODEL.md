# Security model

## Trust boundaries

The language model proposes operations; gateway code authorizes them. Retrieved documents, database strings and conversation text are data, not instructions that can grant access.

- Derive client identity from authenticated credentials.
- Verify KB ownership before model calls or source retrieval.
- Apply tenant and source filters before ranking, embedding and cache lookup.
- Resolve credentials and connections only from server-owned configuration.
- Restrict model plans to registered tools and declared parameters.
- Bind authorized bank, organization or tenant scope on the server where data is shared.
- Require identifiers for entity lookups; explicitly authorize aggregates separately.
- Select minimal columns in SQL and minimize results before generation.
- Recheck scope, document publication and OCR approval after model calls.
- Isolate conversation ownership and version reusable caches.

A model-supplied tenant or bank ID is not authorization. A shared model does not grant shared access to client data.

## Database least privilege

Use restricted runtime roles. Read-only transactions are an additional control, not a substitute for database privileges. A privileged account operating in a read-only session remains a privileged account.

Do not expose arbitrary generated SQL. Syntax validation, approved functions, connection privileges and query limits are complementary controls. Do not execute source stored procedures or external connectors by default.

Never infer business metrics from table names alone. Establish entity grain, join cardinality, status meanings, authoritative sources, time zones and freshness before enabling reports.

## Secrets and traces

API keys belong on application backends and in transport authentication, not browser bundles or model prompts. Source secrets remain in private runtime configuration.

Diagnostic viewers should be separately authorized, redact credentials, use bounded request-local capture and discard partial evidence after authorization or revalidation failures. Avoid persistent raw prompts, records and traces unless explicitly approved with retention and access policies.

Do not publish operational traces, customer records, infrastructure addresses, private catalogs or environment files as examples.

## Limits

Identifier anchoring does not prove that every retrieved fact is semantically necessary. Citation membership does not prove entailment, completeness or correct interpretation. Model selection can fail within permitted scope.

Test unsupported operations, ambiguities, paraphrases, identifier punctuation, stale history, revoked documents, OCR errors, unsafe SQL attempts, wrong tenant scope, source failures and result truncation. Report evaluation scope and failure rates without universal security or accuracy claims.
