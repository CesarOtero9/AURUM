# AURUM

**AURUM — Fiscal & Accounting Intelligence Platform**

AURUM is a unified platform for CFDI processing, SAT monitoring, SIF integration, accounting reconciliation, document management, explainable inference, risk detection, auditability, and future intelligent automation.

The project is being built from scratch by consolidating the strongest capabilities, business rules, workflows, and lessons discovered across multiple legacy CFDI, SAT, SIF, accounting, and inference systems.

AURUM is not intended to become another isolated CFDI utility.

It is being designed as a complete fiscal and accounting intelligence platform.

---

## Vision

AURUM should become the central environment where a fiscal document can be:

* ingested;
* identified;
* parsed;
* classified;
* stored;
* validated against SAT;
* monitored over time;
* associated with SIF information;
* related to accounting policies;
* analyzed by an inference engine;
* reviewed by a human;
* monitored for risks;
* audited from end to end.

A CFDI will not be treated simply as an XML file or a row in Excel.

It will be treated as a complete **fiscal-accounting record**.

---

## Core platform areas

AURUM will progressively include:

### CFDI Core

* XML ingestion.
* CFDI parsing.
* UUID extraction and deduplication.
* Concepts.
* Taxes.
* Payroll.
* INE complement.
* CFDI relationships.
* Classification.
* Reprocessing.

### Document Center

* Original XML.
* Original PDF.
* Generated representations.
* Evidence.
* Hashing and integrity.
* Document association.

### SAT Center

* Live SAT validation.
* Current SAT status.
* Historical SAT observations.
* Cancellation tracking.
* Continuous SAT monitoring.
* Status-change detection.
* Massive download.
* Metadata.
* SAT requests and packages.

### SIF / Accounting Core

* Accounting entities.
* Accounting IDs.
* Accounts.
* Policies.
* Policy movements.
* Charges and credits.
* Accounting periods.
* SIF evidence.
* Evidence status.

### Reconciliation

* CFDI ↔ Policy relationships.
* Imported relationships.
* Manual relationships.
* Inferred relationships.
* Missing-policy detection.
* Missing-CFDI detection.
* Amount mismatches.
* SIF evidence issues.

### Inference Engine

* Context evidence.
* Counterparty evidence.
* UUID evidence.
* Temporal evidence.
* Amount evidence.
* Fiscal-account evidence.
* Payroll-specialized analysis.
* Ranked policy candidates.
* Explainable scoring.
* Human confirmation.

### Risk & Alerts

* Cancelled CFDI with accounting impact.
* CFDI without policy.
* Policy without CFDI.
* Missing SIF evidence.
* Amount differences.
* Stale SAT validation.
* Suspicious relationships.
* Accounting inconsistencies.

### Reporting & Analytics

* Operational dashboards.
* Reconciliation coverage.
* SAT status metrics.
* Accounting metrics.
* Risk monitoring.
* Excel and CSV exports.

### Jobs & Audit

* Massive processes.
* Progress tracking.
* Retries.
* Reprocessing.
* Historical operations.
* Audit trail.

### Integrations

* Internal API.
* N8N.
* Future external tools.
* Future Lu integration.

---

## Core architectural principles

1. **The original XML is immutable evidence.**
2. **The CFDI UUID comes from `TimbreFiscalDigital/@UUID`.**
3. **SAT status is dynamic and must be historically tracked.**
4. **SIF is a first-class subsystem, not a secondary importer.**
5. **CFDI ↔ Policy is a many-to-many relationship.**
6. **Facts, observations, inferences, and human decisions are different concepts.**
7. **Inference must be explainable and auditable.**
8. **Business logic must remain outside the user interface.**
9. **Legacy systems are sources of knowledge, not the new architecture.**
10. **Long-running operations should eventually use durable jobs/workers.**
11. **Important information should preserve its provenance.**
12. **Rules and inference engines should be versionable.**
13. **Original documents must support future reprocessing.**
14. **Institution-specific values must not be hardcoded into the core.**
15. **AURUM must remain independent from Lu. Lu will eventually consume stable AURUM APIs.**

---

## Legacy foundation

AURUM incorporates lessons from several previous systems.

### LEGACY-001 — CFDI Analyzer Pro

Primary knowledge:

* Deep CFDI parsing.
* Concepts.
* Taxes.
* Payroll.
* INE.
* CFDI relationships.
* XML/PDF matching.
* UUID deduplication.
* Reporting.

### LEGACY-002 — SAT CFDI Manager Max

Primary knowledge:

* e.firma.
* Massive SAT download.
* Metadata.
* SAT requests.
* SAT packages.
* Recovery.
* PDF generation.

### LEGACY-003 — SAT SOAP Validator

Primary knowledge:

* Live SAT validation.
* SAT status.
* Cancellation information.
* Status observations.

### DISCOVERY-004 — CFDI–Policy Inference Engine

Primary knowledge:

* Accounting model.
* Ledger import.
* Policies and movements.
* Historical context.
* Temporal analysis.
* Amount matching.
* Fiscal-account analysis.
* Payroll expert.
* Explainable ranking.

### DISCOVERY-005 — CFDI MASTER LOCAL

Primary knowledge:

* Product vision.
* Local CFDI repository.
* SAT monitoring.
* SIF integration.
* Policies.
* Reconciliation.
* Early inference.
* Supplier management.
* Dashboards.
* Integrated CFDI detail.

---

## Development methodology

AURUM follows an incremental development methodology inspired by the workflow successfully used in previous projects.

Each meaningful increment should follow:

```text
Define
↓
Document
↓
Implement
↓
Test
↓
Review
↓
Correct
↓
Commit
↓
Push
↓
Update documentation
```

Large modules should not be developed simultaneously without closing and validating the previous increment.

---

## Current project phase

**Phase 1 — Product Definition & Architecture Foundation**

The repository has been intentionally initialized without production application code.

Current priorities:

1. Define product vision.
2. Define roadmap.
3. Define functional architecture.
4. Define technical architecture.
5. Define domain model.
6. Define database strategy.
7. Bootstrap backend only after the foundation is documented.

---

## Repository documentation

Current foundation documents:

```text
docs/
├── PRODUCT_VISION.md
├── PROJECT_STATE.md
└── ROADMAP.md
```

Future documentation may include:

```text
docs/
├── ARCHITECTURE.md
├── DOMAIN_MODEL.md
├── DATABASE_DESIGN.md
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

These documents will be created incrementally as the corresponding architectural decisions are made.

---

## Current implementation status

| Area                    | Status                |
| ----------------------- | --------------------- |
| Product definition      | 🟡 In progress        |
| Roadmap                 | 🟡 Initial definition |
| Functional architecture | ⚪ Not started         |
| Technical architecture  | ⚪ Not started         |
| Domain model            | ⚪ Not started         |
| Backend                 | ⚪ Not started         |
| Frontend                | ⚪ Not started         |
| Database                | ⚪ Not started         |
| Jobs / Workers          | ⚪ Not started         |
| Tests                   | ⚪ Not started         |
| CI/CD                   | ⚪ Not started         |
| Lu integration          | ⚪ Future              |

This is intentional.

---

## Product statement

> **AURUM will be the fiscal and accounting intelligence center where every CFDI can be identified, understood, monitored, documented, reconciled, explained, and audited from end to end.**
