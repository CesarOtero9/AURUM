from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256

from aurum.domain.cfdi_header import CfdiVersion

FINGERPRINT_SCHEMA = "cfdi-concepts-fingerprint/1"
PARSER_NAME = "cfdi-concepts"
PARSER_VERSION = "concepts-parser/1"


@dataclass(frozen=True, slots=True)
class ParsedCfdiConcept:
    concept_index: int
    clave_prod_serv_raw: str
    no_identificacion_raw: str | None
    cantidad_raw: str
    cantidad: Decimal
    clave_unidad_raw: str
    unidad_raw: str | None
    descripcion_raw: str
    valor_unitario_raw: str
    valor_unitario: Decimal
    importe_raw: str
    importe: Decimal
    descuento_raw: str | None
    descuento: Decimal | None
    objeto_imp_raw: str | None


@dataclass(frozen=True, slots=True)
class ParsedCfdiConcepts:
    version: CfdiVersion
    concepts: tuple[ParsedCfdiConcept, ...]


def _decimal_payload(raw: str | None, value: Decimal | None) -> dict[str, str] | None:
    return None if raw is None else {"source": raw, "parsed": str(value)}


def canonical_fingerprint_payload(concepts: ParsedCfdiConcepts) -> dict[str, object]:
    return {
        "version": concepts.version.value,
        "concept_count": len(concepts.concepts),
        "concepts": [
            {
                "concept_index": concept.concept_index,
                "clave_prod_serv_raw": concept.clave_prod_serv_raw,
                "no_identificacion_raw": concept.no_identificacion_raw,
                "cantidad": _decimal_payload(concept.cantidad_raw, concept.cantidad),
                "clave_unidad_raw": concept.clave_unidad_raw,
                "unidad_raw": concept.unidad_raw,
                "descripcion_raw": concept.descripcion_raw,
                "valor_unitario": _decimal_payload(
                    concept.valor_unitario_raw, concept.valor_unitario
                ),
                "importe": _decimal_payload(concept.importe_raw, concept.importe),
                "descuento": _decimal_payload(concept.descuento_raw, concept.descuento),
                "objeto_imp_raw": concept.objeto_imp_raw,
            }
            for concept in concepts.concepts
        ],
    }


def fingerprint(concepts: ParsedCfdiConcepts) -> tuple[str, str]:
    encoded = json.dumps(
        canonical_fingerprint_payload(concepts),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return FINGERPRINT_SCHEMA, sha256(encoded).hexdigest()
