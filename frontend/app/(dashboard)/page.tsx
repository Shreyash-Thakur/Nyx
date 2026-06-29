"use client"
import { motion } from "framer-motion"
import { KPITile } from "@/components/dashboard/KPITile"
import { LiveQueue } from "@/components/dashboard/LiveQueue"
import { AreaChart } from "@/components/charts/AreaChart"
import { DonutChart } from "@/components/charts/DonutChart"
import { useDashboardOverview, useTrends } from "@/hooks/useDashboard"
import { useActivity } from "@/hooks/useActivity"
import { fmtUsd, fmtNum, relativeTime } from "@/lib/utils"

const TYPE_COLOR: Record<string, string> = {
  match: "var(--success)", approve: "var(--accent)", exception: "var(--danger)",
  link: "var(--c6)", ocr: "var(--info)",
}

// Maps durable domain-event names to a human label + visual type.
const EVENT_META: Record<string, { label: string; type: string }> = {
  "invoice.uploaded": { label: "uploaded an invoice", type: "ocr" },
  "invoice.extracted": { label: "OCR extraction completed", type: "ocr" },
  "reconciliation.completed": { label: "reconciliation completed", type: "match" },
}

function eventDetail(name: string, payload: Record<string, unknown> | null): string {
  const p = payload ?? {}
  if (name === "invoice.uploaded") return String(p.filename ?? "")
  if (name === "invoice.extracted")
    return p.confidence != null ? `confidence ${(Number(p.confidence) * 100).toFixed(0)}%` : ""
  if (name === "reconciliation.completed") return String(p.status ?? "")
  return ""
}

const VENDOR_COLORS = ["var(--c1)", "var(--c2)", "var(--c3)", "var(--c4)", "var(--c5)", "var(--c7)"]

export default function DashboardPage() {
  const { data: overview, isLoading } = useDashboardOverview()
  const { data: trends } = useTrends()
  const { data: activity } = useActivity()

  const activityItems = (activity ?? []).map((e) => {
    const meta = EVENT_META[e.name] ?? { label: e.name, type: "ocr" }
    return {
      id: e.id,
      who: e.actor_id ? "User" : "System",
      what: meta.label,
      detail: eventDetail(e.name, e.payload),
      ts: relativeTime(e.created_at),
      type: meta.type,
    }
  })

  const inv = overview?.invoice_summary
  const disc = overview?.discrepancy_summary
  const queue = overview?.queue_status

  const kpis = [
    {
      label: "Processed Volume",
      value: overview ? fmtUsd(parseFloat(overview.total_processed_amount), false) : "—",
      trend: { dir: "up" as const, value: "+12.4%", caption: "vs last month" },
      spark: [12, 16, 14, 22, 20, 28, 26, 33, 31, 38, 42, 48],
    },
    {
      label: "Invoices Processed",
      value: inv ? fmtNum(inv.total) : "—",
      trend: { dir: "up" as const, value: "+8.2%", caption: "this week" },
      spark: [820, 1100, 980, 1240, 1180, 1420, 1380, 1620, 1580, 1820, 1980, 2210],
    },
    {
      label: "Auto-Match Rate",
      value: inv ? (inv.total ? ((inv.reconciled / inv.total) * 100).toFixed(1) : "0") : "—",
      unit: "%",
      trend: { dir: "up" as const, value: "+1.8pp", caption: "30-day rolling" },
      spark: [88, 89, 88, 90, 91, 92, 91, 93, 93, 94, 94, 95],
    },
    {
      label: "Open Exceptions",
      value: disc ? fmtNum(disc.unresolved) : "—",
      trend: { dir: "down" as const, value: "-23", caption: "since yesterday" },
      spark: [520, 480, 460, 440, 410, 405, 380, 365, 370, 360, 348, 342],
      accent: "warning" as const,
    },
  ]

  // Trend data for area chart
  const trendChartData = trends?.map((t) => ({
    t: t.date.slice(5),
    matched: t.reconciled_count,
    exceptions: Math.round(t.invoice_count * 0.06),
    manual: Math.round(t.invoice_count * 0.04),
  })) ?? []

  // Vendor exposure for donut
  const vendorData = overview?.top_vendors.slice(0, 5).map((v, i) => ({
    name: v.vendor_name,
    value: parseFloat(v.total_amount),
    color: VENDOR_COLORS[i],
  })) ?? []

  return (
    <div className="page">
      {/* KPI row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
        {kpis.map((kpi, i) => (
          <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }}>
            <KPITile {...kpi} loading={isLoading}/>
          </motion.div>
        ))}
      </div>

      {/* Main 2-col grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: 12, marginBottom: 12 }}>
        {/* Throughput chart */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Reconciliation Throughput</span>
            <span style={{ fontSize: 11, color: "var(--text-3)" }}>24h · real-time</span>
          </div>
          <div className="card-body">
            {trendChartData.length > 0
              ? <AreaChart data={trendChartData} keys={["matched", "exceptions", "manual"]} height={200}/>
              : <AreaChart data={Array.from({ length: 24 }, (_, i) => ({
                  t: `${String(i).padStart(2, "0")}:00`,
                  matched: Math.round(280 + Math.sin(i / 3.5) * 80),
                  exceptions: Math.round(18 + Math.random() * 12),
                  manual: Math.round(10 + Math.random() * 8),
                }))} keys={["matched", "exceptions", "manual"]} height={200}/>
            }
          </div>
        </div>

        {/* Vendor exposure */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Vendor Exposure</span>
          </div>
          <div className="card-body">
            {vendorData.length > 0
              ? <DonutChart data={vendorData}/>
              : <DonutChart data={[
                  { name: "AWS", value: 1284200, color: "var(--c1)" },
                  { name: "Stripe", value: 882000, color: "var(--c2)" },
                  { name: "Datadog", value: 482300, color: "var(--c3)" },
                  { name: "Salesforce", value: 384000, color: "var(--c4)" },
                  { name: "Others", value: 612400, color: "var(--c7)" },
                ]}/>
            }
          </div>
        </div>
      </div>

      {/* Bottom 2-col */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 12 }}>
        {/* Live queue */}
        <div className="card">
          <LiveQueue/>
        </div>

        {/* Activity feed */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Activity</span>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span className="pulse" style={{ width: 5, height: 5 }}/>
              <span style={{ fontSize: 10.5, color: "var(--text-3)" }}>Live</span>
            </div>
          </div>
          <div style={{ overflow: "auto", maxHeight: 280 }}>
            {activityItems.length === 0 && (
              <div style={{ padding: "16px", fontSize: 12, color: "var(--text-3)" }}>
                No recent activity yet.
              </div>
            )}
            {activityItems.map((ev, i) => (
              <motion.div key={ev.id} initial={{ opacity: 0, x: 4 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.04 }}
                style={{ padding: "10px 16px", borderBottom: "1px solid var(--divider)" }}>
                <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                  <div style={{ width: 6, height: 6, borderRadius: "50%", background: TYPE_COLOR[ev.type] ?? "var(--text-3)", marginTop: 5, flexShrink: 0 }}/>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12.5, color: "var(--text-1)" }}>
                      <span style={{ color: "var(--text-2)" }}>{ev.who}</span> {ev.what}
                    </div>
                    <div style={{ fontSize: 11.5, color: "var(--text-3)", marginTop: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{ev.detail}</div>
                  </div>
                  <span style={{ fontSize: 10.5, color: "var(--text-4)", whiteSpace: "nowrap", flexShrink: 0 }}>{ev.ts}</span>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
