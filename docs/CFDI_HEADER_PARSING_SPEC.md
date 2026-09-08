# AURUM — CFDI Header / Fiscal Core Parsing Specification

**Status:** Accepted
**Scope:** Derived fiscal-header parsing for CFDI 3.3 and 4.0

---

## 1. Purpose

Define the next CFDI Core vertical slice: deterministic extraction of the essential
fiscal header from immutable XML evidence. This is derived fiscal data, never a
replacement for the original XML. It can be regenerated from the exact evidence bytes.

## 2. Scope

Included: `Comprobante`, `Emisor`, and `Receptor` header attributes listed in this
document for CFDI 3.3 and 4.0. Excluded: concepts, taxes, transfers, retentions,
complements, payroll, INE, payments, Carta Porte, related CFDI, SAT status, SIF,
reconciliation, inference, risk, endpoints, and persistence implementation.

## 3. Definitions

For every extracted field, distinguish these representations:

* **original XML evidence:** immutable byte-perfect `xml_evidence.content`, the only
  source for original quotes, entity references, encoding, and byte representation;
* **source attribute value:** value delivered by the XML parser before domain
  normalization. It preserves observed casing and normally the delivered decimal form,
  but does not promise original quotes, entity references, encoding, or bytes;
* **parsed value:** typed value used by the domain;
* **canonical value:** domain-normalized representation only where an explicit rule
  exists.

Absent, present-empty, and invalid are different states. A required absent or empty value
is a typed parsing error; an optional absent value is absent; an optional empty value is
preserved as raw empty and rejected when its field semantics prohibit it.

## 4. Relationship to `CfdiIdentity`

`CfdiIdentity` remains the sole source of fiscal identity, obtained only from the exact
SAT Timbre. `CfdiFiscalHeader` does not contain the UUID. A future derived-data record
references the persistent identity/evidence association, but the pure domain header is
independent of infrastructure IDs. Consumers combine identity and header at application
boundaries when needed.

## 5. Domain model

Use composition, not a flat DTO:

```text
CfdiFiscalHeader
 ├─ version: CfdiVersion
 ├─ comprobante: ComprobanteHeader
 ├─ issuer: FiscalPartySnapshot
 └─ receiver: ReceiverFiscalSnapshot
```

`ComprobanteHeader` contains version, date, document type, series/folio, currency,
exchange rate, amounts, payment attributes, and version-applicable fields.
`FiscalPartySnapshot` contains RFC, source name, and fiscal-regime code. The receiver
specialization additionally contains fiscal domicile and CFDI-use code. They are
snapshots, not a global Party/Supplier reference: names, regimes, and domiciles are
historical facts represented by the XML.

## 6. Version strategy and namespaces

Use a small `CfdiFiscalHeaderReader` facade with a registry of version-specific readers
keyed by an explicit `CfdiVersion`. Each reader owns one declarative field schema and XSD
structural rules; application code consumes only the version-neutral model. This
prevents dispersed `if version` branches and allows a future version to register another
reader without rewriting the core.

The root must be exactly:

| Version | Required Comprobante namespace |
| --- | --- |
| 3.3 | `http://www.sat.gob.mx/cfd/3` |
| 4.0 | `http://www.sat.gob.mx/cfd/4` |

The reader identifies the root by expanded XML name, never local-name alone. It reads
`Version` from that root, rejects unsupported versions, rejects an unrecognized root
namespace, and raises a distinct mismatch error when a supported `Version` is declared
under the other supported namespace.

Validation is intentionally layered:

```text
XML security / well-formedness
        ↓
CFDI structural parsing
(namespace, version, required XSD attributes, lexical types)
        ↓
Fiscal/business validation
(catalog membership, conditional rules, cross-field rules)
```

This slice centers on the first two layers. Fiscal/business validation is a later,
explicit layer; version readers must not accumulate all tributary and catalogue rules.

## 7. Header matrix

XSD structural validity and fiscal/business applicability are separate. `required` and
`optional` below describe XSD use; `conditional` appears only in business applicability.
The latter is not parser rejection in this slice.

| Field | 3.3 XSD use | 4.0 XSD use | Business applicability | Parsed type | Notes |
| --- | --- | --- | --- | --- | --- |
| Comprobante/Version | required | required | always | `CfdiVersion` | selects reader |
| Fecha | required | required | always | naive `datetime` | no offset assumed |
| TipoDeComprobante | required | required | always | code string | catalogue deferred |
| Serie / Folio | optional | optional | context-dependent; detailed fiscal applicability deferred | exact string | never integer/trimmed |
| Moneda | required | required | always | code string | catalogue deferred |
| TipoCambio | optional | optional | conditional | `Decimal` | currency rule deferred |
| SubTotal / Total | required | required | always | `Decimal` | no ingestion rounding |
| Descuento | optional | optional | conditional | `Decimal` | absent differs from zero |
| Exportacion | absent | required | always in 4.0 | code string | 4.0-only |
| LugarExpedicion | required | required | always | code string | catalogue deferred |
| MetodoPago / FormaPago | optional | optional | conditional | code string | rule deferred |
| CondicionesDePago / Confirmacion | optional | optional | conditional | exact string | no interpretation |
| Emisor/Rfc / RegimenFiscal | required | required | always | RFC / code | catalogue deferred |
| Emisor/Nombre | optional | required | no additional rule in this slice | exact string | corrected XSD use |
| Receptor/Rfc | required | required | always | `FiscalRfc` | canonical uppercase |
| Receptor/Nombre | optional | required | no additional rule in this slice | exact string | snapshot |
| DomicilioFiscalReceptor | absent | required | always in 4.0 | code string | 4.0-only |
| RegimenFiscalReceptor | absent | required | always in 4.0 | code string | 4.0-only |
| UsoCFDI | required | required | always | code string | catalogue deferred |

## 8. Decimal and date semantics

Amounts and `TipoCambio` retain source attribute value and parse with `Decimal`; floats
are prohibited. `Decimal("100.00")` can preserve scale/exponent from the string passed to
its constructor, but byte/lexical proof remains the original XML evidence. Ingestion
applies neither quantization nor business rounding. Decimal equality never proves lexical
equality.

`Fecha` retains source attribute value and parses to a timezone-naive `datetime`. CFDI normally
expresses local issuance time without an offset; AURUM must not invent a zone or convert
it to UTC. Offset-bearing lexical input is invalid for this header model unless the
applicable SAT version artefact explicitly permits it.

## 9. RFC and SAT codes

`FiscalRfc` preserves source value and derives uppercase canonical form. It performs only
lexical validation based on the SAT grammar/type for the supported version, including SAT
generic RFCs `XAXX010101000` and `XEXX010101000`. It does not consult existence,
situation, certificates, or SAT services. The exact grammar must be confirmed from SAT
technical artefacts before implementation; no project-local regex is specified here.

SAT catalogue fields are small typed code value objects or validated code strings with
source-value preservation. Their syntax is checked only where unambiguous (non-empty and
field-local lexical form). Catalogue membership is deliberately deferred: embedding large
and versioned SAT catalogues would make this parser non-deterministic without a catalogue
version policy.

## 10. Raw versus canonical rules

| Group | Source attribute value | Parsed | Canonical |
| --- | --- | --- | --- |
| RFC | parser-delivered value | `FiscalRfc` | uppercase for equality/display |
| Decimal | parser-delivered value | `Decimal` | no automatic rescale |
| Fecha | parser-delivered value | naive `datetime` | none; source value for display |
| Series, folio, names, conditions, confirmation | parser-delivered value | string | none; no trim/case folding |
| SAT codes | parser-delivered value | code string/value object | only an explicit SAT lexical rule |

Original XML evidence is consulted for byte-perfect forensic comparison.

## 11. Typed errors

The reader distinguishes technical XML failure from fiscal-header failure:

* `UnsupportedCfdiVersion`
* `InvalidCfdiNamespace`
* `VersionNamespaceMismatch`
* `MissingRequiredFiscalAttribute`
* `EmptyFiscalAttribute`
* `InvalidFiscalDecimal`
* `InvalidFiscalDate`
* `InvalidFiscalCode`
* `InvalidRfc`
* existing malformed/unsafe XML errors from the secure XML layer

## 12. Parser contract and XML security

Conceptually:

```text
CfdiFiscalHeaderReader.read(evidence: XmlEvidence) -> CfdiFiscalHeader
```

Accepting `XmlEvidence` makes derivation explicitly tied to exact, already-hashed bytes
without recalculating identity. The reader may consume `evidence.original_xml` internally.
It never extracts UUID identity and does not replace the identity reader.

It must use the same secure XML policy as identity ingestion: defused parsing (no DTD,
entities, external entities, or network resolution), total-byte limit before parsing, and
depth, element, and attribute-byte limits during processing. The eventual implementation
should reuse or factor a common secure scan/parser primitive; it must not create a second,
weaker XML security policy.

## 13. Reprocessing, idempotency, and future persistence

Conceptually persist derived parsing provenance with the evidence reference, parser name,
parser implementation version, and `parsed_at`. Reprocessing creates a new derived
result for the same immutable evidence rather than mutating it.

Two versions are independent: `CfdiVersion` identifies the CFDI schema (`3.3` or `4.0`),
while an AURUM parser implementation version identifies logic (for example,
`header-parser/1`). The same CFDI 4.0 can be processed by `header-parser/1` and later
`header-parser/2` without changing its `CfdiVersion`.

For fixed evidence bytes, supported parser version, and fixed parser configuration, output
must be deterministic: same source values, parsed values, canonical values, and typed error.
No current table is designed here. A later persistence specification should decide whether
to retain only the latest successful result, an append-only result history, and how parser
failures are recorded.

## 14. Test strategy and acceptance criteria

Future tests must include valid 3.3/4.0 fixtures; exact namespace/version mismatch;
unsupported version; required/absent/empty attributes; malformed decimal/date/RFC; decimal
scale preservation; raw/canonical RFC; 3.3 absence and 4.0 presence of receiver/export
fields; deterministic reprocessing; and all secure XML limits inherited from identity.

Acceptance requires no mutation of XML evidence, no UUID duplication as header truth,
strict root namespace validation, no float use, no automatic rounding, version rules kept
inside version readers, and no concepts/taxes/complements entering the model.

## 15. Open decisions

* Verify exact 3.3/4.0 XSD cardinalities and conditional rules against selected SAT
  artefacts before implementation, especially names and payment/currency conditions.
* Confirm the exact RFC lexical grammar from SAT artefacts; generic RFC treatment is
  specified but implementation details remain to be verified.
* Select parser-name/version format and derived-result retention policy in the persistence
  increment.
