// Shared UI primitives (Badge, Button, etc) + sidebar + topbar shell.

const { useState: _useState } = React;

// ─── Badge ─────────────────────────────────────────────────────────
function Badge({ variant = "default", children, dot = false }) {
  const cls = `badge ${variant !== "default" ? `badge-${variant}` : ""}`;
  return (
    <span className={cls}>
      {dot && <span className="dot"/>}
      {children}
    </span>
  );
}

// ─── Confidence bar ────────────────────────────────────────────────
function ConfidenceBar({ value, width = 60 }) {
  const pct = Math.round(value * 100);
  const color = value >= 0.95 ? "var(--success)" : value >= 0.85 ? "var(--info)" : value >= 0.7 ? "var(--warning)" : "var(--danger)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div style={{ width, height: 4, background: "var(--bg-3)", borderRadius: 999, overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, transition: "width .6s var(--ease-out)" }}/>
      </div>
      <span className="mono" style={{ fontSize: 11, color: "var(--text-2)", minWidth: 32 }}>{pct}%</span>
    </div>
  );
}

// ─── Avatar ────────────────────────────────────────────────────────
function Avatar({ name, size = 26, color }) {
  const initials = name.split(" ").map(p => p[0]).slice(0, 2).join("");
  const colors = [
    ["#7C6BFF", "#5B49E6"], ["#34D7A0", "#1F9E76"], ["#6FB6F7", "#3B82C9"],
    ["#F26B7B", "#C94858"], ["#F5C26B", "#C9933F"], ["#C99BFF", "#9B6FD8"],
  ];
  const seed = name.charCodeAt(0) % colors.length;
  const [c1, c2] = color || colors[seed];
  return (
    <div style={{
      width: size, height: size, borderRadius: "50%",
      background: `linear-gradient(135deg, ${c1}, ${c2})`,
      color: "white", fontWeight: 600, fontSize: size * 0.4,
      display: "grid", placeItems: "center", flexShrink: 0,
      boxShadow: "0 0 0 0.5px rgba(255,255,255,0.06)",
    }}>{initials}</div>
  );
}

// ─── Sidebar ───────────────────────────────────────────────────────
function Sidebar({ current, onNav }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-mark">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 6h16M4 12h10M4 18h16"/>
          </svg>
        </div>
        <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.1 }}>
          <span className="brand-name">LedgerFlow</span>
          <span className="brand-tag">Ops · v2.4.1</span>
        </div>
      </div>

      <div className="workspace-switcher">
        <div className="workspace-avatar">N</div>
        <div style={{ display: "flex", flexDirection: "column", lineHeight: 1.2, flex: 1, minWidth: 0 }}>
          <span className="workspace-name" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>Nasher Capital</span>
          <span className="workspace-plan">Enterprise · 24 seats</span>
        </div>
        <Icon name="chevDown" size={13} style={{ color: "var(--text-3)" }}/>
      </div>

      <nav style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 2 }}>
        {navConfig.map((section, si) => (
          <div key={si}>
            <div className="nav-section-label">{section.section}</div>
            {section.items.map(item => (
              <div key={item.id}
                className={`nav-item ${current === item.id ? "active" : ""}`}
                onClick={() => onNav(item.id)}>
                <Icon name={item.icon} size={15} className="nav-item-icon"/>
                <span>{item.label}</span>
                {item.badge && (
                  <span className={`nav-item-badge ${item.badge.kind === "danger" ? "danger" : item.badge.kind === "accent" ? "accent" : ""}`}>
                    {item.badge.value}
                  </span>
                )}
              </div>
            ))}
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="sys-health-pill">
          <div className="health-dot"/>
          <span className="health-label">All systems normal</span>
          <span className="health-value">99.98%</span>
        </div>
        <div className="user-row">
          <Avatar name="Aanya Sharma" size={26}/>
          <div style={{ flex: 1, minWidth: 0, lineHeight: 1.2 }}>
            <div className="user-name">Aanya Sharma</div>
            <div className="user-email">aanya@nasher.co</div>
          </div>
          <Icon name="chevUp" size={13} style={{ color: "var(--text-3)" }}/>
        </div>
      </div>
    </aside>
  );
}

// ─── Topbar ────────────────────────────────────────────────────────
function Topbar({ current }) {
  const crumbs = breadcrumbs[current] || ["Workspace"];
  return (
    <header className="topbar">
      <div className="breadcrumb">
        {crumbs.map((c, i) => (
          <React.Fragment key={i}>
            {i > 0 && <Icon name="chevRight" size={12} className="crumb-sep"/>}
            <span className={i === crumbs.length - 1 ? "crumb-current" : ""}>{c}</span>
          </React.Fragment>
        ))}
      </div>

      <div className="search-bar">
        <Icon name="search" size={14}/>
        <input placeholder="Search invoices, vendors, transactions…" />
        <span className="kbd">⌘K</span>
      </div>

      <div className="topbar-actions">
        <div className="live-pill">
          <span className="pulse"/>
          Live · 1.2k events/min
        </div>
        <button className="icon-btn" title="Notifications">
          <Icon name="bell" size={15}/>
          <span className="dot"/>
        </button>
        <button className="icon-btn" title="Command">
          <Icon name="command" size={15}/>
        </button>
        <div style={{ width: 1, height: 20, background: "var(--border)" }}/>
        <button className="btn btn-sm">
          <Icon name="plus" size={13}/>
          New
        </button>
        <button className="btn btn-sm btn-primary">
          <Icon name="sparkle" size={13}/>
          Ask AI
        </button>
      </div>
    </header>
  );
}

// ─── Empty state ───────────────────────────────────────────────────
function EmptyState({ icon, title, body, action }) {
  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      gap: 12, padding: "48px 16px", color: "var(--text-2)", textAlign: "center",
    }}>
      <div style={{
        width: 48, height: 48, borderRadius: 12,
        background: "var(--bg-3)", border: "1px solid var(--border)",
        display: "grid", placeItems: "center",
      }}>
        <Icon name={icon} size={20} style={{ color: "var(--text-3)" }}/>
      </div>
      <div>
        <div style={{ fontSize: 14, color: "var(--text-1)", fontWeight: 500 }}>{title}</div>
        <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 4, maxWidth: 320 }}>{body}</div>
      </div>
      {action}
    </div>
  );
}

Object.assign(window, { Badge, ConfidenceBar, Avatar, Sidebar, Topbar, EmptyState });
