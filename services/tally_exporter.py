from __future__ import annotations

import html
from datetime import datetime
from decimal import Decimal

import pandas as pd


class TallyExporter:
    def entries_to_dataframe(self, records: list[dict], line_lookup: callable) -> pd.DataFrame:
        rows = []
        for record in records:
            for line in line_lookup(record["entry_id"]):
                amount = Decimal(str(line["amount"]))
                rows.append(
                    {
                        "Voucher Date": record["entry_date"],
                        "Voucher Type": record["voucher_type"],
                        "Voucher Number": record["entry_id"],
                        "Ledger Name": line["account_name"],
                        "Dr/Cr": "Dr" if line["side"] == "debit" else "Cr",
                        "Amount": float(amount),
                        "Narration": record["narration"],
                        "Bill Reference": record["invoice_number"] or record["source_file_name"],
                        "Vendor": record["vendor_name"],
                    }
                )
        return pd.DataFrame(rows)

    def entries_to_tally_xml(self, entity_name: str, records: list[dict], line_lookup: callable) -> str:
        vouchers = []
        for record in records:
            lines = []
            for line in line_lookup(record["entry_id"]):
                amount = Decimal(str(line["amount"]))
                signed_amount = amount if line["side"] == "debit" else -amount
                lines.append(
                    f"""
                    <ALLLEDGERENTRIES.LIST>
                        <LEDGERNAME>{html.escape(line["account_name"])}</LEDGERNAME>
                        <ISDEEMEDPOSITIVE>{'Yes' if line["side"] == 'credit' else 'No'}</ISDEEMEDPOSITIVE>
                        <AMOUNT>{signed_amount}</AMOUNT>
                    </ALLLEDGERENTRIES.LIST>
                    """
                )
            tally_date = datetime.fromisoformat(record["entry_date"]).strftime("%Y%m%d")
            vouchers.append(
                f"""
                <VOUCHER VCHTYPE="{html.escape(record['voucher_type'])}" ACTION="Create">
                    <DATE>{tally_date}</DATE>
                    <VOUCHERTYPENAME>{html.escape(record['voucher_type'])}</VOUCHERTYPENAME>
                    <NARRATION>{html.escape(record['narration'])}</NARRATION>
                    <VOUCHERNUMBER>{record['entry_id']}</VOUCHERNUMBER>
                    {''.join(lines)}
                </VOUCHER>
                """
            )
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<ENVELOPE>
    <HEADER>
        <TALLYREQUEST>Import Data</TALLYREQUEST>
    </HEADER>
    <BODY>
        <IMPORTDATA>
            <REQUESTDESC>
                <REPORTNAME>Vouchers</REPORTNAME>
                <STATICVARIABLES>
                    <SVCURRENTCOMPANY>{html.escape(entity_name)}</SVCURRENTCOMPANY>
                </STATICVARIABLES>
            </REQUESTDESC>
            <REQUESTDATA>
                {''.join(vouchers)}
            </REQUESTDATA>
        </IMPORTDATA>
    </BODY>
</ENVELOPE>
"""
