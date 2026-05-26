from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import streamlit as st

from config import LOG_DIR, ensure_directories
from models import BillExtraction, Entity, User
from services.account_mapping_service import AccountMappingService
from services.auth_service import AuthService
from services.entity_service import EntityService
from services.journal_generator import JournalGenerator
from services.logging_service import configure_logging
from services.pdf_extractor import PdfExtractionService
from services.record_service import RecordService
from services.session_store import SessionStore
from services.tally_exporter import TallyExporter
from services.upload_processor import UploadProcessor
from utils.money import as_money


st.set_page_config(page_title="Tally Bill Journal Automation", page_icon=":material/receipt_long:", layout="wide")

ensure_directories()

if "session_id" not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex[:12]
logger = configure_logging(LOG_DIR, st.session_state.session_id)

store = SessionStore(st.session_state)
auth_service = AuthService(store)
entity_service = EntityService(store)
mapping_service = AccountMappingService(store)
upload_processor = UploadProcessor()
extractor = PdfExtractionService()
journal_generator = JournalGenerator()
record_service = RecordService(store)
exporter = TallyExporter()


def current_user() -> User | None:
    data = st.session_state.get("user")
    return AuthService.from_session(data) if data else None


def require_user() -> User:
    user = current_user()
    if user is None:
        st.stop()
    return user


def render_auth() -> None:
    st.title("Tally Bill Journal Automation")
    st.caption("Convert vendor bill PDFs into entity-separated, balanced journal entries for the active session.")
    login_tab, register_tab = st.tabs(["Sign in", "Create user"])

    with login_tab:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", use_container_width=True)
        if submitted:
            try:
                user = auth_service.login(email, password)
                st.session_state.user = AuthService.to_session(user)
                logger.info("User signed in: %s", user.email)
                st.rerun()
            except ValueError as exc:
                logger.warning("Login failed for %s: %s", email, exc)
                st.error(str(exc))

    with register_tab:
        with st.form("register_form"):
            display_name = st.text_input("Display name")
            email = st.text_input("Work email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Create account", use_container_width=True)
        if submitted:
            try:
                user = auth_service.register(email, display_name, password)
                st.session_state.user = AuthService.to_session(user)
                logger.info("User registered: %s", user.email)
                st.rerun()
            except Exception as exc:
                logger.exception("Registration failed")
                st.error(str(exc))


def render_entity_selector(user: User) -> Entity | None:
    entities = entity_service.list_for_user(user)
    with st.sidebar:
        st.subheader("Entity")
        if entities:
            selected_id = st.selectbox("Active entity", [entity.id for entity in entities], format_func=lambda entity_id: next(e.name for e in entities if e.id == entity_id))
            entity = next(e for e in entities if e.id == selected_id)
        else:
            entity = None
            st.info("Create an entity to begin.")

        with st.expander("Create entity", expanded=not entities):
            with st.form("entity_form"):
                name = st.text_input("Company / entity name")
                entity_type = st.text_input("Entity type", value="General")
                gstin = st.text_input("GSTIN")
                submitted = st.form_submit_button("Create entity")
            if submitted:
                try:
                    entity = entity_service.create_entity(user, name, entity_type, gstin)
                    logger.info("Created entity %s for user %s", entity.name, user.email)
                    st.success("Entity created.")
                    st.rerun()
                except Exception as exc:
                    logger.exception("Entity creation failed")
                    st.error(str(exc))

        if st.button("Sign out", use_container_width=True):
            logger.info("User signed out: %s", user.email)
            st.session_state.pop("user", None)
            st.rerun()
    return entity


def render_account_mappings(entity: Entity) -> dict[str, str]:
    mappings = mapping_service.get_mappings(entity)
    with st.sidebar.expander("Account mappings", expanded=True):
        expense_account = st.text_input("Expense / purchase ledger", value=mappings["expense_account"])
        tax_account = st.text_input("Input tax ledger", value=mappings["tax_account"])
        payable_account = st.text_input("Payable / vendor ledger", value=mappings["payable_account"])
        if st.button("Save mappings", use_container_width=True):
            try:
                mapping_service.save_mappings(
                    entity,
                    {
                        "expense_account": expense_account,
                        "tax_account": tax_account,
                        "payable_account": payable_account,
                    },
                )
                logger.info("Saved account mappings for entity %s", entity.id)
                st.success("Mappings saved.")
            except Exception as exc:
                logger.exception("Saving mappings failed")
                st.error(str(exc))
    return {
        "expense_account": expense_account,
        "tax_account": tax_account,
        "payable_account": payable_account,
    }


def prepare_pending_files(entity: Entity, pdf_paths: list[Path]) -> None:
    pending_bills = []
    for pdf_path in pdf_paths:
        try:
            extraction = extractor.extract(pdf_path)
            file_hash = upload_processor.file_hash(pdf_path)
            logger.info("Extracted PDF %s for entity %s", pdf_path.name, entity.id)
            pending_bills.append({"entity_id": entity.id, "file_hash": file_hash, "extraction": extraction})
        except Exception as exc:
            logger.exception("Processing failed for %s", pdf_path)
            st.error(f"{pdf_path.name}: {exc}")
    st.session_state.pending_bills = pending_bills


def render_pending_bills(user: User, entity: Entity, mappings: dict[str, str]) -> None:
    pending_bills = [
        item for item in st.session_state.get("pending_bills", []) if item["entity_id"] == entity.id
    ]
    for pending in pending_bills:
        extraction = pending["extraction"]
        file_hash = pending["file_hash"]
        with st.expander(f"{extraction.source_file_name} - extracted bill", expanded=True):
            edited = render_bill_editor(extraction, key_prefix=file_hash[:12])
            journal_entry = journal_generator.generate(
                entity,
                edited,
                mappings["expense_account"],
                mappings["tax_account"],
                mappings["payable_account"],
                edited.invoice_date or date.today(),
            )
            render_journal_preview(journal_entry)
            if st.button(f"Save bill and journal entry: {extraction.source_file_name}", key=f"save_{file_hash}"):
                try:
                    bill_id, entry_id = record_service.save_bill_and_entry(entity, user, edited, file_hash, journal_entry)
                    st.session_state.pending_bills = [
                        item for item in st.session_state.pending_bills if item["file_hash"] != file_hash
                    ]
                    logger.info("Saved bill %s and entry %s for entity %s", bill_id, entry_id, entity.id)
                    st.success(f"Saved bill #{bill_id} and journal entry #{entry_id}.")
                    st.rerun()
                except Exception as exc:
                    logger.exception("Saving failed for %s", extraction.source_file_name)
                    st.error(str(exc))


def render_bill_editor(extraction: BillExtraction, key_prefix: str) -> BillExtraction:
    cols = st.columns(4)
    vendor = cols[0].text_input("Vendor", value=extraction.vendor_name, key=f"{key_prefix}_vendor")
    invoice_number = cols[1].text_input("Invoice number", value=extraction.invoice_number or "", key=f"{key_prefix}_invoice")
    invoice_date = cols[2].date_input("Invoice date", value=extraction.invoice_date or date.today(), key=f"{key_prefix}_date")
    gross_amount = as_money(cols[3].text_input("Gross amount", value=str(extraction.gross_amount), key=f"{key_prefix}_gross"))

    tax_cols = st.columns(2)
    tax_amount = as_money(tax_cols[0].text_input("Tax amount", value=str(extraction.tax_amount), key=f"{key_prefix}_tax"))
    taxable_amount = as_money(tax_cols[1].text_input("Taxable amount", value=str(max(gross_amount - tax_amount, Decimal('0.00'))), key=f"{key_prefix}_taxable"))

    extraction.vendor_name = vendor.strip() or "Unknown Vendor"
    extraction.invoice_number = invoice_number.strip() or None
    extraction.invoice_date = invoice_date
    extraction.gross_amount = gross_amount
    extraction.tax_amount = tax_amount
    extraction.taxable_amount = taxable_amount
    return extraction


def render_journal_preview(journal_entry) -> None:
    rows = [
        {"Account": line.account_name, "Side": line.side.value.title(), "Amount": float(line.amount)}
        for line in journal_entry.lines
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption(f"Debits: {journal_entry.total_debits} | Credits: {journal_entry.total_credits}")
    st.text_area("Narration", value=journal_entry.narration, height=80, disabled=True)


def render_processor(user: User, entity: Entity, mappings: dict[str, str]) -> None:
    st.header("Upload & Process Bills")
    st.write(f"Active entity: **{entity.name}**")
    uploaded_files = st.file_uploader("Upload PDF bills or ZIP archives", type=["pdf", "zip"], accept_multiple_files=True)
    directory_path = st.text_input("Or process a server-side directory path")

    if st.button("Process bills", type="primary"):
        pdf_paths: list[Path] = []
        try:
            for uploaded_file in uploaded_files or []:
                saved_path = upload_processor.save_uploaded_file(uploaded_file, uploaded_file.name)
                pdf_paths.extend(upload_processor.collect_pdfs([saved_path]))
            if directory_path.strip():
                pdf_paths.extend(upload_processor.collect_pdfs_from_path(directory_path.strip()))
            pdf_paths = sorted(set(pdf_paths))
            if not pdf_paths:
                st.warning("No PDF files found to process.")
                return
            logger.info("Processing %s PDFs for entity %s", len(pdf_paths), entity.id)
            prepare_pending_files(entity, pdf_paths)
        except Exception as exc:
            logger.exception("Batch processing failed")
            st.error(str(exc))
    render_pending_bills(user, entity, mappings)


def render_history(entity: Entity) -> None:
    st.header("History & Export")
    cols = st.columns(5)
    vendor = cols[0].text_input("Vendor contains")
    start_date = cols[1].date_input("From date", value=None)
    end_date = cols[2].date_input("To date", value=None)
    min_amount_text = cols[3].text_input("Min amount")
    max_amount_text = cols[4].text_input("Max amount")

    min_amount = as_money(min_amount_text) if min_amount_text else None
    max_amount = as_money(max_amount_text) if max_amount_text else None
    records = record_service.search_history(entity, vendor, min_amount, max_amount, start_date, end_date)

    if not records:
        st.info("No records found for the selected filters.")
        return

    df = pd.DataFrame(records)
    st.dataframe(df, use_container_width=True, hide_index=True)

    entry_df = exporter.entries_to_dataframe(records, record_service.get_entry_lines)
    st.download_button(
        "Download Tally CSV",
        entry_df.to_csv(index=False).encode("utf-8"),
        file_name=f"{entity.name}_tally_journals.csv",
        mime="text/csv",
    )
    tally_xml = exporter.entries_to_tally_xml(entity.name, records, record_service.get_entry_lines)
    st.download_button(
        "Download Tally XML",
        tally_xml.encode("utf-8"),
        file_name=f"{entity.name}_tally_journals.xml",
        mime="application/xml",
    )


def main() -> None:
    user = current_user()
    if user is None:
        render_auth()
        return

    entity = render_entity_selector(user)
    if entity is None:
        return
    mappings = render_account_mappings(entity)

    st.title("Bill PDF to Tally Journal Entries")
    processor_tab, history_tab, docs_tab = st.tabs(["Process bills", "History & export", "Session notes"])
    with processor_tab:
        render_processor(user, entity, mappings)
    with history_tab:
        render_history(entity)
    with docs_tab:
        render_session_notes()


def render_session_notes() -> None:
    st.subheader("No persistent storage")
    st.write(
        "Users, entities, mappings, bills, and journal entries are stored only in Streamlit session state. "
        "Restarting the app or clearing the browser session removes them."
    )
    st.subheader("Record separation")
    st.write(
        "Every bill, account mapping, and journal entry is linked to an entity id. "
        "The authenticated user must be mapped to that entity before records are shown or exported."
    )
    st.subheader("Journal integrity")
    st.write("Entries are saved only when total debits equal total credits to two decimal places.")


if __name__ == "__main__":
    main()
