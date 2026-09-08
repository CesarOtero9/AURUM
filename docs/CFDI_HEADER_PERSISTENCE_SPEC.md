# AURUM — CFDI Header / Fiscal Core Persistence Specification

**Status:** Accepted
**Scope:** Durable, auditable derived fiscal-header parsing results

---

## 1. Purpose and scope

Define persistence for `CfdiFiscalHeader` results derived from immutable `xml_evidence`.
It covers header parsing provenance, history, failure retention, current-result access,
promotion, concurrency, and reporting. It excludes parser implementation, concepts,
taxes, complements, SAT, SIF, inference, risk, API, and migrations.

## 2. Design principles

`xml_evidence.content` remains byte-perfect primary evidence and is never changed by
parsing. Header data is reproducible derived fiscal data; it can be replaced logically by
a newly derived result, never by mutating evidence or historical results. `CfdiIdentity`
remains the canonical UUID identity. A CFDI schema version (`3.3`/`4.0`) is distinct from
an AURUM parser implementation version (for example `header-parser/1`).

For identical evidence bytes, parser implementation version, and parser-configuration
identity, parsing must produce a deterministic result or typed failure.

## 3. Recommended architecture: history plus current projection

Choose **append-only history plus an explicit current projection**.

| Alternative | Benefit | Rejected limitation |
| --- | --- | --- |
| One mutable current row | few tables | destroys audit/reprocessing history and weakens rollback |
| Append-only history only | strongest audit | common reporting must rank history repeatedly |
| Append-only + current projection | audit plus efficient operational query | one small projection table and promotion transaction |

The result is immutable once stored. Promotion is operational metadata outside the result;
corrections create a new parser result. Reporting uses current projection; audit,
reprocessing, inference, and risk can inspect history and parser provenance.

## 4. Execution, result identity, idempotency, and failures

The historical unit is a **parse execution** because an attempt can fail. A successful
execution references one immutable header result; many successful executions may reference
the same deduplicated result. A failed execution owns no payload.

The derived-result identity is `(evidence_id, parser_name, parser_version,
configuration_hash)`. `configuration_hash` is SHA-256 lowercase hex over canonical,
versioned parser configuration. It is required even if the MVP uses one empty canonical
configuration, because a configuration that changes output must change result identity.

Use `UNIQUE` on that identity for successful results. Add
`result_fingerprint_schema VARCHAR(100) NOT NULL` (for example,
`cfdi-header-fingerprint/1`) and `result_fingerprint VARCHAR(64) NOT NULL`, lowercase
SHA-256 over that schema's canonical serialization of `CfdiFiscalHeader`. These are
determinism verification mechanisms, not components of result identity. A retry with the
same identity reuses the existing result
rather than creating contradictory duplicates, while
each explicit invocation can retain a separate execution event if operational provenance
is needed. For MVP, persist every attempt in `cfdi_header_parse_execution`; successful
retries reference the one result. Failed retries remain separate executions because they
are observations of attempts, not derived facts.

General statuses are `SUCCEEDED` and `FAILED`. Failure retains typed `error_code`, stable
error type, sanitized message, and `parsed_at`; no XML, stack trace, or sensitive runtime
configuration is copied into the row. Detailed stacks belong to observability logs.

## 5. Evidence and identity relationship

Every execution and result has a non-null direct FK to `xml_evidence(id)`. This is
necessary and sufficient to locate exact bytes and extracted UUID. Store
`cfdi_identity_id` only on the current projection as a useful query key, not redundantly
on every history/result row. Its compatibility is enforced by a composite FK:

```text
cfdi_header_current(cfdi_identity_id, evidence_id)
  -> cfdi_identity(id, authoritative_evidence_id)
```

Thus current header is only possible for authoritative evidence of that identity. Conflict
evidence may be parsed historically, but cannot be projected as the current header of a
different identity. This preserves existing identity/evidence integrity without copying
the fiscal UUID into header truth.

## 6. Proposed tables

```text
xml_evidence <- cfdi_header_parse_execution <- cfdi_header_result
                                                   ↑
cfdi_identity <- cfdi_header_current ------------┘
```

### 6.1 `cfdi_header_parse_execution`

Append-only attempt/provenance table.

* `id BIGINT GENERATED ALWAYS AS IDENTITY` primary key.
* `evidence_id BIGINT NOT NULL REFERENCES xml_evidence(id) ON DELETE RESTRICT`.
* `parser_name VARCHAR(100) NOT NULL`; `parser_version VARCHAR(100) NOT NULL`.
* `configuration_hash VARCHAR(64) NOT NULL`, lowercase SHA-256 checks.
* `status VARCHAR(16) NOT NULL` (`SUCCEEDED`, `FAILED`).
* `result_id BIGINT NULL` references a deduplicated successful result.
* `error_code VARCHAR(100) NULL`, `error_type VARCHAR(200) NULL`,
  `error_message TEXT NULL` (sanitized).
* `parsed_at TIMESTAMPTZ NOT NULL`; optional opaque `implementation_id VARCHAR(100)`.

Checks: success requires `result_id` and no error fields; failure requires no result and
an error code/type; `status` is constrained. A composite FK from `(result_id, evidence_id,
parser_name, parser_version, configuration_hash)` to the compatible unique tuple exposed
by result makes provenance drift impossible. No execution fields are mutable.

### 6.2 `cfdi_header_result`

Immutable successful derived facts. `id BIGINT GENERATED ALWAYS AS IDENTITY` is PK; it
has no ownership FK to execution. It retains `evidence_id`, parser name/version,
configuration hash, `result_fingerprint_schema`, and `result_fingerprint` for direct
queryability. Fingerprint schema is non-empty; fingerprint has lowercase SHA-256 checks.
`UNIQUE(evidence_id, parser_name, parser_version, configuration_hash)` is the successful
derived-result identity, and `UNIQUE(id, evidence_id, parser_name, parser_version,
configuration_hash)` supports the execution composite FK.

`implementation_id` remains optional execution provenance (build, Git commit, or artifact
release) and is not result identity. A given `parser_name + parser_version` declares one
stable fingerprint schema and must not silently change it. Under one logical result
identity: same schema plus same fingerprint reuses the existing result; same schema plus a
different fingerprint raises `DerivedResultDeterminismViolation`; a different schema raises
`ParserFingerprintSchemaMismatch`. The latter is a parser-versioning contract violation:
do not create another result, update either stored fingerprint value, compare hashes, or
silently reuse the result. An incompatible canonical representation needs a new fingerprint
schema and, if parsing logic or derived output also changes, a new `parser_version`.

Columns are one relational row, not separate issuer/receiver tables: header snapshots are
one-to-one document facts, current reporting needs them together, and splitting them adds
joins without reuse. JSONB is rejected as primary storage because reporting, constraints,
and numeric/date queryability matter. A small future JSONB diagnostics field is not needed
in this slice.

Core columns: `cfdi_schema_version`, `fecha_source VARCHAR`, `fecha TIMESTAMP WITHOUT
TIME ZONE`, `tipo_comprobante`, `serie_source`, `folio_source`, `moneda`,
`tipo_cambio_source`, `tipo_cambio NUMERIC`, `subtotal_source`, `subtotal NUMERIC`,
`descuento_source`, `descuento NUMERIC NULL`, `total_source`, `total NUMERIC`,
`exportacion NULL`, `lugar_expedicion`, `metodo_pago NULL`, `forma_pago NULL`,
`condiciones_pago_source NULL`, `confirmacion_source NULL`.

Issuer snapshot: `issuer_rfc_source VARCHAR(32)`, `issuer_rfc_canonical VARCHAR(32)`,
`issuer_nombre_source NULL`, `issuer_regimen_fiscal`. Receiver snapshot:
`receiver_rfc_source VARCHAR(32)`, `receiver_rfc_canonical VARCHAR(32)`,
`receiver_nombre_source NULL`, `domicilio_fiscal_receptor NULL`,
`regimen_fiscal_receptor NULL`, `uso_cfdi`.

### 6.3 `cfdi_header_current`

One explicit operational projection per canonical identity:

* `cfdi_identity_id BIGINT PRIMARY KEY REFERENCES cfdi_identity(id) ON DELETE RESTRICT`.
* `evidence_id BIGINT NOT NULL` and composite FK `(cfdi_identity_id, evidence_id)` to
  `(cfdi_identity.id, cfdi_identity.authoritative_evidence_id)`.
* `result_id BIGINT NOT NULL UNIQUE REFERENCES cfdi_header_result(id) ON DELETE RESTRICT`.
* `promoted_at TIMESTAMPTZ NOT NULL`; future `promotion_reason`/actor are deferred.

The result must also reference the same `evidence_id`; enforce this with a unique
`cfdi_header_result(id, evidence_id)` and composite FK `(result_id, evidence_id)`.
This is stronger than an `is_current` boolean: it makes two currents for one identity and
a current pointing to another evidence impossible.

## 7. Source, parsed, canonical, nullability

Original lexical bytes remain only in XML evidence. Persist source attribute values when
they carry audit/display meaning: decimals, date, RFCs, series/folio, names, conditions,
and confirmation. Persist parsed values for Decimal/date and canonical RFC. SAT codes use
source/code columns once; no duplicate canonical copy until an explicit normalization rule
exists. Source strings are parser-delivered values, not claims about quotes/entities/bytes.

`NUMERIC` without fixed precision/scale stores parsed `subtotal`, `descuento`, `total`,
and `tipo_cambio`; it avoids unsupported ingestion rounding and never uses float.
`fecha` uses `TIMESTAMP WITHOUT TIME ZONE`; `parsed_at`/`promoted_at` use `TIMESTAMPTZ`.
RFC canonical/source use bounded `VARCHAR(32)` plus non-empty and uppercase-canonical
checks where appropriate, not online SAT validation. SAT codes use version-flexible
`VARCHAR`, never PostgreSQL ENUM or catalogue FKs in this increment.

Null means either XSD-optional attribute absent or version-inapplicable attribute; the
schema version disambiguates those cases. Present-empty is invalid structural parsing and
does not produce a result. Failed parsing is represented only by execution failure, never
by an all-null successful result. 3.3-only absence for 4.0 receiver/export fields is
expected; 4.0 required fields are non-null on successful 4.0 results through version-aware
checks. `cfdi_header_result` payload is immutable after insert; corrections require a new
parser version or new configuration identity, while current/promotion stays outside it.

Add paired source/parsed checks: required `fecha_source/fecha`, `subtotal_source/subtotal`,
and `total_source/total` are both non-null; optional `tipo_cambio_source/tipo_cambio`,
`descuento_source/descuento`, and source/canonical RFC pairs are either both null or both
non-null where applicable. A successful result cannot contain source without parsed value.

Version-aware checks require 3.3 results to have `exportacion`,
`domicilio_fiscal_receptor`, and `regimen_fiscal_receptor` null. 4.0 successful results
require those fields plus `issuer_nombre_source` and `receiver_nombre_source`, alongside
the common structurally required header fields. Business-conditional payment/currency
rules remain outside database constraints in this slice.

## 8. Promotion, reprocessing, and transaction boundary

Parsing and promotion are separate actions. A parser may run in shadow mode: persist a
successful parser/2 result while parser/1 remains current. Promotion is an explicit
transaction: always lock canonical `cfdi_identity` using `SELECT FOR UPDATE`, validate
successful result/evidence compatibility through FKs, then `INSERT ... ON CONFLICT DO
UPDATE` its single projection row. This serializes promotions even if no current row
exists. “Newest parser wins” is forbidden. A parser/2 failure creates a failed
execution only; existing parser/1 current remains intact.

A successful parse looks up or creates the immutable result by logical identity. If it
exists, schema mismatch raises `ParserFingerprintSchemaMismatch`; then fingerprint mismatch
raises `DerivedResultDeterminismViolation`; otherwise it reuses the result. It then inserts
an append-only `SUCCEEDED` execution referencing that result and commits. Failure
atomically inserts only a `FAILED` execution and commits. A later
promotion is intentionally separate to support validation/approval and logical rollback
by promoting a prior immutable result.

## 9. Concurrency

At PostgreSQL `READ COMMITTED`:

* Same evidence/parser/config: obtain/create result through the unique constraint. On a
  conflict, schema mismatch raises `ParserFingerprintSchemaMismatch`; under the same
  schema, different output raises `DerivedResultDeterminismViolation`; only equal schema
  and fingerprint converge to the existing result.
* Same evidence, different versions/configurations: distinct result identities coexist.
* Concurrent promotions: always lock identity; last explicit committed promotion wins,
  while both results remain historical.
* Failed new parser never locks/removes current projection.
* Mass reprocessing uses short transactions and bounded workers; no distributed/advisory
  locks are needed initially.

## 10. Constraints and indexes

Use `ON DELETE RESTRICT` for all relations. Do not operationally delete evidence,
executions, results, or current projections; derived data is regenerable but retained for
audit. Exceptional retention/purge requires a separate policy.

Indexes: execution `(evidence_id, parsed_at DESC)`, execution `(parser_name,
parser_version)`, partial failed-status index; result issuer/receiver canonical RFC,
`fecha`, `tipo_comprobante`, `total`, and `(moneda, total)` only after query evidence;
current PK by identity is the normal current-header path. Start with RFC, date, type, and
evidence-history indexes; defer monetary/currency indexes until reporting workload proves
them necessary.

## 11. Query and future evolution

Common query is one join: `cfdi_identity -> cfdi_header_current -> cfdi_header_result`.
Audit queries start from execution/result history. Reporting uses current projection;
inference/risk can record the result ID and parser version used as factual provenance.

This design is header-specific now. Concepts, taxes, and complements must not enter these
tables. A future parse-run root may be introduced only when another derived slice proves
shared execution lifecycle needs; do not prematurely generalize it.

## 12. Alembic plan and tests

The next migration, after implementation review, creates result first, execution with its
composite provenance FK second, then current projection and indexes. It must use
PostgreSQL 17 integration tests and no SQLite substitute.

Tests: first success; duplicate same parse; same evidence/different parser version;
failure; failed parser/2 preserving parser/1 current; explicit promotion; concurrent same
parse and promotion; exact Decimal/source values; naive fecha; source/canonical RFC;
3.3 nullability; 4.0 required fields; evidence/identity/result FK mismatch; RESTRICT
delete; rollback; current query; and full parser history.

## 13. Acceptance criteria

Evidence stays immutable; derived facts are reproducible and auditable; current is
unambiguous; failures cannot erase prior valid current; same result identity cannot create
inconsistent duplicates; DB constraints protect evidence/identity compatibility; no float
or invented timezone enters storage; snapshots remain historical; and no concepts, taxes,
or complements enter the slice.

## 14. Open decisions

* Exact canonical serialization for `cfdi-header-fingerprint/1` before implementation.
* Maximum sanitized error-message length and production retention/purge policy.
* Whether early reporting demonstrably needs monetary/currency indexes beyond the initial
  RFC/date/type set.
* Future approval actor and promotion reason after authentication exists.
