# AURUM — CFDI Identity & Immutable Ingestion Specification

**Status:** Proposed design — pending review
**Scope:** CFDI Core — identity and immutable XML evidence only

---

## 1. Purpose

Define the first vertical slice that receives CFDI XML bytes, preserves their exact
original form as immutable evidence, calculates SHA-256, and establishes fiscal identity
only from the `UUID` attribute of
`{http://www.sat.gob.mx/TimbreFiscalDigital}TimbreFiscalDigital`.

The slice makes ingestion idempotent for the same evidence and makes contradictory
identity evidence explicit. It is not a general CFDI parser.

---

## 2. Slice boundaries

### Included

* Receive one XML document as bytes.
* Retain the exact received bytes as immutable evidence.
* Calculate a SHA-256 digest over those exact bytes.
* Safely inspect XML only enough to find the `UUID` attribute on the exact SAT
  `TimbreFiscalDigital` expanded element.
* Validate and canonicalize that UUID.
* Register or recognize the CFDI identity and determine the duplicate outcome.

### Explicitly excluded

* HTTP endpoints, FastAPI request models, file names, multipart handling, and UI.
* Physical storage implementation, database implementation, migrations, or ORM.
* CFDI header extraction, concepts, taxes, payroll, INE, relationships, SAT, SIF,
  reconciliation, classification, jobs, and audit subsystem implementation.
* Interpretation of any XML attribute other than `UUID` on
  `{http://www.sat.gob.mx/TimbreFiscalDigital}TimbreFiscalDigital` for fiscal identity.

---

## 3. Flow and transactional boundary

```text
XML bytes
  -> enforce input-size limit
  -> SHA-256 over exact bytes
  -> secure bounded XML inspection
  -> read UUID only from the exact SAT TimbreFiscalDigital element
  -> UUID validation and canonicalization
  -> inspect identity and evidence indexes
  -> atomically persist outcome
```

The transaction conceptually commits both immutable evidence metadata and the identity
decision, or neither. Evidence bytes are written durably before their metadata is
considered committed. A storage implementation may stage bytes and clean up an
uncommitted object after a failed transaction; it must never alter bytes after their hash
is recorded.

For a new accepted document, the atomic unit is: evidence reference + exact SHA-256 +
canonical UUID + link between both. For a UUID conflict, incoming evidence and its
conflict record are committed atomically, but it is not linked as authoritative evidence
for the existing CFDI identity.

---

## 4. Minimum model

### Value objects

* `CfdiUuid`: a valid RFC 4122 UUID represented canonically as uppercase hyphenated
  text (for example, `039D171E-773B-495C-881F-BBEFBC8991C2`). Construction rejects
  empty, malformed, or non-canonicalizable values. Comparison does not depend on the
  casing originally received.
* `Sha256Digest`: exactly 32 digest bytes, represented externally as lowercase
  64-character hexadecimal text.
* `OriginalXml`: non-empty received bytes. It has no normalized, decoded, or rewritten
  form in this slice.
* `XmlEvidence`: `OriginalXml` plus its `Sha256Digest`; the digest is calculated from
  the original bytes exactly once at construction.

### Entities / records

* `CfdiIdentity`: durable fiscal identity keyed by `CfdiUuid`, with a reference to its
  authoritative accepted evidence.
* `IngestionRecord`: append-only record of an ingestion decision. It contains the
  received evidence reference, canonical UUID when available, outcome, and a reference
  to the existing identity when applicable.
* `IdentityConflict`: append-only record linking incoming evidence to the existing
  `CfdiIdentity` when the same UUID has different bytes.

`CfdiIdentity` deliberately contains no concepts, totals, issuer, receiver, or parsed
CFDI fields. Evidence remains distinct from identity: a hash identifies bytes, while a
UUID identifies the fiscal document.

---

## 5. Application contract

The application layer exposes one use case, conceptually:

```text
ingest_cfdi_xml(original_xml: bytes) -> IngestionResult
```

`IngestionResult` contains:

* `outcome`: `ACCEPTED`, `REINGESTED`, or `IDENTITY_CONFLICT`;
* `cfdi_uuid` when XML inspection succeeded;
* `sha256`;
* the durable identity/evidence reference appropriate to the outcome.

Malformed XML, absent Timbre, and invalid UUID are typed application errors, not an
`IngestionResult`. The contract receives bytes only: source filename and other transport
metadata are neither identity inputs nor part of this slice.

The API adapter may later translate transport input to this contract, and infrastructure
adapters may implement its ports. Neither belongs in the domain model.

---

## 6. Minimum ports

Only these abstract capabilities are required by the application use case:

* `XmlEvidenceStore`: write immutable bytes addressed by a digest and retrieve evidence
  metadata by digest. It abstracts local disk, object storage, or another durable store.
* `CfdiIdentityRepository`: obtain an identity by canonical UUID, obtain the identity
  associated with a digest, and register an accepted identity/evidence association.
* `IngestionRecordRepository`: append re-ingestion and conflict decisions.
* `UnitOfWork`: delimit the atomic metadata decision and coordinate rollback/commit.
* `CfdiIdentityReader`: safely inspect bounded XML bytes and return the raw `UUID`
  attribute only from `{http://www.sat.gob.mx/TimbreFiscalDigital}TimbreFiscalDigital`,
  or a typed extraction error.

`CfdiIdentityReader` is a focused parser port, not a second general CFDI parser. Future
flows must reuse this identity extraction capability rather than derive UUIDs elsewhere.

---

## 7. Identity and duplicate policy

The lookup keys are canonical UUID and SHA-256 of exact incoming bytes. The repository
enforces one authoritative accepted evidence item per canonical UUID and one accepted
canonical UUID per SHA-256.

| Case | Decision | Result |
| --- | --- | --- |
| A. Same UUID + same SHA-256 | Recognize as idempotent re-ingestion. | `REINGESTED`; do not create a second CFDI identity or rewrite evidence. Append only the ingestion decision/provenance if that information is in scope. |
| B. Same UUID + different SHA-256 | Identity conflict. | Preserve incoming bytes as immutable conflict evidence and append `IdentityConflict`; return `IDENTITY_CONFLICT`. Do not overwrite, merge, or silently attach it to the accepted identity. |
| C. Existing SHA-256 + same UUID | Same condition as A. | `REINGESTED`; reuse existing immutable evidence reference. |
| D. Existing SHA-256 + different UUID | Integrity conflict; impossible for correctly functioning deterministic extraction from identical bytes. | Do not accept a new association or overwrite data. Surface `EvidenceIdentityMismatch` and record an integrity incident if it can be done transactionally. |

Case D is not a normal duplicate branch. It indicates repository corruption, an
incorrectly versioned extraction rule, or an implementation defect, and requires
operator investigation. Canonicalization rules must not change historical identity
associations.

---

## 8. Invariants

1. Original XML bytes are immutable once accepted or recorded as conflict evidence.
2. Every stored SHA-256 equals the digest of its exact stored bytes.
3. A CFDI identity is derived only from the `UUID` attribute of
   `{http://www.sat.gob.mx/TimbreFiscalDigital}TimbreFiscalDigital`.
4. UUID comparison and persistence use canonical `CfdiUuid` representation.
5. An accepted canonical UUID has exactly one authoritative accepted evidence item.
6. An accepted evidence digest is associated with exactly one canonical UUID.
7. A conflict cannot replace or mutate an accepted identity/evidence association.
8. No malformed XML, XML without Timbre, or invalid UUID creates a CFDI identity.
9. File names, arbitrary UUID-looking text, related UUIDs, and other attributes are
   never identity fallbacks.

---

## 9. Errors

* `XmlInputTooLarge`: received bytes exceed the configured safety limit.
* `MalformedXml`: XML is syntactically invalid or violates parser safety restrictions.
* `MissingTimbreFiscalDigital`: no
  `{http://www.sat.gob.mx/TimbreFiscalDigital}TimbreFiscalDigital` element is present.
* `MissingTimbreUuid`: the required SAT Timbre element exists but lacks its `UUID`
  attribute.
* `InvalidCfdiUuid`: extracted UUID cannot be parsed and canonicalized.
* `EvidenceIdentityMismatch`: existing digest is associated with a different UUID.
* `EvidenceStorageFailure` and `IdentityPersistenceFailure`: infrastructure failures
  translated at the application boundary without vendor-specific exceptions.

`IDENTITY_CONFLICT` is a business-significant `IngestionResult` outcome for case B; it
is not an exception and does not mean the incoming XML is invalid. `IdentityConflict` is
the optional append-only entity/record used to persist that incident. The remaining
identity-invalid cases stop normal ingestion.

---

## 10. XML security

The identity reader uses a hardened XML parser configuration. At minimum it must:

* reject DTD declarations and external, general, and parameter entity expansion;
* disable external resource resolution, XInclude, and network access;
* enforce configurable limits for input bytes, element depth, attribute size, and total
  elements before or during parsing;
* process the document as bytes and avoid logging its full contents;
* establish identity only from the exact expanded element name
  `{http://www.sat.gob.mx/TimbreFiscalDigital}TimbreFiscalDigital` and require its
  attribute name exactly `UUID`; an element with the same local name in another
  namespace does not establish identity.

The future implementation must choose and document the concrete hardened parser before
adding a dependency. It must not use permissive parser configuration or parse XML twice
for separate ingestion paths.

---

## 11. Minimum persistence

The logical persistence required is intentionally small:

* immutable evidence metadata: evidence reference, SHA-256, byte length, and creation
  timestamp;
* immutable evidence bytes in an implementation-selected durable store;
* CFDI identity: internal identifier, canonical UUID, authoritative evidence reference,
  and creation timestamp;
* append-only ingestion records with outcome;
* append-only conflict records with existing identity reference and incoming evidence
  reference.

Required constraints are unique accepted canonical UUID and unique accepted SHA-256,
plus references that preserve the evidence-to-identity association. Exact tables,
storage provider, transaction mechanism, and migrations are deferred to implementation.

---

## 12. Required tests for implementation

* Valid XML with `{http://www.sat.gob.mx/TimbreFiscalDigital}TimbreFiscalDigital/@UUID`
  is accepted and canonicalized to uppercase.
* UUID input with differing casing is stored and compared canonically in uppercase.
* An element with local name `TimbreFiscalDigital` in an incorrect namespace does not
  establish fiscal identity.
* UUID-like value outside the `UUID` attribute of the exact SAT Timbre element does not
  establish identity.
* XML with no Timbre and Timbre with no UUID are rejected distinctly.
* Malformed XML and unsafe XML constructs are rejected distinctly.
* Invalid UUID values are rejected.
* Hash matches SHA-256 of exact input bytes, including whitespace and encoding bytes.
* Case A/C re-ingestion is idempotent and does not rewrite evidence or create identity.
* Case B creates visible conflict and preserves both byte sequences without replacing
  accepted evidence.
* Case D is surfaced as integrity conflict and creates no new association.
* Failure during evidence or metadata persistence leaves no committed partial identity;
  staged bytes follow cleanup policy.
* Concurrent submissions of same UUID uphold uniqueness invariants.

Use synthetic, sanitized XML fixtures only.

---

## 13. Acceptance criteria

1. One application use case accepts XML bytes without FastAPI, SQLAlchemy, or storage
   implementation dependencies.
2. Original bytes and SHA-256 are represented separately from fiscal identity.
3. Identity comes exclusively from the `UUID` attribute of the exact SAT Timbre element
   and is canonical.
4. All A/B/C/D duplicate outcomes follow this document.
5. Unsafe, malformed, missing, and invalid identity inputs have distinct outcomes.
6. Durable adapters can later attach without changing domain rules.
7. No CFDI details beyond identity are parsed or persisted in this increment.

---

## 14. Open decisions

* Concrete hardened XML library/configuration and numeric safety limits.
* Exact provenance fields and whether every idempotent re-ingestion creates an audit row
  in the first implementation.
* Transaction/outbox strategy if selected evidence store cannot share a transaction with
  metadata persistence.
* Conflict review workflow, retention, and operator-facing presentation.
* Whether cryptographic signature validation becomes a later, separate capability.
