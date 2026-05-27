"use client"
import { motion, AnimatePresence } from "framer-motion"
import { ConfidenceBar } from "@/components/ui/ConfidenceBar"
import { useQueueStatus } from "@/hooks/useDashboard"
import { fmtNum } from "@/lib/utils"

const STAGE_LABELS: Record<string, string> = {
  queued: "Queued", started: "OCR", completed: "Done", failed: "Failed",
}
const STAGE_COLORS: Record<string, string> = {
  queued: "var(--info)", started: "var(--accent)", completed: "var(--success)", failed: "var(--danger)",
}

// Demo live items (augmented with real queue counts)
const DEMO_ITEMS = [
  { id: "INV-29481", vendor: "Stripe Atlas",  amount: 4820.00,  stage: "started",  confidence: 0.97 },
  { id: "INV-29482", vendor: "AWS",            amount: 18432.55, stage: "started",  confidence: 0.92 },
  { id: "INV-29483", vendor: "Notion Labs",    amount: 1200.00,  stage: "completed",confidence: 0.99 },
  { id: "INV-29484", vendor: "Datadog",        amount: 7894.20,  stage: "started",  confidence: 0.84 },
  { id: "INV-29485", vendor: "Linear",         amount: 480.00,   stage: "queued",   confidence: 0.95 },
  { id: "INV-29486", vendor: "Vercel",         amount: 2200.00,  stage: "completed",confidence: 0.99 },
]

export function LiveQueue() {
  const { data: queue } = useQueueStatus()

  return (
    <div>
      <div className="card-header">
        <span className="card-title">Processing Queue</span>
        <div style={{ display: "flex", gap: 12, fontSize: 11, color: "var(--text-3)" }}>
          {queue && (
            <>
              <span style={{ color: "var(--accent)" }}>{queue.queued_jobs} queued</span>
              <span style={{ color: "var(--success)" }}>{queue.processing_jobs} active</span>
              {queue.failed_jobs > 0 && <span style={{ color: "var(--danger)" }}>{queue.failed_jobs} failed</span>}
            </>
          )}
        </div>
      </div>
      <div style={{ overflow: "auto", maxHeight: 280 }}>
        <AnimatePresence initial={false}>
          {DEMO_ITEMS.map((item, idx) => (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: idx * 0.05, duration: 0.3 }}
              style={{
                display: "flex", alignItems: "center", gap: 12,
                padding: "9px 16px", borderBottom: "1px solid var(--divider)",
              }}
            >
              <div className={`stage-dot ${item.stage === "started" ? "active" : item.stage === "completed" ? "done" : item.stage === "failed" ? "error" : ""}`}/>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <span className="mono" style={{ fontSize: 11.5, color: "var(--text-2)" }}>{item.id}</span>
                  <span style={{ fontSize: 12, color: "var(--text-1)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.vendor}</span>
                </div>
              </div>
              <ConfidenceBar value={item.confidence} width={48}/>
              <span className="mono" style={{ fontSize: 12, color: "var(--text-2)", minWidth: 70, textAlign: "right" }}>
                ${item.amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
              <span style={{ fontSize: 10.5, color: STAGE_COLORS[item.stage] ?? "var(--text-3)", minWidth: 60, textAlign: "right" }}>
                {STAGE_LABELS[item.stage] ?? item.stage}
              </span>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
      {queue && (
        <div style={{ padding: "10px 16px", borderTop: "1px solid var(--divider)", display: "flex", gap: 16 }}>
          <span style={{ fontSize: 11, color: "var(--text-3)" }}>
            Completed today: <span style={{ color: "var(--text-2)", fontVariantNumeric: "tabular-nums" }}>{fmtNum(queue.completed_today)}</span>
          </span>
          {queue.average_processing_time_seconds && (
            <span style={{ fontSize: 11, color: "var(--text-3)" }}>
              Avg time: <span style={{ color: "var(--text-2)" }}>{queue.average_processing_time_seconds.toFixed(1)}s</span>
            </span>
          )}
        </div>
      )}
    </div>
  )
}
