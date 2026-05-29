"use client"
import { motion } from "framer-motion"
import { TrendingUp, TrendingDown, AlertTriangle } from "lucide-react"
import { AreaChart } from "@/components/charts/AreaChart"
import { useDashboardOverview, useTrends } from "@/hooks/useDashboard"
import { fmtUsd, fmtNum } from "@/lib/utils"

const VENDOR_PERF = [
  { vendor: "AWS",         spend: 1284200, invoices: 84, avg: 15287, anomaly: 0, onTime: 100, change: +12.4 },
  { vendor: "Stripe",      spend: 882000,  invoices: 12, avg: 73500, anomaly: 1, onTime: 100, change: +8.1 },
  { vendor: "Datadog",     spend: 482300,  invoices: 28, avg: 17225, anomaly: 0, onTime: 96.4, change: +24.2 },
  { vendor: "Salesforce",  spend: 384000,  invoices: 4,  avg: 96000, anomaly: 0, onTime: 100, change: 0 },
  { vendor: "MongoDB",     spend: 248000,  invoices: 12, avg: 20667, anomaly: 0, onTime: 100, change: +5.3 },
  { vendor: "Twilio",      spend: 124000,  invoices: 26, avg: 4769,  anomaly: 2, onTime: 84.6, change: +48.2 },
]

const ANOMALIES = [
  { id: 1, vendor: "Twilio",  desc: "Spend up 48.2% vs trailing avg",   severity: "high"   as const, amount: "+$40.4k" },
  { id: 2, vendor: "Datadog", desc: "Two duplicate invoice numbers",     severity: "high"   as const, amount: "$17.8k" },
  { id: 3, vendor: "Stripe",  desc: "Invoice arrived 11 days early",     severity: "medium" as const, amount: "$73.5k" },
]

const SEV_COLOR = { high: "var(--danger)", medium: "var(--warning)", low: "var(--info)" }

export default function AnalyticsPage() {
  const { data: overview } = useDashboardOverview()
  const { data: trends } = useTrends()

  const trendData = trends?.map((t) => ({
    t: t.date.slice(5),
    invoices: t.invoice_count,
    reconciled: t.reconciled_count,
    amount: parseFloat(t.total_amount) / 1000,
  })) ?? []

  const vendors = overview?.top_vendors.length
    ? overview.top_vendors.map((v) => ({ vendor: v.vendor_name, spend: parseFloat(v.total_amount), invoices: v.invoice_count, avg: parseFloat(v.total_amount) / v.invoice_count, anomaly: v.discrepancy_count, onTime: 100, change: 0 }))
    : VENDOR_PERF

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-title">Analytics</div>
          <div className="page-subtitle">Spend intelligence · 30-day rolling</div>
        </div>
      </div>

      {/* Anomaly banner */}
      {ANOMALIES.length > 0 && (
        <div style={{ marginBottom: 16, display: "flex", flexDirection: "column", gap: 6 }}>
          {ANOMALIES.map((a, i) => (
            <motion.div key={a.id} initial={{ opacity: 0, x: -4 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
              style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "10px 14px", borderRadius: 10,
                background: a.severity === "high" ? "rgba(242,107,123,0.06)" : "rgba(245,194,107,0.06)",
                border: `1px solid ${a.severity === "high" ? "rgba(242,107,123,0.2)" : "rgba(245,194,107,0.2)"}`,
              }}>
              <AlertTriangle size={14} style={{ color: SEV_COLOR[a.severity], flexShrink: 0 }}/>
              <span style={{ fontSize: 12.5, color: "var(--text-1)", flex: 1 }}>
                <strong style={{ color: SEV_COLOR[a.severity] }}>{a.vendor}</strong> — {a.desc}
              </span>
              <span className="mono" style={{ fontSize: 12, color: SEV_COLOR[a.severity] }}>{a.amount}</span>
              <span style={{ fontSize: 10.5, padding: "2px 7px", borderRadius: 99, background: `${SEV_COLOR[a.severity]}20`, color: SEV_COLOR[a.severity] }}>{a.severity}</span>
            </motion.div>
          ))}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
        {/* Trend chart */}
        <div className="card">
          <div className="card-header"><span className="card-title">Invoice Volume</span><span style={{ fontSize: 11, color: "var(--text-3)" }}>30d</span></div>
          <div className="card-body">
            <AreaChart data={trendData.length > 0 ? trendData : Array.from({ length: 30 }, (_, i) => ({ t: `${i + 1}`, invoices: Math.round(80 + Math.sin(i / 4) * 30 + Math.random() * 20), reconciled: Math.round(70 + Math.sin(i / 4) * 25) }))} keys={["invoices", "reconciled"]} height={180}/>
          </div>
        </div>

        {/* Amount trend */}
        <div className="card">
          <div className="card-header"><span className="card-title">Processed Amount</span><span style={{ fontSize: 11, color: "var(--text-3)" }}>$K · 30d</span></div>
          <div className="card-body">
            <AreaChart data={trendData.length > 0 ? trendData : Array.from({ length: 30 }, (_, i) => ({ t: `${i + 1}`, amount: Math.round(800 + Math.sin(i / 5) * 300 + Math.random() * 200) }))} keys={["amount"]} colors={["var(--c2)"]} height={180}/>
          </div>
        </div>
      </div>

      {/* Vendor table */}
      <div className="card">
        <div className="card-header"><span className="card-title">Vendor Performance</span></div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Vendor</th>
                <th>Total spend</th>
                <th>Invoices</th>
                <th>Avg invoice</th>
                <th>On-time %</th>
                <th>Anomalies</th>
                <th>30d change</th>
              </tr>
            </thead>
            <tbody>
              {vendors.map((v, i) => (
                <motion.tr key={v.vendor} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.03 }}>
                  <td style={{ fontWeight: 500 }}>{v.vendor}</td>
                  <td><span className="mono">{fmtUsd(v.spend, false)}</span></td>
                  <td><span className="mono">{fmtNum(v.invoices)}</span></td>
                  <td><span className="mono">{fmtUsd(v.avg, false)}</span></td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <div style={{ width: 48, height: 3, background: "var(--bg-4)", borderRadius: 99 }}>
                        <div style={{ width: `${v.onTime}%`, height: "100%", background: v.onTime === 100 ? "var(--success)" : v.onTime >= 90 ? "var(--warning)" : "var(--danger)", borderRadius: 99 }}/>
                      </div>
                      <span className="mono" style={{ fontSize: 11.5 }}>{v.onTime.toFixed(1)}%</span>
                    </div>
                  </td>
                  <td>
                    {v.anomaly > 0
                      ? <span style={{ fontSize: 11, padding: "2px 7px", borderRadius: 99, background: "var(--danger-glow)", color: "var(--danger)" }}>{v.anomaly} open</span>
                      : <span style={{ fontSize: 11, color: "var(--text-4)" }}>—</span>
                    }
                  </td>
                  <td>
                    <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, color: v.change > 0 ? "var(--warning)" : v.change < 0 ? "var(--success)" : "var(--text-3)" }}>
                      {v.change > 0 ? <TrendingUp size={12}/> : v.change < 0 ? <TrendingDown size={12}/> : null}
                      <span className="mono">{v.change > 0 ? "+" : ""}{v.change.toFixed(1)}%</span>
                    </span>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
