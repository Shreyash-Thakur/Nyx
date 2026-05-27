"use client"
import { usePathname } from "next/navigation"
import { Bell, Command, Plus, Search, Sparkles, ChevronRight } from "lucide-react"
import { useQueueStatus } from "@/hooks/useDashboard"

const CRUMBS: Record<string, string[]> = {
  "/": ["Workspace", "Dashboard"],
  "/invoices": ["Workspace", "Invoice Inbox"],
  "/reconciliation": ["Workspace", "Reconciliation"],
  "/audit": ["Workspace", "Audit Timeline"],
  "/analytics": ["Workspace", "Analytics"],
  "/vendors": ["Records", "Vendors"],
  "/settings": ["Account", "Settings"],
}

export function Topbar() {
  const pathname = usePathname()
  const crumbs = CRUMBS[pathname] ?? ["Workspace"]
  const { data: queue } = useQueueStatus()

  const processingCount = (queue?.queued_jobs ?? 0) + (queue?.processing_jobs ?? 0)

  return (
    <header className="topbar">
      <div className="breadcrumb">
        {crumbs.map((c, i) => (
          <span key={i} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            {i > 0 && <ChevronRight size={12} className="crumb-sep"/>}
            <span className={i === crumbs.length - 1 ? "crumb-current" : ""}>{c}</span>
          </span>
        ))}
      </div>

      <div className="search-bar">
        <Search size={14}/>
        <input placeholder="Search invoices, vendors, transactions…" />
        <span className="kbd">⌘K</span>
      </div>

      <div className="topbar-actions">
        {processingCount > 0 && (
          <div className="live-pill">
            <span className="pulse"/>
            {processingCount} processing
          </div>
        )}
        {processingCount === 0 && (
          <div className="live-pill">
            <span className="pulse"/>
            Live
          </div>
        )}
        <button className="icon-btn" title="Notifications">
          <Bell size={15}/>
          <span className="dot"/>
        </button>
        <button className="icon-btn" title="Command palette">
          <Command size={15}/>
        </button>
        <div style={{ width: 1, height: 20, background: "var(--border)" }}/>
        <button className="btn btn-sm">
          <Plus size={13}/>
          New
        </button>
        <button className="btn btn-sm btn-primary">
          <Sparkles size={13}/>
          Ask AI
        </button>
      </div>
    </header>
  )
}
