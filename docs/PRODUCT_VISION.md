# AURUM — Product Vision

**Version:** 0.1
**Status:** Foundation
**Project:** AURUM — Fiscal & Accounting Intelligence Platform

---

# 1. Product vision

AURUM will be a unified fiscal and accounting intelligence platform designed to centralize CFDI processing, SAT monitoring, SIF integration, accounting information, document management, reconciliation, explainable inference, risk detection, auditability, and future intelligent automation.

The goal is not to combine old applications into a larger application.

The goal is to **rebuild the best capabilities discovered across those applications inside a new architecture designed correctly from the beginning**.

AURUM must become the central operational system where fiscal documents and their accounting context coexist.

---

# 2. The problem

Previous workflows required multiple independent tools for:

* parsing CFDI;
* reading taxes;
* analyzing payroll;
* extracting INE information;
* organizing XML/PDF;
* validating CFDI against SAT;
* downloading CFDI from SAT;
* importing SIF data;
* processing accounting policies;
* reconciling CFDI with policies;
* detecting missing evidence;
* generating reports;
* proposing policy matches;
* maintaining supplier information;
* exporting to Excel.

These capabilities evolved independently.

As a result, previous systems contain:

* duplicated business rules;
* multiple parsers;
* multiple interfaces;
* isolated databases;
* different classifications;
* inconsistent models;
* SQL coupled to UI code;
* repeated imports;
* manual Excel processes;
* fragmented history;
* limited traceability;
* limited interoperability.

AURUM will replace that fragmentation with one coherent platform.

---

# 3. Central product concept

A CFDI must not be treated only as:

* an XML file;
* a PDF;
* a database row;
* an Excel entry.

AURUM will treat it as a **Fiscal-Accounting Record**.

Conceptually:

```text
CFDI RECORD
│
├── Fiscal identity
│   ├── UUID
│   ├── version
│   ├── series
│   ├── folio
│   ├── dates
│   └── type
│
├── Issuer
├── Receiver
│
├── Concepts
├── Taxes
│
├── Complements
│   ├── Payroll
│   ├── INE
│   └── Future complements
│
├── CFDI relationships
│
├── Documents
│   ├── Original XML
│   ├── Original PDF
│   ├── Generated PDF
│   └── Evidence
│
├── SAT
│   ├── Current status
│   ├── Status history
│   └── Cancellation information
│
├── Classification
├── Provenance
│
├── Accounting context
│   ├── Entity
│   ├── Accounting ID
│   ├── SIF
│   ├── Policies
│   └── Movements
│
├── Reconciliation
├── Inference
├── Risks
├── Human decisions
└── Audit history
```

---

# 4. Product pillars

AURUM will be structured around several first-class domains.

---

## 4.1 CFDI Core

The CFDI Core is responsible for understanding the fiscal document.

### Responsibilities

* ingest XML;
* identify CFDI;
* extract UUID;
* validate identity;
* calculate document hash;
* detect duplicates;
* parse fiscal attributes;
* extract issuer;
* extract receiver;
* extract concepts;
* extract taxes;
* extract complements;
* classify documents;
* preserve parser provenance;
* support future reprocessing.

### CFDI information

Initial support should include:

* CFDI 3.x where required by historical information;
* CFDI 4.0;
* Timbre Fiscal Digital;
* subtotal;
* discount;
* total;
* currency;
* exchange rate;
* payment method;
* payment form;
* place of issue;
* certificate data;
* fiscal regimes;
* CFDI use.

### Concepts

Each concept should preserve:

* ClaveProdServ;
* quantity;
* unit;
* ClaveUnidad;
* description;
* unit value;
* amount;
* discount;
* ObjetoImp;
* concept-level taxes.

### Taxes

Support:

* IVA;
* ISR;
* IEPS;
* transferred taxes;
* retained taxes;
* rate;
* quota;
* exempt;
* concept-level lines;
* comprobante-level lines.

### Payroll

Payroll 1.2 should support detailed extraction of:

* payroll type;
* payment date;
* start/end dates;
* paid days;
* perceptions;
* deductions;
* other payments;
* subsidy;
* employee fiscal/work information.

### INE

Support:

* TipoProceso;
* TipoComite;
* IdContabilidad;
* entity;
* scope;
* multiple accounting contexts where applicable.

### CFDI relationships

Relationships must support multiple related UUIDs.

The model must not assume one-to-one relationships.

---

# 5. Document Center

The Document Center will manage files related to fiscal records.

### Initial document types

* original XML;
* original PDF;
* generated representation;
* SAT metadata;
* acknowledgement;
* SIF evidence;
* future supporting documents.

### Principles

The original XML must be preserved exactly as received.

AURUM must know:

* document type;
* source;
* hash;
* file size;
* storage location;
* associated CFDI;
* ingestion date;
* integrity state.

Folders are not the source of truth.

The database represents the operational model.

The storage layer preserves file bytes.

---

# 6. SAT Center

SAT is a first-class subsystem.

AURUM must support both immediate queries and long-term monitoring.

Conceptually:

```text
SAT CENTER
│
├── Live Validation
├── Status History
├── Monitoring
├── Change Detection
├── Massive Download
├── Metadata
├── Requests
├── Packages
└── Recovery
```

---

## 6.1 Live validation

AURUM should validate CFDI using its structured database values whenever possible instead of reparsing XML for every query.

Relevant information includes:

* issuer RFC;
* receiver RFC;
* total;
* UUID.

Results may include:

* CódigoEstatus;
* Estado;
* EsCancelable;
* EstatusCancelacion.

---

## 6.2 SAT historical observations

SAT state is not part of the immutable XML.

It is a time-dependent observation.

Example:

```text
UUID ABC

2026-06-01  VIGENTE
2026-07-01  VIGENTE
2026-08-01  VIGENTE
2026-09-07  CANCELADO
```

AURUM must preserve all relevant observations.

It may also maintain a convenient current-state value.

---

## 6.3 Continuous SAT monitoring

SAT monitoring is a central requirement.

AURUM should eventually support configurable monitoring policies.

Examples:

```text
Recently imported CFDI
→ check frequently

Never checked CFDI
→ high priority

High-value CFDI
→ higher monitoring priority

CFDI linked to active accounting records
→ higher monitoring priority

Older unchanged CFDI
→ lower frequency

Cancelled CFDI
→ specialized monitoring policy
```

Monitoring must not depend on the desktop UI remaining open.

---

## 6.4 Status changes

A change such as:

```text
VIGENTE → CANCELADO
```

must create an operational event.

Example:

```text
SAT STATUS CHANGE

UUID: ...
Previous: VIGENTE
Current: CANCELADO
Detected at: ...
Amount: ...
Policies affected: ...
Accounting context: ...
Severity: HIGH
```

This change can become an input to the Risk Engine.

---

## 6.5 SAT massive download

Future capabilities should include:

* e.firma authentication;
* issued CFDI;
* received CFDI;
* XML requests;
* metadata requests;
* asynchronous requests;
* verification;
* package download;
* ZIP extraction;
* recovery;
* retry policies;
* diagnostics.

These operations should eventually use durable jobs.

---

# 7. SIF / Accounting Core

SIF is a first-class subsystem.

AURUM must not treat SIF merely as an Excel importer.

The objective is to represent enough accounting information to understand the actual accounting lifecycle of a CFDI.

---

## 7.1 Accounting context

Initial concepts include:

* organization;
* accounting entity;
* accounting ID;
* accounting period;
* account catalog;
* policy;
* policy movement;
* policy relationship;
* SIF evidence;
* policy status.

---

## 7.2 Policy

Conceptually:

```text
POLICY
│
├── Identifier
├── Entity
├── Accounting context
├── Period
├── Type
├── Subtype
├── Date
├── Description
├── Status
├── Movements[]
├── CFDI[]
└── Evidence
```

---

## 7.3 Policy movement

A movement may include:

* account;
* line number;
* charge;
* credit;
* description;
* reference;
* operational identifiers;
* source.

---

## 7.4 SIF evidence

AURUM should distinguish:

* active evidence;
* missing evidence;
* evidence without effect;
* deleted evidence;
* unknown evidence states.

Evidence status should not be confused with CFDI SAT state.

---

# 8. Reconciliation Center

The Reconciliation Center determines the relationship between fiscal and accounting information.

Possible states include:

```text
CFDI_WITH_POLICY
CFDI_WITHOUT_POLICY
POLICY_WITH_CFDI
POLICY_WITHOUT_CFDI
MULTIPLE_POLICIES
MULTIPLE_CFDI
AMOUNT_MISMATCH
SIF_EVIDENCE_MISSING
LINK_REQUIRES_REVIEW
```

---

## 8.1 CFDI ↔ Policy relationship

The relationship is many-to-many.

Conceptually:

```text
CFDI
  │
  ▼
CFDI_POLICY_LINK
  ▲
  │
POLICY
```

The relationship itself must contain information.

Example:

```text
CFDI_POLICY_LINK
│
├── CFDI
├── Policy
├── Relationship type
├── Source
├── SIF evidence status
├── CFDI amount
├── Related accounting amount
├── Difference
├── Match percentage
├── Confirmation state
├── Confirmed by
└── Confirmed at
```

---

## 8.2 Relationship provenance

A link should explain how it was created.

Examples:

```text
SIF_IMPORT
UUID_MATCH
INFERENCE_ENGINE
MANUAL
MIGRATION
```

Imported truth and inferred suggestions must never be indistinguishable.

---

# 9. Inference Engine

The Inference Engine is a core AURUM component.

Its purpose is:

> Determine which accounting policy or policies most likely correspond to a CFDI and explain the evidence supporting the result.

Inference does not mean confirmation.

---

## 9.1 Expert architecture

Conceptually:

```text
INFERENCE ENGINE
│
├── Context Expert
├── Counterparty Expert
├── UUID Expert
├── Temporal Expert
├── Amount Expert
├── Fiscal Account Expert
├── Payroll Expert
└── Specialized Experts
```

Possible future specialized experts:

* Honorarios.
* HONORARIOS RESICO.
* Arrendamiento.
* Payroll.
* Social security.
* Fuel.
* Credit notes.
* Payment complements.
* INE-specific operations.

---

## 9.2 Candidate ranking

A candidate result should expose both total score and its components.

Example:

```text
Policy candidate EG-109

Context              15 / 15
Counterparty         24 / 30
Temporal             14 / 15
Amounts              19 / 20
Fiscal accounts      17 / 20
───────────────────────────
TOTAL                89 / 100
```

AURUM should never rely only on a hidden confidence number.

---

## 9.3 Evidence

Evidence should become a first-class concept.

Examples:

```text
EVIDENCE

type: UUID_MATCH
source: POLICY_MOVEMENT
value: ABC...
score: 30
```

```text
EVIDENCE

type: TEMPORAL_MATCH
cfdi_date: ...
policy_date: ...
distance_days: 1
score: 14
```

```text
EVIDENCE

type: AMOUNT_MATCH
expected: 16000.00
observed: 16000.00
account_role: ...
score: 19
```

---

## 9.4 Human confirmation

The engine proposes.

A human can:

* confirm;
* reject;
* choose another candidate;
* leave unresolved.

Example:

```text
Candidate A → 91
Candidate B → 76
Candidate C → 54

Human decision:
CONFIRM A
```

That decision must be historically preserved.

---

## 9.5 Future learning

AURUM should first accumulate high-quality supervised decisions.

Before machine learning is considered, the system should measure:

* top-1 accuracy;
* top-3 accuracy;
* false positives;
* rejected high-confidence matches;
* performance by CFDI type;
* performance by accounting context;
* performance by inference-engine version.

Learning should be evidence-driven, not assumed.

---

# 10. Risk & Alerts Engine

Inference and risk must remain separate.

The Inference Engine asks:

> Where does this CFDI probably belong?

The Risk Engine asks:

> What requires attention?

Possible rules include:

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
ACCOUNTING_CONTEXT_MISSING
MULTIPLE_SUSPICIOUS_LINKS
```

---

## 10.1 Attention Center

A future AURUM dashboard should prioritize work rather than only display statistics.

Example:

```text
AURUM ATTENTION CENTER

CRITICAL      7
HIGH         21
MEDIUM       84
INFORMATION  32
RESOLVED   3421
```

This may become a primary operational workflow.

---

# 11. Cases and human work

Complex inconsistencies may eventually become work cases.

Example:

```text
CASE AU-2026-00381

CFDI:
...

Issue:
No SIF policy relationship found

Inference:
3 candidates detected

Status:
IN_REVIEW

Assigned to:
...

Resolution:
Policy EG-203 confirmed
```

This allows AURUM to evolve from passive reporting into an operational control system.

---

# 12. Facts, observations, inferences and decisions

AURUM must formally distinguish these concepts.

---

## 12.1 Facts

Information extracted directly from immutable evidence.

Examples:

* UUID;
* issuer RFC;
* receiver RFC;
* total;
* concepts;
* taxes;
* issuance date.

---

## 12.2 Observations

External or time-dependent information.

Examples:

* SAT state;
* cancellation state;
* SIF evidence state;
* external status.

---

## 12.3 Inferences

Machine-generated conclusions with uncertainty.

Example:

```text
Policy EG-109 compatibility = 89%
```

---

## 12.4 Decisions

Confirmed operational actions.

Examples:

* user confirmed policy EG-109;
* candidate EG-203 rejected;
* classification manually corrected.

These concepts should not overwrite each other.

---

# 13. Provenance

Important information should preserve its source whenever practical.

Examples:

```text
id_contabilidad
source = CFDI_INE_COMPLEMENT
```

```text
policy_link
source = SIF_IMPORT
```

```text
classification
source = CLASSIFICATION_ENGINE
```

```text
sat_status
source = SAT_SOAP
```

```text
policy_candidate
source = INFERENCE_ENGINE_V1
```

Provenance improves:

* debugging;
* trust;
* auditability;
* reprocessing;
* explanation.

---

# 14. Rule and engine versioning

Business rules will evolve.

AURUM must therefore allow relevant results to retain the version that produced them.

Examples:

```text
classification = HONORARIOS
ruleset_version = 2.1
classified_at = ...
```

```text
inference_engine_version = 1.4
candidate_score = 91
```

This makes historical comparison possible.

---

# 15. Reprocessing

AURUM must assume that parsers, mappings, and rules will improve.

The original XML therefore needs to remain available for future reprocessing.

Example:

```text
Reprocess

scope: CFDI 2025
parser_version: 3
classification_ruleset: 2.4
```

Reprocessing should create new operational representations while preserving auditability.

---

# 16. Reporting & Analytics

AURUM should reduce dependence on Excel as the primary operational interface.

Initial analytics may include:

* total CFDI;
* CFDI amounts;
* active SAT CFDI;
* cancelled CFDI;
* SAT changes;
* total policies;
* total movements;
* reconciliation coverage;
* CFDI without policy;
* policies without CFDI;
* SIF evidence issues;
* accounting differences;
* inference coverage;
* unresolved risks.

Excel and CSV remain useful export formats.

They must not dictate the internal data model.

---

# 17. Jobs & background processing

Long-running operations must eventually execute independently from the UI.

Examples:

* batch ingestion;
* CFDI parsing;
* reprocessing;
* SAT monitoring;
* SAT massive download;
* SIF import;
* ledger import;
* inference;
* report generation;
* PDF rendering.

Conceptual job:

```text
JOB
│
├── id
├── type
├── status
├── requested_at
├── started_at
├── finished_at
├── total_items
├── processed_items
├── successful_items
├── warning_items
├── failed_items
└── logs
```

Possible statuses:

```text
PENDING
RUNNING
COMPLETED
COMPLETED_WITH_WARNINGS
FAILED
CANCELLED
```

---

# 18. Audit and event history

AURUM should be capable of explaining what happened to a CFDI over time.

Example:

```text
10:14 CFDI imported
10:14 XML identity validated
10:15 Classified as HONORARIOS
10:17 SAT observation: VIGENTE
09:22 SIF policy data imported
09:23 Three policy candidates generated
09:26 User confirmed policy EG-193
02:03 SAT observation: VIGENTE
02:05 SAT observation: CANCELADO
02:05 Critical accounting-impact alert generated
```

This should eventually support fiscal and operational audits.

---

# 19. Multi-organization capability

The first use of AURUM may focus on a single organization.

The architecture must nevertheless avoid hardcoding institutional values into the core.

Avoid:

```text
ORGANIZATION_RFC = ...
```

Prefer:

```text
Organization
│
├── RFC
├── Fiscal profile
├── Accounting entities
├── Accounting catalogs
├── SIF configuration
└── Ruleset configuration
```

This produces a cleaner architecture even if multi-organization support is not exposed in V1.

---

# 20. Integration architecture

AURUM should eventually expose stable application services or APIs.

Conceptually:

```text
Web UI ──┐
CLI ─────┤
N8N ─────┼──── AURUM API
LU ──────┘
```

Possible capabilities:

```text
search_cfdi()
get_cfdi_detail()
ingest_cfdi()

check_sat_status()
get_sat_history()

search_policy()
get_policy_detail()

get_reconciliation_status()

find_policy_candidates()
explain_inference()

get_alerts()

generate_report()
```

---

# 21. Future Lu integration

AURUM must work independently from Lu.

Lu will eventually become another consumer of AURUM.

Lu should not directly depend on:

* SQL;
* internal tables;
* filesystem paths;
* SAT SOAP implementation;
* SAT download implementation;
* parser internals;
* SIF Excel formats.

Instead:

```text
LU
 │
 ▼
AURUM API
 │
 ├── CFDI services
 ├── SAT services
 ├── SIF services
 ├── policy services
 ├── inference services
 ├── risk services
 └── reporting services
```

This protects both projects from tight coupling.

---

# 22. Legacy strategy

Legacy systems are knowledge sources.

They provide:

* business rules;
* parsing knowledge;
* tested workflows;
* edge cases;
* integration knowledge;
* user-interface ideas;
* accounting patterns.

Every legacy capability should eventually be classified as:

```text
REUSE
REFACTOR
REDESIGN
DISCARD
```

No legacy application should be copied wholesale into AURUM.

---

# 23. Development philosophy

AURUM will use small, controlled increments.

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
Update project documentation
```

Important principles:

* avoid premature implementation;
* prefer explicit contracts;
* test domain behavior;
* separate domain from infrastructure;
* keep UI replaceable;
* make important operations auditable;
* do not hide uncertainty;
* avoid destructive migrations without strategy;
* maintain `PROJECT_STATE.md`.

---

# 24. Initial definition of success

AURUM V1 should eventually support an integrated workflow like:

```text
Receive CFDI
↓
Validate identity
↓
Preserve original XML
↓
Extract fiscal information
↓
Persist structured representation
↓
Associate documents
↓
Consult SAT
↓
Preserve SAT history
↓
Continuously monitor relevant CFDI
↓
Import SIF / accounting information
↓
Reconstruct policies and movements
↓
Detect known CFDI-policy relationships
↓
Identify unresolved CFDI
↓
Run explainable inference
↓
Present candidates
↓
Receive human confirmation
↓
Detect accounting/fiscal risks
↓
Preserve complete audit history
```

All within one platform.

---

# 25. Product statement

> **AURUM will be the fiscal and accounting intelligence center where every CFDI can be identified, understood, monitored, documented, reconciled, explained, and audited from end to end.**
