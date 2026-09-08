# AURUM — CFDI Identity & Immutable Ingestion Persistence Specification

**Status:** Accepted
**Scope:** Production persistence for CFDI identity and immutable XML evidence

---

## 1. Purpose

Define the smallest PostgreSQL persistence model that can make the implemented CFDI
Identity & Immutable Ingestion slice durable, transactional, concurrent-safe, and
auditable. It preserves exact XML evidence, identity, re-ingestions, and identity
conflicts without implementing CFDI parsing beyond identity.

This specification complements `CFDI_IDENTITY_INGESTION_SPEC.md`; it does not alter its
identity rules or A/B/C/D policy.

---

## 2. Scope

Included:

* immutable XML bytes and SHA-256;
* CFDI fiscal identity and its authoritative evidence;
* re-ingestion outcomes and minimal source provenance;
* case-B conflict evidence and conflict review state;
* PostgreSQL transactions, concurrency, SQLAlchemy 2.x, Alembic, and integration-test
  design.

Excluded:

* header fields, concepts, taxes, complements, SAT, SIF, policies, reconciliation,
  inference, risks, users, authentication, jobs, UI, and physical object storage.

---

## 3. Storage decision

### Decision: PostgreSQL `BYTEA` for the MVP/local-first implementation

Store the exact original XML in `BYTEA` together with its SHA-256 in PostgreSQL. A CFDI
XML is typically small enough that this is a pragmatic first production choice.

It provides one transactional system for bytes, identity, re-ingestion records, and
conflicts; simple backups and restores; portable local deployment; and direct retrieval
for future reprocessing. It avoids the orphan-object and two-phase coordination problems
of a filesystem/object-store adapter while the product is still local-first.

The existing `XmlEvidenceStore` port remains valid. Its first production adapter uses
PostgreSQL. A later object-storage adapter may move bytes out of PostgreSQL while keeping
the evidence metadata, SHA-256, identity, and policy unchanged. That migration requires
an explicit data-copy and backup/restore design; it is not part of this increment.

No hybrid strategy is justified now: storing every XML twice increases backup size and
consistency work without a demonstrated scale requirement.

---

## 4. Conceptual relational model

```text
xml_evidence
      ↑ authoritative_evidence_id
      │
cfdi_identity
      ↑ cfdi_identity_id              ↑ incoming_evidence_id
      └──────── identity_conflict ────┘

xml_evidence ──── ingestion_record ──── cfdi_identity
                              │
                              └──── identity_conflict (nullable)
```

All accepted and conflict XML bytes share `xml_evidence`: conflict evidence is still
immutable fiscal evidence, even though it is not authoritative for an identity.

---

## 5. Tables and constraints

### 5.1 `xml_evidence`

Purpose: immutable exact XML evidence, including accepted and conflict evidence.

| Column | PostgreSQL type | Rules |
| --- | --- | --- |
| `id` | `BIGINT GENERATED ALWAYS AS IDENTITY` | Primary key. |
| `sha256` | `VARCHAR(64)` | Not null, unique, lowercase hex digest. |
| `extracted_fiscal_uuid` | `UUID` | Not null; UUID extracted from these exact bytes by the authoritative SAT Timbre rule. |
| `content` | `BYTEA` | Not null; exact received bytes, never normalized. |
| `byte_length` | `INTEGER` | Not null; positive and equals `octet_length(content)`. |
| `created_at` | `TIMESTAMPTZ` | Not null, default `now()`. |

Constraints:

```text
PRIMARY KEY (id)
UNIQUE (sha256)
UNIQUE (id, extracted_fiscal_uuid)
CHECK (length(sha256) = 64)
CHECK (sha256 ~ '^[0-9a-f]{64}$')
CHECK (byte_length > 0)
CHECK (byte_length = octet_length(content))
```

Rows are append-only. The application database role must have `SELECT` and `INSERT`, but
not ordinary `UPDATE` or `DELETE`, on this table. A later retention policy may introduce
an exceptional administrative procedure; it must never rewrite `content` or `sha256`.
`extracted_fiscal_uuid` is likewise immutable metadata derived from the exact bytes using
the accepted SAT Timbre extraction rule. It does not replace `cfdi_identity` and never
uses a filename, source, or provenance value as identity.

### 5.2 `cfdi_identity`

Purpose: one fiscal identity per SAT UUID and its single authoritative evidence item.

| Column | PostgreSQL type | Rules |
| --- | --- | --- |
| `id` | `BIGINT GENERATED ALWAYS AS IDENTITY` | Primary key. |
| `fiscal_uuid` | `UUID` | Not null, unique SAT fiscal identity. |
| `authoritative_evidence_id` | `BIGINT` | Not null, unique; composite FK to matching evidence UUID. |
| `created_at` | `TIMESTAMPTZ` | Not null, default `now()`. |

Constraints:

```text
PRIMARY KEY (id)
UNIQUE (fiscal_uuid)
UNIQUE (authoritative_evidence_id)
UNIQUE (id, fiscal_uuid)
UNIQUE (id, authoritative_evidence_id)
FOREIGN KEY (authoritative_evidence_id, fiscal_uuid)
  REFERENCES xml_evidence(id, extracted_fiscal_uuid) ON DELETE RESTRICT
```

The composite foreign key makes it impossible to associate an evidence row whose UUID
extracted from exact bytes is A with a CFDI identity whose fiscal UUID is B. The unique
authoritative evidence reference additionally prevents one evidence row from becoming
authoritative for multiple identities; it is not, by itself, the case-D guard.

`cfdi_identity` is append-only for this slice: its UUID and authoritative evidence cannot
be updated. A future, separately designed correction process must retain the original
association rather than silently replace it.

### 5.3 `identity_conflict`

Purpose: retain case-B evidence and its relationship to the authoritative identity.

| Column | PostgreSQL type | Rules |
| --- | --- | --- |
| `id` | `BIGINT GENERATED ALWAYS AS IDENTITY` | Primary key. |
| `cfdi_identity_id` | `BIGINT` | Not null FK to authoritative identity. |
| `incoming_evidence_id` | `BIGINT` | Not null FK to conflict evidence. |
| `fiscal_uuid` | `UUID` | Not null; copied only to form composite integrity constraints. |
| `first_seen_at` | `TIMESTAMPTZ` | Not null, default `now()`. |
| `reviewed_at` | `TIMESTAMPTZ` | Nullable; null means unresolved. |
| `review_note` | `TEXT` | Nullable; only future review metadata. |

Constraints:

```text
PRIMARY KEY (id)
UNIQUE (cfdi_identity_id, incoming_evidence_id)
UNIQUE (id, cfdi_identity_id, incoming_evidence_id)
FOREIGN KEY (cfdi_identity_id, fiscal_uuid)
  REFERENCES cfdi_identity(id, fiscal_uuid) ON DELETE RESTRICT
FOREIGN KEY (incoming_evidence_id, fiscal_uuid)
  REFERENCES xml_evidence(id, extracted_fiscal_uuid) ON DELETE RESTRICT
CHECK (reviewed_at IS NULL OR reviewed_at >= first_seen_at)
```

Only review fields may change later. The two evidence/identity references and first-seen
timestamp are immutable. The unique pair defines one incident for the same identity and
same exact evidence bytes. `first_seen_at` records its first occurrence; later attempts
create new `ingestion_record` rows and their latest `received_at` can be derived without
adding `last_seen_at`.

### 5.4 `ingestion_record`

Purpose: append-only minimal provenance for every successfully parsed ingestion outcome
(`ACCEPTED`, `REINGESTED`, or `IDENTITY_CONFLICT`). Persist it in the first production
version because idempotency and conflicts otherwise lose operational provenance.

| Column | PostgreSQL type | Rules |
| --- | --- | --- |
| `id` | `BIGINT GENERATED ALWAYS AS IDENTITY` | Primary key. |
| `outcome` | `VARCHAR(32)` | Not null, constrained to the three outcomes. |
| `evidence_id` | `BIGINT` | Not null FK to received evidence. |
| `cfdi_identity_id` | `BIGINT` | Not null FK to resolved identity. |
| `authoritative_evidence_id` | `BIGINT` | Not null; composite FK to resolved identity's authoritative evidence. |
| `identity_conflict_id` | `BIGINT` | Nullable; composite FK, required only for conflict outcome. |
| `source_type` | `VARCHAR(32)` | Nullable minimal provenance such as `API`, `IMPORT`, or `MIGRATION`. |
| `source_reference` | `VARCHAR(255)` | Nullable opaque caller/import reference; never a fiscal identity input. |
| `received_at` | `TIMESTAMPTZ` | Not null, default `now()`. |

Constraints:

```text
PRIMARY KEY (id)
FOREIGN KEY (evidence_id) REFERENCES xml_evidence(id) ON DELETE RESTRICT
FOREIGN KEY (cfdi_identity_id) REFERENCES cfdi_identity(id) ON DELETE RESTRICT
FOREIGN KEY (cfdi_identity_id, authoritative_evidence_id)
  REFERENCES cfdi_identity(id, authoritative_evidence_id) ON DELETE RESTRICT
FOREIGN KEY (identity_conflict_id, cfdi_identity_id, evidence_id)
  REFERENCES identity_conflict(id, cfdi_identity_id, incoming_evidence_id)
  ON DELETE RESTRICT
CHECK (outcome IN ('ACCEPTED', 'REINGESTED', 'IDENTITY_CONFLICT'))
CHECK (
  (outcome IN ('ACCEPTED', 'REINGESTED')
    AND identity_conflict_id IS NULL
    AND evidence_id = authoritative_evidence_id)
  OR
  (outcome = 'IDENTITY_CONFLICT'
    AND identity_conflict_id IS NOT NULL
    AND evidence_id <> authoritative_evidence_id)
)
```

Indexes: `(cfdi_identity_id, received_at DESC)`, `(evidence_id)`, and
`(identity_conflict_id)`.

Records are never updated or deleted by the application role. Invalid XML and technical
failures do not create an ingestion record in this slice because they have no accepted
evidence/identity association; application logging covers such diagnostics until a
separate technical-ingestion audit design exists.

For `ACCEPTED` and `REINGESTED`, `evidence_id` is both the exact evidence received in
this event and the identity's authoritative evidence. The composite FK and equality CHECK
make a record pointing at a different, merely valid evidence row impossible. For
`IDENTITY_CONFLICT`, `evidence_id` is the incoming conflict evidence while
`authoritative_evidence_id` remains the accepted evidence of the resolved identity.

---

## 6. Internal identifiers

Use `BIGINT GENERATED ALWAYS AS IDENTITY` for all four persistent entities. It is small,
efficient for joins, and sufficient for the expected local-first lifecycle. These values
are internal only. `cfdi_identity.fiscal_uuid` remains the distinct external SAT identity.

---

## 7. UUID representation

Persist fiscal identity as PostgreSQL `UUID`, not `VARCHAR(36)`. It provides native
validation, compact storage, and efficient equality indexes. PostgreSQL may render a UUID
in lowercase; that is an infrastructure representation detail.

The domain continues to enforce strict SAT lexical validation and canonicalize to
uppercase before persistence. SQLAlchemy adapters convert database UUID values back to
the `CfdiUuid` value object, whose external presentation remains uppercase with hyphens.
Database comparisons use native UUID equality and therefore do not depend on input case.

---

## 8. SHA-256 representation

Persist SHA-256 as `VARCHAR(64)` lowercase hexadecimal, not `BYTEA`. This exactly
matches the current `Sha256Digest` value object, avoids `CHAR` blank-padding semantics,
makes diagnostics and backup inspection simple, and has a small B-tree index.
`UNIQUE (sha256)` is both the evidence deduplication constraint and primary lookup index.

The application computes the digest over exact bytes. Database checks enforce length 64
and lowercase hexadecimal form; byte length is checked independently against `BYTEA`
content.

---

## 9. Transaction and concurrency model

Use a short SQLAlchemy session transaction per application use-case invocation at
PostgreSQL `READ COMMITTED`. Do not use long-lived sessions or distributed locks.

Within one transaction:

1. Validate/parse bytes and calculate hash before opening or early in the transaction.
2. Insert `xml_evidence` with `INSERT ... ON CONFLICT (sha256) DO NOTHING`, then select
   the one evidence row by digest.
3. Find `cfdi_identity` by `fiscal_uuid` using `SELECT ... FOR UPDATE` when it exists.
4. If absent, insert it with the selected evidence as authoritative. The composite FK
   validates that the evidence's extracted UUID equals the identity UUID. If a concurrent
   transaction wins `UNIQUE (fiscal_uuid)`, use a savepoint, recover from the unique
   violation, then re-read and lock the winner row.
5. For case B, insert `identity_conflict` with `INSERT ... ON CONFLICT
   (cfdi_identity_id, incoming_evidence_id) DO NOTHING`, then select the one incident.
   Each concurrent ingestion inserts its own `ingestion_record` referencing that incident.
6. Resolve A/B/C/D, insert the ingestion record, and commit.

The savepoint is essential: a case-B incoming evidence insert must survive an identity
unique-violation race so it can be recorded as conflict in the same outer transaction.
Unique constraints remain authoritative; locks only serialize decisions after an identity
exists. Retry only serialization/deadlock/unique-race paths a bounded number of times;
never retry invalid XML or identity errors.

Two simultaneous identical XML inputs converge to one evidence, one identity, and two
ingestion records (`ACCEPTED` plus `REINGESTED`). Two different XML inputs for one UUID
converge to one authoritative identity and one or more conflict evidence rows. Concurrent
attempts for the same identity/evidence conflict pair converge through the unique
constraint and `ON CONFLICT DO NOTHING` to one `identity_conflict` plus multiple
ingestion records. A shared digest with a different UUID is rejected as
`EvidenceIdentityMismatch` before any new identity association is written; even a faulty
adapter cannot insert that association because the composite FK rejects mismatched
extracted and fiscal UUID values.

---

## 10. A/B/C/D database mapping

| Case | Database decision |
| --- | --- |
| A. UUID + hash equal | Existing `cfdi_identity` points to the same `xml_evidence`; equality CHECK plus composite FK require the `REINGESTED` record to use that authoritative evidence. |
| B. UUID equal + hash different | Insert/reuse incoming `xml_evidence`; lock identity; composite FKs require incoming evidence's extracted UUID to equal the identity UUID; insert `identity_conflict` and `IDENTITY_CONFLICT` record. Never update `authoritative_evidence_id`. |
| C. Hash equal + UUID equal | Same physical state as A; unique SHA-256 and UUID indexes produce `REINGESTED`, whose received and authoritative evidence references must be identical. |
| D. Hash equal + UUID different | `xml_evidence.extracted_fiscal_uuid` differs from the attempted identity UUID; raise `EvidenceIdentityMismatch`, roll back the attempted association, and write no new identity/conflict/re-ingestion record. The composite FK makes the contradictory association impossible even if evidence was previously conflict-only. |

Composite foreign keys ensure UUID-compatible references; unique indexes prevent duplicate
identity/evidence associations; row locking plus retry makes the decision race-safe.
Python chooses the business outcome, but database constraints make invalid durable states
impossible.

---

## 11. Repository and UnitOfWork mapping

PostgreSQL, SQLAlchemy 2.x, and Alembic remain the correct architectural decisions. No
generic CRUD repository is needed.

`UnitOfWork` is implemented by an infrastructure object that owns exactly one SQLAlchemy
`Session` per use-case call. Its context manager calls `session.begin()`, commits only on
successful exit, rolls back on any exception, and closes the session. The application
service owns the UnitOfWork boundary; API and workers obtain it through composition/root
wiring. Domain entities and value objects never import SQLAlchemy.

Small contract adjustments required before implementing adapters:

* `XmlEvidenceStore.store` must return an opaque persisted evidence reference, and add
  lookup by `Sha256Digest`. `void` cannot support FK-backed ingestion/conflict records.
* `CfdiIdentityRepository` needs a persistence reference for a fetched/inserted identity
  and an operation to lock/read by fiscal UUID within the UnitOfWork. Keep its methods
  specific to identity lookup/association; do not introduce a generic repository.
* `IngestionRecordRepository` should accept `outcome`, persisted evidence/identity
  references, optional conflict reference, and minimal `source_type/source_reference`.
* The application command should accept optional `IngestionProvenance`; it must not
  influence UUID or hash calculation.

These are interface refinements, not domain changes. `CfdiIdentityReader` is unchanged.

---

## 12. Conflict persistence and retention

Case-B bytes are inserted into the same `xml_evidence` collection because their evidential
value does not disappear when they conflict. Composite foreign keys guarantee the incoming
evidence has the same extracted fiscal UUID as the referenced identity. `identity_conflict`
answers which accepted identity/evidence was authoritative, which exact incoming evidence
conflicted, when it was first seen, and whether review occurred. It intentionally does
not model a UI, user, or resolution workflow yet.

---

## 13. Reprocessing and deletion

Future parsers consume `xml_evidence.content` and may create derived data without ever
mutating original bytes, hash, or authoritative association. Parser-version history is
deferred, but no proposed key prevents it.

Use `ON DELETE RESTRICT` for all slice foreign keys. Physical deletion is not a normal
operation for fiscal evidence, identities, conflicts, or ingestion records. Retention,
legal holds, archival, and exceptional administrative deletion require a separate policy.
Do not use cascading deletes.

---

## 14. Migration strategy

The first Alembic migration for this slice creates only these four tables, their checks,
foreign keys, unique constraints, and operational indexes. It must be additive,
reviewable, reproducible, and tested against PostgreSQL. No manual schema edits and no
SQLite substitute for PostgreSQL integration semantics.

---

## 15. Integration-test strategy

Add PostgreSQL integration tests only with the persistence increment. Use an isolated
PostgreSQL database per test run (container or controlled local test service), apply
Alembic migrations, and clean state through test transactions or explicit fixtures.

Tests must cover constraints and separate concurrent sessions for A/B/C/D, including
unique-violation recovery, `FOR UPDATE` behavior, rollback of partial identity writes,
immutable evidence retrieval, `RESTRICT` deletes, and `BYTEA` byte-for-byte round trips.
Do not use SQLite as a replacement.

---

## 16. Acceptance criteria

1. Exact XML bytes, SHA-256, identity, conflicts, and ingestion outcomes are durable.
2. One canonical UUID has one authoritative evidence row, enforced by PostgreSQL.
3. Conflict evidence is retained without replacing authoritative evidence.
4. A/B/C/D are correct under concurrent transactions.
5. Application/domain code remains independent of SQLAlchemy.
6. Production storage starts with PostgreSQL `BYTEA` and can later move behind the port.
7. No unrelated CFDI/accounting/SAT concepts enter the first migration.

---

## 17. Open decisions

* Exact numeric XML size limit and database role/grant provisioning.
* Whether production provenance requires an immutable import-batch identifier in the
  first persistence increment.
* Object-storage migration threshold and backup policy after observed evidence volume.
* Conflict-review actor identity once authentication exists.
