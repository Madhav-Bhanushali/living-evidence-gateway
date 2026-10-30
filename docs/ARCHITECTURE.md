# Architecture

## Components

| Component | Responsibility |
| --- | --- |
| Application backend | Hold its API key and send questions |
| Registry | Resolve client identity and KB ownership |
| Catalog | Describe permitted document collections and database tools |
| Policy layer | Validate selected sources, identifiers, fields and limits |
| Document pipeline | Extract, review, version and index source text |
| Database connector | Execute registered parameterized read-only queries |
| Model adapter | Request plans and grounded answers |
| Evidence validator | Recheck scope, versions, references and completeness |

A KB is the logical knowledge collection owned by a client. It can contain several document collections and approved database sources. A source ID is an identifier, not an access grant.

## Client setup

```mermaid
flowchart TD
    Register[Register client] --> KB[Assign owned KB]
    KB --> Key[Generate API key]
    Key --> Backend[Provision secret to application backend]
    KB --> Sources[Register document collections and database tools]
    Sources --> Catalog[Describe purpose and required parameters]
    Catalog --> Policy[Define server-owned access profile]
    Policy --> Evaluate[Test ownership, retrieval and answer correctness]
    Evaluate --> Enable[Enable approved client access]
```

Client and KB identifiers are assigned during onboarding. API keys are randomly generated; the registry stores hashes. The gateway derives the client from the verified key. A caller cannot establish identity by supplying another client's ID in a question.

## Question flow

```mermaid
sequenceDiagram
    participant App as Application backend
    participant GW as Gateway
    participant Reg as Registry and catalog
    participant Model as Language model
    participant Search as Document retriever
    participant DB as Database connector
    App->>GW: API key header, KB ID and question
    GW->>Reg: Verify identity, ownership and conversation
    Reg-->>GW: Scope, catalog and access policy
    GW->>Model: Question and permitted catalog
    Model-->>GW: Proposed structured retrieval plan
    Note over GW: Validate sources, tools, parameters and budgets
    opt Document facts
        GW->>Search: Search within approved source scope
        Search-->>GW: Versioned passages and provenance
    end
    opt Current database facts
        GW->>DB: Registered tool and validated parameters
        DB-->>GW: Typed results and observation time
    end
    Note over GW: Minimize fields and revalidate evidence
    GW->>Model: Question and permitted evidence
    Model-->>GW: Answer and evidence references
    Note over GW: Check references and access again
    GW-->>App: Answer, references and completeness
```

The first model call proposes retrieval; gateway code executes it. The model receives neither the application's API key nor source database credentials.

## Document ingestion

```mermaid
flowchart TD
    Upload[Assign client, KB and source ownership] --> Original[Preserve original and content hash]
    Original --> Native{Usable native text?}
    Native -->|Yes| Extract[Extract text and page metadata]
    Native -->|No| OCR[Run OCR on scanned pages]
    OCR --> Review[Review extraction against original]
    Review --> Decision{Approved exact version?}
    Decision -->|No| Pending[Keep pending]
    Decision -->|Yes| Passages[Create passages and heading paths]
    Extract --> Passages
    Passages --> Index[Publish searchable version atomically]
```

OCR happens during ingestion. An answer request searches approved extracted text. Replacing or revoking a document must invalidate its previous evidence.

## Optional table-of-contents routing

```mermaid
flowchart LR
    Scope[Filter client, KB, sources and active versions] --> TOC[Build heading and section catalog]
    TOC --> Select[Model proposes section IDs]
    Select --> Validate[Check IDs against permitted catalog]
    Validate --> Fetch[Fetch exact versioned sections]
    Fetch --> Evidence[Revalidate permitted evidence]
```

The selector receives structure metadata rather than every section body. Empty selection must not silently broaden access. Large structures require hierarchical batching and explicit budgets. This adds a model call for document questions; it does not replace live database tools or OCR.

## Database access

Use fixed, registered SELECT queries and parameter binding. Prefer non-owner, non-superuser database identities with minimal SELECT privileges. Use verified read-only transactions, schema-qualified relations, approved SQL syntax/functions, timeouts and row/byte limits.

Dynamic facts are fetched at question time. Multiple connections and different sources do not provide a universal atomic snapshot. Results must distinguish zero rows, NULL, unavailable sources and truncated lists.

## Conversation and presentation

User history can resolve unambiguous references; it is not authoritative evidence for current records. New topics should not inherit identifiers from unrelated turns, and assistant-invented IDs cannot authorize retrieval.

Long result sets can be rendered as structured tables with a concise answer. If a result is bounded, show its partial status. A slow-motion flow viewer can replay captured events after a real request; replay pacing must be distinguished from actual runtime.
