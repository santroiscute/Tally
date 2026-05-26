from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from dateutil import parser as date_parser
from pypdf import PdfReader

from models import BillExtraction, BillItem
from utils.money import as_money


class PdfExtractionService:
    amount_pattern = re.compile(r"(?:total|grand total|amount due|invoice total)[^\d]*(\d[\d,]*\.?\d{0,2})", re.I)
    tax_pattern = re.compile(r"(?:gst|cgst|sgst|igst|tax)[^\d]*(\d[\d,]*\.?\d{0,2})", re.I)
    invoice_pattern = re.compile(r"(?:invoice|bill)\s*(?:no|number|#)[:\s-]*([A-Z0-9\-\/]+)", re.I)
    date_pattern = re.compile(r"(?:invoice date|bill date|date)[:\s-]*([0-9]{1,2}[\/\-.][0-9]{1,2}[\/\-.][0-9]{2,4}|[A-Z][a-z]{2,8}\s+\d{1,2},?\s+\d{4})", re.I)

    def extract(self, pdf_path: Path) -> BillExtraction:
        text = self._read_pdf_text(pdf_path)
        if not text.strip():
            raise ValueError(f"No readable text found in {pdf_path.name}. Scanned PDFs require OCR before upload.")

        gross = self._extract_amount(text)
        tax = self._extract_tax(text)
        taxable = max(gross - tax, Decimal("0.00"))
        vendor = self._extract_vendor(text)
        invoice_number = self._extract_invoice_number(text)
        invoice_date = self._extract_date(text)
        items = self._extract_items(text, taxable, tax)
        confidence = Decimal("0.75") if vendor != "Unknown Vendor" and gross > 0 else Decimal("0.45")

        return BillExtraction(
            vendor_name=vendor,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            gross_amount=gross,
            taxable_amount=taxable,
            tax_amount=tax,
            items=items,
            raw_text=text[:20_000],
            confidence=confidence,
            source_file_name=pdf_path.name,
        )

    @staticmethod
    def _read_pdf_text(pdf_path: Path) -> str:
        try:
            reader = PdfReader(str(pdf_path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise ValueError(f"Unable to read PDF {pdf_path.name}: {exc}") from exc

    def _extract_amount(self, text: str) -> Decimal:
        matches = self.amount_pattern.findall(text)
        if matches:
            return as_money(matches[-1])

        numeric_values = [as_money(match) for match in re.findall(r"\b\d[\d,]+\.\d{2}\b", text)]
        return max(numeric_values) if numeric_values else Decimal("0.00")

    def _extract_tax(self, text: str) -> Decimal:
        values = [as_money(match) for match in self.tax_pattern.findall(text)]
        if not values:
            return Decimal("0.00")
        return sum(values[-3:], Decimal("0.00")).quantize(Decimal("0.01"))

    @staticmethod
    def _extract_vendor(text: str) -> str:
        for line in text.splitlines():
            cleaned = line.strip()
            if cleaned and not re.search(r"invoice|tax|date|gst|total", cleaned, re.I):
                return cleaned[:120]
        return "Unknown Vendor"

    def _extract_invoice_number(self, text: str) -> str | None:
        match = self.invoice_pattern.search(text)
        return match.group(1).strip() if match else None

    def _extract_date(self, text: str) -> date | None:
        match = self.date_pattern.search(text)
        if not match:
            return None
        try:
            return date_parser.parse(match.group(1), dayfirst=True).date()
        except (ValueError, OverflowError):
            return None

    @staticmethod
    def _extract_items(text: str, taxable: Decimal, tax: Decimal) -> list[BillItem]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        items: list[BillItem] = []
        for line in lines:
            match = re.search(r"(.{4,80}?)\s+(\d[\d,]*\.\d{2})$", line)
            if match and not re.search(r"total|tax|gst|balance", match.group(1), re.I):
                items.append(BillItem(description=match.group(1).strip(), amount=as_money(match.group(2))))
        if items:
            return items[:25]
        if taxable > 0:
            return [BillItem(description="Bill expense", amount=taxable, tax_amount=tax)]
        return []
