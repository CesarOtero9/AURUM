from __future__ import annotations

from io import BytesIO

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import ParseError, iterparse

from aurum.domain.cfdi_header import (
    CfdiFiscalHeader,
    CfdiVersion,
    ComprobanteHeader,
    EmptyFiscalAttribute,
    FiscalDate,
    FiscalDecimal,
    FiscalPartySnapshot,
    FiscalRfc,
    InvalidCfdiNamespace,
    InvalidCfdiRoot,
    InvalidFiscalCode,
    MissingRequiredFiscalAttribute,
    ReceiverFiscalSnapshot,
    UnexpectedFiscalAttribute,
    UnsupportedCfdiVersion,
    VersionNamespaceMismatch,
)
from aurum.domain.cfdi_identity import MalformedXml, XmlEvidence, XmlInputTooLarge

NS_BY_VERSION = {
    CfdiVersion.CFDI_33: "http://www.sat.gob.mx/cfd/3",
    CfdiVersion.CFDI_40: "http://www.sat.gob.mx/cfd/4",
}


class _BaseVersionHeaderReader:
    version: CfdiVersion

    def _issuer_name(self, attributes: dict[str, str]) -> str | None:
        return _optional(attributes, "Nombre")

    def _receiver_name(self, attributes: dict[str, str]) -> str | None:
        return _optional(attributes, "Nombre")

    def _comprobante_exportacion(self, attributes: dict[str, str]) -> str | None:
        del attributes
        return None

    def _receiver_domicilio(self, attributes: dict[str, str]) -> str | None:
        del attributes
        return None

    def _receiver_regimen(self, attributes: dict[str, str]) -> str | None:
        del attributes
        return None

    def read(self, root) -> CfdiFiscalHeader:
        a = root.attrib

        def required(name: str) -> str:
            return _required(a, name)

        def optional(name: str) -> str | None:
            return _optional(a, name)

        issuer = next(
            (x for x in root if x.tag == f"{{{NS_BY_VERSION[self.version]}}}Emisor"), None
        )
        receiver = next(
            (x for x in root if x.tag == f"{{{NS_BY_VERSION[self.version]}}}Receptor"), None
        )
        if issuer is None:
            raise MissingRequiredFiscalAttribute("Emisor is required")
        if receiver is None:
            raise MissingRequiredFiscalAttribute("Receptor is required")
        ia, ra = issuer.attrib, receiver.attrib
        issuer_name = self._issuer_name(ia)
        receiver_name = self._receiver_name(ra)
        export = self._comprobante_exportacion(a)
        domicile = self._receiver_domicilio(ra)
        receiver_regime = self._receiver_regimen(ra)
        return CfdiFiscalHeader(
            self.version,
            ComprobanteHeader(
                FiscalDate.from_source(required("Fecha")),
                _code(required("TipoDeComprobante")),
                optional("Serie"),
                optional("Folio"),
                _code(required("Moneda")),
                _decimal(optional("TipoCambio")),
                FiscalDecimal.from_source(required("SubTotal")),
                _decimal(optional("Descuento")),
                FiscalDecimal.from_source(required("Total")),
                export,
                _code(required("LugarExpedicion")),
                _code(optional("MetodoPago")) if optional("MetodoPago") else None,
                _code(optional("FormaPago")) if optional("FormaPago") else None,
                optional("CondicionesDePago"),
                optional("Confirmacion"),
            ),
            FiscalPartySnapshot(
                FiscalRfc.from_source(_required(ia, "Rfc")),
                issuer_name,
                _code(_required(ia, "RegimenFiscal")),
            ),
            ReceiverFiscalSnapshot(
                FiscalRfc.from_source(_required(ra, "Rfc")),
                receiver_name,
                domicile,
                receiver_regime,
                _code(_required(ra, "UsoCFDI")),
            ),
        )


class Cfdi33HeaderReader(_BaseVersionHeaderReader):
    version = CfdiVersion.CFDI_33

    def read(self, root) -> CfdiFiscalHeader:
        receiver = next(
            (x for x in root if x.tag == f"{{{NS_BY_VERSION[self.version]}}}Receptor"), None
        )
        forbidden_attributes = (
            (root.attrib, "Exportacion"),
            (receiver.attrib if receiver is not None else {}, "DomicilioFiscalReceptor"),
            (receiver.attrib if receiver is not None else {}, "RegimenFiscalReceptor"),
        )
        for attributes, name in forbidden_attributes:
            if name in attributes:
                raise UnexpectedFiscalAttribute(f"{name} is not allowed in CFDI 3.3")
        return super().read(root)


class Cfdi40HeaderReader(_BaseVersionHeaderReader):
    version = CfdiVersion.CFDI_40

    def _issuer_name(self, attributes: dict[str, str]) -> str:
        return _required(attributes, "Nombre")

    def _receiver_name(self, attributes: dict[str, str]) -> str:
        return _required(attributes, "Nombre")

    def _comprobante_exportacion(self, attributes: dict[str, str]) -> str:
        return _code(_required(attributes, "Exportacion"))

    def _receiver_domicilio(self, attributes: dict[str, str]) -> str:
        return _required(attributes, "DomicilioFiscalReceptor")

    def _receiver_regimen(self, attributes: dict[str, str]) -> str:
        return _code(_required(attributes, "RegimenFiscalReceptor"))


def _required(attributes, name: str) -> str:
    if name not in attributes:
        raise MissingRequiredFiscalAttribute(f"{name} is required")
    return _present(attributes[name], name)


def _optional(attributes, name: str) -> str | None:
    return None if name not in attributes else _present(attributes[name], name)


def _present(value: str, name: str) -> str:
    if value == "":
        raise EmptyFiscalAttribute(f"{name} must not be empty")
    return value


def _decimal(value: str | None) -> FiscalDecimal | None:
    return None if value is None else FiscalDecimal.from_source(value)


def _code(value: str) -> str:
    if not value:
        raise InvalidFiscalCode("Fiscal code must not be empty")
    return value


class CfdiFiscalHeaderReader:
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
            CfdiVersion.CFDI_33: Cfdi33HeaderReader(),
            CfdiVersion.CFDI_40: Cfdi40HeaderReader(),
        }

    def read(self, evidence: XmlEvidence) -> CfdiFiscalHeader:
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
                        len(v.encode()) > self.max_attribute_bytes for v in element.attrib.values()
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
        raw_version = _required(root.attrib, "Version")
        try:
            version = CfdiVersion(raw_version)
        except ValueError as error:
            raise UnsupportedCfdiVersion("CFDI Version is unsupported") from error
        if NS_BY_VERSION[version] != namespace:
            raise VersionNamespaceMismatch("CFDI Version does not match namespace")
        return self._readers[version].read(root)
