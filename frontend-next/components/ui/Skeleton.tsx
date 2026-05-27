import { cn } from "@/lib/utils"

export function Skeleton({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return <div className={cn("skeleton", className)} style={style}/>
}

export function KPISkeleton() {
  return (
    <div className="kpi-tile">
      <Skeleton style={{ height: 12, width: 100 }}/>
      <Skeleton style={{ height: 32, width: 140 }}/>
      <Skeleton style={{ height: 10, width: 80 }}/>
    </div>
  )
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} style={{ padding: "10px 12px", borderBottom: "1px solid var(--divider)", display: "flex", gap: 16 }}>
          <Skeleton style={{ height: 14, flex: 1 }}/>
          <Skeleton style={{ height: 14, width: 80 }}/>
          <Skeleton style={{ height: 14, width: 60 }}/>
        </div>
      ))}
    </div>
  )
}
