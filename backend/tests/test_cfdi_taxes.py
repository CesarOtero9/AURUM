from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from aurum.domain.cfdi_header import (
    EmptyFiscalAttribute,
    InvalidCfdiNamespace,
    InvalidCfdiRoot,
    InvalidFiscalCode,
    InvalidFiscalDecimal,
    MissingRequiredFiscalAttribute,
    UnexpectedFiscalAttribute,
    UnsupportedCfdiVersion,
    VersionNamespaceMismatch,
)
from aurum.domain.cfdi_identity import MalformedXml, OriginalXml, XmlEvidence, XmlInputTooLarge
from aurum.domain.cfdi_taxes import (
    FINGERPRINT_SCHEMA,
    PARSER_NAME,
    PARSER_VERSION,
    canonical_fingerprint_payload,
    fingerprint,
)
from aurum.infrastructure.xml_cfdi_taxes_reader import CfdiTaxesReader

NS33 = "http://www.sat.gob.mx/cfd/3"
NS40 = "http://www.sat.gob.mx/cfd/4"


def _attrs(values: dict[str, str]) -> str:
    return " ".join(f'{key}="{value}"' for key, value in values.items())


def _tax_node(name: str, values: dict[str, str]) -> str:
    return f"<cfdi:{name} {_attrs(values)}/>"


def _concept(
    version: str, taxes: str = "", *, description: str = "Item", objeto: str = "02"
) -> str:
    object_imp = f' ObjetoImp="{objeto}"' if version == "4.0" else ""
    return (
        '<cfdi:Concepto ClaveProdServ="01010101" Cantidad="1" '
        f'ClaveUnidad="H87" Descripcion="{description}" '
        f'ValorUnitario="100" Importe="100"{object_imp}>{taxes}</cfdi:Concepto>'
    )


def _xml(
    *,
    version: str = "4.0",
    namespace: str | None = None,
    root: str = "Comprobante",
    concepts: tuple[str, ...] | None = None,
    aggregate: str = "",
    include_conceptos: bool = True,
) -> bytes:
    namespace = namespace or (NS40 if version == "4.0" else NS33)
    concept_xml = ""
    if include_conceptos:
        children = concepts if concepts is not None else (_concept(version),)
        concept_xml = f"<cfdi:Conceptos>{''.join(children)}</cfdi:Conceptos>"
    return (
        f'<cfdi:{root} xmlns:cfdi="{namespace}" Version="{version}">'
        f"{concept_xml}{aggregate}</cfdi:{root}>"
    ).encode()


def _read(content: bytes, **limits: int):
    return CfdiTaxesReader(**limits).read(XmlEvidence.from_original_xml(OriginalXml(content)))


def _transfer(
    *, factor: str = "Tasa", aggregate: bool = False, extra: dict[str, str] | None = None
) -> str:
    values = {"Base": "100.0000", "Impuesto": "002", "TipoFactor": factor}
    if factor != "Exento":
        values |= {"TasaOCuota": "0.160000", "Importe": "16.0000"}
    if aggregate and factor == "Exento":
        values["Base"] = "100.0000"
    if extra:
        values |= extra
    return _tax_node("Traslado", values)


def _withholding(*, factor: str = "Tasa", extra: dict[str, str] | None = None) -> str:
    values = {
        "Base": "100.0000",
        "Impuesto": "001",
        "TipoFactor": factor,
        "TasaOCuota": "0.100000",
        "Importe": "10.0000",
    }
    if extra:
        values |= extra
    return _tax_node("Retencion", values)


def _aggregate_transfer_33(*, extra: dict[str, str] | None = None) -> str:
    values = {
        "Impuesto": "002",
        "TipoFactor": "Tasa",
        "TasaOCuota": "0.160000",
        "Importe": "16.0000",
    }
    if extra:
        values |= extra
    return _tax_node("Traslado", values)


def _concept_taxes(*, transfers: str = "", withholdings: str = "") -> str:
    parts = []
    if transfers:
        parts.append(f"<cfdi:Traslados>{transfers}</cfdi:Traslados>")
    if withholdings:
        parts.append(f"<cfdi:Retenciones>{withholdings}</cfdi:Retenciones>")
    return f"<cfdi:Impuestos>{''.join(parts)}</cfdi:Impuestos>"


def _aggregate(
    *, transfers: str = "", withholdings: str = "", totals: dict[str, str] | None = None
) -> str:
    values = _attrs(totals or {})
    parts = []
    if transfers:
        parts.append(f"<cfdi:Traslados>{transfers}</cfdi:Traslados>")
    if withholdings:
        parts.append(f"<cfdi:Retenciones>{withholdings}</cfdi:Retenciones>")
    return f"<cfdi:Impuestos {values}>{''.join(parts)}</cfdi:Impuestos>"


@pytest.mark.parametrize("version", ["3.3", "4.0"])
def test_absent_tax_containers_preserve_source_absence(version: str) -> None:
    parsed = _read(_xml(version=version))
    assert parsed.concept_taxes == (parsed.concept_taxes[0],)
    assert parsed.concept_taxes[0].impuestos_present is False
    assert parsed.concept_taxes[0].transfers == parsed.concept_taxes[0].withholdings == ()
    assert parsed.aggregate_taxes.impuestos_present is False
    assert parsed.aggregate_taxes.transfers == parsed.aggregate_taxes.withholdings == ()


@pytest.mark.parametrize("version", ["3.3", "4.0"])
@pytest.mark.parametrize("factor", ["Tasa", "Cuota"])
def test_concept_tax_transfers_preserve_decimal_raw_values(version: str, factor: str) -> None:
    taxes = _concept_taxes(transfers=_transfer(factor=factor))
    value = (
        _read(_xml(version=version, concepts=(_concept(version, taxes),)))
        .concept_taxes[0]
        .transfers[0]
    )
    assert (value.transfer_index, value.base_raw, value.base) == (
        0,
        "100.0000",
        Decimal("100.0000"),
    )
    assert (value.tasa_o_cuota_raw, value.tasa_o_cuota) == ("0.160000", Decimal("0.160000"))
    assert (value.importe_raw, value.importe) == ("16.0000", Decimal("16.0000"))


@pytest.mark.parametrize("version", ["3.3", "4.0"])
def test_concept_exento_transfer_has_no_rate_or_amount(version: str) -> None:
    taxes = _concept_taxes(transfers=_transfer(factor="Exento"))
    value = (
        _read(_xml(version=version, concepts=(_concept(version, taxes),)))
        .concept_taxes[0]
        .transfers[0]
    )
    assert value.tipo_factor_raw == "Exento"
    assert (value.tasa_o_cuota_raw, value.tasa_o_cuota, value.importe_raw, value.importe) == (
        None,
        None,
        None,
        None,
    )


@pytest.mark.parametrize("version", ["3.3", "4.0"])
def test_concept_withholding_requires_and_preserves_all_fields(version: str) -> None:
    withholding = _tax_node(
        "Retencion",
        {
            "Base": "100.00",
            "Impuesto": "001",
            "TipoFactor": "Tasa",
            "TasaOCuota": "0.100000",
            "Importe": "10.00",
        },
    )
    taxes = _concept_taxes(withholdings=withholding)
    value = (
        _read(_xml(version=version, concepts=(_concept(version, taxes),)))
        .concept_taxes[0]
        .withholdings[0]
    )
    assert (value.withholding_index, value.base, value.importe) == (
        0,
        Decimal("100.00"),
        Decimal("10.00"),
    )
    assert (value.base_raw, value.tasa_o_cuota_raw, value.importe_raw) == (
        "100.00",
        "0.100000",
        "10.00",
    )


@pytest.mark.parametrize("version", ["3.3", "4.0"])
@pytest.mark.parametrize("field", ["Base", "Impuesto", "TipoFactor", "TasaOCuota", "Importe"])
def test_concept_withholding_required_fields_are_typed(version: str, field: str) -> None:
    values = {
        "Base": "100",
        "Impuesto": "001",
        "TipoFactor": "Tasa",
        "TasaOCuota": "0.1",
        "Importe": "10",
    }
    values.pop(field)
    with pytest.raises(MissingRequiredFiscalAttribute, match=field):
        _read(
            _xml(
                version=version,
                concepts=(
                    _concept(version, _concept_taxes(withholdings=_tax_node("Retencion", values))),
                ),
            )
        )


@pytest.mark.parametrize("version", ["3.3", "4.0"])
@pytest.mark.parametrize("field", ["Base", "Impuesto", "TasaOCuota"])
def test_concept_withholding_empty_fields_are_typed(version: str, field: str) -> None:
    with pytest.raises(EmptyFiscalAttribute, match=field):
        _read(
            _xml(
                version=version,
                concepts=(
                    _concept(
                        version,
                        _concept_taxes(withholdings=_withholding(extra={field: ""})),
                    ),
                ),
            )
        )


@pytest.mark.parametrize("version", ["3.3", "4.0"])
def test_duplicate_concept_withholdings_preserve_source_occurrences(version: str) -> None:
    parsed = _read(
        _xml(
            version=version,
            concepts=(
                _concept(version, _concept_taxes(withholdings=_withholding() + _withholding())),
            ),
        )
    )
    rows = parsed.concept_taxes[0].withholdings
    assert [row.withholding_index for row in rows] == [0, 1]
    assert replace(rows[0], withholding_index=1) == rows[1]


@pytest.mark.parametrize("version", ["3.3", "4.0"])
def test_concept_preserves_transfers_and_withholdings_independently(version: str) -> None:
    parsed = _read(
        _xml(
            version=version,
            concepts=(
                _concept(
                    version,
                    _concept_taxes(transfers=_transfer(), withholdings=_withholding()),
                ),
            ),
        )
    )
    taxes = parsed.concept_taxes[0]
    assert len(taxes.transfers) == len(taxes.withholdings) == 1


@pytest.mark.parametrize("version", ["3.3", "4.0"])
def test_multiple_concepts_keep_independent_tax_container_facts(version: str) -> None:
    parsed = _read(
        _xml(
            version=version,
            concepts=(
                _concept(version, _concept_taxes(transfers=_transfer())),
                _concept(version, _concept_taxes(withholdings=_withholding())),
                _concept(version),
            ),
        )
    )
    first, second, third = parsed.concept_taxes
    assert [row.concept_index for row in parsed.concept_taxes] == [0, 1, 2]
    assert (len(first.transfers), len(first.withholdings), first.impuestos_present) == (1, 0, True)
    assert (len(second.transfers), len(second.withholdings), second.impuestos_present) == (
        0,
        1,
        True,
    )
    assert (third.transfers, third.withholdings, third.impuestos_present) == ((), (), False)


@pytest.mark.parametrize(
    ("taxes", "match"),
    [
        ("<cfdi:Impuestos><cfdi:Traslados/></cfdi:Impuestos>", "Traslados"),
        ("<cfdi:Impuestos><cfdi:Retenciones/></cfdi:Impuestos>", "Retenciones"),
        ("<cfdi:Impuestos/>", "Impuestos"),
    ],
)
def test_empty_concept_tax_containers_are_typed(taxes: str, match: str) -> None:
    with pytest.raises(MissingRequiredFiscalAttribute, match=match):
        _read(_xml(concepts=(_concept("4.0", taxes),)))


def test_concept_collections_preserve_order_and_duplicate_rows() -> None:
    taxes = _concept_taxes(transfers=_transfer() + _transfer(), withholdings="")
    parsed = _read(_xml(concepts=(_concept("4.0", taxes), _concept("4.0"))))
    first, second = parsed.concept_taxes
    assert [item.transfer_index for item in first.transfers] == [0, 1]
    assert replace(first.transfers[0], transfer_index=1) == first.transfers[1]
    assert second.impuestos_present is False


@pytest.mark.parametrize("version", ["3.3", "4.0"])
def test_concept_transfer_factor_field_rules_are_typed(version: str) -> None:
    missing = _concept_taxes(transfers=_transfer(extra={"TasaOCuota": ""}))
    with pytest.raises(EmptyFiscalAttribute, match="TasaOCuota"):
        _read(_xml(version=version, concepts=(_concept(version, missing),)))
    exento = _concept_taxes(transfers=_transfer(factor="Exento", extra={"Importe": "0"}))
    with pytest.raises(UnexpectedFiscalAttribute, match="Importe"):
        _read(_xml(version=version, concepts=(_concept(version, exento),)))


@pytest.mark.parametrize("version", ["3.3", "4.0"])
@pytest.mark.parametrize("field", ["Base", "Impuesto", "TipoFactor"])
def test_concept_transfer_required_fields_are_typed(version: str, field: str) -> None:
    values = {
        "Base": "100",
        "Impuesto": "002",
        "TipoFactor": "Tasa",
        "TasaOCuota": "0.16",
        "Importe": "16",
    }
    values.pop(field)
    with pytest.raises(MissingRequiredFiscalAttribute, match=field):
        _read(
            _xml(
                version=version,
                concepts=(
                    _concept(version, _concept_taxes(transfers=_tax_node("Traslado", values))),
                ),
            )
        )


def test_tipo_factor_enum_is_structural_and_exempt_withholding_is_preserved() -> None:
    invalid = _concept_taxes(transfers=_transfer(extra={"TipoFactor": "Other"}))
    with pytest.raises(InvalidFiscalCode, match="TipoFactor"):
        _read(_xml(concepts=(_concept("4.0", invalid),)))
    # SAT fiscal validation separately decides whether a withholding may be Exento.
    parsed = _read(
        _xml(
            concepts=(_concept("4.0", _concept_taxes(withholdings=_withholding(factor="Exento"))),)
        )
    )
    value = parsed.concept_taxes[0].withholdings[0]
    assert value.tipo_factor_raw == "Exento"
    assert (value.tasa_o_cuota_raw, value.importe_raw) == ("0.100000", "10.0000")


def test_33_aggregate_transfer_has_no_base_and_requires_other_fields() -> None:
    transfer = _tax_node(
        "Traslado",
        {"Impuesto": "002", "TipoFactor": "Tasa", "TasaOCuota": "0.160000", "Importe": "16.0000"},
    )
    parsed = _read(_xml(version="3.3", aggregate=_aggregate(transfers=transfer)))
    value = parsed.aggregate_taxes.transfers[0]
    assert (value.base_raw, value.base, value.importe) == (None, None, Decimal("16.0000"))


def test_33_aggregate_transfer_rejects_base() -> None:
    transfer = _tax_node(
        "Traslado",
        {
            "Base": "100",
            "Impuesto": "002",
            "TipoFactor": "Tasa",
            "TasaOCuota": "0.16",
            "Importe": "16",
        },
    )
    with pytest.raises(UnexpectedFiscalAttribute, match="Base"):
        _read(_xml(version="3.3", aggregate=_aggregate(transfers=transfer)))


@pytest.mark.parametrize("field", ["Impuesto", "TipoFactor", "TasaOCuota", "Importe"])
def test_33_aggregate_transfer_required_fields_are_typed(field: str) -> None:
    values = {
        "Impuesto": "002",
        "TipoFactor": "Tasa",
        "TasaOCuota": "0.16",
        "Importe": "16",
    }
    values.pop(field)
    with pytest.raises(MissingRequiredFiscalAttribute, match=field):
        _read(
            _xml(
                version="3.3",
                aggregate=_aggregate(transfers=_tax_node("Traslado", values)),
            )
        )


@pytest.mark.parametrize("field", ["TasaOCuota", "Importe"])
def test_33_aggregate_transfer_empty_required_fields_are_typed(field: str) -> None:
    with pytest.raises(EmptyFiscalAttribute, match=field):
        _read(
            _xml(
                version="3.3",
                aggregate=_aggregate(transfers=_aggregate_transfer_33(extra={field: ""})),
            )
        )


def test_40_aggregate_transfer_preserves_base_and_exento_absence() -> None:
    value = _read(
        _xml(aggregate=_aggregate(transfers=_transfer(aggregate=True, factor="Exento")))
    ).aggregate_taxes.transfers[0]
    assert (value.base_raw, value.base, value.tasa_o_cuota, value.importe) == (
        "100.0000",
        Decimal("100.0000"),
        None,
        None,
    )


@pytest.mark.parametrize("factor", ["Tasa", "Cuota"])
@pytest.mark.parametrize("field", ["Base", "Impuesto", "TipoFactor", "TasaOCuota", "Importe"])
def test_40_aggregate_tasa_or_cuota_requires_all_fields(factor: str, field: str) -> None:
    values = {
        "Base": "100",
        "Impuesto": "002",
        "TipoFactor": factor,
        "TasaOCuota": "0.16",
        "Importe": "16",
    }
    values.pop(field)
    with pytest.raises(MissingRequiredFiscalAttribute, match=field):
        _read(_xml(aggregate=_aggregate(transfers=_tax_node("Traslado", values))))


@pytest.mark.parametrize("field", ["TasaOCuota", "Importe"])
def test_40_aggregate_exento_forbids_conditional_fields(field: str) -> None:
    with pytest.raises(UnexpectedFiscalAttribute, match=field):
        _read(
            _xml(
                aggregate=_aggregate(
                    transfers=_transfer(aggregate=True, factor="Exento", extra={field: "0"})
                )
            )
        )


@pytest.mark.parametrize("version", ["3.3", "4.0"])
def test_aggregate_withholding_is_compact(version: str) -> None:
    value = _read(
        _xml(
            version=version,
            aggregate=_aggregate(
                withholdings=_tax_node("Retencion", {"Impuesto": "001", "Importe": "10.0000"})
            ),
        )
    ).aggregate_taxes.withholdings[0]
    assert (
        value.aggregate_withholding_index,
        value.impuesto_raw,
        value.importe_raw,
        value.importe,
    ) == (0, "001", "10.0000", Decimal("10.0000"))


@pytest.mark.parametrize("field", ["Base", "TipoFactor", "TasaOCuota"])
def test_aggregate_withholding_forbids_concept_fields(field: str) -> None:
    values = {"Impuesto": "001", "Importe": "10", field: "1"}
    with pytest.raises(UnexpectedFiscalAttribute, match=field):
        _read(_xml(aggregate=_aggregate(withholdings=_tax_node("Retencion", values))))


@pytest.mark.parametrize("version", ["3.3", "4.0"])
@pytest.mark.parametrize("field", ["Impuesto", "Importe"])
def test_aggregate_withholding_required_and_empty_fields_are_typed(
    version: str, field: str
) -> None:
    values = {"Impuesto": "001", "Importe": "10"}
    values.pop(field)
    with pytest.raises(MissingRequiredFiscalAttribute, match=field):
        _read(
            _xml(
                version=version,
                aggregate=_aggregate(withholdings=_tax_node("Retencion", values)),
            )
        )
    with pytest.raises(EmptyFiscalAttribute, match=field):
        empty_values = {"Impuesto": "001", "Importe": "10"}
        empty_values[field] = ""
        _read(
            _xml(
                version=version,
                aggregate=_aggregate(withholdings=_tax_node("Retencion", empty_values)),
            )
        )


@pytest.mark.parametrize("version", ["3.3", "4.0"])
def test_aggregate_tax_rows_preserve_order_and_duplicates(version: str) -> None:
    transfer = _aggregate_transfer_33() if version == "3.3" else _transfer(aggregate=True)
    withholding = _tax_node("Retencion", {"Impuesto": "001", "Importe": "10.0000"})
    parsed = _read(
        _xml(
            version=version,
            aggregate=_aggregate(
                transfers=transfer + transfer,
                withholdings=withholding + withholding,
            ),
        )
    ).aggregate_taxes
    assert [row.aggregate_transfer_index for row in parsed.transfers] == [0, 1]
    assert replace(parsed.transfers[0], aggregate_transfer_index=1) == parsed.transfers[1]
    assert [row.aggregate_withholding_index for row in parsed.withholdings] == [0, 1]
    assert replace(parsed.withholdings[0], aggregate_withholding_index=1) == parsed.withholdings[1]


@pytest.mark.parametrize("version", ["3.3", "4.0"])
def test_aggregate_totals_preserve_raw_or_absence(version: str) -> None:
    aggregate = _aggregate(
        transfers=_transfer(aggregate=version == "4.0"),
        totals={"TotalImpuestosTrasladados": "16.0000", "TotalImpuestosRetenidos": "0"},
    )
    if version == "3.3":
        aggregate = _aggregate(
            transfers=_tax_node(
                "Traslado",
                {"Impuesto": "002", "TipoFactor": "Tasa", "TasaOCuota": "0.16", "Importe": "16"},
            ),
            totals={"TotalImpuestosTrasladados": "16.0000", "TotalImpuestosRetenidos": "0"},
        )
    parsed = _read(_xml(version=version, aggregate=aggregate)).aggregate_taxes
    assert (parsed.total_trasladados_raw, parsed.total_trasladados) == (
        "16.0000",
        Decimal("16.0000"),
    )
    assert (parsed.total_retenidos_raw, parsed.total_retenidos) == ("0", Decimal("0"))
    assert _read(_xml(version=version)).aggregate_taxes.total_trasladados is None


@pytest.mark.parametrize("version", ["3.3", "4.0"])
@pytest.mark.parametrize("field", ["TotalImpuestosTrasladados", "TotalImpuestosRetenidos"])
def test_aggregate_totals_reject_malformed_decimals(version: str, field: str) -> None:
    transfer = _aggregate_transfer_33() if version == "3.3" else _transfer(aggregate=True)
    with pytest.raises(InvalidFiscalDecimal, match="decimal"):
        _read(
            _xml(
                version=version,
                aggregate=_aggregate(transfers=transfer, totals={field: "1E2"}),
            )
        )


def test_raw_decimal_invalid_and_scientific_forms_are_typed() -> None:
    invalid = _concept_taxes(transfers=_transfer(extra={"Base": "1E2"}))
    with pytest.raises(InvalidFiscalDecimal):
        _read(_xml(concepts=(_concept("4.0", invalid),)))


def test_fingerprint_is_deterministic_order_and_raw_sensitive() -> None:
    taxes = _concept_taxes(transfers=_transfer())
    first = _read(_xml(concepts=(_concept("4.0", taxes),)))
    changed_raw = _read(
        _xml(
            concepts=(
                _concept("4.0", _concept_taxes(transfers=_transfer(extra={"TasaOCuota": "0.16"}))),
            )
        )
    )
    reordered = _read(_xml(concepts=(_concept("4.0"), _concept("4.0", taxes))))
    schema, digest = fingerprint(first)
    assert (PARSER_NAME, PARSER_VERSION, schema) == (
        "cfdi-taxes",
        "taxes-parser/1",
        "cfdi-taxes-fingerprint/1",
    )
    assert FINGERPRINT_SCHEMA == "cfdi-taxes-fingerprint/1"
    assert fingerprint(first) == fingerprint(_read(_xml(concepts=(_concept("4.0", taxes),))))
    assert digest != fingerprint(changed_raw)[1]
    assert digest != fingerprint(reordered)[1]


def test_fingerprint_tracks_tax_row_order_and_container_presence() -> None:
    first_transfer = _transfer(extra={"Impuesto": "002"})
    second_transfer = _transfer(extra={"Impuesto": "003"})
    first_withholding = _withholding(extra={"Impuesto": "001"})
    second_withholding = _withholding(extra={"Impuesto": "002"})
    forward = _read(
        _xml(
            concepts=(
                _concept(
                    "4.0",
                    _concept_taxes(
                        transfers=first_transfer + second_transfer,
                        withholdings=first_withholding + second_withholding,
                    ),
                ),
            ),
            aggregate=_aggregate(
                transfers=_transfer(aggregate=True)
                + _transfer(aggregate=True, extra={"Impuesto": "003"}),
                withholdings=(
                    _tax_node("Retencion", {"Impuesto": "001", "Importe": "10"})
                    + _tax_node("Retencion", {"Impuesto": "002", "Importe": "10"})
                ),
            ),
        )
    )
    reverse = _read(
        _xml(
            concepts=(
                _concept(
                    "4.0",
                    _concept_taxes(
                        transfers=second_transfer + first_transfer,
                        withholdings=second_withholding + first_withholding,
                    ),
                ),
            ),
            aggregate=_aggregate(
                transfers=_transfer(aggregate=True, extra={"Impuesto": "003"})
                + _transfer(aggregate=True),
                withholdings=(
                    _tax_node("Retencion", {"Impuesto": "002", "Importe": "10"})
                    + _tax_node("Retencion", {"Impuesto": "001", "Importe": "10"})
                ),
            ),
        )
    )
    absent = _read(_xml(concepts=(_concept("4.0"),)))
    assert fingerprint(forward)[1] != fingerprint(reverse)[1]
    assert fingerprint(forward)[1] != fingerprint(absent)[1]
    assert "fingerprint_schema" not in canonical_fingerprint_payload(forward)


def test_fingerprint_tracks_each_ordered_tax_collection_independently() -> None:
    transfer_one = _transfer(extra={"Impuesto": "002"})
    transfer_two = _transfer(extra={"Impuesto": "003"})
    withholding_one = _withholding(extra={"Impuesto": "001"})
    withholding_two = _withholding(extra={"Impuesto": "002"})
    aggregate_transfer_one = _transfer(aggregate=True, extra={"Impuesto": "002"})
    aggregate_transfer_two = _transfer(aggregate=True, extra={"Impuesto": "003"})
    aggregate_withholding_one = _tax_node("Retencion", {"Impuesto": "001", "Importe": "10"})
    aggregate_withholding_two = _tax_node("Retencion", {"Impuesto": "002", "Importe": "10"})

    def parsed(
        transfers: str,
        withholdings: str,
        aggregate_transfers: str,
        aggregate_withholdings: str,
    ):
        return _read(
            _xml(
                concepts=(
                    _concept("4.0", _concept_taxes(transfers=transfers, withholdings=withholdings)),
                ),
                aggregate=_aggregate(
                    transfers=aggregate_transfers,
                    withholdings=aggregate_withholdings,
                ),
            )
        )

    baseline = parsed(
        transfer_one + transfer_two,
        withholding_one + withholding_two,
        aggregate_transfer_one + aggregate_transfer_two,
        aggregate_withholding_one + aggregate_withholding_two,
    )
    variations = (
        parsed(
            transfer_two + transfer_one,
            withholding_one + withholding_two,
            aggregate_transfer_one + aggregate_transfer_two,
            aggregate_withholding_one + aggregate_withholding_two,
        ),
        parsed(
            transfer_one + transfer_two,
            withholding_two + withholding_one,
            aggregate_transfer_one + aggregate_transfer_two,
            aggregate_withholding_one + aggregate_withholding_two,
        ),
        parsed(
            transfer_one + transfer_two,
            withholding_one + withholding_two,
            aggregate_transfer_two + aggregate_transfer_one,
            aggregate_withholding_one + aggregate_withholding_two,
        ),
        parsed(
            transfer_one + transfer_two,
            withholding_one + withholding_two,
            aggregate_transfer_one + aggregate_transfer_two,
            aggregate_withholding_two + aggregate_withholding_one,
        ),
    )
    assert all(fingerprint(baseline)[1] != fingerprint(value)[1] for value in variations)


def test_version_namespace_root_and_container_errors_are_typed() -> None:
    with pytest.raises(VersionNamespaceMismatch):
        _read(_xml(version="4.0", namespace=NS33))
    with pytest.raises(UnsupportedCfdiVersion):
        _read(_xml(version="5.0", namespace=NS40))
    with pytest.raises(InvalidCfdiNamespace):
        _read(_xml(namespace="urn:unknown"))
    with pytest.raises(InvalidCfdiRoot):
        _read(_xml(root="Other"))
    with pytest.raises(MissingRequiredFiscalAttribute, match="Conceptos is required"):
        _read(_xml(include_conceptos=False))
    with pytest.raises(MissingRequiredFiscalAttribute, match="Comprobante Version"):
        _read(_xml().replace(b' Version="4.0"', b""))
    with pytest.raises(EmptyFiscalAttribute, match="Comprobante Version"):
        _read(_xml().replace(b'Version="4.0"', b'Version=""'))
    with pytest.raises(MissingRequiredFiscalAttribute, match="at least one Concepto"):
        _read(_xml(concepts=()))
    with pytest.raises(MissingRequiredFiscalAttribute, match="requires Traslados"):
        _read(_xml(aggregate="<cfdi:Impuestos/>"))


def test_xml_security_limits_and_malformed_xml_are_reused() -> None:
    with pytest.raises(XmlInputTooLarge):
        _read(_xml(), max_input_bytes=1)
    with pytest.raises(MalformedXml):
        _read(b"<!DOCTYPE x []>" + _xml())
    with pytest.raises(MalformedXml):
        _read(b'<!DOCTYPE x [<!ENTITY x SYSTEM "file:///x">]>' + _xml())
    deep = (
        _xml()
        .replace(b"<cfdi:Conceptos>", b"<a><b><cfdi:Conceptos>")
        .replace(b"</cfdi:Conceptos>", b"</cfdi:Conceptos></b></a>")
    )
    with pytest.raises(MalformedXml):
        _read(deep, max_depth=2)
    with pytest.raises(MalformedXml):
        _read(_xml(), max_elements=1)
    with pytest.raises(MalformedXml):
        _read(
            _xml().replace(b'Descripcion="Item"', b'Descripcion="' + b"x" * 20 + b'"'),
            max_attribute_bytes=10,
        )
    with pytest.raises(MalformedXml):
        _read(_xml()[:-20])


def test_objeto_imp_does_not_create_or_reject_tax_rows() -> None:
    no_taxes = _read(_xml(concepts=(_concept("4.0", objeto="08"),)))
    with_taxes = _read(
        _xml(concepts=(_concept("4.0", _concept_taxes(transfers=_transfer()), objeto="01"),))
    )
    assert no_taxes.concept_taxes[0].transfers == ()
    assert len(with_taxes.concept_taxes[0].transfers) == 1
