from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256

from aurum.domain.cfdi_header import CfdiVersion

FINGERPRINT_SCHEMA = "cfdi-taxes-fingerprint/1"
PARSER_NAME = "cfdi-taxes"
PARSER_VERSION = "taxes-parser/1"


@dataclass(frozen=True, slots=True)
class ParsedCfdiConceptTransfer:
    transfer_index: int
    base_raw: str
    base: Decimal
    impuesto_raw: str
    tipo_factor_raw: str
    tasa_o_cuota_raw: str | None
    tasa_o_cuota: Decimal | None
    importe_raw: str | None
    importe: Decimal | None


@dataclass(frozen=True, slots=True)
class ParsedCfdiConceptWithholding:
    withholding_index: int
    base_raw: str
    base: Decimal
    impuesto_raw: str
    tipo_factor_raw: str
    tasa_o_cuota_raw: str
    tasa_o_cuota: Decimal
    importe_raw: str
    importe: Decimal


@dataclass(frozen=True, slots=True)
class ParsedCfdiConceptTaxes:
    concept_index: int
    impuestos_present: bool
    transfers: tuple[ParsedCfdiConceptTransfer, ...]
    withholdings: tuple[ParsedCfdiConceptWithholding, ...]


@dataclass(frozen=True, slots=True)
class ParsedCfdiAggregateTransfer:
    aggregate_transfer_index: int
    base_raw: str | None
    base: Decimal | None
    impuesto_raw: str
    tipo_factor_raw: str
    tasa_o_cuota_raw: str | None
    tasa_o_cuota: Decimal | None
    importe_raw: str | None
    importe: Decimal | None


@dataclass(frozen=True, slots=True)
class ParsedCfdiAggregateWithholding:
    aggregate_withholding_index: int
    impuesto_raw: str
    importe_raw: str
    importe: Decimal


@dataclass(frozen=True, slots=True)
class ParsedCfdiAggregateTaxes:
    impuestos_present: bool
    total_trasladados_raw: str | None
    total_trasladados: Decimal | None
    total_retenidos_raw: str | None
    total_retenidos: Decimal | None
    transfers: tuple[ParsedCfdiAggregateTransfer, ...]
    withholdings: tuple[ParsedCfdiAggregateWithholding, ...]


@dataclass(frozen=True, slots=True)
class ParsedCfdiTaxes:
    version: CfdiVersion
    concept_taxes: tuple[ParsedCfdiConceptTaxes, ...]
    aggregate_taxes: ParsedCfdiAggregateTaxes


def _decimal_payload(raw: str | None, value: Decimal | None) -> dict[str, str] | None:
    return None if raw is None else {"source": raw, "parsed": str(value)}


def canonical_fingerprint_payload(taxes: ParsedCfdiTaxes) -> dict[str, object]:
    def transfer_payload(item: ParsedCfdiConceptTransfer) -> dict[str, object]:
        return {
            "transfer_index": item.transfer_index,
            "base": _decimal_payload(item.base_raw, item.base),
            "impuesto_raw": item.impuesto_raw,
            "tipo_factor_raw": item.tipo_factor_raw,
            "tasa_o_cuota": _decimal_payload(item.tasa_o_cuota_raw, item.tasa_o_cuota),
            "importe": _decimal_payload(item.importe_raw, item.importe),
        }

    def withholding_payload(item: ParsedCfdiConceptWithholding) -> dict[str, object]:
        return {
            "withholding_index": item.withholding_index,
            "base": _decimal_payload(item.base_raw, item.base),
            "impuesto_raw": item.impuesto_raw,
            "tipo_factor_raw": item.tipo_factor_raw,
            "tasa_o_cuota": _decimal_payload(item.tasa_o_cuota_raw, item.tasa_o_cuota),
            "importe": _decimal_payload(item.importe_raw, item.importe),
        }

    aggregate = taxes.aggregate_taxes
    return {
        "version": taxes.version.value,
        "concept_taxes": [
            {
                "concept_index": item.concept_index,
                "impuestos_present": item.impuestos_present,
                "transfers": [transfer_payload(value) for value in item.transfers],
                "withholdings": [withholding_payload(value) for value in item.withholdings],
            }
            for item in taxes.concept_taxes
        ],
        "aggregate_taxes": {
            "impuestos_present": aggregate.impuestos_present,
            "total_trasladados": _decimal_payload(
                aggregate.total_trasladados_raw, aggregate.total_trasladados
            ),
            "total_retenidos": _decimal_payload(
                aggregate.total_retenidos_raw, aggregate.total_retenidos
            ),
            "transfers": [
                {
                    "aggregate_transfer_index": item.aggregate_transfer_index,
                    "base": _decimal_payload(item.base_raw, item.base),
                    "impuesto_raw": item.impuesto_raw,
                    "tipo_factor_raw": item.tipo_factor_raw,
                    "tasa_o_cuota": _decimal_payload(item.tasa_o_cuota_raw, item.tasa_o_cuota),
                    "importe": _decimal_payload(item.importe_raw, item.importe),
                }
                for item in aggregate.transfers
            ],
            "withholdings": [
                {
                    "aggregate_withholding_index": item.aggregate_withholding_index,
                    "impuesto_raw": item.impuesto_raw,
                    "importe": _decimal_payload(item.importe_raw, item.importe),
                }
                for item in aggregate.withholdings
            ],
        },
    }


def fingerprint(taxes: ParsedCfdiTaxes) -> tuple[str, str]:
    encoded = json.dumps(
        canonical_fingerprint_payload(taxes),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return FINGERPRINT_SCHEMA, sha256(encoded).hexdigest()
