from __future__ import annotations

from datetime import date
from decimal import Decimal

from config import DEFAULT_TALLY_VOUCHER_TYPE
from models import BillExtraction, Entity, EntrySide, JournalEntry, JournalLine


class JournalGenerator:
    def generate(
        self,
        entity: Entity,
        bill: BillExtraction,
        expense_account: str,
        tax_account: str,
        payable_account: str,
        entry_date: date | None = None,
    ) -> JournalEntry:
        self._validate_account(expense_account, "Expense account")
        self._validate_account(payable_account, "Payable account")
        if bill.tax_amount > 0:
            self._validate_account(tax_account, "Tax account")
        if bill.gross_amount <= 0:
            raise ValueError("Bill amount must be greater than zero before creating a journal entry.")

        lines = [
            JournalLine(expense_account.strip(), EntrySide.DEBIT, bill.taxable_amount),
        ]
        if bill.tax_amount > 0:
            lines.append(JournalLine(tax_account.strip(), EntrySide.DEBIT, bill.tax_amount))
        lines.append(JournalLine(payable_account.strip(), EntrySide.CREDIT, bill.gross_amount))

        invoice_ref = f" invoice {bill.invoice_number}" if bill.invoice_number else ""
        narration = (
            f"Being bill{invoice_ref} from {bill.vendor_name} recorded for {entity.name}; "
            f"gross amount INR {bill.gross_amount}."
        )
        entry = JournalEntry(
            entity_id=entity.id,
            bill_id=None,
            entry_date=entry_date or bill.invoice_date or date.today(),
            voucher_type=DEFAULT_TALLY_VOUCHER_TYPE,
            narration=narration,
            lines=lines,
        )
        if not entry.is_balanced():
            raise ValueError("Generated journal entry is not balanced. Check tax and amount fields.")
        return entry

    @staticmethod
    def _validate_account(account: str, label: str) -> None:
        if not account or not account.strip():
            raise ValueError(f"{label} is required.")
