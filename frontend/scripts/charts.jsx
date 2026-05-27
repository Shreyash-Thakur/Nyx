// Custom SVG chart primitives — Recharts-style look, hand-rolled for full control.
// All charts auto-scale to container width via ResizeObserver.

const { useRef, useEffect, useState, useMemo, useLayoutEffect } = React;

// ─── Container with width tracking ─────────────────────────────────
function useMeasure() {
  const ref = useRef(null);
  const [box, setBox] = useState({ w: 0, h: 0 });
  useLayoutEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setBox({ w: width, h: height });
    });
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, []);
  return [ref, box];
}

// ─── Sparkline ─────────────────────────────────────────────────────
function Sparkline({ data, width = 96, height = 36, color = "var(--accent)", fill = true, animate = true }) {
  const { path, area } = useMemo(() => {
    if (!data || !data.length) return { path: "", area: "" };
    const min = Math.min(...data), max = Math.max(...data);
    const range = max - min || 1;
    const stepX = width / (data.length - 1);
    const pts = data.map((v, i) => [i * stepX, height - 4 - ((v - min) / range) * (height - 8)]);
    const path = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ");
    const area = `${path} L${width} ${height} L0 ${height} Z`;
    return { path, area };
  }, [data, width, height]);

  const gradId = useMemo(() => `spark-${Math.random().toString(36).slice(2, 9)}`, []);
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ overflow: "visible" }}>
      {fill && (<defs>
        <linearGradient id={gradId} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35"/>
          <stop offset="100%" stopColor={color} stopOpacity="0"/>
        </linearGradient>
      </defs>)}
      {fill && <path d={area} fill={`url(#${gradId})`} />}
      <path
        d={path} fill="none" stroke={color} strokeWidth="1.4"
        strokeLinejoin="round" strokeLinecap="round"
        style={animate ? { strokeDasharray: 600, strokeDashoffset: 600, animation: "spark-draw 1.2s var(--ease-out) forwards" } : {}}
      />
    </svg>
  );
}

// ─── Area chart with grid + axis ──────────────────────────────────
function AreaChart({ data, keys, height = 240, colors = ["var(--c1)", "var(--c2)", "var(--c5)"], xKey = "t", showLegend = true, showAxis = true }) {
  const [ref, { w }] = useMeasure();
  const pad = { l: 36, r: 16, t: 16, b: showAxis ? 28 : 8 };
  const innerW = Math.max(0, w - pad.l - pad.r);
  const innerH = height - pad.t - pad.b;
  const [hover, setHover] = useState(null);

  const series = useMemo(() => {
    if (!w) return [];
    const all = data.flatMap(d => keys.map(k => d[k] || 0));
    const max = Math.max(...all, 1);
    const stepX = innerW / Math.max(1, data.length - 1);
    return keys.map((k, ki) => {
      const pts = data.map((d, i) => [i * stepX, innerH - (d[k] / max) * innerH]);
      const path = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join(" ");
      const area = `${path} L${(data.length - 1) * stepX} ${innerH} L0 ${innerH} Z`;
      return { key: k, color: colors[ki % colors.length], path, area, max, pts };
    });
  }, [data, w, innerH, innerW, keys, colors]);

  const yTicks = useMemo(() => {
    if (!series.length) return [];
    const max = series[0].max;
    return [0, 0.25, 0.5, 0.75, 1].map(t => ({ y: innerH - t * innerH, v: Math.round(max * t) }));
  }, [series, innerH]);

  const onMove = (e) => {
    if (!w) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left - pad.l;
    const i = Math.round((x / innerW) * (data.length - 1));
    if (i >= 0 && i < data.length) setHover({ i, x: i * (innerW / Math.max(1, data.length - 1)) });
  };

  return (
    <div ref={ref} style={{ width: "100%", height, position: "relative" }}>
      {w > 0 && (
        <svg width={w} height={height} onMouseMove={onMove} onMouseLeave={() => setHover(null)} style={{ display: "block" }}>
          <defs>
            {series.map((s, i) => (
              <linearGradient key={i} id={`area-${i}`} x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor={s.color} stopOpacity="0.30"/>
                <stop offset="100%" stopColor={s.color} stopOpacity="0"/>
              </linearGradient>
            ))}
          </defs>
          <g transform={`translate(${pad.l},${pad.t})`}>
            {/* Grid */}
            {yTicks.map((t, i) => (
              <g key={i}>
                <line x1="0" x2={innerW} y1={t.y} y2={t.y} stroke="var(--border)" strokeDasharray="2 3" />
                <text x="-8" y={t.y + 3} textAnchor="end" fontSize="10" fill="var(--text-3)" fontFamily="var(--font-mono)">
                  {t.v >= 1000 ? `${(t.v/1000).toFixed(1)}k` : t.v}
                </text>
              </g>
            ))}
            {showAxis && data.map((d, i) => {
              if (i % Math.ceil(data.length / 8) !== 0) return null;
              const x = i * (innerW / Math.max(1, data.length - 1));
              return <text key={i} x={x} y={innerH + 18} textAnchor="middle" fontSize="10" fill="var(--text-3)">{d[xKey]}</text>;
            })}
            {/* Areas */}
            {series.map((s, i) => (
              <g key={i}>
                <path d={s.area} fill={`url(#area-${i})`} />
                <path d={s.path} fill="none" stroke={s.color} strokeWidth="1.6" strokeLinejoin="round"
                  style={{ strokeDasharray: 2000, strokeDashoffset: 2000, animation: `spark-draw 1.4s ${0.1*i}s var(--ease-out) forwards` }} />
              </g>
            ))}
            {/* Hover */}
            {hover && (
              <g>
                <line x1={hover.x} x2={hover.x} y1="0" y2={innerH} stroke="var(--border-bright)" strokeWidth="1"/>
                {series.map((s, i) => {
                  const p = s.pts[hover.i];
                  return p ? (
                    <circle key={i} cx={p[0]} cy={p[1]} r="3.5" fill="var(--bg-1)" stroke={s.color} strokeWidth="2"/>
                  ) : null;
                })}
              </g>
            )}
          </g>
          <style>{`@keyframes spark-draw { to { stroke-dashoffset: 0; } }`}</style>
        </svg>
      )}
      {hover && (
        <div style={{
          position: "absolute", left: pad.l + hover.x + 8, top: 8, pointerEvents: "none",
          background: "var(--bg-4)", border: "1px solid var(--border-strong)", borderRadius: 8,
          padding: "8px 10px", fontSize: 11, color: "var(--text-1)", boxShadow: "var(--sh-3)", minWidth: 120,
        }}>
          <div className="muted" style={{ marginBottom: 4, fontSize: 10 }}>{data[hover.i]?.[xKey]}</div>
          {keys.map((k, i) => (
            <div key={k} style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "space-between" }}>
              <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: colors[i % colors.length] }}/>
                <span className="muted" style={{ textTransform: "capitalize" }}>{k}</span>
              </span>
              <span className="mono">{data[hover.i]?.[k]?.toLocaleString()}</span>
            </div>
          ))}
        </div>
      )}
      {showLegend && (
        <div style={{ position: "absolute", top: 4, right: 8, display: "flex", gap: 12, fontSize: 10.5 }}>
          {keys.map((k, i) => (
            <span key={k} style={{ display: "inline-flex", alignItems: "center", gap: 5, color: "var(--text-2)" }}>
              <span style={{ width: 8, height: 8, borderRadius: 2, background: colors[i % colors.length] }}/>
              <span style={{ textTransform: "capitalize" }}>{k}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Bar chart (grouped/stacked) ──────────────────────────────────
function BarChart({ data, keys, height = 220, colors = ["var(--c1)", "var(--c2)"], xKey = "m", stacked = false }) {
  const [ref, { w }] = useMeasure();
  const pad = { l: 32, r: 12, t: 12, b: 22 };
  const innerW = Math.max(0, w - pad.l - pad.r);
  const innerH = height - pad.t - pad.b;
  const groupW = innerW / data.length;
  const [hover, setHover] = useState(null);

  const max = useMemo(() => {
    if (stacked) return Math.max(...data.map(d => keys.reduce((s, k) => s + (d[k] || 0), 0)), 1);
    return Math.max(...data.flatMap(d => keys.map(k => d[k] || 0)), 1);
  }, [data, keys, stacked]);

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map(t => ({ y: innerH - t * innerH, v: (max * t).toFixed(1) }));

  return (
    <div ref={ref} style={{ width: "100%", height }}>
      {w > 0 && (
        <svg width={w} height={height}>
          <g transform={`translate(${pad.l},${pad.t})`}>
            {yTicks.map((t, i) => (
              <g key={i}>
                <line x1="0" x2={innerW} y1={t.y} y2={t.y} stroke="var(--border)" strokeDasharray="2 3"/>
                <text x="-6" y={t.y + 3} textAnchor="end" fontSize="10" fill="var(--text-3)" fontFamily="var(--font-mono)">{t.v}</text>
              </g>
            ))}
            {data.map((d, di) => {
              const cx = di * groupW + groupW / 2;
              const barW = stacked ? Math.min(28, groupW * 0.45) : Math.min(12, groupW * 0.3);
              let y = innerH;
              return (
                <g key={di} transform={`translate(${cx},0)`} onMouseEnter={() => setHover(di)} onMouseLeave={() => setHover(null)}>
                  {keys.map((k, ki) => {
                    const h = ((d[k] || 0) / max) * innerH;
                    if (stacked) {
                      y -= h;
                      return (
                        <rect key={k} x={-barW/2} y={y} width={barW} height={h}
                          fill={colors[ki % colors.length]} opacity={hover === di ? 1 : 0.85}
                          style={{ transformOrigin: `0 ${innerH}px`, transform: "scaleY(0)", animation: `bar-grow .8s ${0.05*di + 0.1*ki}s var(--ease-out) forwards`, transformBox: "fill-box" }}
                        />
                      );
                    } else {
                      const offset = (ki - (keys.length - 1) / 2) * (barW + 2);
                      return (
                        <rect key={k} x={offset - barW/2} y={innerH - h} width={barW} height={h}
                          fill={colors[ki % colors.length]} opacity={hover === di ? 1 : 0.85}
                          rx="1.5"
                          style={{ transformOrigin: `0 ${innerH}px`, transform: "scaleY(0)", animation: `bar-grow .8s ${0.05*di}s var(--ease-out) forwards`, transformBox: "fill-box" }}
                        />
                      );
                    }
                  })}
                  <text y={innerH + 14} textAnchor="middle" fontSize="10" fill="var(--text-3)">{d[xKey]}</text>
                </g>
              );
            })}
          </g>
          <style>{`@keyframes bar-grow { from { transform: scaleY(0); } to { transform: scaleY(1); } }`}</style>
        </svg>
      )}
    </div>
  );
}

// ─── Donut chart ──────────────────────────────────────────────────
function DonutChart({ data, size = 200, thickness = 18, label, value }) {
  const total = data.reduce((s, d) => s + d.value, 0);
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  let cum = 0;
  const [hoverIdx, setHoverIdx] = useState(null);

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
      <div style={{ position: "relative", width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: "rotate(-90deg)" }}>
          <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--bg-3)" strokeWidth={thickness}/>
          {data.map((d, i) => {
            const pct = d.value / total;
            const len = pct * c;
            const off = c - cum * c;
            cum += pct;
            return (
              <circle key={i}
                cx={size/2} cy={size/2} r={r}
                fill="none" stroke={d.color} strokeWidth={hoverIdx === i ? thickness + 3 : thickness}
                strokeDasharray={`${len} ${c}`} strokeDashoffset={-(c - off)}
                onMouseEnter={() => setHoverIdx(i)} onMouseLeave={() => setHoverIdx(null)}
                style={{ transition: "stroke-width .2s var(--ease-out)", cursor: "pointer",
                  strokeDasharray: `0 ${c}`,
                  animation: `donut-grow 1s ${0.08*i}s var(--ease-out) forwards`,
                  ['--final-len']: `${len} ${c}`,
                }}
              />
            );
          })}
        </svg>
        <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", textAlign: "center" }}>
          <div>
            <div className="muted" style={{ fontSize: 11, marginBottom: 2 }}>{hoverIdx !== null ? data[hoverIdx].name : label}</div>
            <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em" }} className="mono">
              {hoverIdx !== null
                ? `${((data[hoverIdx].value / total) * 100).toFixed(1)}%`
                : value}
            </div>
          </div>
        </div>
        <style>{`@keyframes donut-grow { to { stroke-dasharray: var(--final-len); } }`}</style>
      </div>
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 8 }}>
        {data.map((d, i) => (
          <div key={i}
            onMouseEnter={() => setHoverIdx(i)} onMouseLeave={() => setHoverIdx(null)}
            style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer",
              opacity: hoverIdx !== null && hoverIdx !== i ? 0.45 : 1, transition: "opacity .15s" }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: d.color, flexShrink: 0 }}/>
            <span style={{ flex: 1, fontSize: 12, color: "var(--text-1)" }}>{d.name}</span>
            <span className="mono" style={{ fontSize: 11.5, color: "var(--text-2)" }}>
              {((d.value / total) * 100).toFixed(1)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Heatmap ──────────────────────────────────────────────────────
function Heatmap({ data, rows, cols, maxVal }) {
  const [hover, setHover] = useState(null);
  const max = maxVal || Math.max(...data.flat());

  return (
    <div style={{ position: "relative" }}>
      <div style={{ display: "grid", gridTemplateColumns: `40px repeat(${cols.length}, 1fr)`, gap: 3 }}>
        <div/>
        {cols.map((c, i) => (
          <div key={i} style={{ fontSize: 9.5, color: "var(--text-3)", textAlign: "center", fontFamily: "var(--font-mono)" }}>{c}</div>
        ))}
        {rows.map((r, ri) => (
          <React.Fragment key={ri}>
            <div style={{ fontSize: 10.5, color: "var(--text-3)", display: "flex", alignItems: "center" }}>{r}</div>
            {cols.map((_, ci) => {
              const v = data[ri][ci];
              const intensity = v / max;
              const isHover = hover && hover[0] === ri && hover[1] === ci;
              return (
                <div key={ci}
                  onMouseEnter={() => setHover([ri, ci])}
                  onMouseLeave={() => setHover(null)}
                  style={{
                    aspectRatio: "1.6",
                    background: `rgba(124, 107, 255, ${0.06 + intensity * 0.7})`,
                    border: `1px solid ${isHover ? "var(--accent)" : "rgba(124, 107, 255, " + (0.05 + intensity * 0.3) + ")"}`,
                    borderRadius: 4,
                    display: "grid", placeItems: "center",
                    fontSize: 10,
                    color: intensity > 0.5 ? "var(--text-1)" : "var(--text-3)",
                    fontFamily: "var(--font-mono)",
                    cursor: "pointer",
                    transition: "all .12s var(--ease-out)",
                    transform: isHover ? "scale(1.06)" : "scale(1)",
                  }}>
                  {v > 0 ? v : ""}
                </div>
              );
            })}
          </React.Fragment>
        ))}
      </div>
      {hover && (
        <div style={{
          position: "absolute", top: -38, left: 0, background: "var(--bg-4)",
          border: "1px solid var(--border-strong)", borderRadius: 8,
          padding: "6px 10px", fontSize: 11, color: "var(--text-1)", boxShadow: "var(--sh-2)",
          pointerEvents: "none",
        }}>
          {rows[hover[0]]} · {cols[hover[1]]}:00 · <span className="mono" style={{ color: "var(--accent)" }}>{data[hover[0]][hover[1]]} exceptions</span>
        </div>
      )}
    </div>
  );
}

// ─── Counter that animates from 0 ───────────────────────────────────
function Counter({ to, duration = 1200, format = (v) => v.toLocaleString(), prefix = "", suffix = "" }) {
  const [v, setV] = useState(0);
  useEffect(() => {
    let raf, start;
    const step = (ts) => {
      if (!start) start = ts;
      const p = Math.min(1, (ts - start) / duration);
      const eased = 1 - Math.pow(1 - p, 3);
      setV(to * eased);
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [to, duration]);
  return <>{prefix}{format(v)}{suffix}</>;
}

// ─── Radial gauge ──────────────────────────────────────────────────
function Gauge({ value, max = 100, size = 120, thickness = 10, color = "var(--accent)", label }) {
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.min(1, value / max);
  const dash = pct * c * 0.75; // 270deg arc

  return (
    <div style={{ position: "relative", width: size, height: size }}>
      <svg width={size} height={size} style={{ transform: "rotate(135deg)" }}>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--bg-3)" strokeWidth={thickness}
          strokeDasharray={`${c * 0.75} ${c}`} strokeLinecap="round"/>
        <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={thickness}
          strokeDasharray={`${dash} ${c}`} strokeLinecap="round"
          style={{ transition: "stroke-dasharray .8s var(--ease-out)" }}/>
      </svg>
      <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", textAlign: "center" }}>
        <div>
          <div className="mono" style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em" }}>
            <Counter to={value} format={(v) => v.toFixed(1)}/>
          </div>
          <div className="muted" style={{ fontSize: 10.5, marginTop: 1 }}>{label}</div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { Sparkline, AreaChart, BarChart, DonutChart, Heatmap, Counter, Gauge });
