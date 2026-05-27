// ─── Auth ────────────────────────────────────────────────────────
export interface LoginRequest { email: string; password: string }
export interface RegisterRequest { email: string; full_name: string; password: string; role?: string }
export interface TokenResponse { access_token: string; refresh_token: string; token_type: string; expires_in: number }
export interface UserResponse {
  id: string; email: string; full_name: string; role: "admin" | "accountant" | "viewer";
  is_active: boolean; is_verified: boolean; created_at: string;
}

// ─── Pagination ──────────────────────────────────────────────────
export interface PaginatedResponse<T> {
  items: T[]; total: number; page: number; page_size: number; pages: number;
}

// ─── Invoices ────────────────────────────────────────────────────
export type InvoiceStatus = "uploaded" | "queued" | "processing" | "extracted" | "validated" | "reconciled" | "failed" | "duplicate"
export type PaymentStatus = "pending" | "paid" | "overdue" | "partial" | "cancelled"

export interface InvoiceItem {
  id: string; description: string; hsn_sac_code: string | null;
  quantity: string | null; unit: string | null; unit_price: string | null;
  discount_amount: string | null; tax_rate: string | null; tax_amount: string | null;
  line_total: string | null; sequence_number: number;
}
export interface Invoice {
  id: string; original_filename: string; status: InvoiceStatus; payment_status: PaymentStatus;
  invoice_number: string | null; invoice_date: string | null; due_date: string | null;
  vendor_id: string | null; vendor_name: string | null;
  subtotal: string | null; cgst_amount: string | null; sgst_amount: string | null;
  igst_amount: string | null; total_tax: string | null; total_amount: string | null;
  currency: string; ocr_confidence: number | null; extraction_notes: string | null;
  uploaded_by: string; created_at: string; updated_at: string;
}
export interface InvoiceDetail extends Invoice {
  line_items: InvoiceItem[]; file_size_bytes: number | null; checksum: string | null;
}
export interface InvoiceUpdate {
  invoice_number?: string; invoice_date?: string; due_date?: string;
  vendor_id?: string; payment_status?: PaymentStatus;
  subtotal?: string; total_amount?: string;
}
export interface ProcessingJob {
  id: string; invoice_id: string; job_type: string; status: string;
  attempt_count: number; started_at: string | null; completed_at: string | null;
  error_message: string | null;
}

// ─── Vendors ────────────────────────────────────────────────────
export interface Vendor {
  id: string; name: string; gst_number: string | null; pan_number: string | null;
  email: string | null; phone: string | null; address: string | null;
  is_active: boolean; created_at: string;
}
export interface VendorCreate { name: string; gst_number?: string; email?: string; phone?: string; address?: string }

// ─── Reconciliation ──────────────────────────────────────────────
export type ReconciliationStatus = "pending" | "matched" | "partial_match" | "unmatched" | "discrepancy" | "duplicate" | "manually_resolved"
export type DiscrepancyType = "amount_mismatch" | "duplicate_invoice" | "vendor_mismatch" | "date_mismatch" | "missing_reference" | "tax_mismatch"

export interface ReconciliationRecord {
  id: string; invoice_id: string; status: ReconciliationStatus;
  discrepancy_type: DiscrepancyType | null; confidence_score: number | null;
  reference_document_id: string | null; reference_document_type: string | null;
  expected_amount: string | null; actual_amount: string | null;
  discrepancy_amount: string | null; tolerance_applied: string | null;
  notes: string | null; resolution_notes: string | null;
  matched_by: string | null; created_at: string; updated_at: string;
}
export interface ReconciliationRequest {
  invoice_id: string; reference_document_id?: string; reference_document_type?: string;
  expected_amount?: string; notes?: string;
}
export interface ResolveRequest { resolution_notes: string; status: ReconciliationStatus }

// ─── Dashboard ──────────────────────────────────────────────────
export interface InvoiceCountSummary {
  total: number; uploaded: number; processing: number; extracted: number;
  reconciled: number; failed: number; duplicate: number;
}
export interface DiscrepancySummary {
  total_discrepancies: number; unresolved: number; resolved: number;
  total_discrepancy_amount: string; by_type: Record<string, number>;
}
export interface QueueStatus {
  queued_jobs: number; processing_jobs: number; failed_jobs: number;
  completed_today: number; average_processing_time_seconds: number | null;
}
export interface AnalyticsTrend { date: string; invoice_count: number; total_amount: string; reconciled_count: number }
export interface VendorMetric { vendor_id: string; vendor_name: string; invoice_count: number; total_amount: string; discrepancy_count: number }
export interface DashboardOverview {
  invoice_summary: InvoiceCountSummary; discrepancy_summary: DiscrepancySummary;
  queue_status: QueueStatus; top_vendors: VendorMetric[];
  recent_trends: AnalyticsTrend[]; total_processed_amount: string; pending_payment_amount: string;
}

// ─── Audit ──────────────────────────────────────────────────────
export interface AuditLog {
  id: string; event_type: string; user_id: string | null; invoice_id: string | null;
  description: string; metadata: Record<string, unknown> | null;
  ip_address: string | null; created_at: string;
}

// ─── Filters ────────────────────────────────────────────────────
export interface InvoiceFilters {
  status?: InvoiceStatus; payment_status?: PaymentStatus;
  vendor_id?: string; invoice_number?: string;
  date_from?: string; date_to?: string;
  amount_min?: number; amount_max?: number; search?: string;
  page?: number; page_size?: number;
}
export interface AuditFilters {
  user_id?: string; invoice_id?: string; event_type?: string;
  date_from?: string; date_to?: string; page?: number; page_size?: number;
}
