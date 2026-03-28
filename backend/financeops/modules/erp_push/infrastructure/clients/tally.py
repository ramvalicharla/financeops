from __future__ import annotations

from decimal import Decimal
from typing import Any
from xml.etree import ElementTree as ET

import httpx

from financeops.modules.erp_push.domain.schemas import PushJournalPacket, PushResult

TALLY_NETWORK = "TALLY_NETWORK"
TALLY_REJECTED = "TALLY_REJECTED"
TALLY_ENCODING = "TALLY_ENCODING"

_DEFAULT_HOST = "localhost"
_DEFAULT_PORT = 9000


def _decimal_to_str(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def _build_tally_voucher_xml(packet: PushJournalPacket) -> str:
    lines_xml = []
    for line in packet.lines:
        amount = _decimal_to_str(line.amount)
        lines_xml.append(
            """
        <ALLLEDGERENTRIES.LIST>
          <LEDGERNAME>{ledger}</LEDGERNAME>
          <ISDEEMEDPOSITIVE>{positive}</ISDEEMEDPOSITIVE>
          <AMOUNT>{amount}</AMOUNT>
        </ALLLEDGERENTRIES.LIST>
        """.format(
                ledger=line.account_code,
                positive="Yes" if line.entry_type == "DEBIT" else "No",
                amount=f"-{amount}" if line.entry_type == "DEBIT" else amount,
            ).strip()
        )

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<ENVELOPE>
  <HEADER>
    <TALLYREQUEST>Import Data</TALLYREQUEST>
  </HEADER>
  <BODY>
    <IMPORTDATA>
      <REQUESTDESC>
        <REPORTNAME>Vouchers</REPORTNAME>
      </REQUESTDESC>
      <REQUESTDATA>
        <TALLYMESSAGE xmlns:UDF="TallyUDF">
          <VOUCHER VCHTYPE="Journal" ACTION="Create">
            <DATE>{packet.period_date.replace('-', '')}</DATE>
            <NARRATION>{packet.description or ''}</NARRATION>
            <VOUCHERTYPENAME>Journal</VOUCHERTYPENAME>
            <VOUCHERNUMBER>{packet.jv_number}</VOUCHERNUMBER>
            <REFERENCE>{packet.reference or packet.jv_number}</REFERENCE>
            {' '.join(lines_xml)}
          </VOUCHER>
        </TALLYMESSAGE>
      </REQUESTDATA>
    </IMPORTDATA>
  </BODY>
</ENVELOPE>"""
    return xml.strip()


def _parse_tally_response(response_text: str) -> dict[str, Any]:
    try:
        root = ET.fromstring(response_text)
    except ET.ParseError as exc:
        return {"success": False, "created": 0, "error": f"XML parse error: {exc}"}

    errors = root.findall(".//LINEERROR")
    if errors:
        return {
            "success": False,
            "created": 0,
            "error": "; ".join((node.text or "") for node in errors),
        }

    created = root.find(".//CREATED")
    created_count = int(created.text or "0") if created is not None else 0
    return {"success": created_count > 0, "created": created_count, "error": None}


async def push_journal_to_tally(
    packet: PushJournalPacket,
    *,
    tally_host: str = _DEFAULT_HOST,
    tally_port: int = _DEFAULT_PORT,
    simulation: bool = False,
) -> PushResult:
    xml_payload = _build_tally_voucher_xml(packet)

    if simulation:
        return PushResult(
            success=True,
            external_journal_id=f"SIM-TALLY-{packet.jv_number}",
            raw_response={"simulation": True, "xml_length": len(xml_payload)},
        )

    headers = {"Content-Type": "text/xml; charset=utf-8"}
    try:
        encoded = xml_payload.encode("utf-8")
    except UnicodeEncodeError:
        try:
            encoded = xml_payload.encode("latin-1")
            headers["Content-Type"] = "text/xml; charset=latin-1"
        except UnicodeEncodeError as exc:
            return PushResult(
                success=False,
                error_code=TALLY_ENCODING,
                error_message=f"XML encoding failed: {exc}",
                error_category="HARD",
            )

    url = f"http://{tally_host}:{tally_port}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, content=encoded, headers=headers)
    except (httpx.RequestError, httpx.TimeoutException) as exc:
        return PushResult(
            success=False,
            error_code=TALLY_NETWORK,
            error_message=f"Cannot reach Tally at {url}: {exc}",
            error_category="SOFT",
        )

    parsed = _parse_tally_response(response.text)
    if not parsed["success"]:
        return PushResult(
            success=False,
            error_code=TALLY_REJECTED,
            error_message=str(parsed.get("error") or "Tally rejected voucher"),
            error_category="HARD",
            raw_response={"response": response.text[:500]},
        )

    return PushResult(
        success=True,
        external_journal_id=f"TALLY-{packet.jv_number}",
        raw_response={"created": parsed["created"]},
    )
