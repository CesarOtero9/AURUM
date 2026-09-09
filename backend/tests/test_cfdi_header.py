from __future__ import annotations

from decimal import Decimal

import pytest

from aurum.domain.cfdi_header import (
    FINGERPRINT_SCHEMA,
    PARSER_NAME,
    PARSER_VERSION,
    EmptyFiscalAttribute,
    FiscalDate,
    FiscalDecimal,
    FiscalRfc,
    InvalidCfdiNamespace,
    InvalidCfdiRoot,
    InvalidFiscalDate,
    InvalidFiscalDecimal,
    InvalidRfc,
    MissingRequiredFiscalAttribute,
    UnexpectedFiscalAttribute,
    UnsupportedCfdiVersion,
    VersionNamespaceMismatch,
    fingerprint,
)
from aurum.domain.cfdi_identity import MalformedXml, OriginalXml, XmlEvidence, XmlInputTooLarge
from aurum.infrastructure.xml_cfdi_header_reader import CfdiFiscalHeaderReader

NS33 = "http://www.sat.gob.mx/cfd/3"
NS40 = "http://www.sat.gob.mx/cfd/4"


def attrs(values: dict[str, str]) -> str:
    return " ".join(f'{key}="{value}"' for key, value in values.items())


def xml(
    version: str = "4.0",
    namespace: str | None = None,
    root: str = "Comprobante",
    remove: tuple[str, str] | None = None,
    empty: tuple[str, str] | None = None,
    add: tuple[str, str, str] | None = None,
    issuer_tag: str = "cfdi:Emisor",
    receiver_tag: str = "cfdi:Receptor",
) -> bytes:
    namespace = namespace or (NS40 if version == "4.0" else NS33)
    comp = {
        "Version": version,
        "Fecha": "2024-02-29T23:59:59",
        "TipoDeComprobante": "I",
        "Serie": "A",
        "Folio": "000123",
        "Moneda": "MXN",
        "TipoCambio": "1.0",
        "SubTotal": "100.00",
        "Descuento": "0.00",
        "Total": "100.00",
        "LugarExpedicion": "01000",
        "MetodoPago": "PUE",
        "FormaPago": "01",
        "CondicionesDePago": "credito",
        "Confirmacion": "ABC123",
    }
    issuer = {"Rfc": "aaa010101aaa", "Nombre": "Emisor", "RegimenFiscal": "601"}
    receiver = {"Rfc": "XAXX010101000", "Nombre": "Receptor", "UsoCFDI": "G03"}
    if version == "4.0":
        comp["Exportacion"] = "01"
        receiver.update({"DomicilioFiscalReceptor": "01000", "RegimenFiscalReceptor": "601"})
    groups = {"comp": comp, "issuer": issuer, "receiver": receiver}
    if remove:
        groups[remove[0]].pop(remove[1], None)
    if empty and empty[1] in groups[empty[0]]:
        groups[empty[0]][empty[1]] = ""
    if add:
        groups[add[0]][add[1]] = add[2]
    wrong_ns = (
        ' xmlns:x="urn:wrong"'
        if issuer_tag.startswith("x:") or receiver_tag.startswith("x:")
        else ""
    )
    return (
        f'<cfdi:{root} xmlns:cfdi="{namespace}"{wrong_ns} {attrs(comp)}>'
        f"<{issuer_tag} {attrs(issuer)}/>"
        f"<{receiver_tag} {attrs(receiver)}/>"
        f"</cfdi:{root}>"
    ).encode()


def read(content: bytes, **limits: int):
    return CfdiFiscalHeaderReader(**limits).read(
        XmlEvidence.from_original_xml(OriginalXml(content))
    )


def field_value(header, group: str, name: str):
    return getattr(getattr(header, group), name)


@pytest.mark.parametrize(
    "source,canonical",
    [
        ("AAA010101AAA", "AAA010101AAA"),
        ("aaa010101aaa", "AAA010101AAA"),
        ("ABCD010101ABC", "ABCD010101ABC"),
        ("XAXX010101000", "XAXX010101000"),
        ("XEXX010101000", "XEXX010101000"),
        ("ÑAAA010101AA1", "ÑAAA010101AA1"),
        ("&AAB010101AA1", "&AAB010101AA1"),
    ],
)
def test_rfc_valid(source: str, canonical: str) -> None:
    rfc = FiscalRfc.from_source(source)
    assert (rfc.source, rfc.canonical) == (source, canonical)


@pytest.mark.parametrize(
    "source", ["", "AAA 010101AAA", "AAA010101AA", "ABC-010101AA1", "ØAA010101AAA", "AAA010101AA!"]
)
def test_rfc_invalid(source: str) -> None:
    with pytest.raises(InvalidRfc):
        FiscalRfc.from_source(source)


@pytest.mark.parametrize("source", ["0", "0.00", "1", "100", "100.0", "100.00", "123456789.123456"])
def test_decimal_valid(source: str) -> None:
    value = FiscalDecimal.from_source(source)
    assert value.source == source
    assert value.value == Decimal(source)


def test_decimal_scale_is_preserved() -> None:
    assert FiscalDecimal.from_source("100.00").value.as_tuple().exponent == -2


@pytest.mark.parametrize(
    "source", ["", " 100", "100 ", "+100", "-100", ".5", "5.", "1E2", "1e2", "NaN", "Infinity"]
)
def test_decimal_invalid(source: str) -> None:
    with pytest.raises(InvalidFiscalDecimal):
        FiscalDecimal.from_source(source)


@pytest.mark.parametrize("source", ["2024-01-01T00:00:00", "2024-02-29T23:59:59"])
def test_date_valid_naive(source: str) -> None:
    assert FiscalDate.from_source(source).value.tzinfo is None


@pytest.mark.parametrize(
    "source",
    [
        "2024-01-01",
        "2024-01-01 12:00:00",
        "2024-01-01T12:00",
        "2024-01-01T12:00:00Z",
        "2024-01-01T12:00:00+00:00",
        "2024-01-01T12:00:00-06:00",
        "2024-02-30T12:00:00",
        "2024-13-01T12:00:00",
    ],
)
def test_date_invalid(source: str) -> None:
    with pytest.raises(InvalidFiscalDate):
        FiscalDate.from_source(source)


def test_valid_33_complete_and_minimal() -> None:
    full = read(xml("3.3"))
    minimal = read(xml("3.3", remove=("issuer", "Nombre")))
    minimal_receiver = read(xml("3.3", remove=("receiver", "Nombre")))
    assert full.comprobante.folio == "000123"
    assert full.comprobante.total.value == Decimal("100.00")
    assert full.comprobante.exportacion is None
    assert full.receiver.domicilio_fiscal_receptor is None
    assert minimal.issuer.nombre is None
    assert minimal_receiver.receiver.nombre is None


def test_valid_40_complete() -> None:
    header = read(xml())
    assert header.comprobante.exportacion == "01"
    assert header.issuer.nombre == "Emisor"
    assert header.receiver.nombre == "Receptor"
    assert header.receiver.domicilio_fiscal_receptor == "01000"
    assert header.receiver.regimen_fiscal_receptor == "601"


@pytest.mark.parametrize(
    "group,name",
    [
        ("comp", name)
        for name in [
            "Version",
            "Fecha",
            "TipoDeComprobante",
            "Moneda",
            "SubTotal",
            "Total",
            "LugarExpedicion",
        ]
    ]
    + [("issuer", name) for name in ["Rfc", "RegimenFiscal"]]
    + [("receiver", name) for name in ["Rfc", "UsoCFDI"]]
    + [
        ("comp", "Exportacion"),
        ("issuer", "Nombre"),
        ("receiver", "Nombre"),
        ("receiver", "DomicilioFiscalReceptor"),
        ("receiver", "RegimenFiscalReceptor"),
    ],
)
def test_required_attributes_missing(group: str, name: str) -> None:
    with pytest.raises(MissingRequiredFiscalAttribute):
        read(xml(remove=(group, name)))


@pytest.mark.parametrize(
    "group,name",
    [
        ("comp", name)
        for name in [
            "Version",
            "Fecha",
            "TipoDeComprobante",
            "Moneda",
            "SubTotal",
            "Total",
            "LugarExpedicion",
            "Exportacion",
        ]
    ]
    + [("issuer", name) for name in ["Rfc", "RegimenFiscal", "Nombre"]]
    + [
        ("receiver", name)
        for name in [
            "Rfc",
            "UsoCFDI",
            "Nombre",
            "DomicilioFiscalReceptor",
            "RegimenFiscalReceptor",
        ]
    ],
)
def test_required_attributes_empty(group: str, name: str) -> None:
    with pytest.raises(EmptyFiscalAttribute):
        read(xml(empty=(group, name)))


@pytest.mark.parametrize(
    "xml_name,field",
    [
        ("Serie", "serie"),
        ("Folio", "folio"),
        ("TipoCambio", "tipo_cambio"),
        ("Descuento", "descuento"),
        ("MetodoPago", "metodo_pago"),
        ("FormaPago", "forma_pago"),
        ("CondicionesDePago", "condiciones_pago"),
        ("Confirmacion", "confirmacion"),
    ],
)
def test_optional_comprobante_attributes_absent(xml_name: str, field: str) -> None:
    assert field_value(read(xml(remove=("comp", xml_name))), "comprobante", field) is None


@pytest.mark.parametrize(
    "group,field",
    [("issuer", "nombre"), ("receiver", "nombre")],
)
def test_optional_33_party_names_absent(group: str, field: str) -> None:
    assert field_value(read(xml("3.3", remove=(group, "Nombre"))), group, field) is None


@pytest.mark.parametrize(
    "group,name",
    [
        ("comp", name)
        for name in [
            "Serie",
            "Folio",
            "TipoCambio",
            "Descuento",
            "MetodoPago",
            "FormaPago",
            "CondicionesDePago",
            "Confirmacion",
        ]
    ]
    + [("issuer", "Nombre"), ("receiver", "Nombre")],
)
def test_present_empty_optional_attribute_is_not_silently_absent(
    group: str,
    name: str,
) -> None:
    version = "3.3" if group != "comp" else "4.0"
    with pytest.raises(EmptyFiscalAttribute):
        read(xml(version, empty=(group, name)))


@pytest.mark.parametrize("version,namespace", [("3.3", NS33), ("4.0", NS40)])
def test_matching_namespace_version(version: str, namespace: str) -> None:
    assert read(xml(version, namespace)).version.value == version


@pytest.mark.parametrize("version,namespace", [("4.0", NS33), ("3.3", NS40)])
def test_namespace_version_mismatch(version: str, namespace: str) -> None:
    with pytest.raises(VersionNamespaceMismatch):
        read(xml(version, namespace))


def test_namespace_version_root_errors() -> None:
    with pytest.raises(UnsupportedCfdiVersion):
        read(xml("5.0", NS40))
    with pytest.raises(InvalidCfdiNamespace):
        read(xml(namespace="urn:unknown"))
    with pytest.raises(InvalidCfdiRoot):
        read(xml(root="Foo"))
    with pytest.raises(MissingRequiredFiscalAttribute):
        read(xml(remove=("comp", "Version")))
    with pytest.raises(EmptyFiscalAttribute):
        read(xml(empty=("comp", "Version")))


@pytest.mark.parametrize(
    "group,name,value",
    [
        ("comp", "Exportacion", "01"),
        ("receiver", "DomicilioFiscalReceptor", "01000"),
        ("receiver", "RegimenFiscalReceptor", "601"),
    ],
)
def test_33_rejects_40_only_attributes(group: str, name: str, value: str) -> None:
    with pytest.raises(UnexpectedFiscalAttribute):
        read(xml("3.3", add=(group, name, value)))


@pytest.mark.parametrize(
    "issuer_tag,receiver_tag", [("x:Emisor", "cfdi:Receptor"), ("cfdi:Emisor", "x:Receptor")]
)
def test_wrong_namespace_parties_are_missing(issuer_tag: str, receiver_tag: str) -> None:
    with pytest.raises(MissingRequiredFiscalAttribute):
        read(xml(issuer_tag=issuer_tag, receiver_tag=receiver_tag))


@pytest.mark.parametrize("party", ["Emisor", "Receptor"])
def test_absent_required_party_is_typed(party: str) -> None:
    content = xml().replace(f"<cfdi:{party}".encode(), b"<cfdi:Other", 1)
    with pytest.raises(MissingRequiredFiscalAttribute):
        read(content)


def test_metadata_and_fingerprint_contract() -> None:
    header = read(xml())
    schema, digest = fingerprint(header)
    assert FINGERPRINT_SCHEMA == "cfdi-header-fingerprint/1"
    assert (PARSER_NAME, PARSER_VERSION, schema) == (
        "cfdi-header",
        "header-parser/1",
        "cfdi-header-fingerprint/1",
    )
    assert len(digest) == 64 and set(digest) <= set("0123456789abcdef")
    assert fingerprint(header) == fingerprint(read(xml()))


@pytest.mark.parametrize(
    "old,new",
    [
        (b"100.00", b"100.0"),
        (b'Serie="A"', b'Serie="B"'),
        (b'Nombre="Emisor"', b'Nombre="Otro"'),
        (b'UsoCFDI="G03"', b'UsoCFDI="S01"'),
        (b"aaa010101aaa", b"AAA010101AAA"),
    ],
)
def test_fingerprint_changes_for_source_relevant_fields(old: bytes, new: bytes) -> None:
    assert fingerprint(read(xml()))[1] != fingerprint(read(xml().replace(old, new, 1)))[1]


def test_reader_surfaces_invalid_rfc() -> None:
    with pytest.raises(InvalidRfc):
        read(xml(add=("issuer", "Rfc", "invalid")))


def test_reader_surfaces_invalid_fecha() -> None:
    with pytest.raises(InvalidFiscalDate):
        read(xml(add=("comp", "Fecha", "2024-02-30T00:00:00")))


def test_reader_surfaces_invalid_decimal() -> None:
    with pytest.raises(InvalidFiscalDecimal):
        read(xml(add=("comp", "SubTotal", "1E2")))


def test_xml_security_limits() -> None:
    with pytest.raises(XmlInputTooLarge):
        read(xml(), max_input_bytes=1)
    with pytest.raises(MalformedXml):
        read(b"<!DOCTYPE x []>" + xml())
    with pytest.raises(MalformedXml):
        read(b'<!DOCTYPE x [<!ENTITY x "a">]>' + xml())
    with pytest.raises(MalformedXml):
        read(b'<!DOCTYPE x [<!ENTITY x SYSTEM "file:///x">]>' + xml())
    deep = (
        xml()
        .replace(b"<cfdi:Emisor", b"<a><b><cfdi:Emisor")
        .replace(b"</cfdi:Comprobante>", b"</b></a></cfdi:Comprobante>")
    )
    with pytest.raises(MalformedXml):
        read(deep, max_depth=2)
    with pytest.raises(MalformedXml):
        read(xml(), max_elements=1)
    with pytest.raises(MalformedXml):
        read(
            xml().replace(b'Folio="000123"', b'Folio="' + b"x" * 20 + b'"'), max_attribute_bytes=10
        )


def test_plain_malformed_xml_is_typed() -> None:
    with pytest.raises(MalformedXml):
        read(xml()[:-20])
