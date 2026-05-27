import { confidenceColor } from "@/lib/utils"

export function ConfidenceBar({ value, width = 60 }: { value: number; width?: number }) {
  const pct = Math.round(value * 100)
  const color = confidenceColor(value)
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{ width, height: 4, background: "var(--bg-3)", borderRadius: 999, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, transition: "width .6s var(--ease-out)" }}/>
      </div>
      <span className="mono" style={{ fontSize: 11, color: "var(--text-2)", minWidth: 32 }}>{pct}%</span>
    </div>
  )
}
