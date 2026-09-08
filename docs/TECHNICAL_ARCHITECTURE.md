# AURUM — Technical Architecture

**Version:** 0.1
**Status:** Initial technical architecture
**Current phase:** Phase 3 — Technical Architecture

---

# 1. Purpose

This document defines the initial technical architecture of AURUM.

It complements `ARCHITECTURE.md`.

`ARCHITECTURE.md` defines:

> What AURUM is made of.

This document defines:

> How those capabilities will be implemented technically.

The architecture may evolve, but the initial stack must support:

* CFDI processing;
* large XML volumes;
* SAT connectivity;
* continuous SAT monitoring;
* SIF/accounting imports;
* reconciliation;
* inference;
* background jobs;
* auditability;
* modern UI;
* future N8N integration;
* future Lu integration.

---

# 2. Architecture summary

Initial recommended stack:

```text
Frontend
    Next.js
    React
    TypeScript
        │
        ▼
REST API
        │
        ▼
Backend
    Python
    FastAPI
        │
        ▼
Application / Domain
        │
        ├──────────────┬──────────────┐
        ▼              ▼              ▼
   PostgreSQL       Storage        Connectors
                       │             │
                       │        SAT / SIF
                       │
                       ▼
                  Documents

Background processing
        │
        ▼
Job abstraction
        │
        ▼
Dramatiq / Redis
        future
```

---

# 3. Repository strategy

AURUM will use a single repository containing backend, frontend, documentation, and supporting development assets.

Conceptually:

```text
AURUM/
│
├── backend/
├── frontend/
├── docs/
├── scripts/
├── .gitignore
├── README.md
└── ...
```

This keeps product evolution synchronized while maintaining clear technical boundaries.

---

# 4. Backend language — Python

## Decision

Use **Python** for the backend and domain processing.

## Rationale

AURUM is highly dependent on:

* XML processing;
* SAT integrations;
* spreadsheet ingestion;
* accounting analysis;
* batch processing;
* inference engines;
* data transformation;
* fiscal parsing.

Most legacy knowledge already exists in Python.

Python also provides strong libraries for:

* XML;
* HTTP/SOAP;
* Excel;
* PostgreSQL;
* testing;
* data analysis;
* queues;
* automation.

## Additional advantage

The future Inference Engine can evolve without introducing a second backend language.

---

# 5. Backend framework — FastAPI

## Decision

Use **FastAPI** as the backend application/API framework.

## Responsibilities

FastAPI will expose application capabilities to:

* AURUM frontend;
* CLI tools;
* N8N;
* future Lu integration;
* other trusted clients.

## Example future API surface

```text
/api/v1/cfdi
/api/v1/sat
/api/v1/policies
/api/v1/reconciliation
/api/v1/inference
/api/v1/risks
/api/v1/jobs
```

Exact routes will be defined later.

## Important boundary

FastAPI is an interface layer.

Fiscal and accounting rules must not live inside route functions.

Preferred:

```text
API
 ↓
Application Service
 ↓
Domain
```

Not:

```text
API endpoint
 ↓
raw SQL
 ↓
business rules
```

---

# 6. Backend architecture

Initial internal structure:

```text
backend/
│
├── pyproject.toml
├── tests/
└── src/
    └── aurum/
        │
        ├── domain/
        ├── application/
        ├── infrastructure/
        └── api/
```

---

# 7. Domain layer

The domain layer contains business meaning.

Conceptual structure:

```text
domain/
├── cfdi/
├── documents/
├── accounting/
├── reconciliation/
├── inference/
├── risk/
├── parties/
├── audit/
└── common/
```

The exact package layout may evolve.

## Domain contains

* entities;
* value objects;
* rules;
* domain services;
* domain errors;
* domain events;
* calculations.

## Domain must not depend directly on

* FastAPI;
* SQLAlchemy;
* PyQt;
* React;
* Redis;
* SAT SOAP libraries;
* Excel libraries;
* filesystem dialogs.

---

# 8. Application layer

The application layer coordinates use cases.

Conceptually:

```text
application/
├── commands/
├── queries/
├── services/
└── dto/
```

Possible use cases:

```text
IngestCFDI
GetCFDIDetail
ValidateCFDIInSAT
ImportSIF
ReconcileCFDI
RunInference
ConfirmPolicyCandidate
ResolveRisk
```

The application layer orchestrates domains and infrastructure.

It does not contain low-level SAT/DB/file implementations.

---

# 9. Infrastructure layer

The infrastructure layer implements technical details.

Conceptually:

```text
infrastructure/
├── database/
├── repositories/
├── sat/
├── sif/
├── storage/
├── jobs/
├── logging/
└── external/
```

Examples:

* PostgreSQL repositories;
* SAT SOAP adapter;
* SAT massive-download adapter;
* SIF Excel importer;
* local file storage;
* Redis job backend.

---

# 10. API layer

The API layer exposes application use cases.

Conceptually:

```text
api/
├── routes/
├── schemas/
├── dependencies/
└── errors/
```

Responsibilities:

* validate HTTP input;
* call application layer;
* serialize output;
* enforce authentication/authorization;
* translate application errors into HTTP responses.

It must not implement domain decisions.

---

# 11. Database — PostgreSQL

## Decision

Use **PostgreSQL** as AURUM's primary relational database.

## Why PostgreSQL

AURUM requires:

* complex relationships;
* N:N relations;
* historical observations;
* audit records;
* transactional integrity;
* large data volumes;
* analytical queries;
* indexing;
* constraints;
* structured and semi-structured fields.

PostgreSQL is appropriate for all of these requirements.

---

# 12. Database role

PostgreSQL will be the operational source of structured truth.

It will store concepts such as:

* CFDI;
* concepts;
* taxes;
* payroll;
* CFDI relations;
* SAT observations;
* parties;
* organizations;
* policies;
* movements;
* CFDI-policy links;
* inference runs;
* candidates;
* evidence;
* risks;
* jobs;
* audit events.

Original document bytes may be stored externally through the Document Center rather than directly in the database.

That decision will be refined in `DATABASE_DESIGN.md`.

---

# 13. ORM — SQLAlchemy 2.x

## Decision

Use **SQLAlchemy 2.x** for database access and mapping.

## Rationale

SQLAlchemy provides:

* explicit transaction control;
* mature PostgreSQL support;
* flexible mapping;
* testability;
* migration compatibility;
* ability to execute optimized SQL when necessary.

## Architectural rule

Domain rules should not depend directly on ORM models where avoidable.

Persistence models and domain concepts may be related, but should not become indistinguishable by accident.

---

# 14. Migrations — Alembic

## Decision

Use **Alembic** for database migrations.

All schema evolution must be version-controlled.

Avoid manual production schema changes.

Typical workflow:

```text
model/schema decision
→ migration
→ review
→ test
→ apply
```

---

# 15. Money and numeric precision

Accounting and fiscal amounts must not use binary floating-point semantics for authoritative calculations.

Use decimal-compatible database types and Python decimal values.

Conceptually:

```text
NUMERIC / DECIMAL
```

instead of:

```text
FLOAT
```

for fiscal/accounting money.

---

# 16. Frontend — Next.js + React + TypeScript

## Decision

Use:

* Next.js;
* React;
* TypeScript.

## Purpose

AURUM needs a modern operational interface capable of handling:

* tables;
* filtering;
* dashboards;
* detailed CFDI records;
* policies;
* reconciliation;
* inference review;
* alerts;
* jobs;
* document access.

A web frontend makes future multi-device and centralized deployment easier than another desktop-only UI.

---

# 17. Frontend boundary

The frontend must never connect directly to PostgreSQL.

Preferred:

```text
Next.js
  ↓
AURUM API
  ↓
Application
```

The frontend should not know:

* database table names;
* SAT SOAP details;
* SIF Excel layouts;
* filesystem paths.

---

# 18. Frontend structure

Exact layout will be decided later.

Possible high-level structure:

```text
frontend/
├── app/
├── components/
├── features/
├── lib/
└── types/
```

Feature boundaries should roughly align with AURUM product domains.

---

# 19. API style

## Initial decision

Use **REST** for the initial API.

Reasons:

* clear operational contracts;
* strong FastAPI support;
* simple integration with Next.js;
* simple future N8N integration;
* straightforward Lu tool integration;
* easy debugging.

GraphQL is not currently required.

---

# 20. API versioning

The API should be prepared for explicit versioning.

Example:

```text
/api/v1/...
```

This is especially important because future external clients such as Lu must not break when AURUM evolves.

---

# 21. XML parsing

AURUM should use a hardened XML parser strategy.

Preferred library family:

```text
lxml
```

with secure parser configuration.

The parsing subsystem must consider:

* namespaces;
* CFDI versions;
* complements;
* malformed documents;
* huge batches;
* XML security.

---

# 22. Excel / SIF integration

SIF and accounting files are infrastructure inputs.

Possible Python libraries may include:

* openpyxl;
* pandas only where justified.

Important rule:

Excel column names must be translated inside the SIF adapter.

The Accounting Core must receive normalized objects.

Avoid spreading source-specific column names across the codebase.

---

# 23. SAT adapters

SAT integration will use provider abstractions.

Conceptually:

```text
SATStatusProvider
SATDownloadProvider
SATMetadataProvider
```

Implementations may use:

* SOAP;
* SAT web services;
* other supported mechanisms.

The domain/application layer should depend on contracts, not on Zeep or another specific client.

---

# 24. Storage abstraction

Documents may initially live on local disk.

But the Document Center should use a storage interface.

Conceptually:

```text
DocumentStorage
│
├── save()
├── read()
├── exists()
├── delete()
└── metadata()
```

Initial implementation:

```text
LocalFileStorage
```

Potential future implementations:

```text
NetworkStorage
ObjectStorage
CloudStorage
```

This prevents paths from becoming business logic.

---

# 25. Document hashing

Documents should use cryptographic hashing for integrity.

Initial preferred hash:

```text
SHA-256
```

Potential uses:

* detecting identical source files;
* integrity validation;
* audit evidence;
* avoiding accidental duplication.

UUID remains fiscal identity.

Hash is document identity/integrity.

They are not interchangeable.

---

# 26. Jobs and background processing

AURUM needs background processing for:

* SAT monitoring;
* large XML ingestion;
* SAT massive download;
* SIF imports;
* reprocessing;
* inference;
* exports;
* document generation.

These operations must eventually run independently from the browser/UI.

---

# 27. Initial job strategy

The application should first define an internal job abstraction.

Do not immediately couple every use case to a queue library.

Conceptually:

```text
Job
JobRunner
JobHandler
```

This allows simpler execution during early development.

---

# 28. Future queue — Dramatiq

When distributed/background execution becomes necessary, the initial preferred candidate is **Dramatiq**.

Possible broker:

```text
Redis
```

Why not make Redis mandatory immediately?

Because the first AURUM increments do not require distributed workers.

We should add operational complexity only when the product needs it.

---

# 29. Redis

Redis is a potential future infrastructure component.

Possible uses:

* job broker;
* temporary cache;
* rate limiting;
* distributed coordination.

Redis must not become the source of fiscal/accounting truth.

PostgreSQL remains authoritative for business state.

---

# 30. SAT monitoring architecture

SAT monitoring should eventually use something like:

```text
Monitoring policy
       ↓
Scheduler
       ↓
Job created
       ↓
Worker
       ↓
SAT provider
       ↓
Observation persisted
       ↓
Change detection
       ↓
Risk evaluation
```

The UI is only an observer/controller of this process.

---

# 31. Inference Engine architecture

The Inference Engine will live primarily in Python domain/application code.

Conceptually:

```text
Candidate Generator
        ↓
Experts
├── Context
├── Counterparty
├── UUID
├── Temporal
├── Amount
├── Fiscal Account
└── Payroll
        ↓
Evidence
        ↓
Scoring / Ranking
        ↓
Inference Result
```

The engine should be testable without:

* FastAPI;
* frontend;
* SAT;
* real database connection.

---

# 32. Rule versioning

Versioned engines may use explicit identifiers.

Example:

```text
parser_version = "1.0"
classification_ruleset = "1.0"
inference_engine_version = "1.0"
risk_ruleset_version = "1.0"
```

Exact implementation will be defined later.

---

# 33. Testing strategy

Testing is mandatory from the beginning of application code.

Initial backend testing:

```text
pytest
```

Tests will include:

* unit tests;
* parser fixtures;
* domain tests;
* service tests;
* repository integration tests;
* API tests.

---

# 34. XML fixtures

Representative CFDI fixtures should eventually include:

* standard invoice;
* honorarios;
* RESICO;
* payroll;
* INE;
* credit note;
* payment complement;
* relationships;
* transferred taxes;
* retained taxes;
* edge cases;
* malformed input.

Sensitive production data should not be committed without proper sanitization.

---

# 35. Database testing

Integration tests should eventually run against PostgreSQL-compatible test infrastructure.

Avoid designing queries only against mocks.

Important relational behavior should be tested against a real database engine.

---

# 36. Frontend testing

Frontend testing strategy will be decided when the UI foundation begins.

Potential levels:

* component tests;
* application-flow tests;
* end-to-end tests.

Do not add testing frameworks before they become useful.

---

# 37. Configuration

Configuration must be environment-driven.

Sensitive values must not be committed.

Examples:

```text
DATABASE_URL
SAT credentials/configuration
storage paths
Redis URL
application secrets
```

Use `.env` locally where appropriate.

`.env` must remain ignored by Git.

---

# 38. Secrets

AURUM may eventually manage sensitive information such as:

* SAT credentials;
* e.firma material;
* database credentials;
* external integration secrets.

These must not be:

* hardcoded;
* committed;
* printed in logs.

A dedicated secret-management strategy can be introduced later for deployed environments.

---

# 39. Logging

Application logging and business audit are separate.

## Application logging

Used for:

* diagnostics;
* errors;
* performance;
* infrastructure behavior.

## Audit

Used for:

* business actions;
* important state changes;
* human decisions;
* historical traceability.

They must not be confused.

---

# 40. Error model

AURUM should use explicit error categories.

Examples:

```text
DomainError
ValidationError
DocumentError
SATProviderError
AccountingImportError
PersistenceError
InferenceError
```

Technical failures should preserve their true semantics.

Example:

```text
SAT timeout
```

must not become:

```text
CFDI not found
```

---

# 41. Authentication

Authentication is required before real multi-user deployment.

Exact implementation is not yet selected.

Potential requirements:

* users;
* roles;
* sessions/tokens;
* audit identity;
* permissions.

Authentication should not block initial domain/backend work.

---

# 42. Authorization

AURUM may eventually require role-based permissions.

Possible future roles:

```text
ADMIN
ANALYST
REVIEWER
READ_ONLY
```

Exact roles are not yet defined.

---

# 43. Audit identity

Any human decision should eventually be attributable to a user.

Examples:

* manual CFDI-policy link;
* candidate confirmation;
* risk resolution;
* manual classification correction.

---

# 44. Deployment philosophy

Initial development will be local.

The architecture should nevertheless avoid assumptions that require the backend and frontend to run on one personal computer forever.

Preferred future topology:

```text
Browser
   ↓
Frontend
   ↓
Backend API
   ↓
PostgreSQL
   ↓
Workers / Storage
```

---

# 45. Windows development

Primary development currently occurs on Windows.

Development tooling and early infrastructure choices must remain practical in that environment.

Linux deployment may be introduced later.

---

# 46. Performance expectations

AURUM must be designed for large document collections.

Potential scale includes:

* thousands of CFDI per month;
* hundreds of thousands historically;
* many accounting movements;
* repeated SAT observations;
* inference candidates.

Performance strategy should rely on:

* batch processing;
* indexes;
* pagination;
* streaming where useful;
* bounded concurrency;
* background jobs;
* optimized SQL;
* avoiding repeated XML parsing.

---

# 47. Database query philosophy

Simple queries may use ORM patterns.

Complex analytical/reconciliation queries may use explicit SQL when justified.

The architecture should prioritize:

* correctness;
* clarity;
* performance;
* testability.

ORM usage must not prohibit optimized SQL.

---

# 48. Pagination

Large lists must be paginated.

Avoid loading all:

* CFDI;
* policies;
* movements;
* observations;
* risks;

into frontend memory.

Pagination/search/filter contracts should eventually be standardized.

---

# 49. Search

Search may eventually need:

* UUID;
* RFC;
* person/supplier;
* policy folio;
* accounting ID;
* date;
* amount;
* description.

Initial search can rely on PostgreSQL.

Dedicated search infrastructure should not be introduced prematurely.

---

# 50. Observability

Future production operation may include:

* health checks;
* job metrics;
* error monitoring;
* performance metrics;
* SAT connector health;
* storage health.

Initial backend should at minimum expose a health capability.

---

# 51. Connector principle

External formats must be translated at system boundaries.

Example:

```text
SIF XLSX
   ↓
SIF Adapter
   ↓
Accounting DTO/domain input
```

Not:

```text
Excel column names
↓
spread everywhere
```

Same principle applies to SAT.

---

# 52. Future N8N integration

N8N should consume AURUM APIs.

Examples:

* scheduled report workflows;
* email notifications;
* operational alerts;
* external automation.

N8N should not become the owner of core fiscal/accounting logic.

---

# 53. Future Lu integration

Lu is an external client.

Conceptually:

```text
Lu
 ↓
AURUM API
 ↓
Application layer
 ↓
Domain
```

Potential Lu tools:

```text
search_cfdi
get_cfdi_detail
check_sat_status
get_sat_history
search_policy
get_policy_detail
find_policy_candidates
explain_inference
get_risks
generate_report
```

AURUM must remain functional without Lu.

---

# 54. Explicitly rejected approaches

## 54.1 Desktop-only monolith

AURUM will not be another large PyQt/Tkinter application containing all business logic.

---

## 54.2 Database-first recreation of legacy schema

Legacy tables will not be copied blindly.

The domain model will drive the new schema.

---

## 54.3 UI-driven domain

Screen requirements must not dictate database relationships incorrectly.

---

## 54.4 Excel as database

Excel remains an import/export format.

It is not AURUM's operational source of truth.

---

## 54.5 Filesystem as database

Directory layout does not define AURUM's business state.

---

## 54.6 LLM-based accounting truth

A future LLM may help explain or interact with AURUM.

It must not replace deterministic fiscal/accounting evidence for authoritative reconciliation.

---

## 54.7 Premature microservices

AURUM should begin as a modular application, not as many distributed services.

Domain separation does not require network separation.

If future scale requires service extraction, clear boundaries will make it possible.

---

# 55. Initial architecture style

The preferred starting architecture is:

> **Modular monolith with clean domain/application/infrastructure boundaries.**

This provides:

* lower operational complexity;
* strong transactions;
* simple development;
* clear ownership;
* future extractability.

This is intentionally different from both:

* a monolithic script;
* premature microservices.

---

# 56. Initial technical stack

Current proposed baseline:

```text
Backend:
Python
FastAPI
SQLAlchemy 2.x
Alembic
pytest

Database:
PostgreSQL

Frontend:
Next.js
React
TypeScript

XML:
lxml

Storage:
abstract interface
local implementation initially

Jobs:
internal abstraction initially
Dramatiq later if needed

Broker/cache:
Redis later if needed

API:
REST /api/v1
```

---

# 57. Technical decisions not yet finalized

The following remain open until their implementation phase:

* exact Python version;
* exact package manager;
* exact Next.js version;
* frontend component library;
* authentication provider;
* exact PostgreSQL deployment model;
* production storage provider;
* Redis deployment;
* job scheduling implementation;
* CI/CD provider;
* hosting/deployment platform;
* secrets manager.

These should be chosen when enough requirements exist.

---

# 58. Next documents

After this technical architecture, the next design documents should be:

```text
docs/DOMAIN_MODEL.md
docs/DATABASE_DESIGN.md
```

Order:

```text
Functional Architecture
        ↓
Technical Architecture
        ↓
Domain Model
        ↓
Database Design
        ↓
Repository Bootstrap
```

The database should follow the domain model rather than the reverse.

---

# 59. Technical architecture statement

> **AURUM will begin as a modular Python/FastAPI application backed by PostgreSQL, exposed through stable REST contracts to a modern Next.js frontend, with explicit domain boundaries, infrastructure adapters, preserved source documents, testable inference logic, and a path toward durable workers and future external integrations such as N8N and Lu.**
