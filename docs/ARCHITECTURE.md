# AURUM — Functional Architecture

**Version:** 0.1
**Status:** Initial functional architecture
**Current phase:** Phase 2 — Functional Architecture

---

# 1. Purpose

This document defines the functional architecture of AURUM.

Its purpose is to establish:

* major domains;
* domain responsibilities;
* ownership boundaries;
* interactions between domains;
* principal workflows;
* prohibited coupling.

This document intentionally avoids selecting implementation technologies.

Technical architecture will be defined later.

---

# 2. Architectural objective

AURUM must avoid repeating the main structural problem of previous systems:

> business logic, persistence, user interface, SAT integration, file handling, accounting rules, and reconciliation all living together.

The new architecture must make each major responsibility explicit.

Conceptually:

```text
                         AURUM
                           │
                     APPLICATION
                           │
       ┌───────────────────┼────────────────────┐
       │                   │                    │
       ▼                   ▼                    ▼
   CFDI CORE          SAT CENTER        SIF / ACCOUNTING
       │                   │                    │
       ├──────────┐        │        ┌───────────┤
       ▼          ▼        ▼        ▼           ▼
 DOCUMENTS   CLASSIFICATION       POLICIES   MOVEMENTS
       │                            │
       └──────────────┬─────────────┘
                      ▼
                RECONCILIATION
                      │
             ┌────────┴─────────┐
             ▼                  ▼
      INFERENCE ENGINE      RISK ENGINE
             │                  │
             └────────┬─────────┘
                      ▼
              HUMAN DECISIONS
                      │
                      ▼
                  AUDIT
```

The user interface, CLI, automations, N8N, and future Lu integration must consume these capabilities rather than implement them themselves.

---

# 3. Architectural principles

## 3.1 Domain ownership

Every important concept must have one primary owner.

Examples:

* CFDI identity → CFDI Core.
* SAT status → SAT Center.
* Policy → Accounting Core.
* CFDI-policy relationship → Reconciliation.
* Policy candidate score → Inference Engine.
* Risk → Risk Engine.

This avoids duplicated logic.

---

## 3.2 No business logic in UI

The UI may:

* collect user input;
* display information;
* call application operations;
* display errors;
* trigger actions.

The UI must not:

* parse CFDI;
* classify fiscal documents;
* calculate inference scores;
* query SAT directly;
* create accounting relationships directly;
* execute raw business SQL.

---

## 3.3 Source data and derived data are different

AURUM must distinguish:

```text
SOURCE EVIDENCE
     ↓
STRUCTURED FACTS
     ↓
OBSERVATIONS
     ↓
INFERENCES
     ↓
DECISIONS
```

Each layer has different semantics.

---

## 3.4 External systems remain external

SAT and SIF are external systems/sources.

AURUM integrates with them through adapters/connectors.

AURUM domain logic must not depend directly on:

* SOAP libraries;
* Excel libraries;
* file dialogs;
* network paths;
* SAT response quirks.

---

## 3.5 Reprocessing must be possible

Derived structured data must be reproducible from preserved original evidence where possible.

---

# 4. Major domains

AURUM is divided into the following functional domains:

```text
01 CFDI Core
02 Document Center
03 SAT Center
04 SIF / Accounting Core
05 Reconciliation
06 Inference Engine
07 Risk & Alerts
08 Parties / Suppliers
09 Reporting & Analytics
10 Jobs
11 Audit
12 Integrations
```

---

# 5. Domain 01 — CFDI Core

## 5.1 Purpose

The CFDI Core owns the fiscal meaning of a CFDI.

It is responsible for converting fiscal XML evidence into normalized fiscal facts.

---

## 5.2 Owns

The CFDI Core owns concepts such as:

* CFDI identity;
* UUID;
* CFDI version;
* issuer;
* receiver;
* fiscal dates;
* totals;
* currency;
* concepts;
* taxes;
* payroll;
* INE complement;
* CFDI relationships;
* fiscal classification;
* parser version;
* classification version.

---

## 5.3 Responsibilities

### Ingestion interpretation

Receive a valid source document reference from the application layer and determine whether it contains a supported CFDI.

### Identity

Extract the canonical UUID from:

```text
TimbreFiscalDigital/@UUID
```

### Parsing

Extract normalized fiscal information.

### Deduplication support

Provide canonical fiscal identity used by the persistence/application layer to detect duplicates.

### Classification

Classify fiscal documents using explicit, versioned rules.

### Reprocessing

Allow a preserved source XML to be interpreted again by a newer parser or ruleset.

---

## 5.4 Does not own

CFDI Core must not own:

* physical file storage;
* SAT network communication;
* current SAT status;
* SIF import;
* accounting policies;
* policy matching;
* risk workflow;
* UI rendering.

---

# 6. Domain 02 — Document Center

## 6.1 Purpose

The Document Center manages physical and logical documents associated with AURUM records.

---

## 6.2 Owns

* original XML;
* original PDF;
* generated PDF;
* acknowledgement;
* SIF evidence file;
* metadata file;
* hashes;
* content integrity;
* file metadata;
* storage references.

---

## 6.3 Responsibilities

* preserve immutable original files;
* calculate hashes;
* prevent silent file replacement;
* associate documents with business entities;
* retrieve documents;
* expose document metadata;
* abstract storage location.

---

## 6.4 Storage independence

The functional model must not care whether a file is stored in:

* local disk;
* network share;
* object storage;
* cloud storage.

That is an infrastructure decision.

---

## 6.5 Does not own

Document Center must not:

* interpret tax meaning;
* classify CFDI;
* validate SAT state;
* infer policies.

---

# 7. Domain 03 — SAT Center

## 7.1 Purpose

The SAT Center owns external SAT-related observations and acquisition workflows.

SAT is a first-class domain.

---

## 7.2 Owns

* SAT provider interactions;
* SAT observations;
* current SAT state projection;
* cancellation information;
* SAT status transitions;
* monitoring policy;
* SAT request lifecycle;
* massive download requests;
* packages;
* metadata acquisition.

---

## 7.3 SAT status model

SAT status is an observation over time.

Conceptually:

```text
CFDI
 │
 └── SAT OBSERVATIONS
      ├── observation 1
      ├── observation 2
      ├── observation 3
      └── ...
```

The latest valid observation may be used to derive the current status.

---

## 7.4 Technical failures are not fiscal states

AURUM must distinguish:

```text
SAT says CFDI not found
```

from:

```text
SAT could not be reached
```

Possible conceptual outcomes:

```text
SUCCESS
NOT_FOUND
INVALID_QUERY
NETWORK_ERROR
SAT_UNAVAILABLE
TIMEOUT
PROVIDER_ERROR
```

These must not be collapsed into a single fiscal state.

---

## 7.5 Monitoring

The SAT Center determines when a CFDI should be rechecked.

Possible factors:

* never checked;
* recently imported;
* high amount;
* linked policy;
* last validation age;
* previous state;
* recent state change;
* organizational configuration.

---

## 7.6 Status change event

Example:

```text
VIGENTE
   ↓
CANCELADO
```

The SAT Center detects the transition.

It may publish/emit an application event that the Risk Engine interprets.

SAT Center itself does not decide operational severity.

---

## 7.7 SAT acquisition

Future SAT download workflows belong here:

```text
request
→ verify
→ package
→ download
→ extract
→ hand document to ingestion workflow
```

Downloaded XML must enter the same CFDI Core pipeline as local XML.

There must not be a second SAT-specific parser.

---

## 7.8 Does not own

SAT Center does not own:

* CFDI parsing;
* policy reconciliation;
* risk severity;
* accounting logic;
* user alerts.

---

# 8. Domain 04 — SIF / Accounting Core

## 8.1 Purpose

The Accounting Core owns the accounting representation necessary to understand the context of a CFDI.

SIF is a first-class integration source for this domain.

---

## 8.2 Owns

* organizations;
* accounting entities;
* accounting contexts;
* accounting IDs;
* accounts;
* policies;
* policy movements;
* policy references;
* accounting periods;
* policy status;
* imported SIF accounting data.

---

## 8.3 Policy model

Conceptually:

```text
POLICY
│
├── identity
├── accounting context
├── period
├── type
├── subtype
├── dates
├── description
├── status
└── movements[]
```

---

## 8.4 Policy movement

A movement may contain:

```text
account
charge
credit
description
reference
line number
source identifiers
```

Money must eventually use exact decimal semantics.

---

## 8.5 SIF imports

SIF import is an adapter into Accounting Core.

Conceptually:

```text
SIF FILE
   ↓
SIF ADAPTER
   ↓
NORMALIZED ACCOUNTING MODEL
```

The rest of AURUM should not depend on SIF Excel column names.

---

## 8.6 Idempotency

Repeated import of the same accounting source should not blindly duplicate:

* policies;
* movements;
* links;
* evidence.

Import design must explicitly address idempotency.

---

## 8.7 Does not own

Accounting Core does not own:

* CFDI fiscal parsing;
* CFDI-policy inference;
* SAT state;
* operational risk severity.

---

# 9. Domain 05 — Reconciliation

## 9.1 Purpose

Reconciliation owns the known relationship between fiscal records and accounting records.

---

## 9.2 Core concept

```text
CFDI_POLICY_LINK
```

This is a domain entity, not just a join table.

---

## 9.3 Relationship types

Possible initial concepts:

```text
SIF_IMPORTED
UUID_CONFIRMED
MANUAL
INFERENCE_CONFIRMED
MIGRATED
```

The final names may evolve.

---

## 9.4 Relationship state

The system should be able to distinguish:

```text
PROPOSED
CONFIRMED
REJECTED
SUPERSEDED
```

where relevant.

---

## 9.5 Reconciliation responsibilities

Determine conditions such as:

* CFDI with no policy;
* policy with no CFDI;
* many CFDI for policy;
* many policies for CFDI;
* amount mismatch;
* missing SIF evidence;
* contradictory links.

---

## 9.6 Amount semantics

Reconciliation must not assume that:

```text
CFDI total == one accounting movement
```

The accounting representation may require:

* subtotal;
* taxes;
* retentions;
* multiple accounts;
* multiple movements;
* aggregates.

The Inference Engine may help explain complex matching.

---

## 9.7 Does not own

Reconciliation does not generate probabilistic candidates.

That belongs to the Inference Engine.

Reconciliation owns accepted/known accounting relationships.

---

# 10. Domain 06 — Inference Engine

## 10.1 Purpose

The Inference Engine proposes likely accounting relationships for unresolved CFDI.

It must answer:

> Which policy is the most plausible accounting destination for this CFDI, and what evidence supports that conclusion?

---

## 10.2 Input

The engine may consume:

* CFDI facts;
* accounting context;
* policies;
* movements;
* historical party/accounting information;
* known relationships;
* domain configuration.

---

## 10.3 Output

It produces:

```text
InferenceRun
InferenceCandidate[]
Evidence[]
Score breakdown
Confidence
Explanation data
```

It does not directly create a confirmed relationship.

---

## 10.4 Expert model

Possible experts:

```text
Context Expert
UUID Expert
Counterparty Expert
Temporal Expert
Amount Expert
Fiscal Account Expert
Payroll Expert
```

Future specialized experts may be added independently.

---

## 10.5 Evidence

Evidence should be structured.

Example:

```text
type = TEMPORAL_MATCH
value = 1 day
score = 14
```

Instead of only:

```text
"the dates are similar"
```

Human-readable explanation can be generated from structured evidence.

---

## 10.6 Versioning

Inference results should retain:

* engine version;
* expert versions where necessary;
* scoring configuration;
* timestamp.

---

## 10.7 Human decision

A candidate can later be:

* confirmed;
* rejected;
* ignored;
* replaced by another candidate.

The decision itself belongs to the application/reconciliation workflow and Audit.

---

## 10.8 Does not own

Inference Engine does not:

* silently modify accounting records;
* confirm relationships automatically without explicit policy;
* change original fiscal facts;
* modify SAT states.

---

# 11. Domain 07 — Risk & Alerts

## 11.1 Purpose

The Risk Engine identifies conditions requiring human or automated attention.

It is separate from inference.

---

## 11.2 Inputs

Risk evaluation may consume:

* CFDI state;
* SAT observations;
* SAT changes;
* accounting links;
* SIF evidence;
* reconciliation state;
* inference uncertainty;
* policy balance;
* organizational rules.

---

## 11.3 Example risks

```text
SAT_CANCELLED_WITH_ACCOUNTING_IMPACT
CFDI_WITHOUT_POLICY
POLICY_WITHOUT_CFDI
SIF_EVIDENCE_MISSING
SIF_EVIDENCE_WITHOUT_EFFECT
AMOUNT_MISMATCH
POLICY_UNBALANCED
SAT_STATUS_STALE
UNKNOWN_CLASSIFICATION
MISSING_ACCOUNTING_CONTEXT
AMBIGUOUS_INFERENCE
```

---

## 11.4 Severity

Conceptually:

```text
CRITICAL
HIGH
MEDIUM
LOW
INFO
```

Severity should be based on explicit rules.

---

## 11.5 Risk lifecycle

A risk may evolve:

```text
OPEN
ACKNOWLEDGED
IN_REVIEW
RESOLVED
DISMISSED
```

---

## 11.6 Does not own

Risk Engine does not own:

* SAT querying;
* CFDI parsing;
* accounting import;
* inference scoring.

It evaluates results produced by those domains.

---

# 12. Domain 08 — Parties / Suppliers

## 12.1 Purpose

Provide a reusable representation of fiscal counterparties.

---

## 12.2 Party concept

A party may act as:

* issuer;
* receiver;
* supplier;
* employee;
* customer;
* other fiscal role.

The core party identity should avoid unnecessary duplication.

---

## 12.3 Possible supplier enrichment

Later extensions may include:

* supplier classification;
* accounting profiles;
* associated accounts;
* operational frequency;
* review state;
* supporting documents.

Sensitive or unrelated information should not be added without a clear product reason.

---

## 12.4 Historical context

Party history may support inference.

Example:

```text
Supplier X
historically associated with:
- accounting entity A
- account role B
- policy pattern C
```

Historical facts must remain distinct from inferred recommendations.

---

# 13. Domain 09 — Reporting & Analytics

## 13.1 Purpose

Provide read-oriented operational and analytical views of AURUM information.

---

## 13.2 Responsibilities

* dashboard metrics;
* reconciliation coverage;
* SAT status distribution;
* changes detected;
* risk summaries;
* accounting statistics;
* inference statistics;
* exports.

---

## 13.3 Reporting must consume domain data

Reporting should not recreate business rules independently.

For example:

A report must not implement its own definition of "CFDI without policy".

It should consume the reconciliation state defined by Reconciliation.

---

## 13.4 Exports

Possible outputs:

* XLSX;
* CSV;
* PDF;
* future API exports.

Excel is an output format, not the AURUM data model.

---

# 14. Domain 10 — Jobs

## 14.1 Purpose

Represent long-running, asynchronous, scheduled, or batch work.

---

## 14.2 Example job types

```text
CFDI_INGESTION
CFDI_REPROCESS
SAT_VALIDATION
SAT_MONITORING
SAT_DOWNLOAD
SIF_IMPORT
LEDGER_IMPORT
INFERENCE_RUN
REPORT_EXPORT
PDF_RENDER
```

---

## 14.3 Responsibilities

Track:

* request;
* state;
* progress;
* attempts;
* failures;
* warnings;
* timestamps;
* item counts.

---

## 14.4 Job vs domain logic

Jobs orchestrate work.

They do not contain the business rules themselves.

Example:

```text
SATValidationJob
    ↓
calls SAT Center
```

The job should not implement SAT rules.

---

# 15. Domain 11 — Audit

## 15.1 Purpose

Provide traceability for important actions and state changes.

---

## 15.2 Audit examples

* document ingested;
* CFDI parsed;
* classification generated;
* SAT queried;
* SAT state changed;
* SIF imported;
* policy relationship imported;
* inference executed;
* candidate confirmed;
* candidate rejected;
* manual relationship created;
* risk resolved;
* record reprocessed.

---

## 15.3 Audit is not application logging

Application logs answer:

> What did the software process do?

Audit answers:

> What happened to this business record, when, why, and by whom?

Both may exist, but they serve different purposes.

---

# 16. Domain 12 — Integrations

## 16.1 Purpose

Expose AURUM capabilities safely to external clients and automation.

---

## 16.2 Future consumers

```text
Web UI
CLI
N8N
Lu
Future integrations
```

---

## 16.3 Integration rule

External clients consume stable application contracts.

They should not depend directly on:

* database schema;
* internal files;
* SAT libraries;
* Excel structures;
* internal domain implementation.

---

## 16.4 Lu boundary

Lu must remain external.

Conceptually:

```text
LU
 │
 ▼
AURUM APPLICATION/API
 │
 ├── CFDI
 ├── SAT
 ├── Accounting
 ├── Reconciliation
 ├── Inference
 ├── Risk
 └── Reports
```

AURUM must remain fully usable without Lu.

---

# 17. Cross-domain concept — Organization

AURUM should avoid institution-specific hardcoding.

An Organization may define context such as:

* RFC;
* fiscal identity;
* accounting structures;
* SIF settings;
* domain rules;
* monitoring policy.

Even if V1 exposes only one organization, the domain should not be designed around hardcoded global constants.

---

# 18. Cross-domain concept — Provenance

AURUM should preserve where important information came from.

Examples:

```text
CFDI_INE_COMPLEMENT
SIF_IMPORT
SAT_SOAP
SAT_METADATA
MANUAL
INFERENCE_ENGINE
LEGACY_MIGRATION
```

Provenance may apply to:

* facts;
* observations;
* relationships;
* classifications;
* decisions.

---

# 19. Cross-domain concept — Versioning

Versioning should be available for logic whose output may change over time.

Examples:

* parser;
* classifier;
* inference engine;
* risk rules;
* importer mapping.

This supports reproducibility.

---

# 20. Main workflow 1 — CFDI ingestion

```text
SOURCE
  │
  ▼
Document Center
  │
  ├── preserve bytes
  └── hash
  │
  ▼
CFDI Core
  │
  ├── validate XML
  ├── identify UUID
  ├── parse
  ├── classify
  └── normalize
  │
  ▼
Persistence
  │
  ▼
Audit
```

Later steps may trigger:

* SAT validation;
* reconciliation;
* inference;
* risk evaluation.

---

# 21. Main workflow 2 — SAT monitoring

```text
Monitoring policy
       │
       ▼
 Select CFDI due
       │
       ▼
   SAT Center
       │
       ▼
SAT observation
       │
       ▼
Compare previous
       │
       ├── no relevant change
       │
       └── status changed
                │
                ▼
             Risk Engine
                │
                ▼
          Attention Center
```

---

# 22. Main workflow 3 — SIF accounting import

```text
SIF / accounting source
          │
          ▼
      SIF Adapter
          │
          ▼
   Accounting Core
          │
   ┌──────┴──────┐
   ▼             ▼
Policies      Movements
   │
   ▼
Known evidence/UUID links
   │
   ▼
Reconciliation
```

---

# 23. Main workflow 4 — Reconciliation

```text
CFDI facts
   +
Accounting model
   +
Known links
   │
   ▼
Reconciliation
   │
   ├── resolved
   │
   └── unresolved
          │
          ▼
    Inference Engine
```

---

# 24. Main workflow 5 — Inference and human confirmation

```text
Unresolved CFDI
      │
      ▼
Candidate generation
      │
      ▼
Expert evaluation
      │
      ▼
Structured evidence
      │
      ▼
Rank candidates
      │
      ▼
Human review
   ┌──┼────────────┐
   ▼  ▼            ▼
confirm reject   unresolved
   │
   ▼
Reconciliation
   │
   ▼
Audit
```

---

# 25. Main workflow 6 — Risk evaluation

```text
DOMAIN EVENTS / STATES
        │
        ▼
    Risk Engine
        │
        ▼
     Risk record
        │
        ▼
Attention workflow
        │
        ▼
 Resolution / Audit
```

---

# 26. Dependency direction

Preferred conceptual dependency direction:

```text
External Infrastructure
        ↑
Adapters / Connectors
        ↑
Application Services
        ↑
Domain Logic
```

Domain logic must not depend on UI or specific external libraries.

---

# 27. Anti-patterns explicitly prohibited

AURUM should avoid:

## 27.1 SQL inside UI widgets

Bad:

```text
button click
→ SELECT ...
→ business decision
```

---

## 27.2 SAT calls directly from UI

Bad:

```text
SAT screen
→ SOAP library directly
```

Preferred:

```text
UI
→ application service
→ SAT Center
→ SAT provider
```

---

## 27.3 Business logic in database triggers

Database constraints may enforce integrity.

Core classification/inference rules should not be hidden in triggers.

---

## 27.4 Second parsers for different workflows

There should not be:

```text
local_parser
sat_parser
report_parser
inference_parser
```

There should be one authoritative CFDI interpretation pipeline.

---

## 27.5 Silent automatic confirmation

A high inference score does not automatically become accounting truth unless a future explicit business policy allows it.

---

## 27.6 Technical error interpreted as business state

Examples:

```text
SAT timeout → NO_ENCONTRADO
```

must be prohibited.

---

## 27.7 Hardcoded organization rules in domain code

Institution-specific configuration must remain configurable.

---

# 28. Initial V1 functional boundary

The initial target should include:

```text
CFDI Core
Document preservation
SAT validation
SAT history
SAT monitoring
SIF / Accounting import
Policies and movements
Reconciliation
Inference Engine V1
Basic Risk Engine
Audit
Core operational UI
```

Likely deferred:

* advanced machine learning;
* full Lu integration;
* every CFDI complement;
* advanced workflow/case system;
* every SAT acquisition feature;
* every report;
* DIOT unless later promoted.

---

# 29. Next architectural document

This document defines **what AURUM is made of**.

The next phase must define:

> **How AURUM will be implemented technically.**

The next major decisions will include:

* backend architecture;
* frontend architecture;
* language/framework choices;
* database engine;
* repository layout;
* migration strategy;
* storage abstraction;
* jobs/workers;
* API model;
* authentication;
* tests;
* configuration;
* deployment strategy.

Those decisions belong to the next architecture phase and should not be silently embedded in this document.

---

# 30. Current architecture statement

> **AURUM is a modular fiscal-accounting platform where immutable fiscal evidence is transformed into structured facts, enriched by external observations, connected to accounting context, evaluated through explainable inference and risk rules, and preserved through auditable human decisions.**
