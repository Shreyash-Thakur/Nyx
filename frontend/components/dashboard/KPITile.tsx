"use client"
import { TrendingUp, TrendingDown } from "lucide-react"
import { motion } from "framer-motion"
import { Sparkline } from "@/components/charts/Sparkline"
import { Skeleton } from "@/components/ui/Skeleton"

interface KPITileProps {
  label: string
  value: string
  unit?: string
  trend?: { dir: "up" | "down"; value: string; caption: string }
  spark?: number[]
  accent?: "warning" | "danger"
  loading?: boolean
}

export function KPITile({ label, value, unit, trend, spark, accent, loading }: KPITileProps) {
  if (loading) {
    return (
      <div className="kpi-tile">
        <Skeleton style={{ height: 12, width: 100 }}/>
        <Skeleton style={{ height: 32, width: 140, marginTop: 8 }}/>
        <Skeleton style={{ height: 10, width: 80, marginTop: 6 }}/>
      </div>
    )
  }
  const trendColor = trend?.dir === "up"
    ? (accent === "warning" ? "var(--warning)" : "var(--success)")
    : "var(--danger)"

  return (
    <motion.div
      className="kpi-tile"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="kpi-label">{label}</div>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between" }}>
        <div className="kpi-value" style={{ color: accent === "warning" ? "var(--warning)" : undefined }}>
          {value}{unit && <span style={{ fontSize: 16, color: "var(--text-3)", marginLeft: 2 }}>{unit}</span>}
        </div>
        {spark && <Sparkline data={spark} color={accent === "warning" ? "var(--warning)" : "var(--accent)"}/>}
      </div>
      {trend && (
        <div className="kpi-trend">
          {trend.dir === "up"
            ? <TrendingUp size={12} style={{ color: trendColor }}/>
            : <TrendingDown size={12} style={{ color: trendColor }}/>
          }
          <span style={{ color: trendColor, fontWeight: 500 }}>{trend.value}</span>
          <span className="kpi-trend-caption">{trend.caption}</span>
        </div>
      )}
    </motion.div>
  )
}
