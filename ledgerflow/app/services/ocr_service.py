"""OCR extraction service.

Wraps pytesseract + pdf2image to extract structured fields from invoice PDFs.
Designed to run inside an RQ worker (blocking I/O, CPU-bound).
"""
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ExtractedInvoiceData:
    invoice_number: str | None = None
    vendor_name: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    subtotal: Decimal | None = None
    cgst_amount: Decimal | None = None
    sgst_amount: Decimal | None = None
    igst_amount: Decimal | None = None
    total_tax: Decimal | None = None
    total_amount: Decimal | None = None
    currency: str = "INR"
    line_items: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    raw_text: str = ""
    notes: list[str] = field(default_factory=list)


class OCRService:
    def extract_from_pdf(self, pdf_bytes: bytes) -> ExtractedInvoiceData:
        try:
            import pytesseract
            from pdf2image import convert_from_bytes

            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
            images = convert_from_bytes(pdf_bytes, dpi=300, first_page=1, last_page=3)
        except Exception as exc:
            logger.warning("ocr_conversion_failed", error=str(exc))
            return ExtractedInvoiceData(notes=[f"PDF conversion error: {exc}"])

        full_text = ""
        confidences: list[float] = []

        for img in images:
            try:
                import pytesseract

                data = pytesseract.image_to_data(
                    img,
                    lang=settings.OCR_LANGUAGE,
                    output_type=pytesseract.Output.DICT,
                )
                page_text = pytesseract.image_to_string(img, lang=settings.OCR_LANGUAGE)
                full_text += page_text + "\n"

                valid_confs = [int(c) for c in data["conf"] if str(c).isdigit() and int(c) >= 0]
                if valid_confs:
                    confidences.append(sum(valid_confs) / len(valid_confs))
            except Exception as exc:
                logger.warning("page_ocr_failed", error=str(exc))

        avg_confidence = sum(confidences) / len(confidences) / 100 if confidences else 0.0
        result = self._parse_text(full_text)
        result.confidence = round(avg_confidence, 4)
        result.raw_text = full_text[:10000]
        return result

    def _parse_text(self, text: str) -> ExtractedInvoiceData:
        data = ExtractedInvoiceData()
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

        data.invoice_number = self._extract_invoice_number(text)
        data.vendor_name = self._extract_vendor_name(lines)
        data.invoice_date = self._extract_date(text, "invoice")
        data.due_date = self._extract_date(text, "due")
        data.total_amount = self._extract_amount(text, r"(?:grand\s*total|total\s*amount|amount\s*due)[^\d]*(\d[\d,]*\.?\d*)")
        data.subtotal = self._extract_amount(text, r"(?:sub[\s\-]?total|taxable\s*amount)[^\d]*(\d[\d,]*\.?\d*)")
        data.cgst_amount = self._extract_amount(text, r"cgst[^\d]*(\d[\d,]*\.?\d*)")
        data.sgst_amount = self._extract_amount(text, r"sgst[^\d]*(\d[\d,]*\.?\d*)")
        data.igst_amount = self._extract_amount(text, r"igst[^\d]*(\d[\d,]*\.?\d*)")

        tax_parts = [a for a in [data.cgst_amount, data.sgst_amount, data.igst_amount] if a]
        if tax_parts:
            data.total_tax = sum(tax_parts)

        data.line_items = self._extract_line_items(lines)
        return data

    def _extract_invoice_number(self, text: str) -> str | None:
        patterns = [
            r"invoice\s*(?:no|number|#)[.:\s]*([A-Z0-9\-/]+)",
            r"inv[.:\s]*([A-Z0-9\-/]{3,20})",
            r"bill\s*no[.:\s]*([A-Z0-9\-/]+)",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return None

    def _extract_vendor_name(self, lines: list[str]) -> str | None:
        for line in lines[:5]:
            if len(line) > 3 and not any(kw in line.lower() for kw in ("invoice", "tax", "gst")):
                return line[:100]
        return None

    def _extract_date(self, text: str, kind: str) -> date | None:
        from dateutil import parser as dateparser

        if kind == "invoice":
            pats = [r"(?:invoice\s*date|date)[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})"]
        else:
            pats = [r"(?:due\s*date|payment\s*due)[:\s]*(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})"]

        for pat in pats:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                try:
                    return dateparser.parse(m.group(1), dayfirst=True).date()
                except Exception:
                    pass
        return None

    def _extract_amount(self, text: str, pattern: str) -> Decimal | None:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                raw = m.group(1).replace(",", "")
                return Decimal(raw)
            except InvalidOperation:
                pass
        return None

    def _extract_line_items(self, lines: list[str]) -> list[dict]:
        items = []
        in_table = False
        for i, line in enumerate(lines):
            if re.search(r"description|particulars|item\s*name", line, re.IGNORECASE):
                in_table = True
                continue
            if in_table and re.search(r"(?:sub[\s\-]?total|grand\s*total)", line, re.IGNORECASE):
                break
            if in_table and len(line) > 5:
                amount_match = re.search(r"(\d[\d,]*\.?\d*)\s*$", line)
                if amount_match:
                    try:
                        line_total = Decimal(amount_match.group(1).replace(",", ""))
                        description = line[: amount_match.start()].strip()
                        if description:
                            items.append({
                                "description": description,
                                "line_total": str(line_total),
                                "sequence_number": len(items),
                            })
                    except InvalidOperation:
                        pass
        return items[:50]
