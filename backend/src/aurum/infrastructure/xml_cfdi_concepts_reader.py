from __future__ import annotations

from io import BytesIO

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import ParseError, iterparse

from aurum.domain.cfdi_concepts import ParsedCfdiConcept, ParsedCfdiConcepts
from aurum.domain.cfdi_header import (
    CfdiVersion,
    EmptyFiscalAttribute,
    FiscalDecimal,
    InvalidCfdiNamespace,
    InvalidCfdiRoot,
    MissingRequiredFiscalAttribute,
    UnexpectedFiscalAttribute,
    UnsupportedCfdiVersion,
    VersionNamespaceMismatch,
)
from aurum.domain.cfdi_identity import MalformedXml, XmlEvidence, XmlInputTooLarge
from aurum.infrastructure.xml_cfdi_header_reader import NS_BY_VERSION


class _BaseVersionConceptsReader:
    version: CfdiVersion

    def read(self, root) -> ParsedCfdiConcepts:
        namespace = NS_BY_VERSION[self.version]
        conceptos = next(
            (element for element in root if element.tag == f"{{{namespace}}}Conceptos"),
            None,
        )
        if conceptos is None:
            raise MissingRequiredFiscalAttribute("Conceptos is required")
        concept_elements = [
            element for element in conceptos if element.tag == f"{{{namespace}}}Concepto"
        ]
        if not concept_elements:
            raise MissingRequiredFiscalAttribute("Conceptos must contain at least one Concepto")
        return ParsedCfdiConcepts(
            version=self.version,
            concepts=tuple(
                self._concept(element.attrib, index)
                for index, element in enumerate(concept_elements)
            ),
        )

    def _concept(self, attributes: dict[str, str], index: int) -> ParsedCfdiConcept:
        def required(name: str) -> str:
            return _required(attributes, name, index)

        def optional(name: str) -> str | None:
            return _optional(attributes, name, index)

        cantidad_raw = required("Cantidad")
        valor_unitario_raw = required("ValorUnitario")
        importe_raw = required("Importe")
        descuento_raw = optional("Descuento")
        return ParsedCfdiConcept(
            concept_index=index,
            clave_prod_serv_raw=required("ClaveProdServ"),
            no_identificacion_raw=optional("NoIdentificacion"),
            cantidad_raw=cantidad_raw,
            cantidad=FiscalDecimal.from_source(cantidad_raw).value,
            clave_unidad_raw=required("ClaveUnidad"),
            unidad_raw=optional("Unidad"),
            descripcion_raw=required("Descripcion"),
            valor_unitario_raw=valor_unitario_raw,
            valor_unitario=FiscalDecimal.from_source(valor_unitario_raw).value,
            importe_raw=importe_raw,
            importe=FiscalDecimal.from_source(importe_raw).value,
            descuento_raw=descuento_raw,
            descuento=(
                None if descuento_raw is None else FiscalDecimal.from_source(descuento_raw).value
            ),
            objeto_imp_raw=self._objeto_imp(attributes, index),
        )

    def _objeto_imp(self, attributes: dict[str, str], index: int) -> str | None:
        del attributes, index
        return None


class Cfdi33ConceptsReader(_BaseVersionConceptsReader):
    version = CfdiVersion.CFDI_33

    def _objeto_imp(self, attributes: dict[str, str], index: int) -> str | None:
        if "ObjetoImp" in attributes:
            raise UnexpectedFiscalAttribute(
                f"Concepto[{index}] ObjetoImp is not allowed in CFDI 3.3"
            )
        return None


class Cfdi40ConceptsReader(_BaseVersionConceptsReader):
    version = CfdiVersion.CFDI_40

    def _objeto_imp(self, attributes: dict[str, str], index: int) -> str:
        return _required(attributes, "ObjetoImp", index)


def _required(attributes: dict[str, str], name: str, index: int) -> str:
    if name not in attributes:
        raise MissingRequiredFiscalAttribute(f"Concepto[{index}] {name} is required")
    return _present(attributes[name], name, index)


def _optional(attributes: dict[str, str], name: str, index: int) -> str | None:
    return None if name not in attributes else _present(attributes[name], name, index)


def _present(value: str, name: str, index: int) -> str:
    if value == "":
        raise EmptyFiscalAttribute(f"Concepto[{index}] {name} must not be empty")
    return value


def _root_required(attributes: dict[str, str], name: str) -> str:
    if name not in attributes:
        raise MissingRequiredFiscalAttribute(f"{name} is required")
    if attributes[name] == "":
        raise EmptyFiscalAttribute(f"{name} must not be empty")
    return attributes[name]


class CfdiConceptsReader:
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
        self._readers = {
            CfdiVersion.CFDI_33: Cfdi33ConceptsReader(),
            CfdiVersion.CFDI_40: Cfdi40ConceptsReader(),
        }

    def read(self, evidence: XmlEvidence) -> ParsedCfdiConcepts:
        content = evidence.original_xml.value
        if len(content) > self.max_input_bytes:
            raise XmlInputTooLarge("XML input exceeds the configured size limit")
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
                    if depth > self.max_depth or count > self.max_elements:
                        raise MalformedXml("XML exceeds structural safety limits")
                    if any(
                        len(value.encode()) > self.max_attribute_bytes
                        for value in element.attrib.values()
                    ):
                        raise MalformedXml("XML attribute exceeds the configured size limit")
                    if root is None:
                        root = element
                else:
                    depth -= 1
        except (DefusedXmlException, ParseError) as error:
            raise MalformedXml("XML is malformed or violates parser safety restrictions") from error
        assert root is not None
        namespace = root.tag[1:].split("}", 1)[0] if root.tag.startswith("{") else ""
        if namespace not in NS_BY_VERSION.values():
            raise InvalidCfdiNamespace("CFDI Comprobante namespace is unsupported")
        if root.tag != f"{{{namespace}}}Comprobante":
            raise InvalidCfdiRoot("CFDI root must be the exact Comprobante element")
        raw_version = _root_required(root.attrib, "Version")
        try:
            version = CfdiVersion(raw_version)
        except ValueError as error:
            raise UnsupportedCfdiVersion("CFDI Version is unsupported") from error
        if NS_BY_VERSION[version] != namespace:
            raise VersionNamespaceMismatch("CFDI Version does not match namespace")
        return self._readers[version].read(root)
