"use client"
import { useState } from "react"
import { motion } from "framer-motion"
import { Search, ChevronLeft, ChevronRight } from "lucide-react"
import { useAuditLogs } from "@/hooks/useAudit"
import { TableSkeleton } from "@/components/ui/Skeleton"
import { relativeTime } from "@/lib/utils"

const EVENT_COLORS: Record<string, string> = {
  invoice_uploaded: "var(--accent)",
  invoice_processing_completed: "var(--success)",
  invoice_processing_failed: "var(--danger)",
  reconciliation_matched: "var(--success)",
  reconciliation_discrepancy: "var(--danger)",
  reconciliation_resolved: "var(--info)",
  user_login: "var(--c6)",
  user_created: "var(--c6)",
  invoice_duplicate_detected: "var(--warning)",
}

// Demo events shown when API returns empty
const DEMO_EVENTS = [
  { id: "1", event_type: "reconciliation_matched",       user_id: null, invoice_id: null, description: "INV-29481 → PO-1124 auto-matched (conf 0.97)",              metadata: null, ip_address: null, created_at: new Date(Date.now() - 2000).toISOString() },
  { id: "2", event_type: "invoice_processing_completed", user_id: null, invoice_id: null, description: "OCR extraction completed for 12 documents",                  metadata: { confidence: 0.94 }, ip_address: null, created_at: new Date(Date.now() - 60000).toISOString() },
  { id: "3", event_type: "reconciliation_discrepancy",   user_id: null, invoice_id: null, description: "INV-29476 flagged — amount delta $48.20",                    metadata: null, ip_address: null, created_at: new Date(Date.now() - 120000).toISOString() },
  { id: "4", event_type: "invoice_uploaded",             user_id: null, invoice_id: null, description: "Invoice uploaded: stripe_atlas_q2.pdf (182 KB)",             metadata: null, ip_address: "10.0.1.4", created_at: new Date(Date.now() - 300000).toISOString() },
  { id: "5", event_type: "reconciliation_resolved",      user_id: null, invoice_id: null, description: "Discrepancy manually resolved — FX tolerance approved",       metadata: null, ip_address: null, created_at: new Date(Date.now() - 600000).toISOString() },
  { id: "6", event_type: "user_login",                   user_id: null, invoice_id: null, description: "User signed in: aanya@nasher.co",                            metadata: null, ip_address: "10.0.1.2", created_at: new Date(Date.now() - 3600000).toISOString() },
  { id: "7", event_type: "invoice_processing_completed", user_id: null, invoice_id: null, description: "Batch #417 OCR completed — 28 invoices",                     metadata: { confidence: 0.91 }, ip_address: null, created_at: new Date(Date.now() - 7200000).toISOString() },
  { id: "8", event_type: "invoice_duplicate_detected",   user_id: null, invoice_id: null, description: "Duplicate detected: INV-29420 matches existing INV-29380",   metadata: null, ip_address: null, created_at: new Date(Date.now() - 10800000).toISOString() },
]

export default function AuditPage() {
  const [search, setSearch] = useState("")
  const [page, setPage] = useState(1)
  const [eventType, setEventType] = useState("")

  const { data, isLoading } = useAuditLogs({ page, page_size: 50, event_type: eventType || undefined })
  const events = data?.items.length ? data.items : DEMO_EVENTS

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-title">Audit Timeline</div>
          <div className="page-subtitle">
            Immutable event log · {data ? `${data.total.toLocaleString()} events` : `${DEMO_EVENTS.length} demo events`}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span className="pulse" style={{ width: 5, height: 5 }}/>
          <span style={{ fontSize: 11, color: "var(--text-3)" }}>Live updates</span>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <div className="search-bar" style={{ maxWidth: 300 }}>
          <Search size={13}/>
          <input placeholder="Search events…" value={search} onChange={(e) => setSearch(e.target.value)}/>
        </div>
        <select value={eventType} onChange={(e) => setEventType(e.target.value)}
          style={{ height: 32, padding: "0 10px", background: "var(--bg-3)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12.5, color: "var(--text-1)", outline: "none" }}>
          <option value="">All events</option>
          <option value="invoice_uploaded">Invoice uploaded</option>
          <option value="invoice_processing_completed">OCR completed</option>
          <option value="invoice_processing_failed">Processing failed</option>
          <option value="reconciliation_matched">Reconciliation matched</option>
          <option value="reconciliation_discrepancy">Discrepancy flagged</option>
          <option value="reconciliation_resolved">Discrepancy resolved</option>
          <option value="user_login">User login</option>
        </select>
      </div>

      {/* Timeline */}
      <div className="card">
        {isLoading ? (
          <TableSkeleton rows={8}/>
        ) : (
          <div style={{ position: "relative" }}>
            {/* Timeline line */}
            <div style={{ position: "absolute", left: 31, top: 0, bottom: 0, width: 1, background: "var(--divider)" }}/>

            {events
              .filter((e) => !search || e.description.toLowerCase().includes(search.toLowerCase()) || e.event_type.includes(search.toLowerCase()))
              .map((event, i) => {
                const color = EVENT_COLORS[event.event_type] ?? "var(--text-3)"
                const label = event.event_type.replace(/_/g, " ")
                return (
                  <motion.div key={event.id} initial={{ opacity: 0, x: -4 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.025 }}
                    style={{ display: "flex", gap: 16, padding: "12px 16px", position: "relative" }}>
                    {/* Dot */}
                    <div style={{
                      width: 30, height: 30, borderRadius: "50%",
                      background: "var(--bg-3)", border: "1px solid var(--border)",
                      display: "grid", placeItems: "center", flexShrink: 0, position: "relative", zIndex: 1,
                    }}>
                      <div style={{ width: 8, height: 8, borderRadius: "50%", background: color }}/>
                    </div>

                    {/* Content */}
                    <div style={{ flex: 1, minWidth: 0, paddingTop: 4 }}>
                      <div style={{ display: "flex", gap: 8, alignItems: "baseline", marginBottom: 2 }}>
                        <span style={{ fontSize: 10.5, fontWeight: 500, color, textTransform: "capitalize", letterSpacing: "0.02em" }}>{label}</span>
                        <span style={{ fontSize: 11, color: "var(--text-4)" }}>{relativeTime(event.created_at)}</span>
                        {event.ip_address && (
                          <span className="mono" style={{ fontSize: 10, color: "var(--text-4)", marginLeft: "auto" }}>{event.ip_address}</span>
                        )}
                      </div>
                      <div style={{ fontSize: 12.5, color: "var(--text-1)" }}>{event.description}</div>
                      {event.metadata && Object.keys(event.metadata).length > 0 && (
                        <div style={{ display: "flex", gap: 12, marginTop: 4 }}>
                          {Object.entries(event.metadata).map(([k, v]) => (
                            <span key={k} style={{ fontSize: 11, color: "var(--text-3)" }}>
                              <span style={{ color: "var(--text-4)" }}>{k}: </span>
                              <span className="mono">{String(v)}</span>
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </motion.div>
                )
              })}
          </div>
        )}

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
