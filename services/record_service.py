from __future__ import annotations

from datetime import date
from decimal import Decimal

from models import BillExtraction, Entity, JournalEntry, User
from services.session_store import SessionStore


class RecordService:
    def __init__(self, store: SessionStore):
        self.store = store

    def save_bill_and_entry(
        self,
        entity: Entity,
        user: User,
        bill: BillExtraction,
        file_hash: str,
        journal_entry: JournalEntry,
    ) -> tuple[int, int]:
        if not journal_entry.is_balanced():
            raise ValueError("Journal entry cannot be saved because debits and credits do not match.")
        for existing in self.store.state["bills_store"].values():
            if existing["entity_id"] == entity.id and existing["file_hash"] == file_hash:
                raise ValueError("This bill file has already been processed for the selected entity in this session.")

        bill_id = self.store.next_id("bill")
        entry_id = self.store.next_id("entry")
        self.store.state["bills_store"][bill_id] = {
            "id": bill_id,
            "entity_id": entity.id,
            "uploaded_by_user_id": user.id,
            "source_file_name": bill.source_file_name,
            "file_hash": file_hash,
            "vendor_name": bill.vendor_name,
            "invoice_number": bill.invoice_number,
            "invoice_date": bill.invoice_date.isoformat() if bill.invoice_date else None,
            "gross_amount": str(bill.gross_amount),
            "taxable_amount": str(bill.taxable_amount),
            "tax_amount": str(bill.tax_amount),
            "currency": bill.currency,
            "raw_text": bill.raw_text,
            "extraction_confidence": str(bill.confidence),
            "created_at": self.store.now(),
            "items": [
                {
                    "description": item.description,
                    "amount": str(item.amount),
                    "tax_rate": str(item.tax_rate) if item.tax_rate else None,
                    "tax_amount": str(item.tax_amount),
                }
                for item in bill.items
            ],
        }
        self.store.state["journal_entries_store"][entry_id] = {
            "id": entry_id,
            "entity_id": entity.id,
            "bill_id": bill_id,
            "entry_date": journal_entry.entry_date.isoformat(),
            "voucher_type": journal_entry.voucher_type,
            "narration": journal_entry.narration,
            "total_debits": str(journal_entry.total_debits),
            "total_credits": str(journal_entry.total_credits),
            "created_at": self.store.now(),
        }
        self.store.state["journal_lines_store"][entry_id] = [
            {"account_name": line.account_name, "side": line.side.value, "amount": str(line.amount)}
            for line in journal_entry.lines
        ]
        return bill_id, entry_id

    def search_history(
        self,
        entity: Entity,
        vendor: str = "",
        min_amount: Decimal | None = None,
        max_amount: Decimal | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[dict]:
        records = []
        for bill in self.store.state["bills_store"].values():
            if bill["entity_id"] != entity.id:
                continue
            entry = next(
                (
                    candidate
                    for candidate in self.store.state["journal_entries_store"].values()
                    if candidate["bill_id"] == bill["id"]
                ),
                None,
            )
            if entry is None:
                continue
            gross_amount = Decimal(str(bill["gross_amount"]))
            record_date = bill["invoice_date"] or entry["entry_date"]
            if vendor and vendor.casefold() not in bill["vendor_name"].casefold():
                continue
            if min_amount is not None and gross_amount < min_amount:
                continue
            if max_amount is not None and gross_amount > max_amount:
                continue
            if start_date and record_date < start_date.isoformat():
                continue
            if end_date and record_date > end_date.isoformat():
                continue
            records.append(
                {
                    "bill_id": bill["id"],
                    "entry_id": entry["id"],
                    "vendor_name": bill["vendor_name"],
                    "invoice_number": bill["invoice_number"],
                    "invoice_date": bill["invoice_date"],
                    "gross_amount": bill["gross_amount"],
                    "tax_amount": bill["tax_amount"],
                    "entry_date": entry["entry_date"],
                    "voucher_type": entry["voucher_type"],
                    "narration": entry["narration"],
                    "total_debits": entry["total_debits"],
                    "total_credits": entry["total_credits"],
                    "source_file_name": bill["source_file_name"],
                    "created_at": bill["created_at"],
                }
            )
        records.sort(key=lambda row: (row["invoice_date"] or row["entry_date"], row["created_at"]), reverse=True)
        return records

    def get_entry_lines(self, entry_id: int) -> list[dict]:
        return list(self.store.state["journal_lines_store"].get(entry_id, []))
