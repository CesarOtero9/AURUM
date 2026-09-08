# FILE: docs/PROJECT_STATE.md

# AURUM — Project State

**Version:** 0.2
**Current phase:** Repository / Backend Foundation
**Repository:** AURUM

---

# 1. Current status

AURUM has a documented product and architectural foundation, plus an initial backend
bootstrap. The bootstrap uses Python 3.12, a `src` package layout, FastAPI, and pytest.

It exposes only the technical health endpoint (`GET /health`). No fiscal, accounting,
database, authentication, or worker capability has been implemented.

The package follows the agreed modular-monolith boundaries: `domain`, `application`,
`infrastructure`, and `api`. Quality checks include strict pytest configuration and Ruff
for basic syntax, import, and style errors.

---

# 2. Product direction

AURUM will consolidate the strongest capabilities discovered across previous CFDI, SAT, SIF, accounting, reconciliation, and inference systems.

The platform is expected to include:

* CFDI ingestion;
* CFDI parsing;
* taxes;
* payroll;
* INE;
* CFDI relationships;
* classification;
* XML/PDF document management;
* SAT live validation;
* continuous SAT monitoring;
* historical SAT observations;
* SAT status-change detection;
* SAT massive download;
* SAT metadata;
* SIF integration;
* accounting entities;
* policies;
* policy movements;
* account catalogs;
* SIF evidence;
* CFDI ↔ Policy reconciliation;
* explainable inference;
* risk detection;
* operational alerts;
* supplier/party information;
* reporting;
* durable jobs;
* audit history;
* future N8N integration;
* future Lu integration.

---

# 3. Core architectural decisions already accepted

The following principles are considered part of the current product foundation.

## 3.1 Original XML is immutable evidence

Original XML files must be preserved without modification.

Structured database representations may be regenerated later.

---

## 3.2 UUID identity

CFDI identity must use the UUID extracted specifically from:

```text
TimbreFiscalDigital/@UUID
```

Related UUIDs or arbitrary UUID-looking strings must not be considered document identity.

---

## 3.3 SAT is dynamic

SAT state is not part of the immutable CFDI document.

AURUM must preserve:

* current status;
* query timestamp;
* historical observations;
* detected status changes.

---

## 3.4 SAT monitoring is a core capability

AURUM must eventually revalidate CFDI according to configurable monitoring strategies.

Monitoring must not depend on a desktop UI remaining open.

---

## 3.5 SIF is first-class

SIF is not a secondary importer.

AURUM must understand enough accounting information to reconstruct:

* policies;
* movements;
* entities;
* accounting IDs;
* accounts;
* evidence;
* accounting status.

---

## 3.6 CFDI ↔ Policy is many-to-many

One CFDI may relate to multiple policies.

One policy may relate to multiple CFDI.

The relationship requires its own entity and metadata.

---

## 3.7 Inference is not confirmation

AURUM must distinguish:

* imported relationship;
* deterministic relationship;
* inferred relationship;
* manual relationship;
* confirmed relationship;
* rejected relationship.

---

## 3.8 Inference must be explainable

Every important recommendation should expose supporting evidence and score components.

---

## 3.9 Facts, observations, inferences and decisions are distinct

They must not overwrite or masquerade as one another.

---

## 3.10 Business logic stays outside UI

The application interface must consume services.

Fiscal/accounting rules must not live inside visual components.

---

## 3.11 Legacy systems are knowledge sources

Legacy systems will not be copied wholesale.

Individual capabilities will eventually be classified as:

```text
REUSE
REFACTOR
REDESIGN
DISCARD
```

---

## 3.12 Lu remains external

AURUM must operate independently.

Lu may eventually consume AURUM through stable application APIs.

---

# 4. Legacy discovery

The following systems have been analyzed.

## LEGACY-001 — CFDI Analyzer Pro

Primary value:

* deep CFDI parser;
* concepts;
* taxes;
* payroll;
* INE;
* relationships;
* XML/PDF matching;
* UUID duplicate detection;
* reporting.

General destination:

**Rebuild as modular CFDI Core capabilities.**

---

## LEGACY-002 — SAT CFDI Manager Max

Primary value:

* e.firma;
* massive download;
* XML;
* metadata;
* requests;
* packages;
* recovery;
* generated PDF.

General destination:

**Rebuild as SAT acquisition/document subsystem.**

---

## LEGACY-003 — SAT SOAP Validator

Primary value:

* live SAT status;
* cancellation information;
* retries;
* batch validation.

General destination:

**Rebuild as SAT validation provider and historical observation service.**

---

## DISCOVERY-004 — CFDI–Policy Inference Engine

Primary value:

* normalized CFDI/accounting model;
* ledger import;
* policies;
* movements;
* policy references;
* temporal expert;
* token/counterparty expert;
* amount matching;
* fiscal-account expert;
* payroll expert;
* candidate ranking;
* evidence;
* human review concepts.

General destination:

**Rebuild and absorb into AURUM Accounting Intelligence / Inference Engine.**

---

## DISCOVERY-005 — CFDI MASTER LOCAL

Primary value:

* integrated product concept;
* local fiscal repository;
* document storage;
* SAT monitoring;
* SIF import;
* policies;
* reconciliation;
* early matching engine;
* supplier master;
* dashboard;
* integrated CFDI record detail.

General destination:

**Use primarily as product/workflow reference and selectively recover business logic.**

---

# 5. Current repository structure

Current expected repository:

```text
AURUM/
├── .gitignore
├── README.md
└── docs/
    ├── PRODUCT_VISION.md
    ├── PROJECT_STATE.md
    └── ROADMAP.md
```

A local environment exists as:

```text
.venv/
```

It must remain excluded from Git.

---

# 6. Current implementation state

| Area                    | Status                   |
| ----------------------- | ------------------------ |
| Repository              | ✅ Created                |
| Virtual environment     | ✅ Created                |
| README                  | ✅ Foundation             |
| Product Vision          | ✅ Initial version        |
| Project State           | ✅ Initial version        |
| Roadmap                 | ✅ Initial version        |
| Legacy Discovery        | ✅ Initial pass completed |
| Functional Architecture | Complete (initial)       |
| Technical Architecture  | Complete (initial)       |
| Domain Model            | Complete (initial)       |
| Database Design         | Complete (initial)       |
| Backend                 | Bootstrap implemented    |
| Frontend                | ⚪ Not started            |
| Jobs / Workers          | ⚪ Not started            |
| Tests                   | Health and quality baseline |
| CI/CD                   | ⚪ Not started            |
| Deployment              | ⚪ Not started            |
| Lu integration          | ⚪ Future                 |

---

# 7. Immediate next objective

The next major activity is to specify the first coherent vertical slice:

> **CFDI Identity & Immutable Ingestion.**

Before implementation, define its application contract and its minimum persistence model.
The slice must preserve original XML evidence, calculate SHA-256, obtain identity only
from `TimbreFiscalDigital/@UUID`, and handle duplicate UUIDs explicitly.

---

# 8. Near-term documents

Expected next documentation:

```text
docs/
├── ARCHITECTURE.md
├── DOMAIN_MODEL.md
└── DATABASE_DESIGN.md
```

Later:

```text
docs/
├── CFDI_CORE_SPEC.md
├── SAT_SUBSYSTEM_SPEC.md
├── SIF_ACCOUNTING_SPEC.md
├── RECONCILIATION_SPEC.md
├── EXPERT_ENGINE_ARCHITECTURE.md
├── RISK_ENGINE_SPEC.md
├── DOCUMENT_STORAGE_SPEC.md
├── JOB_SYSTEM_SPEC.md
├── API_CONTRACT.md
└── LU_INTEGRATION_CONTRACT.md
```

Documents should only be created when they become useful.

---

# 9. Current engineering rule

AURUM development follows:

```text
Define
→ Document
→ Implement
→ Test
→ Review
→ Correct
→ Commit
→ Push
→ Update PROJECT_STATE
```

---

# 10. Next milestone

**Milestone: Repository / Backend Foundation**

Completion criteria:

* documented product and architecture foundation;
* Python 3.12 backend package with `src` layout;
* explicit modular-monolith package boundaries;
* FastAPI health endpoint;
* pytest health check;
* reproducible baseline lint configuration.

After that:

**Milestone: CFDI Identity & Immutable Ingestion design.**

---

# END PROJECT_STATE.md
