# AURUM — Domain Model

**Version:** 0.1
**Status:** Initial domain model
**Current phase:** Phase 3 — Technical Architecture

---

# 1. Purpose

This document defines the initial domain model of AURUM.

Its purpose is to identify the main business entities, value objects, relationships, ownership rules, historical concepts, and boundaries that will later guide:

* PostgreSQL schema design;
* repository design;
* API contracts;
* application services;
* inference architecture;
* audit behavior.

This document intentionally describes the domain before defining physical database tables.

The database must adapt to the domain model, not the opposite.

---

# 2. Domain modeling principles

## 2.1 Fiscal evidence and operational state are different

AURUM must distinguish:

```text
IMMUTABLE EVIDENCE
        ↓
      FACTS
        ↓
  OBSERVATIONS
        ↓
   INFERENCES
        ↓
    DECISIONS
```

Examples:

### Immutable evidence

* Original CFDI XML.
* Original PDF.
* SIF source file.

### Fact

* UUID.
* RFC issuer.
* CFDI total.
* Policy movement amount.

### Observation

* SAT status at a specific time.
* SIF evidence status.

### Inference

* Policy A is a likely accounting match.

### Decision

* User confirms Policy A.

These concepts must not overwrite one another.

---

# 3. Aggregate overview

Initial AURUM domain map:

```text
Organization
│
├── AccountingEntity
│    └── AccountingContext
│         ├── Account
│         ├── Policy
│         │    └── PolicyMovement
│         └── SIFEvidence
│
├── Party
│
└── CFDI
     ├── CFDIConcept
     ├── CFDITax
     ├── CFDIRelationship
     ├── Payroll
     ├── INEComplement
     ├── Document
     ├── SATObservation
     ├── CFDIPolicyLink
     ├── InferenceRun
     ├── Risk
     └── AuditEvent
```

Cross-domain concepts:

```text
Evidence
Decision
Job
AuditEvent
Provenance
RuleVersion
```

---

# 4. Organization

## Purpose

Represents the organization operating inside AURUM.

Even if the first deployment uses only one organization, institutional data should not be hardcoded into domain logic.

## Possible attributes

```text
Organization
├── id
├── name
├── fiscal_name
├── rfc
├── active
├── created_at
└── updated_at
```

## Responsibilities

Organization may define configuration such as:

* fiscal identity;
* accounting structure;
* SAT monitoring configuration;
* SIF configuration;
* classification rules;
* risk rules.

## Relationships

```text
Organization 1 ─── N AccountingEntity
Organization 1 ─── N AccountingContext
Organization 1 ─── N CFDI
Organization 1 ─── N Party roles
```

Exact ownership of CFDI may depend on future multi-organization design.

---

# 5. Party

## Purpose

Represents a fiscal or operational person/entity.

A Party may participate in different roles.

Examples:

* CFDI issuer;
* CFDI receiver;
* supplier;
* employee;
* customer;
* service provider.

Avoid creating separate duplicate master entities when the same RFC appears in several roles.

---

## Possible attributes

```text
Party
├── id
├── rfc
├── legal_name
├── person_type
├── fiscal_regime
├── active
├── created_at
└── updated_at
```

Possible person type:

```text
INDIVIDUAL
LEGAL_ENTITY
UNKNOWN
```

---

## Party roles

Roles may be represented separately from Party identity.

Examples:

```text
ISSUER
RECEIVER
SUPPLIER
EMPLOYEE
CUSTOMER
```

One Party may have multiple roles.

---

# 6. SupplierProfile

## Purpose

Optional extension of Party for supplier-specific information.

Not every Party must have a SupplierProfile.

## Possible attributes

```text
SupplierProfile
├── party_id
├── supplier_type
├── review_required
├── operational_frequency
├── notes
└── active
```

Possible future information:

* accounting behavior;
* account mappings;
* historical patterns;
* supporting documents.

Supplier enrichment must remain separate from immutable CFDI facts.

---

# 7. CFDI

## Purpose

CFDI is one of AURUM's central aggregate roots.

It represents the normalized fiscal identity and principal structured facts extracted from a CFDI.

---

## Identity

Canonical fiscal identity:

```text
TimbreFiscalDigital/@UUID
```

The UUID must be normalized consistently.

---

## Possible attributes

```text
CFDI
├── id
├── organization_id
├── uuid
├── version
├── series
├── folio
├── issuance_datetime
├── stamping_datetime
├── voucher_type
├── currency
├── exchange_rate
├── subtotal
├── discount
├── total
├── payment_method
├── payment_form
├── expedition_place
├── export_code
├── issuer_party_id
├── receiver_party_id
├── issuer_rfc_snapshot
├── issuer_name_snapshot
├── receiver_rfc_snapshot
├── receiver_name_snapshot
├── fiscal_classification
├── parser_version
├── classification_ruleset_version
├── created_at
└── updated_at
```

---

## Snapshot principle

Even when issuer/receiver map to Party entities, important fiscal values should preserve document-time snapshots.

Example:

```text
Party current name:
PROVEEDOR XYZ NUEVO SA

CFDI issuer_name_snapshot:
PROVEEDOR XYZ SA
```

The CFDI must preserve what the document contained.

---

# 8. CFDIConcept

## Purpose

Represents one fiscal concept inside a CFDI.

## Relationship

```text
CFDI 1 ─── N CFDIConcept
```

## Possible attributes

```text
CFDIConcept
├── id
├── cfdi_id
├── line_number
├── product_service_key
├── identification_number
├── quantity
├── unit_key
├── unit_name
├── description
├── unit_value
├── amount
├── discount
├── tax_object
└── created_at
```

Money and quantities must use decimal semantics.

---

# 9. CFDITax

## Purpose

Represents normalized fiscal tax lines.

A tax can exist at:

* CFDI/comprobante level;
* concept level.

## Relationship

```text
CFDI 1 ─── N CFDITax
CFDIConcept 0..1 ─── N CFDITax
```

## Possible attributes

```text
CFDITax
├── id
├── cfdi_id
├── concept_id nullable
├── level
├── nature
├── tax_code
├── factor_type
├── rate_or_quota
├── tax_base
├── amount
└── created_at
```

Possible `level`:

```text
DOCUMENT
CONCEPT
```

Possible `nature`:

```text
TRANSFERRED
WITHHELD
```

---

# 10. CFDIRelationshipGroup

## Purpose

Represents a CFDI relationship group and its SAT relationship type.

A CFDI may contain multiple relationships.

## Relationship

```text
CFDI 1 ─── N CFDIRelationshipGroup
```

Possible attributes:

```text
CFDIRelationshipGroup
├── id
├── cfdi_id
├── relationship_type
└── created_at
```

---

# 11. CFDIRelatedUUID

## Purpose

Represents one related CFDI UUID inside a relationship group.

## Relationship

```text
CFDIRelationshipGroup 1 ─── N CFDIRelatedUUID
```

Possible attributes:

```text
CFDIRelatedUUID
├── id
├── relationship_group_id
├── related_uuid
└── resolved_cfdi_id nullable
```

`resolved_cfdi_id` may link to another CFDI already known by AURUM.

This avoids assuming all related UUIDs have already been imported.

---

# 12. INEComplement

## Purpose

Represents normalized information extracted from the INE complement.

## Relationship

Depending on actual multiplicity:

```text
CFDI 1 ─── 0..1 INEComplement
```

with multiple accounting references if needed.

Possible attributes:

```text
INEComplement
├── id
├── cfdi_id
├── process_type
├── committee_type
├── created_at
└── parser_version
```

---

# 13. INEAccountingReference

## Purpose

Represents each accounting identifier/context contained in the INE complement.

## Relationship

```text
INEComplement 1 ─── N INEAccountingReference
```

Possible attributes:

```text
INEAccountingReference
├── id
├── ine_complement_id
├── accounting_id_external
├── entity_code
├── scope
├── provenance
└── resolved_accounting_context_id nullable
```

This allows AURUM to preserve the raw fiscal reference even before mapping it to the local accounting catalog.

---

# 14. Payroll

## Purpose

Represents the main Nómina 1.2 complement.

## Relationship

```text
CFDI 1 ─── 0..1 Payroll
```

Possible attributes:

```text
Payroll
├── id
├── cfdi_id
├── payroll_type
├── payment_date
├── initial_payment_date
├── final_payment_date
├── paid_days
├── total_perceptions
├── total_deductions
├── total_other_payments
├── employee_curp
├── employee_nss
├── contract_type
├── work_regime
├── position
├── department
├── periodicity
├── base_salary
├── integrated_daily_salary
├── state_code
└── parser_version
```

---

# 15. PayrollPerception

## Relationship

```text
Payroll 1 ─── N PayrollPerception
```

Possible attributes:

```text
PayrollPerception
├── id
├── payroll_id
├── line_number
├── perception_type
├── code
├── concept
├── taxable_amount
├── exempt_amount
└── amount
```

---

# 16. PayrollDeduction

## Relationship

```text
Payroll 1 ─── N PayrollDeduction
```

Possible attributes:

```text
PayrollDeduction
├── id
├── payroll_id
├── line_number
├── deduction_type
├── code
├── concept
└── amount
```

---

# 17. PayrollOtherPayment

## Relationship

```text
Payroll 1 ─── N PayrollOtherPayment
```

Possible attributes:

```text
PayrollOtherPayment
├── id
├── payroll_id
├── line_number
├── payment_type
├── code
├── concept
├── amount
└── subsidy_amount nullable
```

---

# 18. Document

## Purpose

Represents one document managed by AURUM.

Document identity is not the same as CFDI identity.

## Possible types

```text
CFDI_XML
CFDI_PDF
GENERATED_PDF
SAT_METADATA
SAT_ACKNOWLEDGEMENT
SIF_EVIDENCE
IMPORT_SOURCE
OTHER
```

## Possible attributes

```text
Document
├── id
├── document_type
├── original_filename
├── mime_type
├── sha256
├── byte_size
├── storage_key
├── source
├── immutable
├── created_at
└── stored_at
```

---

# 19. DocumentLink

## Purpose

Allows documents to be associated with different domain entities.

Possible associations:

* CFDI;
* Policy;
* import job;
* evidence;
* risk/case later.

Instead of hardcoding every document relationship, a typed linking strategy may be considered.

Exact implementation will be decided in database design.

---

# 20. SATObservation

## Purpose

Represents one historical observation returned by a SAT status provider.

A SAT observation is immutable historical evidence of a query result.

## Relationship

```text
CFDI 1 ─── N SATObservation
```

## Possible attributes

```text
SATObservation
├── id
├── cfdi_id
├── provider
├── checked_at
├── outcome
├── status_code
├── fiscal_status
├── cancellable_status
├── cancellation_status
├── raw_response_reference nullable
├── response_duration_ms nullable
├── error_code nullable
├── error_message nullable
└── created_at
```

---

# 21. SAT observation outcome vs fiscal state

These concepts must remain separate.

Possible provider outcome:

```text
SUCCESS
NOT_FOUND
INVALID_QUERY
NETWORK_ERROR
TIMEOUT
SAT_UNAVAILABLE
PROVIDER_ERROR
```

Fiscal state may include:

```text
VIGENTE
CANCELADO
NO_ENCONTRADO
UNKNOWN
```

Only successful/semantically valid provider responses should produce authoritative fiscal observations.

---

# 22. CFDICurrentSATState

## Purpose

Provides convenient current-state access without discarding observation history.

This may be:

* persisted projection;
* derived query/view;
* cached projection.

Exact database strategy remains open.

Conceptually:

```text
CFDI Current SAT State
├── cfdi_id
├── latest_observation_id
├── fiscal_status
├── last_checked_at
└── changed_at
```

The observation history remains authoritative.

---

# 23. SATStatusTransition

## Purpose

Represents a meaningful detected transition between SAT states.

Example:

```text
VIGENTE → CANCELADO
```

Possible attributes:

```text
SATStatusTransition
├── id
├── cfdi_id
├── previous_observation_id
├── current_observation_id
├── previous_status
├── current_status
├── detected_at
└── created_at
```

This transition may become an input to the Risk Engine.

---

# 24. AccountingEntity

## Purpose

Represents a major accounting/institutional entity.

Example interpretation may correspond to an entity/state/committee context depending on the source.

## Relationship

```text
Organization 1 ─── N AccountingEntity
```

Possible attributes:

```text
AccountingEntity
├── id
├── organization_id
├── external_code
├── name
├── active
└── created_at
```

---

# 25. AccountingContext

## Purpose

Represents the precise accounting context used by SIF/INE/policies.

This may correspond to what legacy systems called `id_contabilidad`.

## Relationship

```text
AccountingEntity 1 ─── N AccountingContext
```

Possible attributes:

```text
AccountingContext
├── id
├── accounting_entity_id
├── external_accounting_id
├── name
├── scope
├── committee_type
├── process_type
├── year nullable
├── active
├── source
└── created_at
```

The domain should not assume external IDs are globally unique without scope.

---

# 26. Account

## Purpose

Represents an accounting account.

## Relationship

An account belongs to an accounting catalog/context depending on future modeling.

Possible attributes:

```text
Account
├── id
├── organization_id
├── external_account_code
├── name
├── normalized_name
├── account_role nullable
├── active
├── source
└── created_at
```

Possible `account_role` may later include:

```text
BANK
EXPENSE
IVA_TRANSFERRED
IVA_WITHHELD
ISR_WITHHELD
SUPPLIER
PAYROLL
OTHER
```

Roles should be explicit mappings, not inferred forever through string `LIKE`.

---

# 27. Policy

## Purpose

Policy is a central Accounting aggregate.

## Relationship

```text
AccountingContext 1 ─── N Policy
Policy 1 ─── N PolicyMovement
```

## Possible attributes

```text
Policy
├── id
├── accounting_context_id
├── external_policy_id nullable
├── folio
├── policy_type
├── policy_subtype
├── period_year
├── period_month
├── policy_date
├── description
├── source_status
├── import_source
├── created_at
└── updated_at
```

---

# 28. PolicyMovement

## Purpose

Represents one accounting movement.

## Possible attributes

```text
PolicyMovement
├── id
├── policy_id
├── account_id
├── line_number
├── charge
├── credit
├── description
├── reference
├── external_movement_id nullable
├── source
├── created_at
└── updated_at
```

Amounts must use exact decimal values.

---

# 29. PolicyReference

## Purpose

Represents explicit relationships/references between policies when provided by accounting source data.

Possible relationship types inherited conceptually from legacy work:

```text
RECLASSIFICATION
ADJUSTMENT
REVERSAL
CANCELLATION
REFERENCE
OTHER
```

Relationship:

```text
Policy N ─── N Policy
```

through `PolicyReference`.

---

# 30. SIFEvidence

## Purpose

Represents the operational SIF evidence state related to a policy/CFDI accounting relationship.

Possible attributes:

```text
SIFEvidence
├── id
├── policy_id
├── external_evidence_id nullable
├── status
├── effective_at nullable
├── ineffective_at nullable
├── source
├── imported_at
└── raw_status
```

Possible normalized status:

```text
ACTIVE
MISSING
WITHOUT_EFFECT
DELETED
UNKNOWN
```

Exact semantics will be refined using real SIF data.

---

# 31. CFDIPolicyLink

## Purpose

Represents the known or proposed relationship between a CFDI and an accounting policy.

This is a first-class domain entity.

## Relationship

```text
CFDI N ─── N Policy
```

through:

```text
CFDIPolicyLink
```

---

## Possible attributes

```text
CFDIPolicyLink
├── id
├── cfdi_id
├── policy_id
├── relationship_type
├── state
├── source
├── cfdi_amount_reference nullable
├── policy_amount_reference nullable
├── amount_difference nullable
├── match_percentage nullable
├── sif_evidence_id nullable
├── confirmed_by_user_id nullable
├── confirmed_at nullable
├── rejected_at nullable
├── created_at
└── updated_at
```

---

# 32. CFDIPolicyLink relationship type

Possible types:

```text
SIF_IMPORTED
UUID_MATCH
MANUAL
INFERENCE
MIGRATION
OTHER
```

---

# 33. CFDIPolicyLink state

Possible lifecycle:

```text
PROPOSED
CONFIRMED
REJECTED
SUPERSEDED
```

Authoritative imported SIF relationships may enter directly as confirmed depending on future business policy.

This must be explicit.

---

# 34. ReconciliationStatus

## Purpose

Represents derived reconciliation state.

This may not require a dedicated persisted entity.

Possible states:

```text
RESOLVED
NO_POLICY
NO_CFDI
MULTIPLE_LINKS
AMOUNT_MISMATCH
MISSING_SIF_EVIDENCE
REQUIRES_REVIEW
```

Reconciliation state should be calculated consistently by the Reconciliation domain.

Reports must consume the same definition.

---

# 35. InferenceRun

## Purpose

Represents one execution of the Inference Engine.

A run must be historically reproducible where practical.

## Possible attributes

```text
InferenceRun
├── id
├── cfdi_id
├── engine_version
├── configuration_version
├── accounting_scope
├── started_at
├── completed_at
├── status
├── candidate_count
└── created_at
```

---

# 36. InferenceCandidate

## Purpose

Represents one policy considered by an inference run.

## Relationship

```text
InferenceRun 1 ─── N InferenceCandidate
```

Possible attributes:

```text
InferenceCandidate
├── id
├── inference_run_id
├── policy_id
├── rank
├── total_score
├── confidence
├── context_score
├── identity_score
├── temporal_score
├── amount_score
├── fiscal_account_score
├── specialized_score
└── created_at
```

Not all score columns necessarily need to be fixed physical columns.

Database design will determine whether score components become structured rows or JSON.

---

# 37. Evidence

## Purpose

Evidence is one of the most important cross-domain concepts in AURUM.

It represents a structured reason supporting an inference, risk, or reconciliation conclusion.

## Relationship

Initially most Evidence records may belong to an InferenceCandidate.

Conceptually:

```text
InferenceCandidate 1 ─── N Evidence
```

Possible attributes:

```text
Evidence
├── id
├── candidate_id
├── evidence_type
├── expert_type
├── score
├── weight
├── confidence
├── observed_value
├── expected_value
├── metadata
├── ruleset_version
└── created_at
```

---

# 38. Evidence types

Examples:

```text
UUID_MATCH
RFC_MATCH
COUNTERPARTY_TOKEN_MATCH
ACCOUNTING_CONTEXT_MATCH
PERIOD_MATCH
TEMPORAL_DISTANCE
TOTAL_MATCH
SUBTOTAL_MATCH
IVA_MATCH
ISR_MATCH
ACCOUNT_ROLE_MATCH
PAYROLL_AMOUNT_MATCH
HISTORICAL_PATTERN
```

New evidence types should be extensible without redesigning the entire engine.

---

# 39. HumanDecision

## Purpose

Represents a meaningful human decision made in AURUM.

Examples:

* confirm inference candidate;
* reject candidate;
* create manual CFDI-policy link;
* correct classification;
* resolve risk.

Possible attributes:

```text
HumanDecision
├── id
├── decision_type
├── subject_type
├── subject_id
├── decision
├── reason nullable
├── user_id
├── created_at
└── metadata
```

Whether this becomes one generic entity or specialized decision tables will be evaluated later.

---

# 40. Risk

## Purpose

Represents an identified fiscal/accounting operational risk or attention item.

## Possible attributes

```text
Risk
├── id
├── organization_id
├── cfdi_id nullable
├── policy_id nullable
├── risk_type
├── severity
├── status
├── title
├── description
├── ruleset_version
├── detected_at
├── assigned_user_id nullable
├── resolved_at nullable
├── resolution nullable
└── created_at
```

---

# 41. Risk type

Examples:

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
MULTIPLE_SUSPICIOUS_LINKS
```

---

# 42. Risk severity

Possible initial levels:

```text
CRITICAL
HIGH
MEDIUM
LOW
INFO
```

Severity must be determined by explicit rules.

---

# 43. Risk status

Possible lifecycle:

```text
OPEN
ACKNOWLEDGED
IN_REVIEW
RESOLVED
DISMISSED
```

---

# 44. Case

## Status

Potential future domain concept.

Not required in initial V1.

## Purpose

A Case may group multiple related risks or tasks into a human workflow.

Example:

```text
Case
├── CFDI
├── risks
├── candidates
├── assigned user
├── comments
└── resolution
```

Do not implement until operational need is validated.

---

# 45. Job

## Purpose

Represents an asynchronous, scheduled, massive, or long-running process.

## Possible attributes

```text
Job
├── id
├── organization_id nullable
├── job_type
├── status
├── requested_by_user_id nullable
├── requested_at
├── started_at nullable
├── completed_at nullable
├── total_items nullable
├── processed_items
├── successful_items
├── warning_items
├── failed_items
├── progress_percentage
├── configuration
├── result_summary
├── error_summary nullable
└── created_at
```

---

# 46. Job type

Examples:

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

# 47. Job status

Possible states:

```text
PENDING
RUNNING
COMPLETED
COMPLETED_WITH_WARNINGS
FAILED
CANCELLED
```

---

# 48. JobItem

## Purpose

Potential child entity for item-level tracking within massive jobs.

Example:

```text
Job
 ├── CFDI 1 success
 ├── CFDI 2 success
 ├── CFDI 3 warning
 └── CFDI 4 failed
```

This may be useful for:

* massive ingestion;
* SAT validation;
* reprocessing;
* inference.

Exact persistence strategy will be defined later.

---

# 49. AuditEvent

## Purpose

Represents a business-relevant historical event.

Audit is not the same as technical application logging.

## Possible attributes

```text
AuditEvent
├── id
├── organization_id nullable
├── event_type
├── actor_type
├── actor_id nullable
├── subject_type
├── subject_id
├── occurred_at
├── correlation_id nullable
├── provenance
└── metadata
```

---

# 50. Audit event examples

```text
CFDI_IMPORTED
CFDI_PARSED
CFDI_REPROCESSED
CFDI_CLASSIFIED
SAT_CHECKED
SAT_STATUS_CHANGED
SIF_IMPORTED
POLICY_CREATED
POLICY_UPDATED
CFDI_POLICY_LINK_CREATED
INFERENCE_RUN_COMPLETED
INFERENCE_CANDIDATE_CONFIRMED
INFERENCE_CANDIDATE_REJECTED
RISK_CREATED
RISK_RESOLVED
DOCUMENT_STORED
REPORT_EXPORTED
```

---

# 51. User

## Purpose

Represents an authenticated AURUM user.

Authentication implementation is not yet selected.

Possible attributes:

```text
User
├── id
├── email
├── display_name
├── active
├── created_at
└── updated_at
```

Authorization may eventually use roles.

---

# 52. UserRole

Possible future roles:

```text
ADMIN
ANALYST
REVIEWER
READ_ONLY
```

Exact role system is not part of initial domain implementation.

---

# 53. Provenance

## Purpose

Provenance expresses where data or a relationship came from.

Examples:

```text
CFDI_XML
CFDI_INE_COMPLEMENT
SAT_SOAP
SAT_METADATA
SIF_IMPORT
LEDGER_IMPORT
MANUAL
INFERENCE_ENGINE
LEGACY_MIGRATION
SYSTEM_RULE
```

Implementation may use:

* explicit fields;
* typed source records;
* metadata.

Provenance should remain queryable for important data.

---

# 54. RuleVersion

## Purpose

A conceptual version identifier for logic that may change.

Examples:

```text
parser_version
classification_ruleset_version
inference_engine_version
risk_ruleset_version
sif_import_mapping_version
```

Not every version requires a standalone database entity.

Some may be immutable string identifiers.

---

# 55. ImportBatch / ImportSource

## Purpose

AURUM should preserve context about bulk imports.

This is particularly valuable for:

* SIF;
* Mayor;
* legacy migration;
* massive file ingestion.

Possible model:

```text
ImportBatch
├── id
├── import_type
├── source_document_id
├── source_filename
├── mapping_version
├── started_at
├── completed_at
├── status
├── statistics
└── created_at
```

This may overlap with Job.

The final database design should determine whether `ImportBatch` is a specialized Job or a separate entity.

---

# 56. Current SAT monitoring policy

## Purpose

Defines when a CFDI should be checked again.

Potential conceptual entity:

```text
SATMonitoringPolicy
├── id
├── organization_id
├── name
├── enabled
├── priority
├── conditions
└── schedule
```

V1 may implement policies in application configuration rather than persistent entities.

Do not over-model before operational needs are proven.

---

# 57. ClassificationResult

## Purpose

AURUM should consider preserving classification history rather than only the latest category.

Conceptually:

```text
ClassificationResult
├── id
├── cfdi_id
├── classification
├── subclassification nullable
├── source
├── ruleset_version
├── confidence nullable
├── created_at
└── superseded_at nullable
```

This allows reclassification without destroying historical explanation.

Whether this is implemented in V1 will be decided during database design.

---

# 58. Current classification projection

For convenient querying, CFDI may expose the latest/current classification.

This is a projection.

Historical classification records remain more authoritative when versioning is required.

---

# 59. Accounting historical patterns

Inference may eventually require historical facts such as:

* supplier → accounting context;
* supplier → account;
* recipient → policy pattern;
* payroll employee → policy behavior.

These should be modeled as historical observations or derived analytics rather than hidden global dictionaries.

Do not define specific persistence until the inference requirements are finalized.

---

# 60. Primary relationship map

Initial high-level cardinalities:

```text
Organization
  1 ─── N AccountingEntity
  1 ─── N Party
  1 ─── N CFDI

Party
  1 ─── N CFDI as issuer
  1 ─── N CFDI as receiver

CFDI
  1 ─── N CFDIConcept
  1 ─── N CFDITax
  1 ─── N CFDIRelationshipGroup
  1 ─── 0..1 Payroll
  1 ─── 0..1 INEComplement
  1 ─── N SATObservation
  1 ─── N Document associations
  N ─── N Policy through CFDIPolicyLink
  1 ─── N InferenceRun
  1 ─── N Risk

AccountingEntity
  1 ─── N AccountingContext

AccountingContext
  1 ─── N Policy

Policy
  1 ─── N PolicyMovement
  N ─── N CFDI through CFDIPolicyLink

InferenceRun
  1 ─── N InferenceCandidate

InferenceCandidate
  1 ─── N Evidence
```

---

# 61. Immutable entities / records

The following should normally be append-only or effectively immutable after creation:

* original Document bytes;
* source hashes;
* SATObservation;
* completed InferenceRun;
* InferenceCandidate generated by a completed run;
* Evidence from a completed inference;
* AuditEvent.

Corrections should generally create new facts/events rather than silently rewrite history.

---

# 62. Mutable operational entities

Examples:

* Party profile;
* SupplierProfile;
* Risk state;
* Job progress;
* user assignment;
* Policy operational metadata;
* current projections.

Mutation must remain auditable for important business actions.

---

# 63. Derived projections

Some values may be derived for convenience:

* current SAT state;
* current classification;
* reconciliation status;
* policy count per CFDI;
* risk counts;
* latest inference.

Derived values should not destroy their underlying historical data.

---

# 64. Identity strategy

Most domain entities should use internal AURUM IDs.

External identifiers remain business attributes.

Examples:

```text
CFDI internal id
+
UUID external fiscal identity
```

```text
Policy internal id
+
SIF/external policy identifiers
```

This prevents the database from depending on external identifier stability.

---

# 65. UUID normalization

CFDI UUID should be normalized consistently.

Recommended semantic representation:

```text
uppercase canonical UUID
```

Example:

```text
039D171E-773B-495C-881F-BBEFBC8991C2
```

Normalization must occur at a clear domain boundary.

---

# 66. RFC normalization

RFC should be normalized consistently for comparison.

Likely:

* trim;
* uppercase.

Original snapshot values may still be preserved when needed.

---

# 67. Money

All authoritative fiscal/accounting monetary values must use decimal semantics.

Examples:

```text
Decimal
NUMERIC
```

Do not use binary floating-point for:

* CFDI totals;
* taxes;
* charges;
* credits;
* reconciliation differences.

---

# 68. Dates and time

AURUM must distinguish:

* fiscal issuance datetime;
* stamping datetime;
* SAT query datetime;
* accounting date;
* import datetime;
* audit datetime.

UTC/storage policy will be defined in database/technical implementation.

Fiscal source timezone semantics must not be silently changed.

---

# 69. Soft deletion

Critical fiscal/accounting records should generally not be physically deleted without explicit reason.

Potential strategy:

* active/inactive;
* superseded;
* deleted_at;
* audit events.

Exact strategy will vary by entity and be defined later.

---

# 70. Constraints to preserve

Examples of domain invariants:

## CFDI

```text
UUID must be unique within the relevant fiscal scope.
```

## PolicyMovement

```text
charge >= 0
credit >= 0
```

## InferenceCandidate

```text
candidate belongs to exactly one InferenceRun.
```

## SATObservation

```text
observation belongs to exactly one CFDI.
```

## CFDIPolicyLink

```text
CFDI and Policy references must exist.
```

More invariants will be defined in individual specifications.

---

# 71. Concepts intentionally not fully modeled yet

The following are intentionally deferred:

* DIOT;
* complete Payment Complement domain;
* every possible CFDI complement;
* complex workflow Cases;
* advanced permissions;
* ML models;
* cloud storage;
* external notifications;
* N8N workflows;
* Lu tools;
* advanced supplier banking/contact model.

Deferral prevents premature complexity.

---

# 72. V1 domain priority

Highest-priority V1 entities:

```text
Organization
Party
CFDI
CFDIConcept
CFDITax
CFDIRelationshipGroup
CFDIRelatedUUID
Payroll
PayrollPerception
PayrollDeduction
PayrollOtherPayment
INEComplement
INEAccountingReference
Document
SATObservation
AccountingEntity
AccountingContext
Account
Policy
PolicyMovement
SIFEvidence
CFDIPolicyLink
InferenceRun
InferenceCandidate
Evidence
Risk
Job
AuditEvent
```

Not all must be implemented simultaneously.

They will be introduced incrementally.

---

# 73. Likely implementation order

Domain implementation should roughly follow dependency order:

```text
Organization / Party
        ↓
Document / CFDI
        ↓
Concepts / Taxes / Complements
        ↓
SAT observations
        ↓
Accounting entities / contexts
        ↓
Policies / movements
        ↓
CFDI-policy links
        ↓
Reconciliation
        ↓
Inference
        ↓
Risk
        ↓
Jobs / operational workflows
```

Audit should begin early and grow alongside capabilities.

---

# 74. Domain model vs database schema

This document does not imply:

```text
one entity = one table
```

Some concepts may become:

* tables;
* embedded values;
* JSON;
* views;
* projections;
* derived queries.

The next document, `DATABASE_DESIGN.md`, will make those decisions.

---

# 75. Domain architecture statement

> **AURUM's domain model separates immutable fiscal evidence, structured fiscal/accounting facts, external observations, explainable inferences, operational risks, and human decisions so that every important conclusion remains traceable to its source and history.**
