# FILE: docs/PROJECT_STATE.md

# AURUM — Project State

**Version:** 0.1
**Current phase:** Product Definition & Architecture Foundation
**Repository:** AURUM

---

# 1. Current status

AURUM has been initialized as a new clean repository.

The project intentionally does not contain production application code yet.

The current goal is to establish:

* product definition;
* architecture;
* domain boundaries;
* implementation roadmap;
* engineering methodology.

This prevents AURUM from becoming another monolithic legacy application.

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
| Functional Architecture | ⚪ Not started            |
| Technical Architecture  | ⚪ Not started            |
| Domain Model            | ⚪ Not started            |
| Database Design         | ⚪ Not started            |
| Backend                 | ⚪ Not started            |
| Frontend                | ⚪ Not started            |
| Jobs / Workers          | ⚪ Not started            |
| Tests                   | ⚪ Not started            |
| CI/CD                   | ⚪ Not started            |
| Deployment              | ⚪ Not started            |
| Lu integration          | ⚪ Future                 |

---

# 7. Immediate next objective

The next major activity after the documentation foundation is:

> **Define AURUM Functional Architecture.**

This should define the boundaries and responsibilities of:

* CFDI Core;
* Document Center;
* SAT Center;
* SIF / Accounting Core;
* Reconciliation;
* Inference Engine;
* Risk & Alerts;
* Reporting;
* Jobs;
* Audit;
* Integrations.

No production implementation should begin until those boundaries are sufficiently clear.

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

**Milestone: AURUM Foundation**

Completion criteria:

* repository created;
* product vision documented;
* project state documented;
* initial roadmap documented;
* first documentation commit created and pushed.

After that:

**Milestone: Functional Architecture.**

---

# END PROJECT_STATE.md

# FILE: docs/ROADMAP.md

# AURUM — Roadmap

**Version:** 0.1
**Status:** Initial roadmap

---

# 1. Roadmap philosophy

The roadmap is intentionally incremental.

AURUM will not attempt to implement all legacy capabilities simultaneously.

Each phase should produce a coherent, tested foundation for the next one.

The roadmap may evolve as architecture and domain knowledge improve.

---

# 2. Phase overview

```text
PHASE 0  Legacy Discovery                  ✅
PHASE 1  Product Foundation                🟡
PHASE 2  Functional Architecture           ⚪
PHASE 3  Technical Architecture            ⚪
PHASE 4  Repository / Backend Foundation   ⚪
PHASE 5  CFDI Core                         ⚪
PHASE 6  Document Center                   ⚪
PHASE 7  SAT Validation & Monitoring       ⚪
PHASE 8  SIF / Accounting Core             ⚪
PHASE 9  Reconciliation                    ⚪
PHASE 10 Inference Engine                  ⚪
PHASE 11 Risk & Attention Center           ⚪
PHASE 12 Product UI                        ⚪
PHASE 13 SAT Acquisition                   ⚪
PHASE 14 Reporting / Automation            ⚪
PHASE 15 Learning / Advanced Intelligence  ⚪
PHASE 16 Lu / External Integrations         ⚪
```

---

# 3. PHASE 0 — Legacy Discovery

**Status: Initial discovery completed**

Objectives:

* identify previous systems;
* understand capabilities;
* recover business knowledge;
* detect duplicates;
* identify architectural problems;
* identify useful workflows;
* understand inference evolution.

Main systems:

* LEGACY-001 CFDI Analyzer Pro;
* LEGACY-002 SAT CFDI Manager Max;
* LEGACY-003 SAT SOAP Validator;
* DISCOVERY-004 CFDI–Policy Inference Engine;
* DISCOVERY-005 CFDI MASTER LOCAL.

Future discovery may continue when relevant legacy code is needed.

Discovery is not intended to block new development indefinitely.

---

# 4. PHASE 1 — Product Foundation

**Status: In progress**

## 1.1 Repository creation

* create GitHub repository;
* clone locally;
* configure `main`;
* create `.gitignore`;
* create `.venv`.

## 1.2 Documentation foundation

Create:

```text
README.md
docs/PRODUCT_VISION.md
docs/PROJECT_STATE.md
docs/ROADMAP.md
```

## 1.3 First repository commit

Target commit:

```text
docs: establish Aurum product foundation
```

### Exit criteria

* product vision established;
* principles documented;
* roadmap documented;
* state documented;
* clean first commit pushed.

---

# 5. PHASE 2 — Functional Architecture

Goal:

Define what each major AURUM domain owns before choosing implementation details.

Expected domains:

```text
AURUM
│
├── CFDI Core
├── Document Center
├── SAT Center
├── SIF / Accounting Core
├── Reconciliation
├── Inference Engine
├── Risk & Alerts
├── Parties / Suppliers
├── Reporting & Analytics
├── Jobs
├── Audit
└── Integrations
```

## 2.1 Define domain responsibilities

For each domain:

* purpose;
* inputs;
* outputs;
* owned concepts;
* dependencies;
* prohibited responsibilities.

## 2.2 Define primary workflows

At minimum:

### CFDI ingestion

```text
Input
→ identify
→ validate
→ parse
→ persist
→ preserve original
```

### SAT lifecycle

```text
CFDI
→ query
→ observation
→ compare previous state
→ detect change
→ risk/event
```

### SIF lifecycle

```text
SIF import
→ accounting context
→ policy
→ movements
→ evidence
```

### Reconciliation

```text
CFDI
+
Accounting context
→ known links
→ unresolved records
```

### Inference

```text
Unresolved CFDI
→ candidate generation
→ experts
→ evidence
→ score
→ ranking
→ human decision
```

## 2.3 Produce architecture document

Create:

```text
docs/ARCHITECTURE.md
```

### Exit criteria

* domain boundaries accepted;
* major workflows defined;
* no unclear ownership of core business logic.

---

# 6. PHASE 3 — Technical Architecture

Goal:

Select technologies only after functional boundaries are known.

Decisions will include:

* backend technology;
* frontend technology;
* database;
* migrations;
* storage;
* job system;
* queue if required;
* configuration;
* logging;
* testing;
* API style;
* authentication;
* deployment strategy.

## 3.1 Domain model

Create:

```text
docs/DOMAIN_MODEL.md
```

Initial concepts may include:

```text
Organization
Party
CFDI
CFDIConcept
CFDITax
CFDIRelationship
Payroll
Document
SATObservation
AccountingEntity
AccountingContext
Account
Policy
PolicyMovement
CFDIPolicyLink
InferenceRun
InferenceCandidate
Evidence
Decision
Risk
Job
AuditEvent
```

## 3.2 Database design

Create:

```text
docs/DATABASE_DESIGN.md
```

No schema should blindly reproduce legacy databases.

## 3.3 Architecture decision records

Consider later use of:

```text
docs/adr/
```

for important irreversible decisions.

### Exit criteria

* selected stack justified;
* domain model established;
* persistence strategy established;
* application boundaries understood.

---

# 7. PHASE 4 — Repository / Backend Foundation

This is the first phase containing application code.

## EPIC 4A — Project skeleton

Possible increments:

### 4A.1 Backend package foundation

* source layout;
* configuration;
* dependency management.

### 4A.2 Application startup

* application bootstrap;
* health endpoint/service.

### 4A.3 Test foundation

* test runner;
* first smoke test.

### 4A.4 Database foundation

* database connection;
* migrations;
* development configuration.

### 4A.5 Logging

* structured application logging.

### Exit criteria

A minimal application starts successfully and tests pass.

---

# 8. PHASE 5 — CFDI Core

CFDI Core should be one of the earliest production capabilities.

## EPIC 5A — CFDI identity

### 5A.1 Immutable source document

Store original XML metadata and hash.

### 5A.2 XML loader

Securely load XML.

### 5A.3 TimbreFiscalDigital identity

Extract valid UUID.

### 5A.4 Duplicate detection

Detect duplicates by canonical UUID.

---

## EPIC 5B — CFDI header

Extract:

* version;
* series;
* folio;
* dates;
* type;
* subtotal;
* discount;
* total;
* currency;
* payment information;
* issuer;
* receiver.

---

## EPIC 5C — Concepts

Normalize CFDI concepts.

---

## EPIC 5D — Taxes

Normalize:

* transferred taxes;
* retained taxes;
* concept-level taxes;
* comprobante-level taxes.

---

## EPIC 5E — Complements

Initial priority:

1. Payroll.
2. INE.
3. Relations.

---

## EPIC 5F — Classification

Build classification as a versioned domain service.

Do not embed classification inside database triggers or UI.

---

## EPIC 5G — Reprocessing

Allow structured representations to be rebuilt from preserved originals.

### Exit criteria

AURUM can ingest and persist representative historical CFDI correctly with tests.

---

# 9. PHASE 6 — Document Center

## 6.1 Storage abstraction

Define storage interface independent of local/network/cloud implementation.

## 6.2 XML document management

Associate immutable XML with CFDI.

## 6.3 PDF association

Associate original PDF.

## 6.4 Hash/integrity

Track document integrity.

## 6.5 Document retrieval

Allow application services to retrieve fiscal documents.

### Future

* generated representation;
* OCR fallback;
* supporting evidence;
* cloud storage.

---

# 10. PHASE 7 — SAT Validation & Monitoring

SAT monitoring is a V1 priority.

## EPIC 7A — SAT provider abstraction

Define SAT status provider contract.

---

## EPIC 7B — Live validation

* validate one CFDI;
* normalize response;
* distinguish technical failure from fiscal result.

Important:

```text
NETWORK_ERROR != CFDI_NOT_FOUND
```

---

## EPIC 7C — SAT observations

Persist historical observations.

---

## EPIC 7D — Current SAT state

Maintain convenient current state derived from observations.

---

## EPIC 7E — Change detection

Detect:

```text
VIGENTE → CANCELADO
```

and other relevant transitions.

---

## EPIC 7F — Batch validation

Validate many CFDI safely.

---

## EPIC 7G — Monitoring policies

Initial policies may consider:

* never checked;
* recently imported;
* stale validation;
* high amount;
* linked accounting records;
* recently changed state.

---

## EPIC 7H — Scheduler / durable execution

SAT monitoring must eventually operate independently from UI lifecycle.

### Exit criteria

AURUM can continually track and historically explain SAT state.

---

# 11. PHASE 8 — SIF / Accounting Core

SIF is another V1 priority.

## EPIC 8A — Accounting entities

Normalize organization/entity/accounting context.

---

## EPIC 8B — Account catalog

Import and maintain accounting accounts.

---

## EPIC 8C — Policies

Persist policies.

---

## EPIC 8D — Policy movements

Persist charges/credits and descriptions.

---

## EPIC 8E — SIF importer

Import relevant SIF/Mayor files through a clean adapter.

---

## EPIC 8F — Evidence

Persist SIF evidence status independently.

---

## EPIC 8G — Import provenance

Preserve import/source metadata.

### Exit criteria

AURUM can reconstruct enough SIF/accounting context for reconciliation.

---

# 12. PHASE 9 — Reconciliation

## EPIC 9A — CFDI Policy Link

Implement many-to-many relationship.

---

## EPIC 9B — Imported links

Recover authoritative SIF/UUID relationships.

---

## EPIC 9C — Reconciliation states

Identify:

* CFDI without policy;
* policy without CFDI;
* multiple relationships;
* amount differences;
* evidence issues.

---

## EPIC 9D — Reconciliation metrics

Calculate coverage and operational queues.

### Exit criteria

AURUM understands what is reconciled and what remains unresolved.

---

# 13. PHASE 10 — Inference Engine

The new inference engine should recover the strongest concepts from DISCOVERY-004 without copying its implementation blindly.

## EPIC 10A — Inference run model

Persist each run.

---

## EPIC 10B — Candidate generation

Efficiently select plausible policies.

---

## EPIC 10C — Evidence model

Create structured evidence.

---

## EPIC 10D — Context Expert

Compare:

* entity;
* accounting;
* period;
* document direction.

---

## EPIC 10E — Counterparty / UUID Expert

Analyze names, RFC, UUID and useful text signals.

---

## EPIC 10F — Temporal Expert

Score date proximity intelligently.

---

## EPIC 10G — Amount Expert

Analyze accounting movements against fiscal totals/components.

---

## EPIC 10H — Fiscal Account Expert

Understand account-role patterns.

---

## EPIC 10I — Payroll Expert

Specialized payroll analysis.

---

## EPIC 10J — Ranking

Combine evidence into explainable scores.

---

## EPIC 10K — Human decision

Allow:

* confirm;
* reject;
* choose alternative;
* unresolved.

---

## EPIC 10L — Evaluation

Measure engine performance.

### Exit criteria

The system can propose policy candidates and explain why.

---

# 14. PHASE 11 — Risk & Attention Center

## EPIC 11A — Risk model

Create formal risk objects.

---

## EPIC 11B — Initial rules

Potential rules:

```text
SAT_CANCELLED_WITH_ACCOUNTING_IMPACT
CFDI_WITHOUT_POLICY
POLICY_WITHOUT_CFDI
SIF_EVIDENCE_MISSING
AMOUNT_MISMATCH
POLICY_UNBALANCED
SAT_STATUS_STALE
UNKNOWN_CLASSIFICATION
```

---

## EPIC 11C — Severity

Possible levels:

```text
CRITICAL
HIGH
MEDIUM
LOW
INFO
```

---

## EPIC 11D — Attention workflow

Support:

* open;
* acknowledged;
* assigned;
* resolved;
* dismissed.

---

## EPIC 11E — Cases

Evaluate whether complex risks should become work cases.

### Exit criteria

AURUM tells users what requires attention, not only what data exists.

---

# 15. PHASE 12 — Product UI

A polished interface should be built on stable application services.

Likely primary views:

```text
Dashboard
Attention Center
CFDI Explorer
CFDI Record
SAT Monitor
Policies
Policy Detail
Reconciliation
Inference Review
Documents
Reports
Settings
```

The detailed CFDI record should become one of the central product experiences.

---

# 16. PHASE 13 — SAT Acquisition

After the core SAT status system is stable:

* e.firma;
* massive download;
* metadata;
* request lifecycle;
* packages;
* recovery;
* retry;
* diagnostics;
* ingestion integration.

SAT acquisition should feed the same CFDI Core rather than create a second parser.

---

# 17. PHASE 14 — Reporting & Automation

Possible capabilities:

* Excel reports;
* CSV;
* scheduled reports;
* operational summaries;
* advanced dashboards;
* N8N integration;
* notifications;
* configurable jobs.

---

# 18. PHASE 15 — Learning & Advanced Intelligence

Only after enough verified human decisions exist.

Possible work:

* inference quality dashboards;
* historical benchmark sets;
* rule optimization;
* statistical learning;
* specialized models;
* anomaly detection.

AURUM should not rush into opaque ML before obtaining high-quality ground truth.

---

# 19. PHASE 16 — Lu & External Integrations

Lu integration begins only after stable application APIs exist.

Potential tools:

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

Lu should remain a client of AURUM.

---

# 20. Proposed V1 boundary

AURUM V1 should prioritize:

```text
CFDI Core
+
Document preservation
+
SAT validation/history/monitoring
+
SIF / Accounting import
+
Policy/movement model
+
Reconciliation
+
Inference Engine V1
+
Risk basics
+
Core UI
+
Audit
```

Not required for initial V1:

* full Lu integration;
* advanced machine learning;
* every SAT acquisition feature;
* every possible CFDI complement;
* every report;
* every automation;
* DIOT unless later promoted in scope.

---

# 21. Current next action

Current roadmap position:

```text
PHASE 1 — Product Foundation
```

After the first documentation commit:

```text
PHASE 2 — Functional Architecture
```

The next major document will be:

```text
docs/ARCHITECTURE.md
```

No production backend code should be started before completing the initial architecture discussion.

# END ROADMAP.md
