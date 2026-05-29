"use client"
import { useMemo } from "react"

export function Sparkline({
  data, width = 96, height = 36,
  color = "var(--accent)", fill = true,
}: {
  data: number[]; width?: number; height?: number; color?: string; fill?: boolean
}) {
  const { path, area } = useMemo(() => {
    if (!data?.length) return { path: "", area: "" }
    const min = Math.min(...data), max = Math.max(...data)
    const range = max - min || 1
    const stepX = width / (data.length - 1)
    const pts = data.map((v, i) => [i * stepX, height - 4 - ((v - min) / range) * (height - 8)])
    const path = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ")
    const area = `${path} L${width} ${height} L0 ${height} Z`
    return { path, area }
  }, [data, width, height])

  const gradId = useMemo(() => `spark-${Math.random().toString(36).slice(2, 8)}`, [])

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ overflow: "visible" }}>
      {fill && (
        <defs>
          <linearGradient id={gradId} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.35"/>
            <stop offset="100%" stopColor={color} stopOpacity="0"/>
          </linearGradient>
        </defs>
      )}
      {fill && <path d={area} fill={`url(#${gradId})`}/>}
      <path d={path} fill="none" stroke={color} strokeWidth="1.4" strokeLinejoin="round" strokeLinecap="round"
        style={{ strokeDasharray: 600, strokeDashoffset: 600, animation: "spark-draw 1.2s var(--ease-out) forwards" }}
      />
    </svg>
  )
}
