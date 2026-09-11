# AURUM — Accounting Source Evidence

**Status:** Evidence-backed design checkpoint. PolicyIdentitySchema v1 is accepted for
domain design; this is not a persistence or importer specification.

## 1. Status and scope

This ledger records the evidence used to guide the Accounting / SIF Core, starting with
Policy Identity and Mayor semantics. It deliberately separates:

- **Observed operational evidence:** facts seen in representative operational files,
  catalogs, historical data, or deterministic legacy processing.
- **Accounting / normative support:** topics that require authoritative accounting or
  official fiscal/SIF sources.
- **Provisional interpretation:** useful design direction that is not yet a domain
  invariant.
- **Open research:** questions that must not be silently resolved in code.

It does not itself authorize a migration, importer, automatic reconciliation rule, or
accounting conclusion.

## 2. Evidence hierarchy

Use the highest available evidence for a decision:

1. Direct structured observation from Reporte XML SIF.
2. Direct structured observation from Reporte de Mayor.
3. Repeated deterministic behavior confirmed in representative source files or legacy
   processing.
4. Accounting catalog or reference data.
5. Human-confirmed operational interpretation.
6. Historical or statistical evidence.
7. Heuristic or inference.

Lower-authority evidence must not silently override a higher-authority observation. A
derived conclusion must retain the observations and rule/version that support it.

## 3. Policy Identity evidence

### Observed operational evidence

Representative source forms expose candidate structured dimensions:

- entity or accounting context;
- `accounting_id` / `id_contabilidad`;
- fiscal or accounting year;
- accounting period;
- policy type;
- policy subtype; and
- policy number.

Observed renderings include a legacy/SIF-like form such as
`ENTITY_ACCOUNTING_P<type-code>-<subtype-code>-<number>/<period>-<year>` and a
Mayor reference form such as `YEAR-N-SUBTYPE-NUMBER-MONTH`. These are source
representations, not canonical truth, and one sample must not freeze a parser.

### Accepted domain-design direction

`PolicyIdentitySchema` defines the required identity dimensions, optional non-identity
dimensions, and source-only dimensions for an accepted accounting identity model.
The current seven dimensions are the PolicyIdentitySchema v1 candidate tuple for domain
design. Raw `POLIZA` strings are retained separately, and multiple representations may
resolve to one identity. Leading-zero and lexical-equivalence behavior must be explicit;
it is never guessed.

### Still provisional

PolicyIdentitySchema v1 does **not** freeze the final PostgreSQL UNIQUE tuple. Source
evidence has established the structural design direction, but persistence design must
still confirm the exact identity scope and any canonical AccountingContext boundary.

## 4. AccountingContext evidence

### Observed operational evidence

An explicit `id_contabilidad` is strong structured evidence. Accounting catalog/reference
data can associate it with entity, scope or ámbito, committee, and process where supplied.

Historical provider/entity affinity is only probabilistic evidence; it is not master data
and must not establish accounting context by itself.

### Accepted domain-design direction

Policy Identity should ultimately reference a normalized `AccountingContext` (or accepted
equivalent), rather than duplicate uncontrolled entity/accounting strings. The present
tuple exposes entity and `accounting_id` for clarity and legacy compatibility. The exact
persistence representation remains a later design decision.

## 5. Mayor acquisition and provenance

### Observed operational evidence

Mayor reports are periodic external SIF snapshots, normally acquired month by month for
multiple entities or committees and parameterized by year, ámbito, entity, and date range.
Legacy workflows consolidate them downstream.

### Accepted domain-design direction

Future ingestion preserves the immutable original file, acquisition/import occurrence,
requested context, context found inside the file, importer/parser version, and row/source
location. Repeated monthly imports are new provenance observations, not new PolicyIdentity
records merely because the same policy appears again.

## 6. Policy to AccountingMovement

### Supported invariant

One `PolicyIdentity` has many `AccountingMovement` records. A policy is an accounting
grouping composed of movements across accounts; movement attributes do not define or mutate
Policy Identity.

### Observed movement fields

Representative Mayor data includes account, source description, accounting period, policy
type/subtype/number, registration date, operation date, movement concept/narrative, origin
of registration, policy reference, CEI/project/office/observation fields where present,
debit, credit, balance, and source provenance.

Future fiscal/accounting quantities use exact decimals, never float semantics.

## 7. Movement narrative evidence

### Observed operational evidence

`Concepto del Movimiento` is a high-value semantic source. It can signal accounting actions
such as PROVISION, PAGO, TRANSFERENCIA, COMPROBACION, REEMBOLSO, REPOSICION, AJUSTE, and
RECLASIFICACION; it can also contain persons/suppliers, invoice or folio references,
economic purpose, month/period, and policy references. Human-entered narrative has spelling
variants, abbreviations, and errors.

### Accepted domain-design direction

Preserve `concept_raw` faithfully. Any normalized extraction or future
`MovementNarrativeAnalysis` is derived, versioned, explainable evidence—not a replacement
for source text or a frozen table design.

## 8. Policy references and inter-policy relations

### Observed operational evidence

A populated Policy Reference does not mean reversal by itself. A strong observed reversal
pattern combines all of the following: `Origen del Registro = REVERSA DE POLIZA`, a populated
reference resolvable to an original policy, and the same accounts and amounts with exact
opposite accounting effect.

Adjustments and reclassifications often reference another policy in reviewed evidence, but
their exact accounting and legal semantics require normative research.

### Provisional direction

Future relations may include `REVERSAL`, `ADJUSTMENT`, and `RECLASSIFICATION`. Do not freeze
SQL enums or automate conclusions from a reference alone.

## 9. DR / EG and accounting-role interpretation

### Observed tendencies

`DR` frequently appears with provisioning, recognition, comprobación, and honorarios
narratives. `EG` frequently appears with payment, transfer, payroll, honorarios, and
reimbursement narratives.

### Provisional interpretation

Do **not** encode `DR == PROVISION` or `EG == PAYMENT`. A future AccountingRole inference
could combine subtype, narrative, account structure, debit/credit pattern, dates, policy
relations, and source evidence. Possible roles include provision, payment, reimbursement,
reclassification, and reversal; none is implied by subtype alone.

## 10. Petty cash / caja chica evidence

### Observed operational evidence

Petty-cash or fondo-fijo policies can include multiple suppliers, small heterogeneous
purchases, and reimbursement/resupply narratives. A responsible person may differ from the
actual CFDI issuers.

### Design consequence

Supplier-to-policy matching cannot assume one policy equals one supplier. Future
reconciliation may need to segment narrative into several economic events. Do not create a
CajaChica-specific persistence model now.

## 11. CFDI to Policy relation evidence

### Supported invariant

`CFDI <-> Policy` is many-to-many. A provision and payment policy may both relate to a CFDI,
and one policy can include multiple CFDIs or persons.

The future relationship—not PolicyIdentity—must preserve source, status/history, role when
known, provenance, and separate human-decision or inference state. There is no canonical
single policy per UUID.

## 12. Reporte XML SIF evidence

### Observed operational evidence

Reporte XML SIF provides direct UUID-to-POLIZA evidence, exposes structured policy components,
and can expose `ACTIVA` or `SIN EFECTO` relation status. It is stronger relationship evidence
than inference.

`SIN EFECTO` is not a Mayor PolicyIdentity state. Mayor corrections may appear through
reversals, reclassifications, or adjustments. Future reconciliation may correlate these
sources, but must not automate causality without supporting evidence.

## 13. Fiscal and accounting temporal evidence

### Observed operational evidence

CFDI timbrado date is a strong temporal search signal. Mayor includes special periods such as
`CIERRE`. Report-download year and parser-execution time never define the accounting year.

### Provisional interpretation

Accounting is generally expected to align with a relevant timbrado period, but that is not a
universal hard invariant. Recognition-period rules need accounting/normative research.

## 14. Reconciliation evidence order

This is a provisional priority, not a numeric scoring model:

1. Direct Reporte XML SIF UUID-to-Policy observation.
2. Explicit `id_contabilidad` / AccountingContext.
3. Relevant structured CFDI evidence, including accounting identifiers where applicable.
4. Supplier/person evidence in movement narrative.
5. Temporal compatibility.
6. Financial amount compatibility.
7. Account-pattern compatibility.
8. Historical provider/entity or provider/policy patterns.
9. Weak token heuristics.

## 15. Human decision loop

Future reconciliation may propose ranked candidates. A human can accept one, reject
candidates, assign a different policy, explain how it was found, or leave the CFDI unresolved
while assigning entity/accounting context.

The decision must retain selected policy, rejected candidates, reason, evidence, free-text
explanation, user and timestamp, and the producing rule/model version. It is auditable
evidence, not automatic self-training truth.

## 16. External entity-resolution workflow

When no policy is found, operations may identify likely entity/context and send an Excel or
report to the state/entity. Responses can recognize the transaction, deny it, supply a
different policy, start reconciliation/cancellation work, or leave it pending.

Future Case Management should preserve what was sent, when and to whom, included UUIDs/cases,
responses/reply chain, attachments, and later resolution. External committees need not use
AURUM directly. This is not implementation scope now.

## 17. SIF change-resilience requirement

SIF is an external mutable system. Therefore SIF XLS/XLSX layouts are adapter contracts, not
domain models: preserve raw files, version importers, and fail explicitly and observably on
schema/column changes. A future SIF redesign requires a new adapter version while stable
business semantics remain canonical in AURUM.

## 18. Accounting / normative research register

Detailed verification against current Mexican NIF is not available locally in this checkpoint.
Do not infer specific NIF conclusions or paragraph citations. Use CINIF/current Mexican NIF as
the primary source family; official SAT CFDI and official INE/SIF material for fiscal and
SIF-specific semantics; IFRS/IASB Conceptual Framework only as secondary conceptual support.

| Topic | Why AURUM needs it | Observed operational behavior | Normative/accounting source needed | Status | Consequence if confirmed |
| --- | --- | --- | --- | --- | --- |
| Accrual/provision vs payment | Role interpretation | DR/EG tendencies and narratives | CINIF NIF | Open | Rule boundary for roles |
| Recognition and cash settlement | Link stages safely | Provision/payment may differ | CINIF NIF | Open | N:M reconciliation rules |
| Reversal treatment | Relation semantics | REVERSA pattern observed | CINIF NIF | Open | Deterministic relation rule |
| Reclassification treatment | Relation semantics | References sometimes present | CINIF NIF | Open | Separate derived relation |
| Adjustment treatment | Relation semantics | References sometimes present | CINIF NIF | Open | Separate derived relation |
| Petty cash/reimbursements | Multi-event policies | Multiple suppliers/concepts | CINIF NIF / practice | Open | Specialized reconciliation |
| Payroll | Role and movement interpretation | EG narratives may mention payroll | CINIF NIF / official rules | Open | Role evidence only |
| Professional fees/honorarios | Classification | DR/EG narratives may mention fees | CINIF NIF / SAT | Open | Derived classification |
| Withholding taxes | Fiscal/accounting effects | Potential movement/tax signals | SAT / CINIF NIF | Open | Reconciliation evidence |
| Credit notes / CFDI de egreso | Economic correction | Source-specific fiscal effects | Official SAT | Open | Link interpretation |
| CFDI related documents | Fiscal linkage | Related-document metadata | Official SAT | Open | Separate fiscal evidence |
| CFDI substitution | Successor semantics | Possible replacement workflows | Official SAT | Open | Historical link handling |
| Cancellation effects | State versus accounting | SIF may say SIN EFECTO | SAT / INE/SIF | Open | No automatic causal rule |
| Recognition period versus dates | Temporal compatibility | Timbrado is a search signal | CINIF NIF / SAT | Open | Avoid hard temporal rule |
| Duplicate economic transaction | Candidate ranking | Repeated operational records | CINIF NIF / methods | Open | Explainable detection |
| Partial payments | N:M settlement | Payment may be incomplete | CINIF NIF / SAT | Open | Link role/evidence |
| Multiple payments per CFDI | N:M settlement | Operationally possible | CINIF NIF / SAT | Open | Link history |
| One payment/policy, many CFDIs | N:M settlement | Policy can group evidence | CINIF NIF / SAT | Open | No 1:1 shortcut |

## 19. PolicyIdentitySchema v1 decision

**Accepted for domain design.** The evidence supports a versioned structured identity,
source-observation separation, unresolved observations for missing required components, and a
deterministic canonical key under an accepted schema.

### Gate status

- **Policy Identity source-evidence gate: CLOSED.** The reviewed source evidence is sufficient
  for PolicyIdentitySchema v1 domain design.
- **Policy Identity persistence-design gate: OPEN.** Persistence design still needs exact
  identity-scope decisions, including AccountingContext scope and the candidate tuple's final
  uniqueness semantics.
- **Accounting normative-semantics gate: OPEN.** Authoritative accounting and fiscal research
  is still required before accounting-semantic automation is finalized.

It does **not** accept a persistence schema, SQL UNIQUE constraint, importer grammar, or the
universal business meaning of each candidate field. Before persistence design, confirm the
scope of `accounting_id` and AccountingContext, whether entity remains independently
identity-defining, whether type/subtype are identity dimensions in each source, special-period
handling, and policy-number lexical/equivalence rules.

## 20. Open questions

- What is the exact identity role of `accounting_id` versus normalized AccountingContext?
- Is entity identity-defining once AccountingContext is canonical?
- What is the exact treatment of special period `CIERRE`?
- What do source policy type/subtype codes mean, and when are they identity-defining?
- How should partial payments and provision/payment stages be related?
- What are the fiscal/accounting effects of credit notes and CFDI substitutions?
- What are the normative meanings of adjustment, reclassification, and reversal?
- How can AccountingRole be inferred safely and explainably?
- How should adapter versions accommodate future SIF layout evolution?

## 21. Design checkpoint invariants

1. Policy identity is structured; a concatenated POLIZA string is never sole truth.
2. Source observations retain raw representation and provenance separately from identity.
3. Required fields are defined by PolicyIdentitySchema; missing required data remains an
   unresolved observation and does not fabricate a complete identity.
4. Identity fields are immutable once created under an accepted schema; corrections preserve
   history rather than silently rewriting it.
5. Policy-to-movement is 1:N; CFDI-to-Policy is N:M and has independent provenance/status.
6. Direct SIF UUID-to-Policy evidence outranks inference; inference cannot mutate identity or
   automatically confirm a relationship.
7. Normative semantic automation remains gated on authoritative research.
