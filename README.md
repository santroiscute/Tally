# Tally Bill Journal Automation

A Streamlit application that converts vendor bill PDFs into balanced journal entries for Tally, with session authentication, multi-entity separation, searchable in-session history, and CSV/XML exports.

## Features

- Upload multiple PDF bills or ZIP archives.
- Process all PDFs in a server-side directory path.
- Extract vendor, invoice number, date, gross amount, tax amount, and basic line items from readable PDFs.
- Review and correct extracted bill fields before saving.
- Generate balanced double-entry journals:
  - Debit expense or purchase ledger.
  - Debit input tax ledger when tax exists.
  - Credit payable or vendor ledger.
- Maintain separate entities and records per authenticated session user.
- Search active-session history by entity, date, vendor, and amount.
- Export prior entries as Tally-oriented CSV or Tally XML.
- Keep users, entities, bills, bill items, journals, and mappings in Streamlit session state only.
- Write rotating per-session logs to `logs/session_<id>.log`.

## Setup

```powershell
cd "E:\Swadha Project\tally_bill_journal_app"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL shown by Streamlit, create a session user, create an entity, configure mappings, and process bills.

No external storage engine is required. All application records are held in memory for the active Streamlit session.

## Account Mapping Configuration

Each entity has its own mappings stored in the active session:

- `expense_account`: Purchase or expense ledger to debit.
- `tax_account`: Input GST or tax ledger to debit.
- `payable_account`: Sundry creditor, vendor, or accounts payable ledger to credit.

Use the sidebar in the app to update these. Example presets are in `sample_data/account_mappings.example.json`.

Recommended examples:

- Trading company: `Purchase Accounts`, `Input GST`, `Sundry Creditors`
- Services company: `Professional Fees`, `Input GST`, `Accounts Payable`
- Manufacturing company: `Raw Material Purchases`, `Input GST`, `Sundry Creditors`

## Tally Export

The History & Export tab provides:

- `Download Tally CSV`: tabular voucher lines with date, voucher type, ledger, Dr/Cr, amount, narration, and bill reference.
- `Download Tally XML`: voucher import envelope using the selected entity as `SVCURRENTCOMPANY`.

Before importing into Tally, make sure ledger names exactly match the ledgers in the target Tally company.

## Session Store Structure

The app intentionally has no persistent storage dependency. `services/session_store.py` initializes these in-memory collections inside `st.session_state`:

- `users_store`: session users with PBKDF2 password hashes.
- `entities_store`: company/entity master records.
- `entity_users_store`: user-to-entity access control.
- `account_mappings_store`: per-entity ledger mappings.
- `bills_store`: extracted invoice header details, raw text, and optional line items.
- `journal_entries_store`: voucher headers, totals, narration, and entity/bill links.
- `journal_lines_store`: debit and credit lines for each journal entry.

Multi-entity separation is enforced by entity ids and by querying entities through `entity_users_store`.

## Production Notes

- For multi-user production, add a storage implementation behind the existing service boundaries.
- The PDF parser reads text-based PDFs. Scanned image PDFs should be OCR processed before upload.
- Add SSO, role-based sharing, and approval workflows by extending `AuthService`, `EntityService`, and a future repository layer.
- Tally import behavior can vary by configuration. Validate XML in a staging Tally company before production import.
