from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Optional


class EntrySide(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"


@dataclass(frozen=True)
class User:
    id: int
    email: str
    display_name: str


@dataclass(frozen=True)
class Entity:
    id: int
    name: str
    entity_type: str
    gstin: Optional[str] = None


@dataclass
class BillItem:
    description: str
    amount: Decimal
    tax_rate: Optional[Decimal] = None
    tax_amount: Decimal = Decimal("0.00")


@dataclass
class BillExtraction:
    vendor_name: str
    invoice_number: Optional[str]
    invoice_date: Optional[date]
    gross_amount: Decimal
    taxable_amount: Decimal
    tax_amount: Decimal
    currency: str = "INR"
    items: list[BillItem] = field(default_factory=list)
    raw_text: str = ""
    confidence: Decimal = Decimal("0.50")
    source_file_name: str = ""


@dataclass
class JournalLine:
    account_name: str
    side: EntrySide
    amount: Decimal


@dataclass
class JournalEntry:
    entity_id: int
    bill_id: Optional[int]
    entry_date: date
    voucher_type: str
    narration: str
    lines: list[JournalLine]

    @property
    def total_debits(self) -> Decimal:
        return sum((line.amount for line in self.lines if line.side == EntrySide.DEBIT), Decimal("0.00"))

    @property
    def total_credits(self) -> Decimal:
        return sum((line.amount for line in self.lines if line.side == EntrySide.CREDIT), Decimal("0.00"))

    def is_balanced(self) -> bool:
        return self.total_debits.quantize(Decimal("0.01")) == self.total_credits.quantize(Decimal("0.01"))
