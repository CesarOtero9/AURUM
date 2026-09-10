# AURUM — Policy Identity Specification

**Status:** Accepted — identity architecture; persistence tuple pending source-evidence gate
**Scope:** Canonical identity for Accounting / SIF policies (`POLIZA`)

## 1. Purpose

Define one stable, structured identity for an accounting policy. This is the Accounting
/ SIF counterpart to fiscal UUID identity. It lets AURUM recognize the same policy across
Mayor, Reporte XML SIF, legacy Excel, and future sources without treating a displayed
concatenated string as the source of truth.

## 2. Scope and non-goals

This specification defines policy identity, its canonical key, and source observations.
It does not define Mayor parsing, movements, SIF-file layouts, CFDI-policy links,
reconciliation, inference, APIs, UI, workers, or migrations.

It does not assign business meaning to source codes such as `PN` or `EG` until real source
evidence establishes that meaning.

## 3. Operational context

The two identity axes are:

```text
Fiscal:             UUID
Accounting / SIF:   POLIZA
```

An operational representation may look like `BCS_199_PN-EG-15/07-2026`. It is evidence
of how one source rendered a policy, not the canonical identity by itself. The future
trusted fiscal/accounting bridge is `Reporte XML SIF -> UUID <-> POLIZA`; that bridge is
separate from policy identity.

## 4. Canonical Policy Identity

The current candidate identity schema uses this ordered tuple:

```text
(entity, accounting_id, fiscal_year, accounting_period, policy_type,
 policy_subtype, policy_number)
```

These are safe structural dimensions to model now, but source evidence has not yet proved
that every one is identity-defining for every real SIF policy. The seven-field tuple is the
working candidate for examples and source normalization. Final persistence uniqueness must
wait for representative Mayor and Reporte XML SIF evidence to confirm policy-subtype scope,
accounting-ID scope, any additional AccountingContext dimension, and whether any listed
dimension is descriptive or source-specific. A database surrogate ID may coexist with the
accepted tuple; it does not replace structured identity.

| Component | Classification | Reason |
| --- | --- | --- |
| Entity | Candidate identity dimension | Policies appear within an entity/context. |
| Accounting ID | Candidate identity dimension | Legacy `id_contabilidad` may distinguish accounting contexts. |
| Fiscal year | Candidate identity dimension | Period-like values recur across years. |
| Accounting period | Candidate identity dimension | Candidate temporal scope; source domain requires confirmation. |
| Policy type | Candidate identity dimension | Stable coded position, not inferred meaning. |
| Policy subtype | Candidate identity dimension | Separate source-coded position where supplied; identity role unproven. |
| Policy number | Candidate identity dimension | Source policy folio/reference within the candidate context. |
| Canonical key | Derived representation | Deterministic only under an accepted schema. |
| Source POLIZA string/label | Source representation only | May vary by document/layout. |
| Source description, dates, row location | Observation/descriptive | Do not identify the policy. |

### PolicyIdentitySchema

An accepted, versioned `PolicyIdentitySchema` defines which dimensions are required
identity dimensions, optional non-identity dimensions, and source-only dimensions for an
accounting model. A canonical PolicyIdentity requires every component required by its
accepted schema, not every field that a source happens to expose. No canonical
PolicyIdentity is created when a required component is unavailable or unresolved.

## 5. Identity components

### Entity

`entity` references the future normalized AURUM entity catalog, not merely a copied source
label. The catalog supplies the stable entity code used in identity; source code and source
label remain on an observation. `BCS` is an example code, not a claim about catalog design.

### Accounting ID

`accounting_id` is a source/accounting-context code conceptually compatible with documented
`id_contabilidad`, but is not the INE CFDI complement's accounting reference. It is text,
not an integer: numeric-looking values and meaningful leading zeroes are preserved. Entity
plus accounting ID is not assumed to be the complete scope. PolicyIdentity should eventually
reference a normalized AccountingContext (or equivalent) once accepted; the explicit fields
remain useful for legacy compatibility but must not persist conflicting duplicate context.

### Fiscal year and accounting period

`fiscal_year` is a four-digit accounting/fiscal year. `accounting_period` is a separately
stored code, initially normalized as a two-digit monthly period (`01`–`12`) when the source
proves it is monthly. `07-2026` therefore maps to period `07`, year `2026`; it is not a
creation date. Extraordinary periods are not invented: a future accepted catalog/domain can
extend the period code without changing the identity model.

### Type, subtype, and number

`policy_type` and `policy_subtype` are separate source-derived code dimensions only when a
source layout explicitly establishes two positions, such as `PN-EG`. Neither code receives
business meaning here, and representative sources must confirm whether either is universal
or identity-defining under the accepted schema.

`policy_number` is a trimmed, non-empty text code. It is not coerced to integer; leading
zeroes and future alphanumeric values are retained. A source-specific parser decides whether
an observed token is a number, not PolicyIdentity itself.

## 6. Normalization rules

For complete components:

1. Reject null, empty, or whitespace-only identity components.
2. Trim outer whitespace; preserve internal meaningful characters.
3. Normalize entity, accounting ID, type, and subtype to uppercase ASCII-compatible code
   forms. Their allowed alphabets are bounded by source evidence/catalog validation.
4. Preserve accounting ID and policy-number lexical digits, including leading zeroes.
5. Normalize a proven monthly period to two digits. Reject `00` and `13`–`99` in the initial
   monthly domain.
6. Fiscal year is four digits in the accepted operational range; exact range belongs to the
   domain validator, not a date parser.
7. Reject delimiter characters reserved by the canonical key (`|` and `=`) inside normalized
   components unless a future reversible escaping rule is accepted.

Source values are never overwritten by normalized values.

## 7. Canonical key

Use `canonical_key` as a deterministic, human-readable representation under an accepted
PolicyIdentitySchema:

```text
ENTITY=<entity>|ACCOUNTING_ID=<accounting_id>|YEAR=<fiscal_year>|PERIOD=<period>|TYPE=<type>|SUBTYPE=<subtype>|NUMBER=<number>
```

One normalized tuple under that schema maps to one canonical key, and key and structured
tuple must never disagree. Application validation creates it rather than accepting an
arbitrary caller-provided key. Once a schema is accepted for persistence, its canonical key
and structured tuple can both be protected by uniqueness constraints. If source evidence
requires another identity dimension, evolve the identity schema explicitly; never silently
change key semantics. A key is not a hash and is reversible by labeled components.

No missing required component is encoded as an empty segment. Incomplete references have no
canonical key and cannot be promoted to `policy_identity`; optional or source-only dimensions
do not block identity creation.

## 8. Policy observation and provenance boundary

`PolicyIdentity` answers: “what policy is this?” A future `PolicyObservation` answers:
“which source said this policy appeared?” Multiple observations can resolve to one identity.

A PolicyObservation conceptually retains:

```text
policy_identity_id nullable
raw_policy_reference
source_document/evidence reference
source location (sheet/row/XML path where available)
source kind (MAYOR, SIF_XML_REPORT, LEGACY_EXCEL, ...)
import batch / observed_at
parser or importer name and version
normalization outcome and unresolved reason nullable
```

It never replaces the raw source string with the canonical key. An incomplete or malformed
reference is retained as an unresolved observation, with no fabricated identity.

## 9. Accounting movement boundary

The future relationship is:

```text
PolicyIdentity 1 -> N AccountingMovement
```

Mayor imports may regenerate movement observations without changing policy identity.
Accounts, debit, credit, concept/description, source registration, reference policy, and
reversal/reclassification indicators belong to AccountingMovement and its provenance, not
to PolicyIdentity.

## 10. UUID ↔ Policy boundary

Policy identity exists independently of CFDI linkage. Future `CfdiPolicyLink` behavior is
non-negotiably N:M and has its own provenance, status/history (including `ACTIVA` and
`SIN EFECTO` where supplied), and evidentiary source.

Direct Reporte XML SIF observations have greater evidentiary authority than inference.
Inference creates candidates only; it never changes PolicyIdentity and never automatically
creates a confirmed UUID↔POLIZA relationship.

## 11. Duplicate and collision semantics

| Situation | Required handling |
| --- | --- |
| Same complete tuple observed repeatedly | One PolicyIdentity; append observations. |
| Different source strings normalize to same tuple | One PolicyIdentity; preserve every raw string/observation. |
| Similar strings normalize to different tuples | Separate policies. |
| Same canonical key presented with conflicting fields | Identity-integrity error; never silently merge. |
| Incomplete reference | Unresolved observation; no complete policy manufactured. |

## 12. Mutability

Identity-defining fields and canonical key are immutable after creation. A parser correction
creates a corrected observation and, if its tuple differs, a different PolicyIdentity. Any
future supersession/reconciliation relation must be explicit and must not rewrite history.
Descriptive source observations are append-only; a newer observation does not erase an
earlier one.

## 13. Persistence direction

Future PostgreSQL persistence should begin with:

```text
policy_identity
  id surrogate PK
  accounting_context_id FK nullable until AccountingContext is accepted
  entity_id / accounting_id candidate dimensions for legacy compatibility
  fiscal_year text/integer domain value
  accounting_period text domain value
  policy_type text
  policy_subtype text
  policy_number text
  canonical_key text
  candidate UNIQUE tuple and canonical-key constraints,
  frozen only after PolicyIdentitySchema/source-evidence acceptance

policy_observation
  id surrogate PK
  policy_identity_id nullable FK
  source evidence/document and location
  raw_policy_reference
  parser/importer name and version
  import batch / observed_at
  resolution status or unresolved reason
```

Use `ON DELETE RESTRICT` on provenance chains. Observation timestamps and source-document
details do not belong in `policy_identity`. The eventual migration freezes the accepted
identity schema and its uniqueness semantics after AccountingContext/source review.

## 14. Domain types

Material value objects are `EntityCode`, `AccountingId`, `FiscalYear`, `AccountingPeriod`,
`PolicyTypeCode`, `PolicySubtypeCode`, `PolicyNumber`, and `CanonicalPolicyKey`. They protect
normalization, emptiness, reserved-delimiter, and leading-zero invariants. `PolicyIdentity`
composes them. Source parsing DTOs should keep raw strings separately rather than forcing
every source token through a value object before it is understood.

## 15. Error model

Use small typed errors at the appropriate boundary:

- `MissingPolicyIdentityComponent` for incomplete required tuples;
- `InvalidPolicyIdentityComponent` for malformed normalized values;
- `InvalidAccountingPeriod` or `InvalidFiscalYear` for domain violations;
- `CanonicalPolicyKeyMismatch` for a supplied key inconsistent with fields;
- `PolicyIdentityCollision` for conflicting claimed identity;
- `MalformedPolicySourceReference` for source parsing failures.

The first five are identity/integrity errors. The last is an adapter parsing error and must
retain the raw reference in an unresolved observation where ingestion succeeds.

## 16. Parsing and adapter boundary

PolicyIdentity does not parse Excel, Reporte XML SIF, or legacy strings. Mayor,
SIF XML-report, and legacy Excel adapters translate their layouts into source-reference
DTOs and then request canonical identity construction. Excel column names and source token
positions remain infrastructure details.

## 17. Legacy compatibility

Legacy VBA/Python/Excel normalization is behavioral evidence, not an implementation template.
Migration must use representative golden fixtures to prove that equivalent operational
policies converge, different policies remain separate, raw strings survive, and every
normalization rule is explicit and explainable.

## 18. Worked examples under the current candidate schema

| Raw source reference | Structured normalized components | Canonical key / outcome |
| --- | --- | --- |
| `BCS_199_PN-EG-15/07-2026` | `BCS`, `199`, `2026`, `07`, `PN`, `EG`, `15` | `ENTITY=BCS|ACCOUNTING_ID=199|YEAR=2026|PERIOD=07|TYPE=PN|SUBTYPE=EG|NUMBER=15` |
| `BCS_199_PN-EG-0015/07-2026` | Same except number `0015` | Distinct candidate identity unless explicit source/business evidence defines an equivalence rule. |
| ` bcs _ 199 _ pn-eg-15 / 07-2026 ` | Layout parser trims/separates then uppercases codes; number remains `15` | Same identity as example 1 if the layout parser recognizes this spelling. |
| `BCS_0199_PN-EG-15/07-2026` | Accounting ID `0199` | Different identity from `199`; leading zero is preserved. |
| `BCS_199_PN-EG-15` | Year/period absent | Unresolved PolicyObservation; no canonical key/PolicyIdentity. |

The examples do not assign semantics to `PN` or `EG`.

## 19. Invariants

1. A complete PolicyIdentity has every component required by its accepted PolicyIdentitySchema and one deterministic canonical key.
2. Canonical tuple and key never disagree; both are immutable once created under an accepted schema.
3. Source references and observations are retained separately from canonical identity.
4. Repeated complete observations deduplicate identity but append provenance.
5. Incomplete references cannot create a fabricated complete policy.
6. Policy → AccountingMovement is 1:N; movements never redefine policy identity.
7. CFDI ↔ Policy is N:M and belongs to a separate relationship model.
8. Inference does not mutate identity or silently confirm a link.

## 20. Open questions

### Safe decisions now

Structured identity, PolicyIdentitySchema, source-observation separation, text preservation,
deterministic keys under an accepted schema, immutable identity, 1:N movement boundary, and
N:M CFDI boundary are safe architectural decisions.

### Source facts requiring SIF/Mayor evidence

- Exact business semantics and valid domains of `PN` and `EG`.
- Whether extraordinary/adjustment periods exist and their codes.
- Whether `accounting_id` is stable globally or must be scoped further by entity/year.
- Whether policy numbers can be alphanumeric or have source-defined equivalence rules.
- Whether the same tuple may legitimately recur in another unmodeled accounting context.
- Exact layouts and authoritative components in Reporte XML SIF versus Mayor.

### Pre-persistence source evidence gate

Before Policy Identity persistence is designed or implemented, review representative Reporte
de Mayor, Reporte XML SIF, and useful current consolidated legacy outputs. The review exists
only to freeze identity dimensions and source representation semantics. It must resolve the
exact POLIZA composition; `PN`/`EG` independence and identity role; `accounting_id` scope;
period domain; policy-number lexical/equivalence rules; and whether another AccountingContext
dimension is required. PostgreSQL UNIQUE constraints must not be frozen before this gate.

## 21. Acceptance criteria

This design is ready for acceptance when reviewers agree that it provides structured,
deterministic, immutable policy identity under an accepted schema; preserves source
provenance; prevents fabricated complete identities; keeps movements and CFDI relationships
outside identity; defers final PostgreSQL uniqueness to the source-evidence gate; and commits
to legacy golden-fixture compatibility before import implementation.
