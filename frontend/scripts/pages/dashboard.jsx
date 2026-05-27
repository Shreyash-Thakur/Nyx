// ─── Executive Dashboard ───────────────────────────────────────────
const { useState: _useStateDash, useEffect: _useEffectDash } = React;

function DashboardPage() {
  return (
    <div className="page" data-screen-label="dashboard">
      <PageHeader/>
      <KPIGrid/>
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 14, marginTop: 14 }}>
        <ThroughputCard/>
        <ActivityCard/>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14, marginTop: 14 }}>
        <HeatmapCard/>
        <VendorExposureCard/>
        <QueueCard/>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 14, marginTop: 14 }}>
        <CashflowCard/>
        <SystemHealthCard/>
      </div>
    </div>
  );
}

function PageHeader() {
  return (
    <div className="page-header">
      <div>
        <h1 className="page-title">
          Operations overview
          <span className="live-pill" style={{ fontSize: 10 }}>
            <span className="pulse"/>
            Live
          </span>
        </h1>
        <p className="page-subtitle">Monday, April 24 · Period closes in 6 days · 3 analysts active</p>
      </div>
      <div className="page-actions">
        <div className="segment">
          <button>1H</button>
          <button>24H</button>
          <button className="active">7D</button>
          <button>30D</button>
          <button>MTD</button>
          <button>QTD</button>
        </div>
        <button className="btn btn-sm">
          <Icon name="download" size={13}/>
          Export
        </button>
        <button className="btn btn-sm">
          <Icon name="refresh" size={13}/>
        </button>
      </div>
    </div>
  );
}

function KPIGrid() {
  return (
    <div className="kpi-grid">
      {kpiTiles.map((t, i) => (
        <KPICard key={t.id} tile={t} delay={i * 0.06}/>
      ))}
    </div>
  );
}

function KPICard({ tile, delay = 0 }) {
  const trendIcon = tile.trend.dir === "up" ? "arrowUp" : tile.trend.dir === "down" ? "arrowDown" : "arrowRight";
  const trendCls = tile.trend.dir;
  const accentColor =
    tile.accent === "warning" ? "var(--warning)" :
    tile.accent === "success" ? "var(--success)" :
    tile.accent === "danger"  ? "var(--danger)" : "var(--accent)";

  return (
    <div className="kpi-card" style={{ animation: `fade-in 0.5s ${delay}s var(--ease-out) both` }}>
      <div className="accent-strip" style={{ background: `linear-gradient(90deg, transparent, ${accentColor}, transparent)` }}/>
      <div className="kpi-label">
        <Icon name={tile.icon} size={13}/>
        {tile.label}
      </div>
      <div className="kpi-value">
        {tile.value}
        {tile.unit && <span className="unit">{tile.unit}</span>}
      </div>
      <div className="kpi-meta">
        <span className={`trend ${trendCls}`}>
          <Icon name={trendIcon} size={11}/>
          {tile.trend.value}
        </span>
        <span className="dim">{tile.trend.caption}</span>
      </div>
      <div className="kpi-spark">
        <Sparkline data={tile.spark} width={86} height={32} color={accentColor}/>
      </div>
    </div>
  );
}

// ─── Throughput area chart ────────────────────────────────────────
function ThroughputCard() {
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">
            <Icon name="flow" size={14} style={{ color: "var(--accent)" }}/>
            Reconciliation throughput
          </div>
          <div className="card-subtitle">Hourly volume · matched, exceptions & manual reviews</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Badge variant="success" dot>+12.4% week-over-week</Badge>
          <button className="icon-btn" title="Expand">
            <Icon name="expand" size={13}/>
          </button>
        </div>
      </div>
      <div className="card-body" style={{ padding: "8px 16px 16px" }}>
        <AreaChart
          data={throughputData}
          keys={["matched", "exceptions", "manual"]}
          colors={["var(--c1)", "var(--c5)", "var(--c4)"]}
          height={240}
        />
      </div>
    </div>
  );
}

// ─── Live activity feed ──────────────────────────────────────────
function ActivityCard() {
  const [items, setItems] = _useStateDash(activityFeed);

  // Tiny demo: shift feed forward every 6s
  _useEffectDash(() => {
    const id = setInterval(() => {
      setItems(prev => {
        const next = [...prev];
        const head = next.shift();
        head.ts = "0s ago";
        next.push(head);
        return next.map((x, i) => ({ ...x, ts: i === next.length - 1 ? "0s ago" : x.ts }));
      });
    }, 6000);
    return () => clearInterval(id);
  }, []);

  const typeColor = {
    match: "var(--c1)", approve: "var(--success)", exception: "var(--danger)",
    link: "var(--c6)", ocr: "var(--c3)", rule: "var(--warning)",
  };

  return (
    <div className="card" style={{ display: "flex", flexDirection: "column" }}>
      <div className="card-header">
        <div className="card-title">
          <Icon name="bolt" size={14} style={{ color: "var(--accent)" }}/>
          Realtime activity
        </div>
        <Badge variant="accent" dot>1.2k/min</Badge>
      </div>
      <div style={{ flex: 1, overflow: "auto", padding: "4px 0" }}>
        {items.map((it, i) => (
          <div key={`${it.id}-${i}`} style={{
            display: "flex", alignItems: "flex-start", gap: 10,
            padding: "10px 16px", borderBottom: "1px solid var(--divider)",
            animation: i === 0 ? "slide-in-right 0.4s var(--ease-out)" : undefined,
          }}>
            <div style={{
              width: 24, height: 24, borderRadius: 6, flexShrink: 0, marginTop: 1,
              background: `${typeColor[it.type]}15`,
              border: `1px solid ${typeColor[it.type]}30`,
              display: "grid", placeItems: "center", color: typeColor[it.type],
            }}>
              <Icon name={
                it.type === "match" ? "link" :
                it.type === "approve" ? "check" :
                it.type === "exception" ? "alert" :
                it.type === "link" ? "link" :
                it.type === "ocr" ? "scan" : "bolt"
              } size={12}/>
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 12.5, color: "var(--text-1)", lineHeight: 1.35 }}>
                <span style={{ fontWeight: 500 }}>{it.who}</span>
                <span className="muted"> {it.what} </span>
                <span style={{ color: "var(--text-1)" }}>{it.detail}</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 3 }}>
                <span style={{ fontSize: 10.5, color: "var(--text-3)" }}>{it.ts}</span>
                {it.amount && <span className="mono" style={{ fontSize: 11, color: "var(--text-2)" }}>{it.amount}</span>}
              </div>
            </div>
          </div>
        ))}
      </div>
      <div className="card-footer" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span>Showing last {items.length} events</span>
        <a href="#audit" style={{ color: "var(--accent)" }}>View all →</a>
      </div>
    </div>
  );
}

// ─── Heatmap card ────────────────────────────────────────────────
function HeatmapCard() {
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">
            <Icon name="grid" size={14} style={{ color: "var(--accent)" }}/>
            Discrepancy heatmap
          </div>
          <div className="card-subtitle">Exceptions raised by day × hour</div>
        </div>
        <Badge variant="warning" dot>Peak Tue 10:00</Badge>
      </div>
      <div className="card-body">
        <Heatmap data={heatmapData} rows={heatmapDays} cols={heatmapHours}/>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 14, fontSize: 10.5, color: "var(--text-3)" }}>
          <span>Low</span>
          <div style={{ flex: 1, height: 6, margin: "0 10px", borderRadius: 999,
            background: "linear-gradient(90deg, rgba(124,107,255,0.06), rgba(124,107,255,0.85))" }}/>
          <span>High</span>
        </div>
      </div>
    </div>
  );
}

// ─── Vendor exposure donut ────────────────────────────────────────
function VendorExposureCard() {
  const total = vendorExposure.reduce((s, d) => s + d.value, 0);
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">
            <Icon name="vendors" size={14} style={{ color: "var(--accent)" }}/>
            Top vendor exposure
          </div>
          <div className="card-subtitle">% of monthly outflows · 253 active vendors</div>
        </div>
      </div>
      <div className="card-body">
        <DonutChart
          data={vendorExposure}
          size={170} thickness={20}
          label="Outflow MTD"
          value={fmtUsd(total, { cents: false })}
        />
      </div>
    </div>
  );
}

// ─── Live processing queue ───────────────────────────────────────
function QueueCard() {
  const stages = [
    { id: "ocr",     label: "OCR",      color: "var(--c3)" },
    { id: "match",   label: "Match",    color: "var(--c1)" },
    { id: "approve", label: "Approve",  color: "var(--c2)" },
    { id: "post",    label: "Post",     color: "var(--c4)" },
  ];
  const grouped = stages.map(s => ({ ...s, items: liveQueue.filter(q => q.stage === s.id) }));

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">
            <Icon name="layers" size={14} style={{ color: "var(--accent)" }}/>
            Processing pipeline
          </div>
          <div className="card-subtitle">{liveQueue.length} invoices in flight</div>
        </div>
        <Badge variant="success" dot>Healthy</Badge>
      </div>
      <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {grouped.map((s, i) => (
          <div key={s.id}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 5 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <span style={{ width: 6, height: 6, borderRadius: 50, background: s.color, boxShadow: `0 0 6px ${s.color}` }}/>
                <span style={{ fontSize: 11.5, color: "var(--text-2)", fontWeight: 500 }}>{s.label}</span>
              </div>
              <span className="mono" style={{ fontSize: 11, color: "var(--text-3)" }}>{s.items.length}</span>
            </div>
            <div style={{ display: "flex", gap: 2, height: 6, borderRadius: 999, overflow: "hidden", background: "var(--bg-3)" }}>
              {s.items.map((q, qi) => (
                <div key={qi} style={{
                  flex: 1, background: s.color, opacity: 0.85,
                  animation: `pulse-soft 1.4s ${qi * 0.15}s ease-in-out infinite`,
                }}/>
              ))}
            </div>
          </div>
        ))}
        <div style={{ marginTop: 6, padding: "10px 0 0", borderTop: "1px solid var(--divider)", fontSize: 11.5, color: "var(--text-2)", display: "flex", justifyContent: "space-between" }}>
          <span>Avg processing time</span>
          <span className="mono" style={{ color: "var(--text-1)" }}>1.84s</span>
        </div>
      </div>
    </div>
  );
}

// ─── Cashflow / monthly stacked ──────────────────────────────────
function CashflowCard() {
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">
            <Icon name="trend" size={14} style={{ color: "var(--accent)" }}/>
            Cashflow — inflow vs outflow
          </div>
          <div className="card-subtitle">Trailing 12 months · $M</div>
        </div>
        <div style={{ display: "flex", gap: 14, fontSize: 10.5 }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 5, color: "var(--text-2)" }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: "var(--c2)" }}/>
            Inflow
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 5, color: "var(--text-2)" }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: "var(--c1)" }}/>
            Outflow
          </span>
        </div>
      </div>
      <div className="card-body" style={{ padding: "8px 16px 16px" }}>
        <BarChart data={cashflow} keys={["inflow", "outflow"]} colors={["var(--c2)", "var(--c1)"]} height={200}/>
      </div>
    </div>
  );
}

// ─── System health ────────────────────────────────────────────────
function SystemHealthCard() {
  const services = [
    { name: "OCR Engine",     status: "ok",   latency: "184ms", uptime: 99.99 },
    { name: "Match Engine",   status: "ok",   latency: "32ms",  uptime: 99.98 },
    { name: "JPM Connector",  status: "ok",   latency: "412ms", uptime: 99.92 },
    { name: "Stripe Webhook", status: "warn", latency: "1.2s",  uptime: 98.4 },
    { name: "Posting Queue",  status: "ok",   latency: "44ms",  uptime: 100 },
  ];
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">
            <Icon name="shield" size={14} style={{ color: "var(--accent)" }}/>
            System health
          </div>
          <div className="card-subtitle">5 services · 30-day SLA</div>
        </div>
        <Badge variant="success" dot>99.98%</Badge>
      </div>
      <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {services.map(s => (
          <div key={s.name} style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "8px 12px", background: "var(--bg-3)", borderRadius: 8,
            border: "1px solid var(--border)",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span className={`s-dot ${s.status === "ok" ? "success" : "warning"}`}/>
              <span style={{ fontSize: 12, color: "var(--text-1)", fontWeight: 500 }}>{s.name}</span>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <span className="mono" style={{ fontSize: 11, color: "var(--text-3)" }}>{s.latency}</span>
              <span className="mono" style={{ fontSize: 11, color: "var(--text-2)", minWidth: 42, textAlign: "right" }}>{s.uptime}%</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

Object.assign(window, { DashboardPage });
