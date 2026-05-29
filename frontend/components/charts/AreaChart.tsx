"use client"
import {
  AreaChart as ReAreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from "recharts"

interface Props {
  data: Record<string, unknown>[]
  keys: string[]
  xKey?: string
  colors?: string[]
  height?: number
}

const COLORS = ["#7C6BFF", "#34D7A0", "#F26B7B", "#F5C26B", "#6FB6F7"]

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div style={{
      background: "var(--bg-4)", border: "1px solid var(--border-strong)",
      borderRadius: 8, padding: "8px 12px", fontSize: 11,
      boxShadow: "var(--sh-3)",
    }}>
      <div style={{ color: "var(--text-3)", marginBottom: 4 }}>{label}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "space-between", marginBottom: 2 }}>
          <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: p.color }}/>
            <span style={{ color: "var(--text-2)", textTransform: "capitalize" }}>{p.dataKey}</span>
          </span>
          <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-1)" }}>{p.value?.toLocaleString()}</span>
        </div>
      ))}
    </div>
  )
}

export function AreaChart({ data, keys, xKey = "t", colors = COLORS, height = 240 }: Props) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ReAreaChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <defs>
          {keys.map((k, i) => (
            <linearGradient key={k} id={`grad-${k}`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor={colors[i % colors.length]} stopOpacity={0.3}/>
              <stop offset="100%" stopColor={colors[i % colors.length]} stopOpacity={0}/>
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid strokeDasharray="2 4" stroke="var(--border)" vertical={false}/>
        <XAxis dataKey={xKey} tick={{ fontSize: 10, fill: "var(--text-3)", fontFamily: "var(--font-mono)" }} axisLine={false} tickLine={false}/>
        <YAxis tick={{ fontSize: 10, fill: "var(--text-3)", fontFamily: "var(--font-mono)" }} axisLine={false} tickLine={false} tickFormatter={(v) => v >= 1000 ? `${(v/1000).toFixed(1)}k` : v}/>
        <Tooltip content={<CustomTooltip/>}/>
        {keys.length > 1 && (
          <Legend
            wrapperStyle={{ fontSize: 10.5, color: "var(--text-2)", paddingTop: 4 }}
            formatter={(v) => <span style={{ textTransform: "capitalize", color: "var(--text-2)" }}>{v}</span>}
          />
        )}
        {keys.map((k, i) => (
          <Area
            key={k} type="monotone" dataKey={k}
            stroke={colors[i % colors.length]} strokeWidth={1.6}
            fill={`url(#grad-${k})`}
            animationDuration={800} animationEasing="ease-out"
          />
        ))}
      </ReAreaChart>
    </ResponsiveContainer>
  )
}
