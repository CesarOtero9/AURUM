from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from aurum.domain.cfdi_concepts import FINGERPRINT_SCHEMA, PARSER_NAME, PARSER_VERSION, fingerprint
from aurum.domain.cfdi_header import (
    EmptyFiscalAttribute,
    InvalidCfdiNamespace,
    InvalidCfdiRoot,
    InvalidFiscalDecimal,
    MissingRequiredFiscalAttribute,
    UnexpectedFiscalAttribute,
    UnsupportedCfdiVersion,
    VersionNamespaceMismatch,
)
from aurum.domain.cfdi_identity import MalformedXml, OriginalXml, XmlEvidence, XmlInputTooLarge
from aurum.infrastructure.xml_cfdi_concepts_reader import CfdiConceptsReader

NS33 = "http://www.sat.gob.mx/cfd/3"
NS40 = "http://www.sat.gob.mx/cfd/4"


def attrs(values: dict[str, str]) -> str:
    return " ".join(f'{key}="{value}"' for key, value in values.items())


def concept(
    *,
    version: str = "4.0",
    remove: str | None = None,
    empty: str | None = None,
    add: tuple[str, str] | None = None,
    values: dict[str, str] | None = None,
) -> str:
    fields = {
        "ClaveProdServ": "01010101",
        "NoIdentificacion": "SKU-A",
        "Cantidad": "1.00",
        "ClaveUnidad": "H87",
        "Unidad": "Pieza",
        "Descripcion": "Servicio ágil",
        "ValorUnitario": "100.00",
        "Importe": "100.00",
        "Descuento": "0.00",
    }
    if version == "4.0":
        fields["ObjetoImp"] = "02"
    if values:
        fields.update(values)
    if remove:
        fields.pop(remove, None)
    if empty and empty in fields:
        fields[empty] = ""
    if add:
        fields[add[0]] = add[1]
    return f"<cfdi:Concepto {attrs(fields)}/>"


def xml(
    *,
    version: str = "4.0",
    namespace: str | None = None,
    root: str = "Comprobante",
    concepts: tuple[str, ...] | None = None,
    include_conceptos: bool = True,
) -> bytes:
    namespace = namespace or (NS40 if version == "4.0" else NS33)
    children = ""
    if include_conceptos:
        concept_children = (concept(version=version),) if concepts is None else concepts
        children = f"<cfdi:Conceptos>{''.join(concept_children)}</cfdi:Conceptos>"
    opening = f'<cfdi:{root} xmlns:cfdi="{namespace}" Version="{version}">'
    return f"{opening}{children}</cfdi:{root}>".encode()


def read(content: bytes, **limits: int):
    return CfdiConceptsReader(**limits).read(XmlEvidence.from_original_xml(OriginalXml(content)))


def test_valid_33_concept_preserves_raw_and_decimals() -> None:
    parsed = read(xml(version="3.3"))
    result = parsed.concepts[0]
    assert parsed.version.value == "3.3"
    assert result.concept_index == 0
    assert result.cantidad_raw == "1.00"
    assert result.cantidad == Decimal("1.00")
    assert result.valor_unitario == Decimal("100.00")
    assert result.importe == Decimal("100.00")
    assert result.objeto_imp_raw is None


def test_valid_40_concept_requires_and_preserves_objeto_imp() -> None:
    result = read(xml()).concepts[0]
    assert result.objeto_imp_raw == "02"


@pytest.mark.parametrize("version", ["3.3", "4.0"])
def test_source_order_and_duplicates_are_preserved(version: str) -> None:
    first = concept(version=version, values={"Descripcion": "Same", "Importe": "10.00"})
    second = concept(version=version, values={"Descripcion": "Same", "Importe": "10.00"})
    third = concept(version=version, values={"Descripcion": "Last", "Importe": "20.00"})
    parsed = read(xml(version=version, concepts=(first, second, third)))
    assert [item.concept_index for item in parsed.concepts] == [0, 1, 2]
    assert [item.descripcion_raw for item in parsed.concepts] == ["Same", "Same", "Last"]
    assert replace(parsed.concepts[0], concept_index=1) == parsed.concepts[1]


@pytest.mark.parametrize("version", ["3.3", "4.0"])
@pytest.mark.parametrize("field", ["NoIdentificacion", "Unidad", "Descuento"])
def test_optional_attributes_absent(version: str, field: str) -> None:
    result = read(
        xml(version=version, concepts=(concept(version=version, remove=field),))
    ).concepts[0]
    attribute = {
        "NoIdentificacion": "no_identificacion_raw",
        "Unidad": "unidad_raw",
        "Descuento": "descuento_raw",
    }[field]
    assert getattr(result, attribute) is None
    if field == "Descuento":
        assert result.descuento is None


@pytest.mark.parametrize("version", ["3.3", "4.0"])
def test_explicit_zero_discount_is_distinct_from_absence(version: str) -> None:
    result = read(
        xml(version=version, concepts=(concept(version=version, values={"Descuento": "0"}),))
    ).concepts[0]
    assert (result.descuento_raw, result.descuento) == ("0", Decimal("0"))


@pytest.mark.parametrize("version", ["3.3", "4.0"])
@pytest.mark.parametrize(
    "field",
    ["ClaveProdServ", "Cantidad", "ClaveUnidad", "Descripcion", "ValorUnitario", "Importe"],
)
def test_required_attributes_missing(version: str, field: str) -> None:
    with pytest.raises(MissingRequiredFiscalAttribute, match=rf"Concepto\[0\] {field}"):
        read(xml(version=version, concepts=(concept(version=version, remove=field),)))


@pytest.mark.parametrize("version", ["3.3", "4.0"])
@pytest.mark.parametrize("field", ["Cantidad", "Descripcion", "ClaveProdServ"])
def test_representative_required_attributes_empty(version: str, field: str) -> None:
    with pytest.raises(EmptyFiscalAttribute, match=rf"Concepto\[0\] {field}"):
        read(xml(version=version, concepts=(concept(version=version, empty=field),)))


@pytest.mark.parametrize("field", ["Cantidad", "ValorUnitario", "Importe", "Descuento"])
def test_invalid_concept_decimal_is_typed(field: str) -> None:
    with pytest.raises(InvalidFiscalDecimal):
        read(xml(concepts=(concept(values={field: "1E2"}),)))


def test_decimal_source_scale_and_precision_are_preserved() -> None:
    result = read(
        xml(
            concepts=(
                concept(
                    values={
                        "Cantidad": "0.000000000000000001",
                        "ValorUnitario": "100.0000",
                        "Importe": "100.000000000000000000",
                    }
                ),
            )
        )
    ).concepts[0]
    assert result.cantidad_raw == "0.000000000000000001"
    assert result.cantidad == Decimal("0.000000000000000001")
    assert result.valor_unitario.as_tuple().exponent == -4
    assert result.importe.as_tuple().exponent == -18


def test_40_missing_objeto_imp_is_typed() -> None:
    with pytest.raises(MissingRequiredFiscalAttribute, match=r"Concepto\[0\] ObjetoImp"):
        read(xml(concepts=(concept(remove="ObjetoImp"),)))


def test_33_rejects_objeto_imp() -> None:
    with pytest.raises(UnexpectedFiscalAttribute, match=r"Concepto\[0\] ObjetoImp"):
        read(xml(version="3.3", concepts=(concept(version="3.3", add=("ObjetoImp", "02")),)))


@pytest.mark.parametrize("version,namespace", [("3.3", NS33), ("4.0", NS40)])
def test_matching_namespace_version(version: str, namespace: str) -> None:
    assert read(xml(version=version, namespace=namespace)).version.value == version


@pytest.mark.parametrize("version,namespace", [("4.0", NS33), ("3.3", NS40)])
def test_namespace_version_mismatch(version: str, namespace: str) -> None:
    with pytest.raises(VersionNamespaceMismatch):
        read(xml(version=version, namespace=namespace))


def test_unsupported_version_namespace_and_root_are_typed() -> None:
    with pytest.raises(UnsupportedCfdiVersion):
        read(xml(version="5.0", namespace=NS40))
    with pytest.raises(InvalidCfdiNamespace):
        read(xml(namespace="urn:unknown"))
    with pytest.raises(InvalidCfdiRoot):
        read(xml(root="Other"))


def test_root_version_errors_are_not_concept_scoped() -> None:
    with pytest.raises(MissingRequiredFiscalAttribute, match=r"^Version is required$"):
        read(xml().replace(b' Version="4.0"', b""))
    with pytest.raises(EmptyFiscalAttribute, match=r"^Version must not be empty$"):
        read(xml().replace(b'Version="4.0"', b'Version=""'))


def test_codes_are_preserved_without_catalogue_lexical_validation() -> None:
    result = read(
        xml(concepts=(concept(values={"ClaveProdServ": "custom", "ClaveUnidad": "unit"}),))
    ).concepts[0]
    assert (result.clave_prod_serv_raw, result.clave_unidad_raw) == ("custom", "unit")


def test_missing_and_empty_conceptos_are_typed() -> None:
    with pytest.raises(MissingRequiredFiscalAttribute, match="Conceptos is required"):
        read(xml(include_conceptos=False))
    with pytest.raises(MissingRequiredFiscalAttribute, match="at least one Concepto"):
        read(xml(concepts=()))


def test_fingerprint_contract_is_deterministic_and_order_sensitive() -> None:
    first = read(xml())
    reordered = read(
        xml(
            concepts=(
                concept(values={"Descripcion": "B"}),
                concept(values={"Descripcion": "A"}),
            )
        )
    )
    schema, digest = fingerprint(first)
    assert (PARSER_NAME, PARSER_VERSION, schema) == (
        "cfdi-concepts",
        "concepts-parser/1",
        "cfdi-concepts-fingerprint/1",
    )
    assert FINGERPRINT_SCHEMA == "cfdi-concepts-fingerprint/1"
    assert len(digest) == 64 and set(digest) <= set("0123456789abcdef")
    assert fingerprint(first) == fingerprint(read(xml()))
    assert digest != fingerprint(reordered)[1]


def test_xml_security_and_malformed_xml_use_existing_errors() -> None:
    with pytest.raises(XmlInputTooLarge):
        read(xml(), max_input_bytes=1)
    with pytest.raises(MalformedXml):
        read(b"<!DOCTYPE x []>" + xml())
    with pytest.raises(MalformedXml):
        read(b'<!DOCTYPE x [<!ENTITY x SYSTEM "file:///x">]>' + xml())
    deep = (
        xml()
        .replace(b"<cfdi:Conceptos>", b"<a><b><cfdi:Conceptos>")
        .replace(b"</cfdi:Conceptos>", b"</cfdi:Conceptos></b></a>")
    )
    with pytest.raises(MalformedXml):
        read(deep, max_depth=2)
    with pytest.raises(MalformedXml):
        read(xml(), max_elements=1)
    with pytest.raises(MalformedXml):
        read(
            xml().replace(
                'Descripcion="Servicio ágil"'.encode(),
                b'Descripcion="' + b"x" * 20 + b'"',
            ),
            max_attribute_bytes=10,
        )
    with pytest.raises(MalformedXml):
        read(xml()[:-20])
