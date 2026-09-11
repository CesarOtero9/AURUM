from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import ParseError, iterparse

from aurum.domain.cfdi_header import (
    CfdiVersion,
    EmptyFiscalAttribute,
    FiscalDecimal,
    InvalidCfdiNamespace,
    InvalidCfdiRoot,
    InvalidFiscalCode,
    MissingRequiredFiscalAttribute,
    UnexpectedFiscalAttribute,
    UnsupportedCfdiVersion,
    VersionNamespaceMismatch,
)
from aurum.domain.cfdi_identity import MalformedXml, XmlEvidence, XmlInputTooLarge
from aurum.domain.cfdi_taxes import (
    ParsedCfdiAggregateTaxes,
    ParsedCfdiAggregateTransfer,
    ParsedCfdiAggregateWithholding,
    ParsedCfdiConceptTaxes,
    ParsedCfdiConceptTransfer,
    ParsedCfdiConceptWithholding,
    ParsedCfdiTaxes,
)
from aurum.infrastructure.xml_cfdi_header_reader import NS_BY_VERSION


class _TaxesReader:
    def __init__(self, version: CfdiVersion) -> None:
        self.version = version
        self.namespace = NS_BY_VERSION[version]

    def read(self, root) -> ParsedCfdiTaxes:
        concepts = _child(root, self.namespace, "Conceptos")
        if concepts is None:
            raise MissingRequiredFiscalAttribute("Conceptos is required")
        concept_elements = _children(concepts, self.namespace, "Concepto")
        if not concept_elements:
            raise MissingRequiredFiscalAttribute("Conceptos must contain at least one Concepto")
        return ParsedCfdiTaxes(
            version=self.version,
            concept_taxes=tuple(
                self._concept_taxes(element, index)
                for index, element in enumerate(concept_elements)
            ),
            aggregate_taxes=self._aggregate_taxes(root),
        )

    def _concept_taxes(self, concept, concept_index: int) -> ParsedCfdiConceptTaxes:
        impuestos = _child(concept, self.namespace, "Impuestos")
        if impuestos is None:
            return ParsedCfdiConceptTaxes(concept_index, False, (), ())
        transfers = self._concept_transfers(impuestos, concept_index)
        withholdings = self._concept_withholdings(impuestos, concept_index)
        if not transfers and not withholdings:
            raise MissingRequiredFiscalAttribute(
                f"Concepto[{concept_index}] Impuestos requires Traslados or Retenciones"
            )
        return ParsedCfdiConceptTaxes(concept_index, True, transfers, withholdings)

    def _concept_transfers(
        self, impuestos, concept_index: int
    ) -> tuple[ParsedCfdiConceptTransfer, ...]:
        container = _child(impuestos, self.namespace, "Traslados")
        if container is None:
            return ()
        elements = _children(container, self.namespace, "Traslado")
        if not elements:
            raise MissingRequiredFiscalAttribute(
                f"Concepto[{concept_index}] Traslados requires Traslado"
            )
        return tuple(
            self._concept_transfer(element.attrib, concept_index, index)
            for index, element in enumerate(elements)
        )

    def _concept_transfer(
        self, attributes: dict[str, str], concept_index: int, index: int
    ) -> ParsedCfdiConceptTransfer:
        context = f"Concepto[{concept_index}] Traslado[{index}]"
        base_raw, base = _decimal_required(attributes, "Base", context)
        factor = _required(attributes, "TipoFactor", context)
        rate_raw, rate, amount_raw, amount = _factor_values(attributes, factor, context)
        return ParsedCfdiConceptTransfer(
            index,
            base_raw,
            base,
            _required(attributes, "Impuesto", context),
            factor,
            rate_raw,
            rate,
            amount_raw,
            amount,
        )

    def _concept_withholdings(
        self, impuestos, concept_index: int
    ) -> tuple[ParsedCfdiConceptWithholding, ...]:
        container = _child(impuestos, self.namespace, "Retenciones")
        if container is None:
            return ()
        elements = _children(container, self.namespace, "Retencion")
        if not elements:
            raise MissingRequiredFiscalAttribute(
                f"Concepto[{concept_index}] Retenciones requires Retencion"
            )
        values: list[ParsedCfdiConceptWithholding] = []
        for index, element in enumerate(elements):
            attributes = element.attrib
            context = f"Concepto[{concept_index}] Retencion[{index}]"
            factor = _required(attributes, "TipoFactor", context)
            values.append(
                ParsedCfdiConceptWithholding(
                    index,
                    *_decimal_required(attributes, "Base", context),
                    _required(attributes, "Impuesto", context),
                    factor,
                    *_decimal_required(attributes, "TasaOCuota", context),
                    *_decimal_required(attributes, "Importe", context),
                )
            )
        return tuple(values)

    def _aggregate_taxes(self, root) -> ParsedCfdiAggregateTaxes:
        impuestos = _child(root, self.namespace, "Impuestos")
        if impuestos is None:
            return ParsedCfdiAggregateTaxes(False, None, None, None, None, (), ())
        context = "Comprobante Impuestos"
        total_transferred_raw, total_transferred = _decimal_optional(
            impuestos.attrib, "TotalImpuestosTrasladados", context
        )
        total_withheld_raw, total_withheld = _decimal_optional(
            impuestos.attrib, "TotalImpuestosRetenidos", context
        )
        transfers = self._aggregate_transfers(impuestos)
        withholdings = self._aggregate_withholdings(impuestos)
        if not transfers and not withholdings:
            raise MissingRequiredFiscalAttribute(
                "Comprobante Impuestos requires Traslados or Retenciones"
            )
        return ParsedCfdiAggregateTaxes(
            True,
            total_transferred_raw,
            total_transferred,
            total_withheld_raw,
            total_withheld,
            transfers,
            withholdings,
        )

    def _aggregate_transfers(self, impuestos) -> tuple[ParsedCfdiAggregateTransfer, ...]:
        container = _child(impuestos, self.namespace, "Traslados")
        if container is None:
            return ()
        elements = _children(container, self.namespace, "Traslado")
        if not elements:
            raise MissingRequiredFiscalAttribute("Comprobante Traslados requires Traslado")
        return tuple(
            self._aggregate_transfer(element.attrib, index)
            for index, element in enumerate(elements)
        )

    def _aggregate_transfer(
        self, attributes: dict[str, str], index: int
    ) -> ParsedCfdiAggregateTransfer:
        context = f"Comprobante Traslado[{index}]"
        factor = _required(attributes, "TipoFactor", context)
        if self.version == CfdiVersion.CFDI_33:
            if "Base" in attributes:
                raise UnexpectedFiscalAttribute(f"{context} Base is not allowed in CFDI 3.3")
            rate_raw, rate = _decimal_required(attributes, "TasaOCuota", context)
            amount_raw, amount = _decimal_required(attributes, "Importe", context)
            base_raw = base = None
        else:
            base_raw, base = _decimal_required(attributes, "Base", context)
            rate_raw, rate, amount_raw, amount = _factor_values(attributes, factor, context)
        return ParsedCfdiAggregateTransfer(
            index,
            base_raw,
            base,
            _required(attributes, "Impuesto", context),
            factor,
            rate_raw,
            rate,
            amount_raw,
            amount,
        )

    def _aggregate_withholdings(self, impuestos) -> tuple[ParsedCfdiAggregateWithholding, ...]:
        container = _child(impuestos, self.namespace, "Retenciones")
        if container is None:
            return ()
        elements = _children(container, self.namespace, "Retencion")
        if not elements:
            raise MissingRequiredFiscalAttribute("Comprobante Retenciones requires Retencion")
        values: list[ParsedCfdiAggregateWithholding] = []
        for index, element in enumerate(elements):
            attributes = element.attrib
            context = f"Comprobante Retencion[{index}]"
            for name in ("Base", "TipoFactor", "TasaOCuota"):
                if name in attributes:
                    raise UnexpectedFiscalAttribute(f"{context} {name} is not allowed")
            amount_raw, amount = _decimal_required(attributes, "Importe", context)
            values.append(
                ParsedCfdiAggregateWithholding(
                    index, _required(attributes, "Impuesto", context), amount_raw, amount
                )
            )
        return tuple(values)


def _factor_values(
    attributes: dict[str, str], factor: str, context: str
) -> tuple[str | None, Decimal | None, str | None, Decimal | None]:
    if factor not in {"Tasa", "Cuota", "Exento"}:
        raise InvalidFiscalCode(f"{context} TipoFactor is unsupported")
    if factor == "Exento":
        for name in ("TasaOCuota", "Importe"):
            if name in attributes:
                raise UnexpectedFiscalAttribute(f"{context} {name} is not allowed for Exento")
        return None, None, None, None
    rate_raw, rate = _decimal_required(attributes, "TasaOCuota", context)
    amount_raw, amount = _decimal_required(attributes, "Importe", context)
    return rate_raw, rate, amount_raw, amount


def _child(parent, namespace: str, name: str):
    return next((item for item in parent if item.tag == f"{{{namespace}}}{name}"), None)


def _children(parent, namespace: str, name: str):
    return [item for item in parent if item.tag == f"{{{namespace}}}{name}"]


def _required(attributes: dict[str, str], name: str, context: str) -> str:
    if name not in attributes:
        raise MissingRequiredFiscalAttribute(f"{context} {name} is required")
    if attributes[name] == "":
        raise EmptyFiscalAttribute(f"{context} {name} must not be empty")
    return attributes[name]


def _decimal_required(attributes: dict[str, str], name: str, context: str):
    raw = _required(attributes, name, context)
    return raw, FiscalDecimal.from_source(raw).value


def _decimal_optional(attributes: dict[str, str], name: str, context: str):
    if name not in attributes:
        return None, None
    return _decimal_required(attributes, name, context)


class CfdiTaxesReader:
    def __init__(
        self,
        max_input_bytes: int = 5 * 1024 * 1024,
        max_depth: int = 64,
        max_elements: int = 10_000,
        max_attribute_bytes: int = 4_096,
    ) -> None:
        self.max_input_bytes = max_input_bytes
        self.max_depth = max_depth
        self.max_elements = max_elements
        self.max_attribute_bytes = max_attribute_bytes

    def read(self, evidence: XmlEvidence) -> ParsedCfdiTaxes:
        content = evidence.original_xml.value
        if len(content) > self.max_input_bytes:
            raise XmlInputTooLarge("XML input exceeds the configured size limit")
        root = _secure_root(content, self.max_depth, self.max_elements, self.max_attribute_bytes)
        namespace = root.tag[1:].split("}", 1)[0] if root.tag.startswith("{") else ""
        if namespace not in NS_BY_VERSION.values():
            raise InvalidCfdiNamespace("CFDI Comprobante namespace is unsupported")
        if root.tag != f"{{{namespace}}}Comprobante":
            raise InvalidCfdiRoot("CFDI root must be the exact Comprobante element")
        raw_version = _required(root.attrib, "Version", "Comprobante")
        try:
            version = CfdiVersion(raw_version)
        except ValueError as error:
            raise UnsupportedCfdiVersion("CFDI Version is unsupported") from error
        if NS_BY_VERSION[version] != namespace:
            raise VersionNamespaceMismatch("CFDI Version does not match namespace")
        return _TaxesReader(version).read(root)


def _secure_root(content: bytes, max_depth: int, max_elements: int, max_attribute_bytes: int):
    depth = count = 0
    root = None
    try:
        for event, element in iterparse(
            BytesIO(content),
            events=("start", "end"),
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        ):
            if event == "start":
                depth += 1
                count += 1
                if depth > max_depth or count > max_elements:
                    raise MalformedXml("XML exceeds structural safety limits")
                if any(
                    len(value.encode()) > max_attribute_bytes for value in element.attrib.values()
                ):
                    raise MalformedXml("XML attribute exceeds the configured size limit")
                if root is None:
                    root = element
            else:
                depth -= 1
    except (DefusedXmlException, ParseError) as error:
        raise MalformedXml("XML is malformed or violates parser safety restrictions") from error
    assert root is not None
    return root
