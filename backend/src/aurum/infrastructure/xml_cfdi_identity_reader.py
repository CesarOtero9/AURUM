from __future__ import annotations

from io import BytesIO

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import ParseError, iterparse

from aurum.domain.cfdi_identity import (
    CfdiUuid,
    MalformedXml,
    MissingTimbreFiscalDigital,
    MissingTimbreUuid,
    MultipleTimbreFiscalDigital,
    OriginalXml,
    XmlInputTooLarge,
)

SAT_TIMBRE_NAMESPACE = "http://www.sat.gob.mx/TimbreFiscalDigital"
SAT_TIMBRE_TAG = f"{{{SAT_TIMBRE_NAMESPACE}}}TimbreFiscalDigital"


class SecureCfdiIdentityReader:
    def __init__(
        self,
        max_input_bytes: int = 5 * 1024 * 1024,
        max_depth: int = 64,
        max_elements: int = 10_000,
        max_attribute_bytes: int = 4_096,
    ) -> None:
        self._max_input_bytes = max_input_bytes
        self._max_depth = max_depth
        self._max_elements = max_elements
        self._max_attribute_bytes = max_attribute_bytes

    def read_uuid(self, original_xml: OriginalXml) -> CfdiUuid:
        content = original_xml.value
        if len(content) > self._max_input_bytes:
            raise XmlInputTooLarge("XML input exceeds the configured size limit")

        depth = 0
        element_count = 0
        timbre_count = 0
        timbre_uuid: str | None = None
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
                    element_count += 1
                    if depth > self._max_depth or element_count > self._max_elements:
                        raise MalformedXml("XML exceeds structural safety limits")
                    if any(
                        len(value.encode()) > self._max_attribute_bytes
                        for value in element.attrib.values()
                    ):
                        raise MalformedXml("XML attribute exceeds the configured size limit")
                    if element.tag == SAT_TIMBRE_TAG:
                        timbre_count += 1
                        timbre_uuid = element.attrib.get("UUID")
                else:
                    depth -= 1
                    element.clear()
        except (DefusedXmlException, ParseError) as error:
            raise MalformedXml("XML is malformed or violates parser safety restrictions") from error

        if timbre_count == 0:
            raise MissingTimbreFiscalDigital("Exact SAT TimbreFiscalDigital is absent")
        if timbre_count > 1:
            raise MultipleTimbreFiscalDigital("Multiple SAT TimbreFiscalDigital elements found")
        if timbre_uuid is None:
            raise MissingTimbreUuid("SAT TimbreFiscalDigital has no UUID attribute")

        return CfdiUuid.from_raw(timbre_uuid)
