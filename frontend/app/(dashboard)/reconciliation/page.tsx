"use client"
import { useState } from "react"
import { motion } from "framer-motion"
import { CheckCircle, AlertTriangle, XCircle, ChevronLeft, ChevronRight } from "lucide-react"
import { useReconciliation, useResolve } from "@/hooks/useReconciliation"
import { ConfidenceBar } from "@/components/ui/ConfidenceBar"
import { Badge } from "@/components/ui/Badge"
import { TableSkeleton } from "@/components/ui/Skeleton"
import { fmtUsd, fmtDate, relativeTime } from "@/lib/utils"
import type { ReconciliationRecord, ReconciliationStatus } from "@/types/api"
import toast from "react-hot-toast"

// Static demo pairs (shown when API has no data yet)
const DEMO_PAIRS = [
  { id: "1", invoice_id: "inv-1", status: "matched" as const, confidence_score: 1.0, actual_amount: "4820.00", discrepancy_amount: null, notes: null, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), discrepancy_type: null, expected_amount: "4820.00", matched_by: null, reference_document_id: "TX-447921", reference_document_type: "bank", resolution_notes: null, tolerance_applied: null },
  { id: "2", invoice_id: "inv-2", status: "discrepancy" as const, confidence_score: 0.81, actual_amount: "720.00", discrepancy_amount: "-48.20", discrepancy_type: "amount_mismatch" as const, notes: "Figma invoice delta $48.20", created_at: new Date().toISOString(), updated_at: new Date().toISOString(), expected_amount: "671.80", matched_by: null, reference_document_id: "TX-447902", reference_document_type: "bank", resolution_notes: null, tolerance_applied: "6.72" },
  { id: "3", invoice_id: "inv-3", status: "matched" as const, confidence_score: 0.99, actual_amount: "2200.00", discrepancy_amount: null, notes: null, created_at: new Date().toISOString(), updated_at: new Date().toISOString(), discrepancy_type: null, expected_amount: "2200.00", matched_by: null, reference_document_id: "TX-447895", reference_document_type: "bank", resolution_notes: null, tolerance_applied: null },
  { id: "4", invoice_id: "inv-4", status: "discrepancy" as const, confidence_score: 0.74, actual_amount: "4248.75", discrepancy_amount: "200.00", discrepancy_type: "amount_mismatch" as const, notes: "Twilio: bank shows $200 over", created_at: new Date().toISOString(), updated_at: new Date().toISOString(), expected_amount: "4448.75", matched_by: null, reference_document_id: "TX-447874", reference_document_type: "bank", resolution_notes: null, tolerance_applied: "44.49" },
  { id: "5", invoice_id: "inv-5", status: "unmatched" as const, confidence_score: 0.0, actual_amount: null, discrepancy_amount: null, notes: "No invoice found for refund", created_at: new Date().toISOString(), updated_at: new Date().toISOString(), discrepancy_type: "missing_reference" as const, expected_amount: "1840.00", matched_by: null, reference_document_id: "TX-447883", reference_document_type: "bank", resolution_notes: null, tolerance_applied: null },
]

const STATUS_ICON = {
  matched: <CheckCircle size={14} style={{ color: "var(--success)" }}/>,
  discrepancy: <AlertTriangle size={14} style={{ color: "var(--danger)" }}/>,
  unmatched: <XCircle size={14} style={{ color: "var(--text-3)" }}/>,
  partial_match: <AlertTriangle size={14} style={{ color: "var(--warning)" }}/>,
  duplicate: <AlertTriangle size={14} style={{ color: "var(--warning)" }}/>,
  manually_resolved: <CheckCircle size={14} style={{ color: "var(--info)" }}/>,
  pending: <AlertTriangle size={14} style={{ color: "var(--text-3)" }}/>,
}

const STATUS_BADGE: Record<string, "success" | "danger" | "warning" | "info" | "default"> = {
  matched: "success", discrepancy: "danger", unmatched: "default",
  partial_match: "warning", duplicate: "warning", manually_resolved: "info", pending: "default",
}

function ResolveModal({ record, onClose }: { record: ReconciliationRecord; onClose: () => void }) {
  const [notes, setNotes] = useState("")
  const [newStatus, setNewStatus] = useState<ReconciliationStatus>("manually_resolved")
  const { mutate: resolve, isPending } = useResolve()

  return (
    <div style={{ padding: 24, minWidth: 380 }}>
      <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text-1)", marginBottom: 4 }}>Resolve Discrepancy</div>
      <div style={{ fontSize: 12, color: "var(--text-3)", marginBottom: 20 }}>
        Record {record.id.slice(0, 8)}… · {fmtUsd(parseFloat(record.discrepancy_amount ?? "0"))} delta
      </div>
      <div style={{ marginBottom: 12 }}>
        <label style={{ fontSize: 11.5, color: "var(--text-3)", display: "block", marginBottom: 5 }}>Resolution status</label>
        <select value={newStatus} onChange={(e) => setNewStatus(e.target.value as ReconciliationStatus)}
          style={{ width: "100%", height: 34, padding: "0 10px", background: "var(--bg-3)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13, color: "var(--text-1)", outline: "none" }}>
          <option value="manually_resolved">Manually resolved</option>
          <option value="matched">Mark as matched</option>
          <option value="unmatched">Mark as unmatched</option>
        </select>
      </div>
      <div style={{ marginBottom: 16 }}>
        <label style={{ fontSize: 11.5, color: "var(--text-3)", display: "block", marginBottom: 5 }}>Resolution notes</label>
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={3}
          placeholder="Explain the resolution…"
          style={{ width: "100%", padding: "8px 10px", background: "var(--bg-3)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13, color: "var(--text-1)", outline: "none", resize: "vertical" }}/>
      </div>
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
        <button className="btn btn-sm" onClick={onClose}>Cancel</button>
        <button className="btn btn-sm btn-primary" disabled={!notes || isPending}
          onClick={() => resolve({ id: record.id, data: { resolution_notes: notes, status: newStatus } }, { onSuccess: onClose })}>
          {isPending ? "Saving…" : "Confirm"}
        </button>
      </div>
    </div>
  )
}

export default function ReconciliationPage() {
  const [page, setPage] = useState(1)
  const [filterStatus, setFilterStatus] = useState("")
  const [resolving, setResolving] = useState<ReconciliationRecord | null>(null)
  const { data, isLoading } = useReconciliation({ status: filterStatus || undefined, page, page_size: 20 })

  const records = data?.items.length ? data.items : DEMO_PAIRS

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-title">Reconciliation</div>
          <div className="page-subtitle">
            {data ? `${data.total} records` : `${DEMO_PAIRS.length} demo records`}
            {data?.items.some((r) => r.status === "discrepancy") && (
              <span style={{ marginLeft: 12, color: "var(--danger)" }}>
                · {data.items.filter((r) => r.status === "discrepancy").length} open exceptions
              </span>
            )}
          </div>
        </div>
        <select value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}
          style={{ height: 32, padding: "0 10px", background: "var(--bg-3)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12.5, color: "var(--text-1)", outline: "none" }}>
          <option value="">All statuses</option>
          <option value="matched">Matched</option>
          <option value="discrepancy">Discrepancy</option>
          <option value="unmatched">Unmatched</option>
          <option value="manually_resolved">Resolved</option>
        </select>
      </div>

      {/* Resolve modal */}
      {resolving && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center" }}
          onClick={(e) => { if (e.target === e.currentTarget) setResolving(null) }}>
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }}
            style={{ background: "var(--bg-2)", border: "1px solid var(--border-strong)", borderRadius: 16 }}>
            <ResolveModal record={resolving} onClose={() => setResolving(null)}/>
          </motion.div>
        </div>
      )}

      <div className="card">
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Invoice ref</th>
                <th>Bank ref</th>
                <th>Expected</th>
                <th>Actual</th>
                <th>Delta</th>
                <th>Confidence</th>
                <th>Date</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td colSpan={9} style={{ padding: 0 }}><TableSkeleton rows={6}/></td></tr>
              ) : records.map((rec, i) => {
                const delta = rec.discrepancy_amount ? parseFloat(rec.discrepancy_amount) : null
                return (
                  <motion.tr key={rec.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.03 }}>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        {STATUS_ICON[rec.status] ?? null}
                        <Badge variant={STATUS_BADGE[rec.status] ?? "default"}>
                          {rec.status.replace(/_/g, " ")}
                        </Badge>
                      </div>
                    </td>
                    <td><span className="mono" style={{ fontSize: 11.5, color: "var(--text-3)" }}>{rec.invoice_id.slice(0, 8)}…</span></td>
                    <td><span className="mono" style={{ fontSize: 11.5, color: "var(--text-3)" }}>{rec.reference_document_id ?? "—"}</span></td>
                    <td><span className="mono">{rec.expected_amount ? fmtUsd(parseFloat(rec.expected_amount)) : "—"}</span></td>
                    <td><span className="mono">{rec.actual_amount ? fmtUsd(parseFloat(rec.actual_amount)) : "—"}</span></td>
                    <td>
                      {delta != null
                        ? <span className="mono" style={{ color: delta < 0 ? "var(--danger)" : "var(--warning)", fontWeight: 500 }}>
                            {delta > 0 ? "+" : ""}{fmtUsd(delta)}
                          </span>
                        : <span style={{ color: "var(--text-4)" }}>—</span>
                      }
                    </td>
                    <td>
                      {rec.confidence_score != null
                        ? <ConfidenceBar value={rec.confidence_score} width={52}/>
                        : "—"
                      }
                    </td>
                    <td><span style={{ fontSize: 11.5, color: "var(--text-3)" }}>{relativeTime(rec.created_at)}</span></td>
                    <td>
                      {rec.status === "discrepancy" && (
                        <button className="btn btn-sm" onClick={() => setResolving(rec as ReconciliationRecord)}>
                          Resolve
                        </button>
                      )}
                    </td>
                  </motion.tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {data && data.pages > 1 && (
          <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "10px 16px", borderTop: "1px solid var(--divider)", justifyContent: "flex-end" }}>
            <button className="btn btn-sm" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1}><ChevronLeft size={13}/></button>
            <span style={{ fontSize: 12, color: "var(--text-3)" }}>{page} / {data.pages}</span>
            <button className="btn btn-sm" onClick={() => setPage((p) => Math.min(data.pages, p + 1))} disabled={page === data.pages}><ChevronRight size={13}/></button>
          </div>
        )}
      </div>
    </div>
  )
}
