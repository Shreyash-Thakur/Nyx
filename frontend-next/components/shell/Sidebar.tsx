"use client"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  LayoutDashboard, FileText, GitMerge, Clock, BarChart2,
  Building2, BookOpen, Zap, Users, Settings, ChevronDown, ChevronUp,
} from "lucide-react"
import { useAuthStore } from "@/store/auth.store"
import { useLogout } from "@/hooks/useAuth"

const NAV = [
  {
    section: "Workspace",
    items: [
      { href: "/", label: "Dashboard", icon: LayoutDashboard },
      { href: "/invoices", label: "Invoice Inbox", icon: FileText, badge: { value: "12", kind: "default" } },
      { href: "/reconciliation", label: "Reconciliation", icon: GitMerge, badge: { value: "3", kind: "danger" } },
      { href: "/audit", label: "Audit Timeline", icon: Clock },
      { href: "/analytics", label: "Analytics", icon: BarChart2 },
    ],
  },
  {
    section: "Records",
    items: [
      { href: "/vendors", label: "Vendors", icon: Building2 },
    ],
  },
  {
    section: "Account",
    items: [
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
]

function Avatar({ name, size = 26 }: { name: string; size?: number }) {
  const initials = name.split(" ").map((p) => p[0]).slice(0, 2).join("")
  const colors = [
    ["#7C6BFF", "#5B49E6"], ["#34D7A0", "#1F9E76"], ["#6FB6F7", "#3B82C9"],
    ["#F26B7B", "#C94858"], ["#F5C26B", "#C9933F"],
  ]
  const [c1, c2] = colors[name.charCodeAt(0) % colors.length]
  return (
    <div style={{
      width: size, height: size, borderRadius: "50%",
      background: `linear-gradient(135deg, ${c1}, ${c2})`,
      color: "white", fontWeight: 600, fontSize: size * 0.4,
      display: "grid", placeItems: "center", flexShrink: 0,
    }}>
      {initials}
    </div>
  )
}

export function Sidebar() {
  const pathname = usePathname()
  const user = useAuthStore((s) => s.user)
  const logout = useLogout()

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href)

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-mark">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" style={{ position: "relative", zIndex: 1 }}>
            <path d="M4 6h16M4 12h10M4 18h16"/>
          </svg>
        </div>
        <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.1 }}>
          <span className="brand-name">LedgerFlow</span>
          <span className="brand-tag">Ops · v1.0</span>
        </div>
      </div>

      <div className="workspace-switcher">
        <div className="workspace-avatar">N</div>
        <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.2, flex: 1, minWidth: 0 }}>
          <span className="workspace-name" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {user?.full_name?.split(" ")[0] ?? "Workspace"}
          </span>
          <span className="workspace-plan">Enterprise · Finance</span>
        </div>
        <ChevronDown size={13} style={{ color: "var(--text-3)", flexShrink: 0 }}/>
      </div>

      <nav style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 2 }}>
        {NAV.map((section) => (
          <div key={section.section}>
            <div className="nav-section-label">{section.section}</div>
            {section.items.map((item) => {
              const Icon = item.icon
              const active = isActive(item.href)
              return (
                <Link key={item.href} href={item.href} style={{ textDecoration: "none" }}>
                  <div className={`nav-item${active ? " active" : ""}`}>
                    <Icon size={15} className="nav-item-icon"/>
                    <span>{item.label}</span>
                    {item.badge && (
                      <span className={`nav-item-badge${item.badge.kind === "danger" ? " danger" : item.badge.kind === "accent" ? " accent" : ""}`}>
                        {item.badge.value}
                      </span>
                    )}
                  </div>
                </Link>
              )
            })}
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="sys-health-pill">
          <div className="health-dot"/>
          <span className="health-label">All systems normal</span>
          <span className="health-value">99.98%</span>
        </div>
        <div className="user-row" onClick={logout} title="Click to sign out">
          {user ? <Avatar name={user.full_name} size={26}/> : <div style={{ width: 26, height: 26, borderRadius: "50%", background: "var(--bg-4)" }}/>}
          <div style={{ flex: 1, minWidth: 0, lineHeight: 1.2 }}>
            <div className="user-name">{user?.full_name ?? "—"}</div>
            <div className="user-email">{user?.email ?? "—"}</div>
          </div>
          <ChevronUp size={13} style={{ color: "var(--text-3)" }}/>
        </div>
      </div>
    </aside>
  )
}
