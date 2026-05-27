"use client"
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts"

interface Slice { name: string; value: number; color: string }

function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null
  const p = payload[0]
  return (
    <div style={{
      background: "var(--bg-4)", border: "1px solid var(--border-strong)",
      borderRadius: 8, padding: "8px 12px", fontSize: 11,
    }}>
      <div style={{ color: "var(--text-1)", fontWeight: 500 }}>{p.name}</div>
      <div style={{ color: "var(--text-2)", fontFamily: "var(--font-mono)", marginTop: 2 }}>
        ${p.value.toLocaleString()}
      </div>
    </div>
  )
}

export function DonutChart({ data, height = 180 }: { data: Slice[]; height?: number }) {
  return (
    <div style={{ display: "flex", gap: 24, alignItems: "center" }}>
      <ResponsiveContainer width={height} height={height} style={{ flexShrink: 0 }}>
        <PieChart>
          <Pie
            data={data} cx="50%" cy="50%"
            innerRadius={height * 0.28} outerRadius={height * 0.44}
            paddingAngle={2} dataKey="value"
            animationDuration={800} animationEasing="ease-out"
          >
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.color} stroke="transparent"/>
            ))}
          </Pie>
          <Tooltip content={<CustomTooltip/>}/>
        </PieChart>
      </ResponsiveContainer>
      <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
        {data.map((d) => (
          <div key={d.name} style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "space-between" }}>
            <span style={{ display: "flex", alignItems: "center", gap: 7 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: d.color, flexShrink: 0 }}/>
              <span style={{ fontSize: 12, color: "var(--text-2)" }}>{d.name}</span>
            </span>
            <span style={{ fontSize: 11.5, color: "var(--text-1)", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums" }}>
              ${(d.value / 1000).toFixed(0)}k
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
