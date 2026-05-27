"use client"
import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Upload, Search, Filter, RefreshCw, ChevronLeft, ChevronRight } from "lucide-react"
import { useInvoices } from "@/hooks/useInvoices"
import { InvoiceStatusBadge } from "@/components/invoices/InvoiceStatusBadge"
import { InvoiceUpload } from "@/components/invoices/InvoiceUpload"
import { ConfidenceBar } from "@/components/ui/ConfidenceBar"
import { TableSkeleton } from "@/components/ui/Skeleton"
import { fmtUsd, fmtDate, relativeTime } from "@/lib/utils"
import type { InvoiceFilters, InvoiceStatus } from "@/types/api"

const STATUS_OPTIONS: Array<{ value: InvoiceStatus | ""; label: string }> = [
  { value: "", label: "All statuses" },
  { value: "uploaded", label: "Uploaded" },
  { value: "queued", label: "Queued" },
  { value: "processing", label: "Processing" },
  { value: "extracted", label: "Extracted" },
  { value: "reconciled", label: "Reconciled" },
  { value: "failed", label: "Failed" },
  { value: "duplicate", label: "Duplicate" },
]

export default function InvoicesPage() {
  const [showUpload, setShowUpload] = useState(false)
  const [search, setSearch] = useState("")
  const [status, setStatus] = useState<InvoiceStatus | "">("")
  const [page, setPage] = useState(1)

  const filters: InvoiceFilters = {
    search: search || undefined,
    status: status || undefined,
    page,
    page_size: 20,
  }

  const { data, isLoading, refetch, isRefetching } = useInvoices(filters)

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-title">Invoice Inbox</div>
          <div className="page-subtitle">
            {data ? `${data.total.toLocaleString()} invoices` : "Loading…"}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-sm" onClick={() => refetch()} disabled={isRefetching}>
            <RefreshCw size={12} style={isRefetching ? { animation: "spin 1s linear infinite" } : {}}/>
            Refresh
          </button>
          <button className="btn btn-sm btn-primary" onClick={() => setShowUpload(true)}>
            <Upload size={13}/>
            Upload Invoice
          </button>
        </div>
      </div>

      {/* Upload modal */}
      <AnimatePresence>
        {showUpload && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center" }}
            onClick={(e) => { if (e.target === e.currentTarget) setShowUpload(false) }}>
            <motion.div initial={{ opacity: 0, scale: 0.95, y: 8 }} animate={{ opacity: 1, scale: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95 }}
              style={{ background: "var(--bg-2)", border: "1px solid var(--border-strong)", borderRadius: 16, boxShadow: "var(--sh-3)" }}>
              <InvoiceUpload onClose={() => setShowUpload(false)}/>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Filters */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16, alignItems: "center" }}>
        <div className="search-bar" style={{ maxWidth: 320 }}>
          <Search size={13}/>
          <input placeholder="Invoice # or vendor…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }}/>
        </div>
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value as InvoiceStatus | ""); setPage(1) }}
          style={{
            height: 32, padding: "0 10px", background: "var(--bg-3)",
            border: "1px solid var(--border)", borderRadius: 8,
            fontSize: 12.5, color: "var(--text-1)", outline: "none", cursor: "pointer",
          }}
        >
          {STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <div style={{ marginLeft: "auto", fontSize: 11.5, color: "var(--text-3)" }}>
          {data && `Page ${data.page} of ${data.pages}`}
        </div>
      </div>

      {/* Table */}
      <div className="card">
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Invoice #</th>
                <th>Vendor</th>
                <th>Date</th>
                <th>Amount</th>
                <th>Status</th>
                <th>Payment</th>
                <th>Confidence</th>
                <th>Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td colSpan={8} style={{ padding: 0 }}><TableSkeleton rows={8}/></td></tr>
              ) : data?.items.length === 0 ? (
                <tr>
                  <td colSpan={8} style={{ textAlign: "center", padding: "40px 16px", color: "var(--text-3)" }}>
                    No invoices found
                  </td>
                </tr>
              ) : data?.items.map((inv, i) => (
                <motion.tr key={inv.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.02 }}>
                  <td>
                    <span className="mono" style={{ fontSize: 12, color: "var(--text-2)" }}>
                      {inv.invoice_number ?? <span style={{ color: "var(--text-4)" }}>Extracting…</span>}
                    </span>
                  </td>
                  <td style={{ maxWidth: 200 }}>
                    <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "block" }}>
                      {inv.vendor_name ?? <span style={{ color: "var(--text-4)" }}>Unknown</span>}
                    </span>
                  </td>
                  <td><span className="mono" style={{ fontSize: 12 }}>{fmtDate(inv.invoice_date)}</span></td>
                  <td>
                    <span className="mono" style={{ fontSize: 12.5, fontWeight: 500 }}>
                      {inv.total_amount ? fmtUsd(parseFloat(inv.total_amount)) : "—"}
                    </span>
                  </td>
                  <td><InvoiceStatusBadge status={inv.status}/></td>
                  <td><InvoiceStatusBadge status={inv.payment_status}/></td>
                  <td>
                    {inv.ocr_confidence != null
                      ? <ConfidenceBar value={inv.ocr_confidence} width={52}/>
                      : <span style={{ fontSize: 11, color: "var(--text-4)" }}>—</span>
                    }
                  </td>
                  <td><span style={{ fontSize: 11.5, color: "var(--text-3)" }}>{relativeTime(inv.created_at)}</span></td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {data && data.pages > 1 && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 16px", borderTop: "1px solid var(--divider)", justifyContent: "flex-end" }}>
            <button className="btn btn-sm" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}>
              <ChevronLeft size={13}/>
            </button>
            <span style={{ fontSize: 12, color: "var(--text-3)" }}>{page} / {data.pages}</span>
            <button className="btn btn-sm" onClick={() => setPage((p) => Math.min(data.pages, p + 1))} disabled={page === data.pages}>
              <ChevronRight size={13}/>
            </button>
          </div>
        )}
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
