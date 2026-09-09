from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from hashlib import sha256
from re import fullmatch

RFC_PATTERN = r"[A-Z&Ñ]{3,4}[0-9]{6}[A-Z0-9]{3}"
DATE_PATTERN = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
DECIMAL_PATTERN = r"[0-9]+(?:\.[0-9]+)?"
FINGERPRINT_SCHEMA = "cfdi-header-fingerprint/1"
PARSER_NAME = "cfdi-header"
PARSER_VERSION = "header-parser/1"


class CfdiHeaderError(Exception):
    pass


class UnsupportedCfdiVersion(CfdiHeaderError):
    pass


class InvalidCfdiNamespace(CfdiHeaderError):
    pass


class InvalidCfdiRoot(CfdiHeaderError):
    pass


class VersionNamespaceMismatch(CfdiHeaderError):
    pass


class MissingRequiredFiscalAttribute(CfdiHeaderError):
    pass


class EmptyFiscalAttribute(CfdiHeaderError):
    pass


class UnexpectedFiscalAttribute(CfdiHeaderError):
    pass


class InvalidFiscalDecimal(CfdiHeaderError):
    pass


class InvalidFiscalDate(CfdiHeaderError):
    pass


class InvalidFiscalCode(CfdiHeaderError):
    pass


class InvalidRfc(CfdiHeaderError):
    pass


class CfdiVersion(StrEnum):
    CFDI_33 = "3.3"
    CFDI_40 = "4.0"


@dataclass(frozen=True, slots=True)
class FiscalRfc:
    source: str
    canonical: str

    @classmethod
    def from_source(cls, source: str) -> FiscalRfc:
        canonical = source.upper()
        if fullmatch(RFC_PATTERN, canonical) is None:
            raise InvalidRfc("RFC has an unsupported bounded SAT lexical form")
        return cls(source, canonical)


@dataclass(frozen=True, slots=True)
class FiscalDecimal:
    source: str
    value: Decimal

    @classmethod
    def from_source(cls, source: str) -> FiscalDecimal:
        if fullmatch(DECIMAL_PATTERN, source) is None:
            raise InvalidFiscalDecimal("Fiscal decimal has an invalid lexical form")
        try:
            return cls(source, Decimal(source))
        except InvalidOperation as error:
            raise InvalidFiscalDecimal("Invalid fiscal decimal") from error


@dataclass(frozen=True, slots=True)
class FiscalDate:
    source: str
    value: datetime

    @classmethod
    def from_source(cls, source: str) -> FiscalDate:
        # CFDI header /1 supports the XSD-style second-precision lexical form only.
        if fullmatch(DATE_PATTERN, source) is None:
            raise InvalidFiscalDate("Fecha must be YYYY-MM-DDTHH:MM:SS")
        try:
            return cls(source, datetime.strptime(source, "%Y-%m-%dT%H:%M:%S"))
        except ValueError as error:
            raise InvalidFiscalDate("Invalid CFDI Fecha") from error


@dataclass(frozen=True, slots=True)
class ComprobanteHeader:
    fecha: FiscalDate
    tipo_comprobante: str
    serie: str | None
    folio: str | None
    moneda: str
    tipo_cambio: FiscalDecimal | None
    subtotal: FiscalDecimal
    descuento: FiscalDecimal | None
    total: FiscalDecimal
    exportacion: str | None
    lugar_expedicion: str
    metodo_pago: str | None
    forma_pago: str | None
    condiciones_pago: str | None
    confirmacion: str | None


@dataclass(frozen=True, slots=True)
class FiscalPartySnapshot:
    rfc: FiscalRfc
    nombre: str | None
    regimen_fiscal: str


@dataclass(frozen=True, slots=True)
class ReceiverFiscalSnapshot:
    rfc: FiscalRfc
    nombre: str | None
    domicilio_fiscal_receptor: str | None
    regimen_fiscal_receptor: str | None
    uso_cfdi: str


@dataclass(frozen=True, slots=True)
class CfdiFiscalHeader:
    version: CfdiVersion
    comprobante: ComprobanteHeader
    issuer: FiscalPartySnapshot
    receiver: ReceiverFiscalSnapshot


def _decimal_payload(value: FiscalDecimal | None) -> dict[str, str] | None:
    return None if value is None else {"source": value.source, "parsed": str(value.value)}


def canonical_fingerprint_payload(header: CfdiFiscalHeader) -> dict[str, object]:
    c = header.comprobante
    return {
        "version": header.version.value,
        "comprobante": {
            "fecha_source": c.fecha.source,
            "fecha_parsed": c.fecha.value.isoformat(),
            "tipo_comprobante": c.tipo_comprobante,
            "serie": c.serie,
            "folio": c.folio,
            "moneda": c.moneda,
            "tipo_cambio": _decimal_payload(c.tipo_cambio),
            "subtotal": _decimal_payload(c.subtotal),
            "descuento": _decimal_payload(c.descuento),
            "total": _decimal_payload(c.total),
            "exportacion": c.exportacion,
            "lugar_expedicion": c.lugar_expedicion,
            "metodo_pago": c.metodo_pago,
            "forma_pago": c.forma_pago,
            "condiciones_pago": c.condiciones_pago,
            "confirmacion": c.confirmacion,
        },
        "issuer": {
            "rfc_source": header.issuer.rfc.source,
            "rfc_canonical": header.issuer.rfc.canonical,
            "nombre": header.issuer.nombre,
            "regimen_fiscal": header.issuer.regimen_fiscal,
        },
        "receiver": {
            "rfc_source": header.receiver.rfc.source,
            "rfc_canonical": header.receiver.rfc.canonical,
            "nombre": header.receiver.nombre,
            "domicilio_fiscal_receptor": header.receiver.domicilio_fiscal_receptor,
            "regimen_fiscal_receptor": header.receiver.regimen_fiscal_receptor,
            "uso_cfdi": header.receiver.uso_cfdi,
        },
    }


def fingerprint(header: CfdiFiscalHeader) -> tuple[str, str]:
    encoded = json.dumps(
        canonical_fingerprint_payload(header),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return FINGERPRINT_SCHEMA, sha256(encoded).hexdigest()
