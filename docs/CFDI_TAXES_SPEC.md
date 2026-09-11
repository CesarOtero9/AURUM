# AURUM — CFDI Taxes Specification

**Status:** Accepted — Taxes parsing/domain design; parser implementation not started
**Scope:** Canonical parsing/domain design for fiscal taxes represented in CFDI 3.3 and
4.0. This is a source-fact design only; parser, persistence, migrations, and tests are not
started by this document.

---

## 1. Scope and non-goals

This slice records the tax facts expressed by the base CFDI XML, while preserving the
distinction between tax facts on a `Concepto` and tax facts aggregated at `Comprobante`.

Out of scope are persistence, accounting classification, deductibility/accreditability,
DIOT, payroll or honorarios interpretation, catalogue enrichment, inferred taxes, arithmetic
reconciliation, UI/reporting, payment-complement taxes, local-tax complements, and
credit-note/cancellation semantics.

## 2. Evidence hierarchy and authoritative references

### A. SAT technical/normative evidence

1. [SAT, Anexo 20 / CFDI 4.0 technical standard](https://www.sat.gob.mx/cs/Satellite?blobcol=urldata&blobkey=id&blobtable=MungoBlobs&blobwhere=1461175118249&ssbinary=true): identifies the CFDI 4.0 namespace and base XSD; documents the `Concepto/Impuestos` and
   `Comprobante/Impuestos` structures, their attributes, and conditional rules.
2. [SAT, Anexo 20 / CFDI 3.3 technical standard](https://wwwmat.sat.gob.mx/cs/Satellite?blobcol=urldata&blobkey=id&blobtable=MungoBlobs&blobwhere=1461173537740&ssbinary=true): documents the corresponding 3.3 XSD structure and conditional rules.
3. [SAT, Formato de Factura (Anexo 20)](https://wwwmat.sat.gob.mx/consultas/35025/formato-de-factura-electronica-(anexo-20)): confirms CFDI 4.0 introduced `ObjetoImp`, is the current valid CFDI version, and provides current FAQ guidance for `c_ObjetoImp`.
4. [SAT, RMF 2026](https://www.sat.gob.mx/minisitio/NormatividadRMFyRGCE/documentos2026/rmf/rmf/RMF_2026-DOF-28122025.pdf): confirms the current use of `c_ObjetoImp` key `05` for the PODEBI IVA-credit scenario.

The official XSD locations referenced by the SAT standard are
`http://www.sat.gob.mx/sitio_internet/cfd/3/cfdv33.xsd` and
`http://www.sat.gob.mx/sitio_internet/cfd/4/cfdv40.xsd`. They are the structural source;
the SAT technical publications above are retained here because they make the same XSD
attributes and conditional use readable.

### B. Operational observations

Representative AURUM XML evidence will be used later as compatibility fixtures, but it does
not override SAT structure. No operational observation establishes accounting treatment.

### C. Design conclusions

The conclusions marked **accepted design direction** below preserve official source facts
without deciding accounting, validation, or catalogue-enrichment meaning.

### D. Unresolved questions

Only items requiring a separate parser, arithmetic-validation, persistence, or semantic
design checkpoint remain open in section 27.

## 3. Fiscal hierarchy

The two source levels are distinct and must remain distinct:

```text
CFDI
├── Conceptos
│   └── Concepto[*]
│       └── Impuestos?                         # concept-level source container
│           ├── Traslados? / Traslado[*]
│           └── Retenciones? / Retencion[*]
└── Impuestos?                                 # comprobante aggregate source container
    ├── Traslados? / Traslado[*]
    └── Retenciones? / Retencion[*]
```

Concept-level rows and aggregate rows are separate source facts from different XML locations.
They must not be flattened into a generic collection or treated as cached sums. Any future
cross-check is derived validation, not a parsing shortcut.

## 4. Canonical concept-level tax model

**Accepted design direction:** use immutable parser result objects equivalent to:

```text
ParsedCfdiConceptTaxes
  concept_index
  impuestos_present
  transfers: ordered ParsedCfdiConceptTransfer[*]
  withholdings: ordered ParsedCfdiConceptWithholding[*]

ParsedCfdiConceptTransfer
  transfer_index, base_raw/base, impuesto_raw, tipo_factor_raw
  tasa_o_cuota_raw?/tasa_o_cuota?, importe_raw?/importe?

ParsedCfdiConceptWithholding
  withholding_index, base_raw/base, impuesto_raw, tipo_factor_raw
  tasa_o_cuota_raw/tasa_o_cuota, importe_raw/importe
```

Names are provisional; an implementation must follow the established Header/Concepts naming
conventions. A common internal decimal/raw helper is permitted only if it cannot erase the
different source contracts of transfer, withholding, and aggregate rows.

The accepted future persistence parent is immutable `cfdi_concept.id`; this only freezes the
parent boundary, not any tax persistence schema.

## 5. Concept-level Traslado matrix

The official 3.3 and 4.0 technical standards have the same base structural matrix below.
`Impuestos`, `Traslados`, and each `Traslado` are optional/conditional containers as shown;
when `Traslados` exists it contains one or more `Traslado` children.

| Attribute | CFDI 3.3 | CFDI 4.0 | Rule |
| --- | --- | --- | --- |
| `Base` | required | required | Decimal source fact. |
| `Impuesto` | required | required | `c_Impuesto` source code. |
| `TipoFactor` | required | required | `c_TipoFactor` source code. |
| `TasaOCuota` | conditional | conditional | Required for `Tasa` or `Cuota`; absent for `Exento`. |
| `Importe` | conditional | conditional | Required for `Tasa` or `Cuota`; absent for `Exento`. |

The parser will enforce only this structural/factor-dependent presence matrix. Catalogue
membership and arithmetic correctness are not part of this design.

## 6. Concept-level Retencion matrix

For both CFDI 3.3 and 4.0, a concept `Retencion` has the following required attributes:

| Attribute | CFDI 3.3 | CFDI 4.0 | Rule |
| --- | --- | --- | --- |
| `Base` | required | required | Decimal source fact. |
| `Impuesto` | required | required | `c_Impuesto` source code. |
| `TipoFactor` | required | required | Required factor code. |
| `TasaOCuota` | required | required | Required decimal source fact. |
| `Importe` | required | required | Required decimal source fact. |

SAT's CFDI 4.0 validation material additionally says a withholding `TipoFactor` must differ
from `Exento`. That is a versioned fiscal validation rule to preserve as future validation
evidence; it must not be replaced by a guessed symmetry with transfers.

## 7. Comprobante-level aggregate tax model

**Accepted design direction:** aggregate taxes use separate immutable objects:

```text
ParsedCfdiAggregateTaxes
  impuestos_present
  total_trasladados_raw?/total_trasladados?
  total_retenidos_raw?/total_retenidos?
  transfers: ordered ParsedCfdiAggregateTransfer[*]
  withholdings: ordered ParsedCfdiAggregateWithholding[*]
```

Aggregate `Retencion` is compact in both versions: exactly `Impuesto` and `Importe` are
required. It does not inherit `Base`, `TipoFactor`, or `TasaOCuota` from a concept retention.

Aggregate `Traslado` is structurally different from a concept transfer:

| Attribute | CFDI 3.3 aggregate Traslado | CFDI 4.0 aggregate Traslado |
| --- | --- | --- |
| `Base` | version-forbidden / structurally absent | required |
| `Impuesto` | required | required |
| `TipoFactor` | required | required |
| `TasaOCuota` | required | conditional; absent for the all-Exento case |
| `Importe` | required | conditional; absent for the all-Exento case |

This differs deliberately from **CFDI 3.3 concept Traslado**, where `Base`, `Impuesto`, and
`TipoFactor` are required and `TasaOCuota`/`Importe` are conditional. SAT's 4.0 standard
documents the aggregate `Base` as the sum of concept bases, while the 3.3 aggregate XSD does
not define that attribute.

Aggregate totals are source attributes on `Comprobante/Impuestos` in both versions:

| Attribute | CFDI 3.3 | CFDI 4.0 | Parser behavior |
| --- | --- | --- | --- |
| `TotalImpuestosRetenidos` | optional in XSD; conditional when concept retentions exist | optional in XSD; conditional when concept retentions exist | Preserve raw/Decimal when present; absent is `None`, never a calculated replacement. |
| `TotalImpuestosTrasladados` | optional in XSD; conditional when concept transfers exist | optional in XSD; conditional when taxable/non-Exento concept transfers exist | Preserve raw/Decimal when present; absent is `None`, never a calculated replacement. |

Arithmetic equality, rounding, and current SAT validation formulas are future validation work.

## 8. Raw lexical and Decimal policy

For every present decimal-like tax attribute (`Base`, `TasaOCuota`, `Importe`, and aggregate
totals), retain both the parser-delivered lexical value and exact `Decimal`. Never use binary
float, quantize, round, normalize trailing zeros, or calculate a missing value.

An absent conditional attribute is `raw=None, parsed=None`; an explicit permitted zero keeps
its exact raw text and `Decimal("0")`. Thus `"0"`, `"0.00"`, and `"0.160000"` remain
lexically distinguishable. The immutable XML remains the byte-perfect original evidence.

## 9. Source order, duplicates, and structural identity

Document order is preserved independently for concept transfers, concept withholdings,
aggregate transfers, and aggregate withholdings. Each collection uses zero-based local
indexes. Identical rows remain distinct occurrences; no code/amount/value-derived
deduplication is permitted.

Domain-level identities are structural only:

```text
concept transfer     = (concept_index, transfer_index)
concept withholding  = (concept_index, withholding_index)
aggregate transfer   = (aggregate_transfer_index)
aggregate withholding = (aggregate_withholding_index)
```

These are not future SQL primary-key decisions.

## 10. Impuesto and TipoFactor codes

`Impuesto` and `TipoFactor` retain their raw source code. Common `c_Impuesto` codes (such as
001, 002, and 003) are not replaced by labels such as ISR, IVA, or IEPS. SAT catalogue
membership, descriptions, versions, and temporal validity are future reference-data policy.

The parser records the factor as represented and applies only the verified structural
consequences:

- `Tasa` or `Cuota`: concept transfer `TasaOCuota` and `Importe` are required.
- `Exento`: those concept-transfer attributes are absent; it is not an error or implicit zero.
- Concept withholdings retain their separately required fields and must not borrow transfer
  semantics.

## 11. ObjetoImp in CFDI 4.0 and rule ownership

`ObjetoImp` is a required Concepto source attribute in 4.0 and absent/version-forbidden in
3.3, as already accepted by the Concepts slice. It expresses whether the commercial operation
is object of tax; it is not a substitute for tax children or tax amounts.

The current official SAT material demonstrates that the catalogue is not safely limited to
historical 01–04. The following matrix freezes the evidence classification and ownership; it
does not convert catalogue labels into accounting meaning.

| Code | Official meaning/evidence | Concepto/Impuestos consequence supported here | Specific tax-node restriction supported here | Source | Responsible layer |
| --- | --- | --- | --- | --- | --- |
| `01` | No objeto de impuesto. | `ObjetoImp` itself is required in 4.0; the XSD still makes the tax container conditional. | No additional code-specific node rule is established by the current cited technical material. | SAT `c_ObjetoImp` catalogue / Anexo 20 | Catalogue policy for meaning/validity; versioned fiscal validation for any cross-node rule. |
| `02` | Sí objeto de impuesto. | Same XSD fact: source tax container remains conditional. | No parser-created tax row; any required tax-combination rule is fiscal validation. | SAT Anexo 20 and filling material | Structural parser preserves; fiscal validation cross-checks. |
| `03` | Sí objeto del impuesto y no obligado al desglose. | Same structural container rule. | No additional node restriction is established here beyond the catalogue meaning. | SAT `c_ObjetoImp` catalogue / Anexo 20 | Catalogue policy; fiscal validation if SAT publishes a cross-node rule. |
| `04` | Sí objeto del impuesto y no causa impuesto; SAT FAQ gives real-interest IVA as an example. | Same structural container rule. | No additional parser rule follows from the FAQ alone. | SAT Factura FAQ | Catalogue policy; fiscal validation. |
| `05` | Sí objeto del impuesto, IVA crédito PODEBI. RMF 2026 explicitly directs this key in the PODEBI scenario. | Same structural container rule. | No base-XSD tax-node restriction is implied by the RMF citation. | SAT RMF 2026, rule 11.11.11 | Catalogue policy/current fiscal validation. |
| `06` | Sí objeto del IVA, no traslado IVA; SAT FAQ identifies specified RMF scenarios. | Same structural container rule. | No additional parser rule follows from the FAQ alone. | SAT Factura FAQ | Catalogue policy/current fiscal validation. |
| `07` | No traslado IVA, sí desglose IEPS. | Same structural container rule. | The FAQ describes the IEPS-display scenario; parser still records only actual nodes. | SAT Factura FAQ | Catalogue policy/current fiscal validation. |
| `08` | No traslado IVA, no desglose IEPS. | Same structural container rule. | No actual tax node is fabricated or prohibited by the structural parser solely from this label. | SAT Factura FAQ | Catalogue policy/current fiscal validation. |

Rule ownership is therefore frozen:

1. **Structural parser:** exact CFDI 4.0 `ObjetoImp` attribute presence, exact XML
   namespace/version, tax-container shape, row attributes, and factor-dependent fields.
2. **Versioned fiscal validation:** current SAT cross-node rules that compare `ObjetoImp`,
   tax-node combinations, CFDI type, catalogue versions, and RMF/validation matrices.
3. **SAT catalogue policy:** code membership, descriptions, effective dates, and replacement
   history.

The parser preserves the raw code. It never creates a tax child, calculates an amount, or
infers accounting treatment from `ObjetoImp`.

## 12. Container presence

For a concept, `Impuestos` is optional/conditional. Its absence is a source fact, represented
as `impuestos_present=False` with no child rows. If present, it may contain `Traslados`,
`Retenciones`, or both; each present collection contains at least one child. A structurally
empty present container is rejected when the XSD/accepted structural contract forbids it.

At `Comprobante`, `Impuestos` is optional/conditional and is represented independently as
`impuestos_present`. It may have aggregate transfers, aggregate withholdings, or both. The
reader preserves node presence where it is material and never fabricates totals or rows.

## 13. Arithmetic validation is future work

This parser reads fiscal source facts. It does not validate or calculate `Base * TasaOCuota`,
concept-to-aggregate sums, aggregate totals, or invoice-total relationships. Those future
checks require official rounding formulas, currency decimal support, version-specific rules,
and accepted tolerances. A failed future validation is not permission to alter parsed facts.

## 14. Fiscal facts are not accounting semantics

Canonical tax parsing records tax code, base, factor, rate/quota, amount, transfer/withholding
kind, order, and source location. It does not decide IVA acreditable/no acreditable/trasladado,
ISR retained for honorarios, payroll treatment, recoverability, capitalization, or DIOT.

Tax structure can later be evidence for classification, but a single tax row never establishes
normal supplier, honorarios, payroll, expense category, accounting account, or policy link.
Those layers require their own versioned rules, wider CFDI context, and provenance.

## 15. Related-CFDI, credit-note, and complement boundary

Each CFDI preserves its taxes exactly as represented. Egreso, substitutions, cancellations,
related-CFDI effects, payment complements, and local-tax complements remain separate fiscal
and semantic slices; they must not mutate or reinterpret base tax facts here.

## 16. Security and parser strategy

The future reader reuses Identity/Header/Concepts secure XML behavior: exact supported
namespace/version pairing, no local-name-only traversal, input/attribute/depth/element bounds,
DTD/entity/external-resource rejection, and typed malformed XML failures.

**Recommendation:** introduce an independently testable `CfdiTaxesReader` over immutable
evidence, sharing only a small internal safe XML traversal/version-resolution utility when a
future refactor can preserve accepted public readers. It avoids embedding taxes in
`ParsedCfdiConcept`, keeps aggregate taxes reachable, and avoids coupling tax semantics to the
Concepts parser. Re-parsing is acceptable until a shared traversal is concretely justified;
no refactor is authorized by this document.

## 17. Typed error strategy

Reuse fiscal parser errors where semantically accurate: `MissingRequiredFiscalAttribute`,
`EmptyFiscalAttribute`, `UnexpectedFiscalAttribute`, `InvalidFiscalDecimal`, unsupported
version/namespace errors, and secure XML errors. A future narrowly typed structural error may
be justified for factor-forbidden fields or invalid tax-container structure.

Errors identify version, concept index where applicable, tax kind/index, attribute, and safe
raw value. Generic database or accounting errors are not parser behavior.

## 18. Determinism and future fingerprinting

The future tax result exposes fingerprint schema/version separately as result metadata and
provenance, exactly as Header and Concepts do. Its canonical hashed payload must **not** embed
the schema literal unless all existing fiscal slices are intentionally redesigned together.

The canonical payload follows the established convention: CFDI version, source-container
presence where material, aggregate totals, and all ordered raw/parsed rows serialize
deterministically; a lowercase SHA-256 digest is computed from that payload. It must later
support historical identity `(evidence_id, parser_name, parser_version, configuration_hash)`
without overwriting prior results.

## 19. Persistence boundary

No tax persistence is designed or implemented here. Future concept-tax rows attach to the
immutable `cfdi_concept.id`. Aggregate rows will need a parent at the fiscal derived-result
level, but its exact FK/table design belongs to CFDI Taxes Persistence Design.

## 20. Future parser test plan

The parser checkpoint must test:

- 3.3 and 4.0: no taxes, transfers, withholdings, both, multiple concepts, and independent
  collections;
- `Tasa`, `Cuota`, and `Exento` transfer field presence; withholding requirements by matrix;
- 4.0 `ObjetoImp` parser facts plus separately versioned fiscal-validation fixtures for the
  frozen ownership matrix;
- raw trailing zeros, high precision within accepted lexical facets, explicit permitted zero,
  malformed decimals, and existing scientific-notation behavior;
- stable order and duplicate identical rows;
- aggregate rows, totals, node presence, and optional absence;
- exact version/namespace pairs, unsupported/mismatched versions, required/forbidden fields;
- existing secure XML limits and typed errors.

No PostgreSQL tests belong to parser implementation. Tax persistence gets a separate real
PostgreSQL test plan.

## 21. Source-evidence matrix

| Question | Official source | Evidence | Design consequence | Confidence |
| --- | --- | --- | --- | --- |
| Concept tax hierarchy | SAT 3.3/4.0 standards | Optional concept `Impuestos`; separate transfer/withholding collections | Separate ordered concept tax objects | High |
| Aggregate hierarchy | SAT 3.3/4.0 standards | Separate comprobante `Impuestos` summary | Separate aggregate objects | High |
| 3.3 concept Traslado | SAT CFDI 3.3 standard | Base/Impuesto/TipoFactor required; rate/amount conditional | Factor-aware concept parser matrix | High |
| 3.3 aggregate Traslado | SAT CFDI 3.3 standard | No Base; Impuesto/TipoFactor/TasaOCuota/Importe required | Separate 3.3 aggregate object and version-forbidden Base | High |
| 4.0 concept Traslado | SAT CFDI 4.0 standard | Base/Impuesto/TipoFactor required; rate/amount conditional | Factor-aware concept parser matrix | High |
| 4.0 aggregate Traslado | SAT CFDI 4.0 standard | Base/Impuesto/TipoFactor required; rate/amount conditional for Exento | Separate 4.0 aggregate object | High |
| Concept Retencion | SAT 3.3/4.0 standards | Base/Impuesto/TipoFactor/TasaOCuota/Importe required | Separate withholding parser matrix | High |
| Aggregate Retencion | SAT 3.3/4.0 standards | Exactly Impuesto/Importe; no Base/factor/rate | Compact aggregate withholding object | High |
| Exento | SAT 3.3/4.0 standards | Transfer rate/amount required only for Tasa/Cuota | Preserve absence, never fabricate zero | High |
| Aggregate totals | SAT 3.3/4.0 standards | Conditional `TotalImpuestosRetenidos`/`Trasladados` on Comprobante/Impuestos | Preserve source; no calculated replacement | High |
| ObjetoImp 01–08 ownership | SAT CFDI 4.0 standard, Factura FAQ, RMF 2026 | Required source attribute; current code meanings and some scenario guidance | Structural parser / fiscal validation / catalogue policy are separate | High |
| Fingerprint precedent | Existing accepted Header/Concepts implementation | Schema returned separately from hashed payload | Taxes follows same convention | High |

## 22. Open questions

1. Exact public domain type names and whether a common internal tax-row primitive is worthwhile.
2. Final representation of source-node presence when valid distinctions are material.
3. Exact fingerprint schema and parser/configuration identifiers.
4. Standalone reader versus a future shared internal XML traversal after a compatibility review.
5. Aggregate-tax persistence parent and immutable result/current model.
6. The dedicated arithmetic-validation layer, including official rounding/currency formulas.
7. Exact future SAT catalogue infrastructure, including acquisition and temporal-version
   lifecycle.

## 23. Acceptance criteria

This design is acceptable only if official SAT evidence is recorded; 3.3/4.0 matrices are
explicit; concept and aggregate facts, and transfers and withholdings, remain separate; factor
rules, raw-plus-Decimal semantics, order, and duplicates are explicit; current `ObjetoImp`
evidence is not reduced to an obsolete set; accounting/inference is excluded; the parser test
plan is concrete; and no parser or persistence implementation has started.
