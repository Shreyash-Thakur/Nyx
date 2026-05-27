// ─── Landing v2 — light-mode product surface fragments ──────────────
// Real-looking product micro-screens used throughout the page.

const { useState: _uS, useEffect: _uE, useRef: _uR } = React;

// ─── Tiny icons (sparingly used) ───────────────────────────────────
const I = {
  arrow: (p={}) => <svg {...p} width={p.s||14} height={p.s||14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 5l7 7-7 7"/></svg>,
  check: (p={}) => <svg {...p} width={p.s||14} height={p.s||14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 12l5 5L20 6"/></svg>,
  alert: (p={}) => <svg {...p} width={p.s||14} height={p.s||14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/></svg>,
  spark: (p={}) => <svg {...p} width={p.s||14} height={p.s||14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3l1.8 4.7L18.5 9l-4.7 1.8L12 15l-1.8-4.7L5.5 9l4.7-1.8L12 3z"/></svg>,
  doc: (p={}) => <svg {...p} width={p.s||14} height={p.s||14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>,
  link: (p={}) => <svg {...p} width={p.s||14} height={p.s||14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/></svg>,
  command: (p={}) => <svg {...p} width={p.s||14} height={p.s||14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M18 3a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0-3-3H6a3 3 0 0 0-3 3 3 3 0 0 0 3 3 3 3 0 0 0 3-3V6a3 3 0 0 0-3-3 3 3 0 0 0-3 3 3 3 0 0 0 3 3h12a3 3 0 0 0 3-3 3 3 0 0 0-3-3z"/></svg>,
  bolt: (p={}) => <svg {...p} width={p.s||14} height={p.s||14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>,
  search: (p={}) => <svg {...p} width={p.s||14} height={p.s||14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>,
};

// ─── Status badge ──────────────────────────────────────────────────
function Pill({ kind = "neutral", children, dot = false, size = "default" }) {
  const map = {
    success:  { bg: "rgba(74,143,110,0.10)", fg: "#3F7A5F", bd: "rgba(74,143,110,0.22)" },
    warning:  { bg: "rgba(182,140,44,0.10)", fg: "#8A6920", bd: "rgba(182,140,44,0.22)" },
    danger:   { bg: "rgba(194,85,85,0.10)",  fg: "#A14545", bd: "rgba(194,85,85,0.22)" },
    accent:   { bg: "rgba(79,91,213,0.10)",  fg: "#3E4AB8", bd: "rgba(79,91,213,0.22)" },
    info:     { bg: "rgba(79,91,213,0.06)",  fg: "var(--ink-2)", bd: "rgba(20,22,30,0.10)" },
    neutral:  { bg: "rgba(20,22,30,0.04)",   fg: "var(--ink-2)", bd: "rgba(20,22,30,0.08)" },
  };
  const c = map[kind] || map.neutral;
  const fs = size === "sm" ? 10 : 10.5;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      fontFamily: "var(--f-mono)", fontSize: fs,
      letterSpacing: "0.04em", textTransform: "uppercase",
      padding: "2px 7px 2px 7px",
      background: c.bg, color: c.fg,
      border: `1px solid ${c.bd}`,
      borderRadius: 999, fontWeight: 500,
      whiteSpace: "nowrap",
    }}>
      {dot && <span style={{ width: 5, height: 5, borderRadius: 50, background: c.fg }}/>}
      {children}
    </span>
  );
}

// ─── Confidence bar ─────────────────────────────────────────────────
function ConfBar({ value, w = 40 }) {
  const pct = Math.round(value * 100);
  const color = value >= 0.95 ? "var(--positive)" : value >= 0.85 ? "var(--accent)" : value >= 0.7 ? "var(--amber)" : "var(--negative)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
      <div style={{ width: w, height: 3, background: "rgba(20,22,30,0.06)", borderRadius: 999 }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 999 }}/>
      </div>
      <span className="mono" style={{ fontSize: 10, color: "var(--ink-3)", minWidth: 24 }}>{pct}%</span>
    </div>
  );
}

// ─── Sparkline ─────────────────────────────────────────────────────
function Spark({ data, w = 80, h = 24, color = "var(--accent)" }) {
  if (!data?.length) return null;
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const stepX = w / (data.length - 1);
  const pts = data.map((v, i) => [i * stepX, h - 2 - ((v - min) / range) * (h - 4)]);
  const path = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ');
  const area = `${path} L${w} ${h} L0 ${h} Z`;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`}>
      <path d={area} fill={color} opacity="0.10"/>
      <path d={path} fill="none" stroke={color} strokeWidth="1.4" strokeLinejoin="round" strokeLinecap="round"/>
    </svg>
  );
}

// ─── PRODUCT FRAGMENT: Inbox panel ──────────────────────────────────
function ProductInbox({ style }) {
  const items = [
    { v: "Stripe Atlas", id: "INV-29481", amt: "$4,820.00", s: "matched" },
    { v: "AWS",          id: "INV-29482", amt: "$18,432.55", s: "matched" },
    { v: "Notion Labs",  id: "INV-29483", amt: "$1,200.00", s: "approved" },
    { v: "Datadog",      id: "INV-29484", amt: "$7,894.20", s: "review" },
    { v: "Linear",       id: "INV-29485", amt: "$480.00",   s: "matched" },
    { v: "Vercel",       id: "INV-29486", amt: "$2,200.00", s: "posted" },
  ];
  const meta = { matched: "success", approved: "accent", posted: "info", review: "warning" };
  return (
    <div className="card-elevated" style={{ width: 360, ...style }}>
      <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <I.doc s={13} style={{ color: "var(--ink-3)" }}/>
          <span style={{ fontSize: 12.5, fontWeight: 500 }}>Inbox</span>
          <Pill size="sm">10 of 12,847</Pill>
        </div>
        <I.search s={13} style={{ color: "var(--ink-4)" }}/>
      </div>
      {items.map((it, i) => (
        <div key={i} style={{
          display: "grid", gridTemplateColumns: "1fr auto",
          alignItems: "center", gap: 12,
          padding: "10px 14px",
          borderBottom: i < items.length - 1 ? "1px solid var(--line)" : "none",
          background: i === 3 ? "var(--accent-tint)" : "transparent",
          borderLeft: i === 3 ? "2px solid var(--accent)" : "2px solid transparent",
        }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 500 }}>{it.v}</span>
              <span className="mono" style={{ fontSize: 10.5, color: "var(--ink-4)" }}>{it.id}</span>
            </div>
            <div style={{ marginTop: 4 }}>
              <Pill kind={meta[it.s]} size="sm" dot>{it.s}</Pill>
            </div>
          </div>
          <span className="mono" style={{ fontSize: 12.5, fontWeight: 500, color: "var(--ink-1)" }}>{it.amt}</span>
        </div>
      ))}
    </div>
  );
}

// ─── PRODUCT FRAGMENT: Invoice preview with OCR ────────────────────
function ProductInvoicePreview({ style }) {
  return (
    <div className="card-elevated" style={{ width: 320, ...style }}>
      <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <I.spark s={13} style={{ color: "var(--accent)" }}/>
          <span style={{ fontSize: 12.5, fontWeight: 500 }}>Extracted</span>
          <Pill kind="accent" size="sm">94% conf</Pill>
        </div>
        <span className="mono" style={{ fontSize: 10.5, color: "var(--ink-4)" }}>INV-29484</span>
      </div>
      <div style={{ padding: "14px 16px" }}>
        {[
          { l: "Vendor",     v: "Datadog, Inc.", c: 0.99 },
          { l: "Invoice #",  v: "INV-29484", c: 1.0 },
          { l: "Issued",     v: "Apr 23, 2026", c: 0.97 },
          { l: "Due",        v: "May 23, 2026", c: 0.95 },
          { l: "PO match",   v: "PO-1101", c: 0.92 },
          { l: "Subtotal",   v: "$7,894.20", c: 0.96 },
          { l: "Tax",        v: "$0.00", c: 0.99 },
          { l: "Total due",  v: "$7,894.20", c: 0.99 },
        ].map((r, i, arr) => (
          <div key={i} style={{
            display: "grid", gridTemplateColumns: "84px 1fr auto",
            gap: 12, alignItems: "center",
            padding: "7px 0",
            borderBottom: i < arr.length - 1 ? "1px solid var(--line)" : "none",
          }}>
            <span style={{ fontSize: 11, color: "var(--ink-3)" }}>{r.l}</span>
            <span className="mono" style={{ fontSize: 12, color: "var(--ink-1)" }}>{r.v}</span>
            <ConfBar value={r.c} w={32}/>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── PRODUCT FRAGMENT: Reconciliation match ────────────────────────
function ProductRecon({ style }) {
  return (
    <div className="card-elevated" style={{ width: 380, ...style }}>
      <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <I.link s={13} style={{ color: "var(--ink-3)" }}/>
          <span style={{ fontSize: 12.5, fontWeight: 500 }}>Match · Pair #3</span>
        </div>
        <Pill kind="warning" dot>discrepancy</Pill>
      </div>
      <div style={{ padding: 16 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", alignItems: "center", gap: 12 }}>
          <ReconSide label="Invoice" name="Figma, Inc." sub="INV-29487" amt="$720.00"/>
          <ReconLink/>
          <ReconSide label="Bank txn" name="FIGMA INC ACH" sub="TX-447902" amt="$671.80" diff/>
        </div>
        <div style={{
          marginTop: 14, padding: "10px 12px",
          background: "rgba(182,140,44,0.07)",
          border: "1px solid rgba(182,140,44,0.20)",
          borderRadius: 8,
          display: "flex", alignItems: "flex-start", gap: 10,
        }}>
          <I.alert s={14} style={{ color: "var(--amber)", marginTop: 1, flexShrink: 0 }}/>
          <div style={{ fontSize: 12, color: "var(--ink-2)", lineHeight: 1.45 }}>
            Delta <span className="mono" style={{ color: "var(--amber)", fontWeight: 500 }}>−$48.20</span>.
            Suggested: apply FX-rounding tolerance and approve.
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 12, justifyContent: "flex-end" }}>
          <button className="btn btn-sm">Reject</button>
          <button className="btn btn-sm btn-primary">Approve</button>
        </div>
      </div>
    </div>
  );
}
function ReconSide({ label, name, sub, amt, diff }) {
  return (
    <div style={{ padding: "10px 12px", background: "var(--card-soft)", borderRadius: 8, border: "1px solid var(--line)" }}>
      <div className="label-cap" style={{ marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 12.5, fontWeight: 500, color: "var(--ink-1)" }}>{name}</div>
      <div className="mono" style={{ fontSize: 10, color: "var(--ink-4)", marginTop: 2 }}>{sub}</div>
      <div className="mono" style={{ fontSize: 15, fontWeight: 500, color: diff ? "var(--amber)" : "var(--ink-1)", marginTop: 8 }}>{amt}</div>
    </div>
  );
}
function ReconLink() {
  return (
    <svg width="32" height="48" viewBox="0 0 32 48">
      <path d="M0 24 L 32 24" stroke="var(--ink-5)" strokeWidth="1" strokeDasharray="2 2"/>
      <circle cx="16" cy="24" r="9" fill="var(--paper)" stroke="var(--amber)" strokeWidth="1"/>
      <path d="M16 19 L 16 25 M 16 28 L 16 29" stroke="var(--amber)" strokeWidth="1.4" strokeLinecap="round"/>
    </svg>
  );
}

// ─── PRODUCT FRAGMENT: Audit event card ────────────────────────────
function ProductAudit({ style }) {
  const events = [
    { t: "10:42:18", who: "Priya M.", verb: "approved batch", obj: "#418", meta: "$184,820.00", kind: "approve" },
    { t: "10:41:02", who: "System",   verb: "auto-matched",   obj: "INV-29481 → PO-1124", meta: "conf 0.97", kind: "match" },
    { t: "10:38:47", who: "System",   verb: "OCR extracted",  obj: "12 documents", meta: "Batch #419", kind: "ocr" },
    { t: "10:32:14", who: "Marcus T.", verb: "linked vendor", obj: "Stripe Atlas", meta: "merchant_847", kind: "link" },
    { t: "10:29:41", who: "System",   verb: "flagged",        obj: "INV-29476", meta: "Δ $48.20", kind: "exception" },
  ];
  const dotColor = { approve: "var(--positive)", match: "var(--accent)", ocr: "var(--ink-3)", link: "var(--sage)", exception: "var(--amber)" };
  return (
    <div className="card-elevated" style={{ width: 380, ...style }}>
      <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--line)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ width: 7, height: 7, borderRadius: 50, background: "var(--positive)", animation: "live-pulse 2.2s var(--ease-out) infinite" }}/>
          <span style={{ fontSize: 12.5, fontWeight: 500 }}>Audit · live</span>
        </div>
        <span className="mono" style={{ fontSize: 10.5, color: "var(--ink-4)" }}>Apr 24</span>
      </div>
      {events.map((e, i) => (
        <div key={i} style={{
          display: "grid", gridTemplateColumns: "56px 14px 1fr auto",
          alignItems: "flex-start", gap: 10,
          padding: "10px 14px",
          borderBottom: i < events.length - 1 ? "1px solid var(--line)" : "none",
        }}>
          <span className="mono" style={{ fontSize: 10.5, color: "var(--ink-4)", paddingTop: 1 }}>{e.t}</span>
          <span style={{ width: 5, height: 5, borderRadius: 50, background: dotColor[e.kind], marginTop: 6 }}/>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 12.5, color: "var(--ink-1)", lineHeight: 1.35 }}>
              <span style={{ fontWeight: 500 }}>{e.who}</span>
              <span style={{ color: "var(--ink-3)" }}> {e.verb} </span>
              <span style={{ color: "var(--ink-1)" }}>{e.obj}</span>
            </div>
            <div className="mono" style={{ fontSize: 10.5, color: "var(--ink-4)", marginTop: 2 }}>{e.meta}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── PRODUCT FRAGMENT: KPI tile ────────────────────────────────────
function ProductKPI({ style, label, value, delta, trend = "up", sparkData }) {
  const tColor = trend === "up" ? "var(--positive)" : trend === "down" ? "var(--negative)" : "var(--ink-3)";
  return (
    <div className="card-elevated" style={{ width: 220, padding: 16, ...style }}>
      <div className="label-cap">{label}</div>
      <div className="mono" style={{ fontSize: 26, fontWeight: 500, color: "var(--ink-1)", marginTop: 8, letterSpacing: "-0.02em" }}>{value}</div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 12 }}>
        <span className="mono" style={{ fontSize: 11, color: tColor }}>{trend === "up" ? "↑" : "↓"} {delta}</span>
        <Spark data={sparkData} w={84} h={22} color={tColor}/>
      </div>
    </div>
  );
}

// ─── PRODUCT FRAGMENT: Command palette ─────────────────────────────
function ProductCommandPalette({ style }) {
  const items = [
    { i: "doc",   l: "Open invoice…",       k: "I" },
    { i: "link",  l: "Match transaction…",  k: "M" },
    { i: "spark", l: "Run reconciliation",  k: "R" },
    { i: "check", l: "Approve batch…",      k: "⏎" },
    { i: "bolt",  l: "Create rule",         k: "" },
  ];
  return (
    <div className="card-elevated" style={{ width: 320, ...style }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 14px", borderBottom: "1px solid var(--line)" }}>
        <I.command s={14} style={{ color: "var(--ink-3)" }}/>
        <span style={{ fontSize: 13, color: "var(--ink-3)", flex: 1 }}>Search or run a command…</span>
        <span className="kbd">esc</span>
      </div>
      <div>
        {items.map((it, i) => {
          const Icon = I[it.i];
          return (
            <div key={i} style={{
              display: "flex", alignItems: "center", gap: 12,
              padding: "9px 14px",
              borderBottom: i < items.length - 1 ? "1px solid var(--line)" : "none",
              background: i === 0 ? "var(--accent-tint)" : "transparent",
              borderLeft: i === 0 ? "2px solid var(--accent)" : "2px solid transparent",
              fontSize: 13,
            }}>
              <Icon s={13} style={{ color: i === 0 ? "var(--accent)" : "var(--ink-3)" }}/>
              <span style={{ flex: 1, color: "var(--ink-1)" }}>{it.l}</span>
              {it.k && <span className="kbd">{it.k}</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── PRODUCT FRAGMENT: Mini analytics chart ───────────────────────
function ProductAnalytics({ style }) {
  const W = 320, H = 140, pad = { l: 28, r: 12, t: 12, b: 22 };
  const iw = W - pad.l - pad.r;
  const ih = H - pad.t - pad.b;
  const months = ["Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr"];
  const data = [2.4, 3.1, 3.8, 3.6, 4.2, 4.8, 4.6, 5.2, 5.8];
  const max = 6.5;
  const stepX = iw / (data.length - 1);
  const pts = data.map((v, i) => [i * stepX, ih - (v / max) * ih]);
  const path = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(' ');
  const area = `${path} L${(data.length - 1) * stepX} ${ih} L0 ${ih} Z`;
  return (
    <div className="card-elevated" style={{ width: 320, ...style }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", padding: "12px 14px 4px" }}>
        <div>
          <div className="label-cap">Processed volume</div>
          <div className="mono" style={{ fontSize: 22, fontWeight: 500, color: "var(--ink-1)", letterSpacing: "-0.02em", marginTop: 4 }}>$48.27M</div>
        </div>
        <Pill kind="success" dot size="sm">+12.4%</Pill>
      </div>
      <svg width={W} height={H} style={{ display: "block" }}>
        <defs>
          <linearGradient id="ana-grad" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.18"/>
            <stop offset="100%" stopColor="var(--accent)" stopOpacity="0"/>
          </linearGradient>
        </defs>
        <g transform={`translate(${pad.l},${pad.t})`}>
          {[0, 0.5, 1].map((t, i) => (
            <line key={i} x1="0" x2={iw} y1={ih - t*ih} y2={ih - t*ih} stroke="var(--line)" strokeDasharray="2 3"/>
          ))}
          <path d={area} fill="url(#ana-grad)"/>
          <path d={path} fill="none" stroke="var(--accent)" strokeWidth="1.8" strokeLinejoin="round"/>
          {pts.map((p, i) => (
            <circle key={i} cx={p[0]} cy={p[1]} r="2.5" fill="var(--paper)" stroke="var(--accent)" strokeWidth="1.6"/>
          ))}
          {months.map((m, i) => (
            <text key={i} x={i * stepX} y={ih + 14} textAnchor="middle" fontSize="9.5" fill="var(--ink-4)" fontFamily="var(--f-mono)">{m}</text>
          ))}
        </g>
      </svg>
    </div>
  );
}

// ─── PRODUCT FRAGMENT: Processing pipeline ────────────────────────
function ProductPipeline({ style }) {
  const stages = [
    { l: "OCR",      c: 12, p: 100 },
    { l: "Extract",  c: 8,  p: 86 },
    { l: "Match",    c: 6,  p: 62 },
    { l: "Approve",  c: 3,  p: 38 },
    { l: "Post",     c: 2,  p: 22 },
  ];
  return (
    <div className="card-elevated" style={{ width: 340, padding: "14px 16px", ...style }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <I.bolt s={13} style={{ color: "var(--accent)" }}/>
          <span style={{ fontSize: 12.5, fontWeight: 500 }}>Pipeline</span>
        </div>
        <Pill kind="success" dot size="sm">Healthy</Pill>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {stages.map((s, i) => (
          <div key={s.l}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
              <span style={{ fontSize: 11.5, color: "var(--ink-2)" }}>{s.l}</span>
              <span className="mono" style={{ fontSize: 10.5, color: "var(--ink-3)" }}>{s.c} in flight</span>
            </div>
            <div style={{ height: 4, background: "rgba(20,22,30,0.05)", borderRadius: 999, overflow: "hidden" }}>
              <div style={{
                width: `${s.p}%`, height: "100%", borderRadius: 999,
                background: `linear-gradient(90deg, var(--accent), var(--accent-deep))`,
                animation: `pipeline-flow 2.4s ${i * 0.2}s ease-in-out infinite alternate`,
              }}/>
            </div>
          </div>
        ))}
      </div>
      <style>{`
        @keyframes pipeline-flow {
          from { opacity: 0.7; }
          to   { opacity: 1; }
        }
      `}</style>
    </div>
  );
}

Object.assign(window, {
  I, Pill, ConfBar, Spark,
  ProductInbox, ProductInvoicePreview, ProductRecon, ProductAudit,
  ProductKPI, ProductCommandPalette, ProductAnalytics, ProductPipeline,
});
