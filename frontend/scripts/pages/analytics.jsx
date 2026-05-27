// ─── Analytics & Insights ──────────────────────────────────────────

const { useState: _useStateAn, useMemo: _useMemoAn } = React;

function AnalyticsPage() {
  const [vendor, setVendor] = _useStateAn(null);

  return (
    <div className="page" data-screen-label="analytics" style={{ maxWidth: 1700 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">
            Analytics & insights
            <Badge variant="accent" dot>4 anomalies detected</Badge>
          </h1>
          <p className="page-subtitle">Vendor spend, anomaly detection & operational forecasting.</p>
        </div>
        <div className="page-actions">
          <div className="segment">
            <button>Day</button>
            <button>Week</button>
            <button className="active">Month</button>
            <button>Quarter</button>
            <button>YTD</button>
          </div>
          <button className="btn btn-sm">
            <Icon name="filter" size={13}/>
            All vendors
          </button>
          <button className="btn btn-sm btn-primary">
            <Icon name="download" size={13}/>
            Report
          </button>
        </div>
      </div>

      {/* Top metric strip */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14, marginBottom: 14 }}>
        <MetricTile title="Total spend MTD" value="$3.84M" delta="+12.4%" tone="up" sub="vs Mar 2026"/>
        <MetricTile title="Avg invoice value" value="$2,484" delta="-4.2%" tone="down" sub="trailing 30d"/>
        <MetricTile title="Cycle time" value="1.84d" delta="-18%" tone="up-good" sub="receipt → posted"/>
        <MetricTile title="DSO" value="42.1d" delta="+1.4d" tone="down-bad" sub="this quarter"/>
      </div>

      {/* Forecasting strip */}
      <ForecastCard/>

      {/* Vendor table + anomaly side */}
      <div style={{ display: "grid", gridTemplateColumns: "1.7fr 1fr", gap: 14, marginTop: 14 }}>
        <VendorPerformanceTable vendor={vendor} onSelect={setVendor}/>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <AnomalyCard/>
          <SpendCategoryCard/>
        </div>
      </div>
    </div>
  );
}

function MetricTile({ title, value, delta, tone, sub }) {
  const color =
    tone === "up" || tone === "up-good" ? "var(--success)" :
    tone === "down-bad" ? "var(--danger)" :
    tone === "down" ? "var(--text-2)" : "var(--text-3)";
  const icon = (tone === "up" || tone === "down-bad") ? "arrowUp" : "arrowDown";

  return (
    <div className="card" style={{ padding: 16 }}>
      <div style={{ fontSize: 11.5, color: "var(--text-3)", marginBottom: 8 }}>{title}</div>
      <div className="mono" style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-0.02em" }}>{value}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 6 }}>
        <span className={`trend ${tone.startsWith("up") || tone === "down-bad" ? "up" : "down"}`} style={{ color }}>
          <Icon name={icon} size={11}/> {delta}
        </span>
        <span className="dim" style={{ fontSize: 11 }}>{sub}</span>
      </div>
    </div>
  );
}

// ─── Forecast / trend chart ─────────────────────────────────────
function ForecastCard() {
  // Build trend with forecast extension
  const data = _useMemoAn(() => {
    const r = seededRand(13);
    const out = [];
    const months = ["Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"];
    for (let i = 0; i < 12; i++) {
      const base = 2.4 + i * 0.18 + Math.sin(i / 2) * 0.3 + r() * 0.2;
      const forecast = i >= 8;
      out.push({ t: months[i], actual: forecast ? null : +(base).toFixed(2), forecast: forecast ? +(base * 1.04).toFixed(2) : null, upper: forecast ? +(base * 1.18).toFixed(2) : null, lower: forecast ? +(base * 0.88).toFixed(2) : null });
    }
    return out;
  }, []);

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">
            <Icon name="trend" size={14} style={{ color: "var(--accent)" }}/>
            Operational spend — actuals & forecast
          </div>
          <div className="card-subtitle">12-month trailing · 4-month projection (95% confidence band)</div>
        </div>
        <div style={{ display: "flex", gap: 14, fontSize: 10.5, color: "var(--text-2)" }}>
          <Lk c="var(--accent)" l="Actual"/>
          <Lk c="var(--c2)" l="Forecast" dashed/>
          <Lk c="rgba(124,107,255,0.2)" l="95% band" block/>
        </div>
      </div>
      <div className="card-body" style={{ padding: "12px 16px 16px" }}>
        <ForecastChart data={data} height={220}/>
      </div>
    </div>
  );
}

function Lk({ c, l, dashed, block }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
      {block ? <span style={{ width: 14, height: 8, background: c, borderRadius: 2 }}/>
        : <span style={{ width: 14, height: 0, borderTop: `1.5px ${dashed ? "dashed" : "solid"} ${c}` }}/>}
      {l}
    </span>
  );
}

function ForecastChart({ data, height = 220 }) {
  const [ref, { w }] = useMeasure();
  const pad = { l: 36, r: 16, t: 8, b: 24 };
  const innerW = Math.max(0, w - pad.l - pad.r);
  const innerH = height - pad.t - pad.b;

  const max = Math.max(...data.map(d => Math.max(d.actual || 0, d.forecast || 0, d.upper || 0))) * 1.1;
  const stepX = innerW / Math.max(1, data.length - 1);

  // path builders
  const yOf = v => innerH - (v / max) * innerH;

  const actualPts = data.map((d, i) => d.actual !== null ? [i * stepX, yOf(d.actual)] : null);
  const actualPath = actualPts.filter(Boolean).map((p, i) => `${i === 0 ? "M" : "L"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ");

  // forecast — connect last actual point to forecast
  const lastActualIdx = data.findIndex(d => d.actual === null) - 1;
  const forecastPts = [];
  if (lastActualIdx >= 0) forecastPts.push([lastActualIdx * stepX, yOf(data[lastActualIdx].actual)]);
  data.forEach((d, i) => { if (d.forecast !== null) forecastPts.push([i * stepX, yOf(d.forecast)]); });
  const forecastPath = forecastPts.map((p, i) => `${i === 0 ? "M" : "L"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ");

  // band
  const upperPts = data.filter(d => d.upper !== null).map((d, i) => {
    const di = data.findIndex(x => x === d);
    return [di * stepX, yOf(d.upper)];
  });
  const lowerPts = data.filter(d => d.lower !== null).map((d, i) => {
    const di = data.findIndex(x => x === d);
    return [di * stepX, yOf(d.lower)];
  });
  const bandPath = upperPts.length > 0
    ? `M${upperPts[0][0]} ${upperPts[0][1]} ${upperPts.slice(1).map(p => `L${p[0]} ${p[1]}`).join(" ")} ${lowerPts.slice().reverse().map(p => `L${p[0]} ${p[1]}`).join(" ")} Z`
    : "";

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map(t => ({ y: innerH - t * innerH, v: (max * t).toFixed(1) + "M" }));

  return (
    <div ref={ref} style={{ width: "100%", height }}>
      {w > 0 && (
        <svg width={w} height={height}>
          <defs>
            <linearGradient id="actual-grad" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.3"/>
              <stop offset="100%" stopColor="var(--accent)" stopOpacity="0"/>
            </linearGradient>
          </defs>
          <g transform={`translate(${pad.l},${pad.t})`}>
            {yTicks.map((t, i) => (
              <g key={i}>
                <line x1="0" x2={innerW} y1={t.y} y2={t.y} stroke="var(--border)" strokeDasharray="2 3"/>
                <text x="-8" y={t.y + 3} textAnchor="end" fontSize="10" fill="var(--text-3)" fontFamily="var(--font-mono)">${t.v}</text>
              </g>
            ))}
            {/* Forecast section divider */}
            {lastActualIdx >= 0 && (
              <line x1={lastActualIdx * stepX} x2={lastActualIdx * stepX}
                y1="0" y2={innerH} stroke="var(--border-strong)" strokeDasharray="3 4"/>
            )}
            {/* Confidence band */}
            <path d={bandPath} fill="var(--accent-soft)" opacity="0.5"/>
            {/* Actual area + line */}
            <path d={`${actualPath} L${lastActualIdx * stepX} ${innerH} L0 ${innerH} Z`} fill="url(#actual-grad)"/>
            <path d={actualPath} fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinejoin="round"
              style={{ strokeDasharray: 2000, strokeDashoffset: 2000, animation: "spark-draw 1.6s var(--ease-out) forwards" }}/>
            {/* Forecast dashed */}
            <path d={forecastPath} fill="none" stroke="var(--c2)" strokeWidth="2" strokeDasharray="4 4"
              style={{ strokeDasharray: 2000, strokeDashoffset: 2000, animation: "spark-draw 1.6s 0.3s var(--ease-out) forwards" }}/>
            {/* Data points */}
            {data.map((d, i) => {
              if (d.actual !== null) return <circle key={i} cx={i * stepX} cy={yOf(d.actual)} r="3" fill="var(--bg-1)" stroke="var(--accent)" strokeWidth="2"/>;
              if (d.forecast !== null) return <circle key={i} cx={i * stepX} cy={yOf(d.forecast)} r="3" fill="var(--bg-1)" stroke="var(--c2)" strokeWidth="2"/>;
              return null;
            })}
            {/* x-axis */}
            {data.map((d, i) => (
              <text key={i} x={i * stepX} y={innerH + 18} textAnchor="middle" fontSize="10"
                fill={i > lastActualIdx ? "var(--c2)" : "var(--text-3)"} fontWeight={i > lastActualIdx ? 500 : 400}>
                {d.t}
              </text>
            ))}
            {/* Forecast badge */}
            {lastActualIdx >= 0 && (
              <g transform={`translate(${lastActualIdx * stepX + 8}, 4)`}>
                <rect width="58" height="18" rx="4" fill="var(--bg-4)" stroke="var(--border-strong)"/>
                <text x="29" y="12" textAnchor="middle" fontSize="10" fill="var(--c2)" fontFamily="var(--font-mono)">FORECAST</text>
              </g>
            )}
          </g>
        </svg>
      )}
    </div>
  );
}

// ─── Vendor performance table ──────────────────────────────────
function VendorPerformanceTable({ vendor, onSelect }) {
  const [sortBy, setSortBy] = _useStateAn("spend");
  const rows = [...vendorPerformance].sort((a, b) => b[sortBy] - a[sortBy]);

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">
            <Icon name="vendors" size={14} style={{ color: "var(--accent)" }}/>
            Vendor performance
          </div>
          <div className="card-subtitle">{rows.length} vendors · sorted by {sortBy}</div>
        </div>
        <div className="segment">
          <button className={sortBy === "spend" ? "active" : ""} onClick={() => setSortBy("spend")}>Spend</button>
          <button className={sortBy === "invoices" ? "active" : ""} onClick={() => setSortBy("invoices")}>Volume</button>
          <button className={sortBy === "change" ? "active" : ""} onClick={() => setSortBy("change")}>Δ%</button>
        </div>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table className="tbl">
          <thead>
            <tr>
              <th>Vendor</th>
              <th style={{ textAlign: "right" }}>Spend (MTD)</th>
              <th style={{ textAlign: "center" }}>Invoices</th>
              <th style={{ textAlign: "right" }}>Avg</th>
              <th style={{ textAlign: "center" }}>On-time</th>
              <th>Trend</th>
              <th style={{ textAlign: "right" }}>vs prev</th>
              <th>Flags</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((v, i) => {
              const maxSpend = rows[0].spend;
              const spendPct = (v.spend / maxSpend) * 100;
              return (
                <tr key={v.vendor} onClick={() => onSelect(v)}
                  style={{ cursor: "pointer" }}>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <div style={{
                        width: 24, height: 24, borderRadius: 5,
                        background: `var(--c${(i % 7) + 1})`, opacity: 0.85,
                        display: "grid", placeItems: "center",
                        fontSize: 10, fontWeight: 600, color: "rgba(0,0,0,0.7)",
                      }}>{v.vendor.slice(0, 2).toUpperCase()}</div>
                      <span className="primary">{v.vendor}</span>
                    </div>
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "flex-end" }}>
                      <div style={{ width: 50, height: 4, background: "var(--bg-3)", borderRadius: 999, overflow: "hidden" }}>
                        <div style={{ width: `${spendPct}%`, height: "100%", background: `var(--c${(i % 7) + 1})`, opacity: 0.85 }}/>
                      </div>
                      <span className="mono" style={{ color: "var(--text-1)", minWidth: 70, textAlign: "right" }}>
                        {fmtUsd(v.spend, { cents: false })}
                      </span>
                    </div>
                  </td>
                  <td style={{ textAlign: "center" }} className="mono">{v.invoices}</td>
                  <td className="num">{fmtUsd(v.avg, { cents: false })}</td>
                  <td style={{ textAlign: "center" }}>
                    <span className="mono" style={{ color: v.onTime >= 99 ? "var(--success)" : v.onTime >= 90 ? "var(--warning)" : "var(--danger)" }}>
                      {v.onTime}%
                    </span>
                  </td>
                  <td><Sparkline data={genSpark(v.vendor)} width={70} height={22} color={v.change >= 0 ? "var(--c2)" : "var(--c5)"}/></td>
                  <td style={{ textAlign: "right" }}>
                    <span className={`trend ${v.change > 0 ? "up" : v.change < 0 ? "down" : "flat"}`}>
                      {v.change > 0 ? "+" : ""}{v.change}%
                    </span>
                  </td>
                  <td>
                    {v.anomaly > 0 ? <Badge variant="warning" dot>{v.anomaly}</Badge> : <span style={{ color: "var(--text-4)" }}>—</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function genSpark(seed) {
  const r = seededRand(seed.charCodeAt(0));
  return Array.from({ length: 12 }, () => 20 + r() * 60);
}

// ─── Anomaly card ────────────────────────────────────────────────
function AnomalyCard() {
  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">
            <Icon name="alert" size={14} style={{ color: "var(--warning)" }}/>
            Anomalies detected
          </div>
          <div className="card-subtitle">AI flagged 4 outliers this week</div>
        </div>
        <a style={{ color: "var(--accent)", fontSize: 11.5 }} href="#">Tune →</a>
      </div>
      <div className="card-body" style={{ padding: 0 }}>
        {anomalies.map((a, i) => {
          const color = a.severity === "high" ? "var(--danger)" : a.severity === "medium" ? "var(--warning)" : "var(--info)";
          return (
            <div key={a.id} style={{
              display: "flex", alignItems: "flex-start", gap: 10,
              padding: "12px 16px", borderBottom: i < anomalies.length - 1 ? "1px solid var(--divider)" : "none",
            }}>
              <div style={{
                width: 28, height: 28, borderRadius: 8,
                background: `${color}15`, border: `1px solid ${color}40`,
                display: "grid", placeItems: "center", color,
                flexShrink: 0,
              }}>
                <Icon name="zap" size={13}/>
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 12.5, color: "var(--text-1)", fontWeight: 500 }}>{a.vendor}</span>
                  <Badge variant={a.severity === "high" ? "danger" : a.severity === "medium" ? "warning" : "info"}>
                    {a.severity}
                  </Badge>
                </div>
                <div style={{ fontSize: 11.5, color: "var(--text-2)", marginTop: 3 }}>{a.desc}</div>
              </div>
              <span className="mono" style={{ fontSize: 11.5, color, fontWeight: 500 }}>{a.amount}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Spend category breakdown ────────────────────────────────────
function SpendCategoryCard() {
  const cats = [
    { name: "Infrastructure",  value: 1680, color: "var(--c1)" },
    { name: "SaaS subscriptions", value: 920, color: "var(--c2)" },
    { name: "Professional svcs",  value: 612, color: "var(--c3)" },
    { name: "Marketing",          value: 348, color: "var(--c4)" },
    { name: "Travel & ops",       value: 280, color: "var(--c5)" },
  ];
  const total = cats.reduce((s, c) => s + c.value, 0);

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">
            <Icon name="layers" size={14} style={{ color: "var(--accent)" }}/>
            Spend by category
          </div>
          <div className="card-subtitle">Month-to-date · ${total/1000}M total</div>
        </div>
      </div>
      <div className="card-body">
        {/* horizontal stacked bar */}
        <div style={{ display: "flex", height: 8, borderRadius: 999, overflow: "hidden", marginBottom: 14 }}>
          {cats.map((c, i) => (
            <div key={i} style={{
              width: `${(c.value / total) * 100}%`, background: c.color,
              borderRight: i < cats.length - 1 ? "1px solid var(--bg-2)" : "none",
            }}/>
          ))}
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 9 }}>
          {cats.map((c, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: c.color, flexShrink: 0 }}/>
              <span style={{ flex: 1, fontSize: 12, color: "var(--text-1)" }}>{c.name}</span>
              <span className="mono" style={{ fontSize: 11.5, color: "var(--text-2)" }}>
                ${(c.value / 1000).toFixed(2)}M
              </span>
              <span className="mono" style={{ fontSize: 11, color: "var(--text-3)", minWidth: 38, textAlign: "right" }}>
                {((c.value / total) * 100).toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { AnalyticsPage });
