# AURUM — CFDI Concepts Persistence Specification

**Status:** Accepted — Concepts persistence design; implementation not started
**Scope:** Durable, auditable persistence of accepted CFDI Concepts parser results.

## 1. Status and scope

This specification defines PostgreSQL persistence for `ParsedCfdiConcepts` derived from
immutable CFDI XML evidence. It follows the accepted Header persistence architecture:
immutable results, append-only executions, deterministic registration, and explicit current
projection.

Out of scope: parser changes, taxes or aggregate taxes, classification, reconciliation,
inference, UI/reporting, SAT catalogue enrichment, migrations, and implementation code.

## 2. Persistence principles

- Original XML remains immutable byte-perfect evidence; Concepts are reproducible derived facts.
- Results, child concepts, and executions are historical facts; reprocessing never overwrites.
- Current is a projection/pointer, never a mutation of historical result data.
- Persistence is idempotent and concurrency-safe.
- Every source `Concepto` occurrence is one child row; identical values never collapse.
- Provenance, raw lexical values, exact decimals, and fingerprints are retained for audit.

## 3. Result identity, schema registry, and fingerprint

Use the accepted Header logical identity:

```text
(evidence_id, parser_name, parser_version, configuration_hash)
```

Use a slice-specific `cfdi_concepts_parser_schema`, analogous to Header's registry.
`cfdi-concepts` has its own fingerprint payload/schema and must not share Header's schema
namespace. Do not introduce a shared global Fiscal parser-schema registry in this slice. A
future cross-slice consolidation may be considered only if concrete duplication justifies it.
The registry permits exactly one `result_fingerprint_schema` for a
`(parser_name, parser_version)` pair across all evidence and configurations.

For an existing logical identity:

1. Same schema and fingerprint: reuse the result and append a `SUCCEEDED` execution.
2. Same schema and different fingerprint: typed determinism violation.
3. Different schema: typed parser-fingerprint-schema mismatch before comparing digests.

`implementation_id` is execution provenance only. Persistence validates declared fingerprint
shape but does not recompute the parser's canonical ordered payload in SQL.

## 4. Candidate persistence model

The future implementation must use these accepted names:

- `cfdi_concepts_parser_schema`
- `cfdi_concepts_result`
- `cfdi_concept`
- `cfdi_concepts_parse_execution`
- `cfdi_concepts_current`

If a concrete repository/database collision is discovered during implementation, stop and
report it; do not silently rename this schema.

### `cfdi_concepts_parser_schema`

```text
id
parser_name
parser_version
result_fingerprint_schema
```

Require `UNIQUE(parser_name, parser_version)` and a compatible unique tuple
`(parser_name, parser_version, result_fingerprint_schema)` for result provenance. Do not put
configuration, evidence, or executions in this registry.

### `cfdi_concepts_result`

```text
id
evidence_id
parser_name
parser_version
configuration_hash
cfdi_version
concept_count
result_fingerprint_schema
result_fingerprint
created_at
```

Require `UNIQUE(evidence_id, parser_name, parser_version, configuration_hash)`, immutable
evidence FK, a composite parser-schema FK, and a compatible unique provenance tuple including
`id`, evidence, parser, version, and configuration for executions/current. `cfdi_version`
is bounded to `3.3`/ `4.0` and is distinct from AURUM parser version.

### `cfdi_concept`

Immutable ordered child:

```text
id, result_id, concept_index
clave_prod_serv_raw, no_identificacion_raw nullable
cantidad_raw, cantidad NUMERIC
clave_unidad_raw, unidad_raw nullable
descripcion_raw
valor_unitario_raw, valor_unitario NUMERIC
importe_raw, importe NUMERIC
descuento_raw nullable, descuento NUMERIC nullable
objeto_imp_raw nullable
created_at
```

It contains no Header duplication, tax values, catalogue descriptions, search projection, or
accounting classification.

### `cfdi_concepts_parse_execution`

Append-only Header-style attempt record:

```text
id, evidence_id, parser_name, parser_version, configuration_hash, status
result_id nullable
error_code nullable, error_type nullable, error_message nullable
implementation_id nullable, parsed_at
```

A successful composite FK proves result/evidence/parser/version/configuration compatibility.
`SUCCEEDED` requires a result and no errors; `FAILED` requires no result plus code/type,
with optional message.

### `cfdi_concepts_current`

```text
cfdi_identity_id, evidence_id, result_id, promoted_at
```

Mirror Header current: one row per identity, unique `result_id`, and composite FKs proving
authoritative identity/evidence plus result/evidence compatibility.

## 5. Child identity and source order

Within a result:

```text
UNIQUE(result_id, concept_index)
CHECK(concept_index >= 0)
```

`concept_index` is zero-based XML order. No value-derived uniqueness is allowed: description,
codes, amounts, `NoIdentificacion`, or combinations of them cannot collapse children.
Identical source lines at 0 and 1 are distinct.

Parser/application guarantees contiguous `0..concept_count-1` before write. PostgreSQL
enforces non-negative uniqueness but not cross-row contiguity. Avoid a trigger: it adds
write-order coupling without improving immutable provenance. Integration tests prove complete
contiguous children are written atomically.

## 6. Decimal, text, and code persistence

`cantidad`, `valor_unitario`, `importe`, and present `descuento` use unrestricted
PostgreSQL `NUMERIC` and Python `Decimal`, never float/real/double precision, matching
Header. Each has its raw source string: `"1.00"` and `"1.0000"` remain lexically
different though numerically equal. No fixed scale, rounding, quantization, or lexical
normalization is permitted.

Require:

```text
descuento_raw IS NULL <=> descuento IS NULL
```

Absent discount is NULL/NULL; explicit `"0"` is raw non-null plus NUMERIC zero.

Text/code fields retain parser-delivered values: no case fold, accent removal, tokenization,
catalogue replacement, or search normalization. Only `NoIdentificacion`, `Unidad`, and the
discount pair are nullable under the current parser contract.

## 7. Version and concept-count integrity

Result `cfdi_version` has a bounded-string check for `3.3`/ `4.0`. Repository registration
accepts only parser-valid children: 3.3 has `objeto_imp_raw IS NULL`; 4.0 has it non-null.

Do not duplicate `cfdi_version` into children solely for a cross-table CHECK and do not add a
trigger. A CHECK cannot join to the parent. Parser validity, atomic registration, and focused
PostgreSQL tests are the accepted auditable boundary. Any database-only cross-row policy needs
a future explicit design.

`cfdi_concepts_result` persists `concept_count` as deterministic fingerprint metadata with
`CHECK(concept_count > 0)`. Registration verifies
`concept_count == len(parsed concepts)` and writes all children atomically with a new result.
PostgreSQL uses no trigger to maintain or cross-count children; repository validation plus
PostgreSQL integration tests protect this invariant.

## 8. Idempotency, reprocessing, and failure history

Repeated logical registration reuses one result/child set, appends a successful execution, and
does not repromote current. Schema/determinism mismatch creates no replacement or success event.

New parser version/configuration creates a new historical result. Old results, children, and
executions remain unchanged. Failed parses create only append-only `FAILED` executions with
safe typed error metadata and evidence provenance; no raw XML, result, or children are created.

## 9. Current promotion and concurrency

Promotion follows Header exactly, without newest-wins:

1. Lock `cfdi_identity` through `SELECT ... FOR UPDATE`.
2. Load result and verify its evidence is authoritative for that identity.
3. UPSERT `cfdi_concepts_current`; change only projection and `promoted_at`.

Failure leaves current intact. Explicit promotion—not execution time—selects current.

Concurrent registration follows Header savepoint recovery: registry/result unique constraints
arbitrate; inserts use `session.begin_nested()`; loser rolls back only the savepoint, reloads
winner under PostgreSQL READ COMMITTED, compares schema before digest, and appends a compatible
execution. Expected races do not poison outer UoW or leak raw `IntegrityError`. Children are
written only with the winning result in the same transaction. Promotion serializes on identity.

## 10. Repository and transaction boundary

Future repository operations inside existing SQLAlchemy UoW:

```text
record_success(evidence_id, parsed_concepts, configuration_hash, implementation_id?)
record_failure(evidence_id, configuration_hash, error, implementation_id?)
get_current(identity_id)
promote(identity_id, result_id)
```

One successful operation atomically creates/reuses registry, creates result and all children
when new, then appends execution. A child write failure rolls back the result attempt; no
partial successful result remains. Promotion is explicit, not record-success side effect.

## 11. Foreign keys, deletion, and indexes

Use `ON DELETE RESTRICT` for result→evidence, result→registry, child→result,
execution→result provenance, and current→identity/evidence/result. No cascade is appropriate
for immutable accepted results.

Required indexes: logical-result unique key; parser-schema keys;
`UNIQUE(result_id, concept_index)`; current identity PK and unique result; execution
`(evidence_id, parsed_at DESC)`; execution `(parser_name, parser_version)`; failed-execution
partial index on `parsed_at`. Consider child `result_id`, `clave_prod_serv_raw`, and
`no_identificacion_raw` only when access patterns justify them. Do not pre-create full text or
numeric indexes.

## 12. Future ConceptTax boundary

Future concept-level tax rows attach to immutable `cfdi_concept.id`, representing the exact
source `Concepto` occurrence, never description or order alone. This freezes the stable parent
boundary only; it does not freeze ConceptTax result tables, parser schemas, execution history,
Traslado/Retencion child structure, aggregate-tax persistence, or tax fingerprint/current
semantics. Those belong to future CFDI Taxes Design. This slice adds no tax table, placeholder,
aggregate structure, or tax columns.

## 13. Migration direction

A future frozen Alembic migration explicitly creates registry, result, child, execution, and
current tables with columns/types/FKs/unique checks/indexes. It must not import live ORM
metadata. Downgrade reverses dependent tables and indexes safely. No migration is created now.

## 14. PostgreSQL test strategy

Real PostgreSQL tests using `AURUM_TEST_DATABASE_URL` must cover:

- migration upgrade, expected constraints/indexes, safe downgrade/upgrade;
- valid 3.3/4.0 results and multiple ordered children;
- raw scale/NUMERIC round trip, absent discount NULL/NULL, explicit zero;
- identical values at different indexes surviving separately;
- idempotent reuse with one child set and multiple executions;
- reprocessing via parser version/configuration with preserved history;
- fingerprint/schema registry stability, failure history, promotion/current preservation, and
  authoritative-evidence rejection;
- rollback without partial children; deterministic same-result race without duplicate children;
  concurrent promotion serialization; and
- Identity/Header regressions, combined persistence suite, and full backend gate.

SQLite is not a substitute.

## 15. Full-gate expectation

Future implementation acceptance requires focused Concepts PostgreSQL tests, Identity/Header
persistence regressions, combined persistence suite, full backend tests, Ruff, format,
`compileall`, `pip check`, diff check, and real PostgreSQL migration-head validation.

## 16. Open questions

1. Confirm repository current-read return shape while retaining Header promotion semantics.
2. Confirm whether SAT catalogue projections justify raw-code indexes.
3. Define internal ConceptTax/tax-result granularity beyond the frozen `cfdi_concept` parent
   boundary.
4. Decide whether a unified Fiscal Parse Bundle changes promotion granularity.

## 17. Acceptance criteria

This design is acceptable only if immutable results/history, ordered child identity, duplicate
preservation, raw plus exact NUMERIC semantics, idempotent registration, current/history
separation, savepoint concurrency, clean ConceptTax boundary, PostgreSQL test plan, and frozen
migration direction are explicit—without implementation or migration work.
