"""Tally XML export -- dry-run only (docs/architecture/08-integrations.md §6).

No live connector, no per-tenant mapping config table, no network call: this
is the pure, testable core of what a real Tally push would eventually build
on. ``build_tally_xml`` is a pure function -- same invoice in, byte-identical
XML out -- which is exactly what makes "dry run" trustworthy: the accountant
reviewing it sees precisely what a real push would send, nothing hidden
behind a network round-trip.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring

from sqlalchemy.orm import Session

from app.core.events import DomainEvent, event_bus
from app.core.exceptions import ValidationError
from app.models.invoice import Invoice, InvoiceStatus
from app.models.user import User
from app.repositories.invoice_repository import InvoiceRepository

# Hardcoded default voucher/ledger mapping. A real per-tenant config table
# (integration_configs in the architecture doc) is future work; this is the
# pure-function core that config would eventually parameterize.
DEFAULT_VOUCHER_TYPE = "Purchase"
DEFAULT_VENDOR_LEDGER = "Sundry Creditors"
DEFAULT_EXPENSE_LEDGER = "Purchase Accounts"
DEFAULT_CGST_LEDGER = "CGST"
DEFAULT_SGST_LEDGER = "SGST"
DEFAULT_IGST_LEDGER = "IGST"

# Only a fully reconciled invoice is trustworthy enough to export -- exporting
# an unreconciled figure to the books of record is exactly the kind of mistake
# a dry-run screen exists to prevent.
EXPORTABLE_STATUSES = (InvoiceStatus.RECONCILED,)


@dataclass(frozen=True)
class TallyExportResult:
    invoice_id: uuid.UUID
    voucher_type: str
    narration: str
    xml: str
    generated_at: datetime


def build_tally_xml(invoice: Invoice) -> tuple[str, str]:
    """Pure function: same invoice -> byte-identical XML. No I/O, no DB writes.

    Returns ``(narration, xml)``.
    """
    if invoice.total_amount is None:
        raise ValidationError("Invoice has no total_amount to export")

    vendor_name = invoice.vendor.name if invoice.vendor else "Unknown Vendor"
    invoice_ref = invoice.invoice_number or str(invoice.id)
    date_str = invoice.invoice_date.isoformat() if invoice.invoice_date else "unknown date"
    narration = f"Invoice {invoice_ref} dated {date_str} from {vendor_name}"

    envelope = Element("ENVELOPE")
    header = SubElement(envelope, "HEADER")
    SubElement(header, "TALLYREQUEST").text = "Import Data"

    body = SubElement(envelope, "BODY")
    import_data = SubElement(body, "IMPORTDATA")
    request_desc = SubElement(import_data, "REQUESTDESC")
    SubElement(request_desc, "REPORTNAME").text = "Vouchers"
    request_data = SubElement(import_data, "REQUESTDATA")
    message = SubElement(request_data, "TALLYMESSAGE")

    voucher = SubElement(message, "VOUCHER", {"VCHTYPE": DEFAULT_VOUCHER_TYPE, "ACTION": "Create"})
    SubElement(voucher, "DATE").text = (
        invoice.invoice_date.strftime("%Y%m%d") if invoice.invoice_date else ""
    )
    SubElement(voucher, "NARRATION").text = narration
    SubElement(voucher, "VOUCHERTYPENAME").text = DEFAULT_VOUCHER_TYPE
    SubElement(voucher, "PARTYLEDGERNAME").text = vendor_name

    def ledger_entry(name: str, amount: Decimal, *, positive: bool) -> None:
        entry = SubElement(voucher, "ALLLEDGERENTRIES.LIST")
        SubElement(entry, "LEDGERNAME").text = name
        SubElement(entry, "ISDEEMEDPOSITIVE").text = "Yes" if positive else "No"
        signed = amount if positive else -amount
        SubElement(entry, "AMOUNT").text = f"{signed:.2f}"

    # Credit the vendor for the full invoice total; debit expense + tax ledgers.
    ledger_entry(DEFAULT_VENDOR_LEDGER, invoice.total_amount, positive=False)
    expense_amount = invoice.subtotal if invoice.subtotal is not None else invoice.total_amount
    ledger_entry(DEFAULT_EXPENSE_LEDGER, expense_amount, positive=True)
    if invoice.cgst_amount:
        ledger_entry(DEFAULT_CGST_LEDGER, invoice.cgst_amount, positive=True)
    if invoice.sgst_amount:
        ledger_entry(DEFAULT_SGST_LEDGER, invoice.sgst_amount, positive=True)
    if invoice.igst_amount:
        ledger_entry(DEFAULT_IGST_LEDGER, invoice.igst_amount, positive=True)

    raw = tostring(envelope, encoding="unicode")
    xml = minidom.parseString(raw).toprettyxml(indent="  ")
    return narration, xml


class TallyExportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.invoice_repo = InvoiceRepository(db)

    def dry_run(self, invoice_id: uuid.UUID, current_user: User) -> TallyExportResult:
        invoice = self.invoice_repo.get_for_tenant_or_raise(invoice_id, current_user.tenant_id)
        if invoice.status not in EXPORTABLE_STATUSES:
            raise ValidationError(
                f"Invoice must be reconciled before Tally export "
                f"(current status: {invoice.status})"
            )

        narration, xml = build_tally_xml(invoice)
        generated_at = datetime.now(timezone.utc)

        event_bus.publish(
            self.db,
            DomainEvent(
                name="invoice.tally_export_generated",
                aggregate_type="invoice",
                aggregate_id=invoice.id,
                actor_id=current_user.id,
                tenant_id=invoice.tenant_id,
                payload={
                    "description": f"Tally export (dry-run) generated for invoice {invoice_id}",
                    "voucher_type": DEFAULT_VOUCHER_TYPE,
                },
            ),
        )
        self.db.commit()

        return TallyExportResult(
            invoice_id=invoice.id,
            voucher_type=DEFAULT_VOUCHER_TYPE,
            narration=narration,
            xml=xml,
            generated_at=generated_at,
        )
