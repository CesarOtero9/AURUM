# AURUM — CFDI Concepts Specification

**Status:** Accepted — Concepts parsing/domain design; persistence not started
**Scope:** Canonical parsing and domain design for CFDI concept lines in CFDI 3.3 and 4.0.

---

## 1. Status and scope

This specification defines a future Fiscal Core slice that extracts normalized concept lines
from immutable CFDI XML evidence. It is a source-parsing and domain contract, not a SAT
catalogue validator or accounting interpretation engine.

Out of scope:

- persistence implementation and migrations;
- concept-level tax implementation and comprobante-level aggregate taxes;
- inventory, accounting, supplier, entity, or expense classification;
- ML, inference, reconciliation, UI, reporting, and SAT catalogue synchronization.

## 2. Domain role

A CFDI Concept is one source concept line belonging to exactly one CFDI represented by
accepted XML evidence. Its core source relationship is:

```text
CfdiIdentity / authoritative CFDI evidence  1 -> N  CfdiConcept
```

The original XML remains immutable evidence. A parsed concept is a derived fiscal fact that
can be regenerated from it; it does not replace the XML or redefine the UUID identity.

Source order is significant and preserved. Description, product/service code, amount, and
`NoIdentificacion` are attributes, never line identity. Two lexically and numerically equal
lines remain two concepts when they occur twice in the XML.

## 3. XML source evidence and version boundary

The parser supports only CFDI 3.3 and 4.0 and must identify the parent `Comprobante` by its
exact expanded name and supported version/namespace pairing, consistent with the Header
reader. Concepts are read only from the version-appropriate CFDI namespace and from the
version-appropriate `Conceptos` / `Concepto` structure; local-name matching is insufficient.

Relevant concept attributes are:

- `ClaveProdServ`;
- `NoIdentificacion`;
- `Cantidad`;
- `ClaveUnidad`;
- `Unidad`;
- `Descripcion`;
- `ValorUnitario`;
- `Importe`;
- `Descuento`; and
- `ObjetoImp` (CFDI 4.0 only).

The core Concepto presence matrix is verified for this checkpoint from official SAT / Anexo 20
technical material: `Conceptos` contains one or more `Concepto` children; both supported
versions require `ClaveProdServ`, `Cantidad`, `ClaveUnidad`, `Descripcion`, `ValorUnitario`,
and `Importe`; both make `NoIdentificacion`, `Unidad`, and `Descuento` optional; and CFDI 4.0
requires `ObjetoImp`. CFDI 3.3 has no `ObjetoImp` attribute in its Concepto schema.

Exact lexical facets beyond typed Decimal parsing, and catalogue/version policy, remain open
and must not be guessed by the parser.

## 4. Canonical Concept data shape

The future domain shape is deliberately source-oriented:

```text
ParsedCfdiConcept
├── concept_index
├── clave_prod_serv_raw
├── no_identificacion_raw?
├── cantidad: FiscalDecimal
├── clave_unidad_raw
├── unidad_raw?
├── descripcion_raw
├── valor_unitario: FiscalDecimal
├── importe: FiscalDecimal
├── descuento?
└── objeto_imp_raw?                 # 4.0 source attribute only
```

For each decimal, preserve both the parser-delivered lexical/source attribute and its typed
exact `Decimal` representation, as Header does for fiscal decimals. This raw/parsed pair is
an accepted domain-design requirement for auditability, determinism, fingerprinting, and
faithful reprocessing comparison. The immutable XML remains the byte-perfect original evidence.
Future persistence decides exact SQL columns and types, but not whether both representations
are retained.

For code and text fields, retain the parser-delivered source value. The immutable XML is the
only byte-perfect evidence for original encoding, quotes, entities, and lexical bytes. A
future result may also retain source location/provenance (for example, the `Concepto` ordinal
and parser result/evidence reference), but it must not pretend to preserve a byte offset unless
the XML reader can reliably provide one.

## 5. Concept identity

Within one successful concepts parse result, identity is structural source position:

```text
(parse result, concept_index)
```

This is distinct from a future database surrogate key and from the result identity itself.
The recommended ordinal convention is **zero-based** (`0` for the first XML `Concepto`): it
maps directly to an ordered sequence and avoids an implicit subtraction in parser code. If
future reporting needs a human line number, it displays `concept_index + 1` without changing
the stored source-order identity.

Do not use a value-based natural key and do not deduplicate repeated lines.

## 6. Ordering

1. The parser emits concepts in document order under the applicable `Conceptos` element.
2. The first emitted concept has index `0`; each next sibling increments by one.
3. Sorting by description, code, quantity, amount, or tax data is prohibited.
4. For the same immutable evidence, parser version, and configuration, source order and
   indexes must be identical.

Order is a source fact; a later display order or accounting grouping is derived data.

## 7. Decimal semantics

`Cantidad`, `ValorUnitario`, `Importe`, and present `Descuento` use exact `Decimal`
semantics. Binary float, automatic rounding, quantization, or coercion of invalid input is
prohibited.

- An absent required numeric attribute raises `MissingRequiredFiscalAttribute`, or an accepted
  concept-scoped equivalent.
- A present-empty required numeric attribute raises `EmptyFiscalAttribute`, or an accepted
  concept-scoped equivalent.
- A malformed present numeric lexical value raises `InvalidFiscalDecimal`, or an accepted
  concept-scoped equivalent.
- An absent optional `Descuento` is `raw=None, parsed=None`, not `Decimal("0")`.
- An explicit source `Descuento="0"` becomes `raw="0", parsed=Decimal("0")`; it is
  distinguishable from absence.

Do not add arithmetic validation such as `Importe == Cantidad * ValorUnitario` in this slice.
That is a future fiscal-validation decision requiring its own accepted rules and evidence.

## 8. Text semantics

`Descripcion`, `Unidad`, and `NoIdentificacion` are source text, not classification input.

- Preserve the parser-delivered source attribute value faithfully, including the behavior
  supplied by the applicable XML/XSD lexical contract.
- Do not independently case-fold, strip accents, tokenize, or search-normalize it.
- Do not add destructive business whitespace normalization. If a later field-local lexical
  rule requires rejection or normalization, it must be explicit, deterministic, versioned,
  and preserve the parser-delivered source value.
- Do not classify, search-normalize, or infer supplier/accounting meaning while parsing.

Future search normalization, language analysis, or semantic categorization is derived data
with its own version and provenance.

## 9. SAT code fields

`ClaveProdServ`, `ClaveUnidad`, and, in 4.0, `ObjetoImp` are source code values. The parser
preserves source values and may apply only explicit field-local lexical validation supported
by the accepted SAT artefact. It must not substitute an unknown code, embed a catalogue
description as source truth, or depend on mutable catalogue membership without a versioned
catalogue policy.

Catalogue lookup and membership validation are future enrichment/reference-data work. An
unknown-but-lexically-accepted code is not silently mapped to another code.

## 10. ObjetoImp

For CFDI 4.0, `ObjetoImp` is a **required** concept source attribute. It indicates whether the
commercial operation is or is not subject to tax and is represented separately from any future
tax interpretation.

For CFDI 3.3, `ObjetoImp` is absent and forbidden by version. The version-neutral parsed model
may expose `objeto_imp=None` for a valid 3.3 concept because that attribute does not exist in
that version. If it is physically present in a 3.3 `Concepto` under the CFDI 3.3 contract, the
reader raises the established typed unexpected/version-forbidden fiscal attribute error.

`ObjetoImp` alone never proves that a tax child exists, that it has a particular amount, or
that a tax treatment should be inferred. Those require future concept-tax source parsing and
fiscal-rule evidence.

## 11. Concept-level taxes boundary

Concept taxes are future ordered child facts, not flattened `CfdiConcept` columns:

```text
CfdiConcept  1 -> N  ConceptTax / ConceptTaxDetail
```

The concepts model must preserve sufficient parent identity and order for future children to
retain their source association. The tax slice must be able to preserve, where supplied,
Traslados and Retenciones with base, impuesto, tipo factor, tasa/cuota, and importe. This
specification does not define their final model, cardinality, calculation validation, or
persistence shape.

## 12. Aggregate taxes boundary

Concept-level taxes and `Comprobante`-level aggregate taxes are distinct source structures.
Neither is a substitute for the other, and neither belongs in Header or as a flattened
concept amount. The future CFDI Taxes design must model their separate provenance and any
cross-checks as derived validation, not as a source-parsing shortcut.

## 13. Parser contract

Conceptually:

```text
CfdiConceptsReader.read(evidence: XmlEvidence) -> ParsedCfdiConcepts
```

The reader accepts immutable XML evidence and is tied to its exact bytes. It does not derive
UUID identity, change Header behavior, parse taxes/complements, or make accounting decisions.
It must reuse the established secure XML policy: byte limits, DTD/entity/external-entity
rejection, bounded depth/elements/attribute bytes, and typed malformed-XML handling.

For supported version/namespace pairs, it returns concepts in source order. It raises typed
errors for unsupported version/namespace, missing required attributes, empty disallowed
attributes, invalid decimal lexical forms, invalid explicit code lexical forms, and version-
forbidden attributes when the accepted matrix requires rejection. It does not become a full
SAT XSD validator.

The precise error class names are implementation decisions, but should follow Header's
`MissingRequiredFiscalAttribute`, `EmptyFiscalAttribute`, `UnexpectedFiscalAttribute`,
`InvalidFiscalDecimal`, `InvalidFiscalCode`, and existing secure-XML error conventions rather
than introduce broad exception tuples.

## 14. Version-specific validation matrix

This matrix is backed by official SAT / Anexo 20 technical material. It describes source
attribute presence only; catalogue membership and fiscal/business validation remain separate.

| Field | CFDI 3.3 | CFDI 4.0 | Required? |
| --- | --- | --- | --- |
| `ClaveProdServ` | supported | supported | required both |
| `NoIdentificacion` | supported | supported | optional both |
| `Cantidad` | supported | supported | required both |
| `ClaveUnidad` | supported | supported | required both |
| `Unidad` | supported | supported | optional both |
| `Descripcion` | supported | supported | required both |
| `ValorUnitario` | supported | supported | required both |
| `Importe` | supported | supported | required both |
| `Descuento` | supported | supported | optional both |
| `ObjetoImp` | forbidden/absent | supported | required in 4.0 |

The Header version contract remains authoritative for root/version/namespace semantics. This
table is limited to `Concepto` attributes and must be replaced with an artefact-cited matrix
before parser implementation begins.

## 15. Determinism and fingerprints

The future concepts result follows the accepted Header direction:

```text
logical result identity
  = (evidence_id, parser_name, parser_version, configuration_hash)
```

For fixed evidence, supported parser version, and fixed configuration, parsing must yield the
same concept count, ordered concepts, source fields, parsed values, canonical values where
explicitly defined, and typed failure. A future fingerprint schema must serialize an explicit
ordered list containing the schema literal, version, concept count, each index, and every
modeled source/parsed/canonical field. It must use deterministic canonical serialization and
a lowercase SHA-256 digest, not dataclass/default ordering or incidental XML attribute order.

`CfdiVersion` and AURUM parser version are independent. If parsing semantics change, parser
version changes; prior derived results remain historical.

## 16. Reprocessing

The same immutable XML may be parsed by a newer Concepts parser/configuration. New successful
derived results do not overwrite historical results. Whether concepts are promoted
independently or as part of a future combined fiscal parse bundle is deliberately open for the
persistence/application design; source ordering and result provenance remain stable either way.

## 17. Relationship to Header

Header owns comprobante-level fields, issuer/receiver snapshots, totals, and header metadata.
Concept owns exactly one item/service line. Header data must not be copied into every concept;
concept values must not be used to overwrite Header totals or identity evidence.

## 18. Relationship to future classification

The canonical source model excludes provider-normal/honorarios/nómina classification,
accounting account, entity inference, policy inference, semantic/expense category, historical
matching, and supplier resolution. Those are future derived, enrichment, or inference layers
and must preserve their own rule/model version and evidence.

## 19. Legacy and golden-output relevance

Legacy Excel reports may flatten concepts into columns or attach derived classifications.
AURUM remains normalized 1:N. Future representative fixtures and golden tests should compare
concept count, source order, descriptions, quantities, amounts, product/service and unit
codes, discounts, and `ObjetoImp` against source XML and useful legacy outputs. They must not
replicate legacy denormalization as the canonical domain model.

## 20. Candidate domain types and errors

Possible future types are `ParsedCfdiConcept`, `ParsedCfdiConcepts`, and a small
`ConceptIndex` value only if it materially protects non-negative, sequential source order.
Plain immutable typed fields are preferable to wrappers without an invariant.

Likely parser errors include concept-scoped forms of `MissingRequiredFiscalAttribute`,
`EmptyFiscalAttribute`, `UnexpectedFiscalAttribute`, `InvalidFiscalDecimal`,
`InvalidFiscalCode`, and `UnsupportedCfdiVersion`. Parsing errors are distinct from future
catalogue, tax, accounting, or inference findings.

## 21. Persistence direction

Future persistence may use an immutable concepts result/container and immutable ordered child
concept rows linked to evidence/result, with unrestricted `NUMERIC` for decimals and derived
provenance. Table names, current-projection policy, child keys, and SQL constraints remain for
a dedicated persistence specification. No migration is authorized by this document.

## 22. Indexing considerations

Future access patterns may justify indexes by evidence/result, `ClaveProdServ`, and
`NoIdentificacion`. Description search belongs to a future normalized/search projection, not
an unexamined source-text index. Amount indexes need demonstrated query use; do not index every
decimal field preemptively.

## 23. Open questions

1. Confirm exact accepted lexical facets and constraints beyond typed Decimal parsing.
2. Decide whether source XML location beyond ordinal is available and valuable.
3. Define the future concept-tax child model and its relation to aggregate taxes.
4. Define catalogue validation responsibility and catalogue-version policy.
5. Decide whether concepts are promoted independently or in a fiscal parse bundle.
6. Decide whether arithmetic consistency checks belong to parsing or a separate fiscal
   validation layer.

## 24. Acceptance criteria

This design is acceptable only when it makes cardinality/order explicit; prohibits value-based
deduplication; records the verified SAT 3.3/4.0 presence matrix; preserves source/raw and exact
decimal semantics; separates `ObjetoImp`, concept taxes, and aggregate taxes; aligns
determinism/versioning with Header; excludes accounting/inference behavior from source parsing;
and leaves persistence unimplemented.
