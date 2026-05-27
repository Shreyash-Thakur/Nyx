// ─── Audit Timeline ────────────────────────────────────────────────
// Interactive timeline with event playback feel, filtering, expandable logs.

const { useState: _useStateAud, useEffect: _useEffectAud, useMemo: _useMemoAud } = React;

function AuditPage() {
  const [filter, setFilter] = _useStateAud(null);
  const [selected, setSelected] = _useStateAud(auditEvents[0]);
  const [playing, setPlaying] = _useStateAud(false);

  const filtered = filter ? auditEvents.filter(e => e.type === filter) : auditEvents;

  // Group by date
  const grouped = _useMemoAud(() => {
    const out = {};
    filtered.forEach(e => { (out[e.date] ||= []).push(e); });
    return Object.entries(out);
  }, [filtered]);

  // Playback — auto-step through events
  _useEffectAud(() => {
    if (!playing) return;
    const id = setInterval(() => {
      setSelected(cur => {
        const idx = filtered.findIndex(e => e.id === cur?.id);
        const next = filtered[(idx + 1) % filtered.length];
        return next;
      });
    }, 1400);
    return () => clearInterval(id);
  }, [playing, filtered]);

  return (
    <div className="page" data-screen-label="audit" style={{ maxWidth: 1600 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">
            Audit timeline
            <Badge variant="info">12 events · 24h</Badge>
          </h1>
          <p className="page-subtitle">Every change to the ledger, immutably logged.</p>
        </div>
        <div className="page-actions">
          <button className="btn btn-sm">
            <Icon name="filter" size={13}/>
            User: All
          </button>
          <button className="btn btn-sm">
            <Icon name="history" size={13}/>
            Range: 24h
          </button>
          <button className="btn btn-sm" onClick={() => setPlaying(!playing)}>
            <Icon name={playing ? "pause" : "play"} size={13}/>
            {playing ? "Pause" : "Playback"}
          </button>
          <button className="btn btn-sm btn-primary">
            <Icon name="download" size={13}/>
            Export to SIEM
          </button>
        </div>
      </div>

      {/* Filter chips */}
      <div style={{ display: "flex", gap: 6, marginBottom: 14, flexWrap: "wrap" }}>
        <FilterChip label="All events" active={!filter} onClick={() => setFilter(null)} count={auditEvents.length}/>
        {Object.entries(auditTypeMeta).map(([key, meta]) => {
          const count = auditEvents.filter(e => e.type === key).length;
          if (count === 0) return null;
          return (
            <FilterChip key={key} label={meta.label} color={meta.color}
              active={filter === key} onClick={() => setFilter(filter === key ? null : key)}
              count={count}/>
          );
        })}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: 14, alignItems: "start" }}>
        <div className="card" style={{ overflow: "visible" }}>
          <div className="card-header">
            <div className="card-title">
              <Icon name="history" size={14} style={{ color: "var(--accent)" }}/>
              Activity stream
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              <button className="icon-btn"><Icon name="refresh" size={13}/></button>
              <button className="icon-btn"><Icon name="expand" size={13}/></button>
            </div>
          </div>
          <div className="card-body" style={{ padding: "8px 0" }}>
            <TimelineStream grouped={grouped} selected={selected} onSelect={setSelected} playing={playing}/>
          </div>
        </div>

        <EventDetail event={selected}/>
      </div>
    </div>
  );
}

function FilterChip({ label, active, color, onClick, count }) {
  return (
    <button onClick={onClick} style={{
      display: "inline-flex", alignItems: "center", gap: 6,
      padding: "5px 10px", borderRadius: 999,
      background: active ? (color ? `${color}18` : "var(--accent-soft)") : "var(--bg-3)",
      border: `1px solid ${active ? (color || "var(--accent)") : "var(--border)"}`,
      color: active ? (color || "var(--accent)") : "var(--text-2)",
      fontSize: 11.5, fontWeight: 500,
      transition: "all 0.15s",
    }}>
      {color && <span style={{ width: 6, height: 6, borderRadius: 50, background: color }}/>}
      {label}
      <span style={{ fontSize: 10, opacity: 0.7 }}>{count}</span>
    </button>
  );
}

// ─── Timeline stream ─────────────────────────────────────────────
function TimelineStream({ grouped, selected, onSelect, playing }) {
  return (
    <div style={{ position: "relative" }}>
      {/* Vertical rail */}
      <div style={{
        position: "absolute", left: 76, top: 12, bottom: 12, width: 1,
        background: "linear-gradient(180deg, var(--accent-glow), var(--border) 16%, var(--border) 84%, var(--accent-glow))",
      }}/>
      {grouped.map(([date, events], gi) => (
        <div key={date}>
          <div style={{
            position: "sticky", top: 0, zIndex: 2,
            display: "flex", alignItems: "center", gap: 8,
            padding: "8px 16px 6px 84px",
            background: "linear-gradient(180deg, var(--bg-2) 60%, transparent)",
            fontSize: 11, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: 0.6, fontWeight: 500,
          }}>
            <span>{date}, 2026</span>
            <span style={{ flex: 1, height: 1, background: "var(--divider)" }}/>
            <span style={{ fontFamily: "var(--font-mono)", textTransform: "none", letterSpacing: 0 }}>
              {events.length} events
            </span>
          </div>
          {events.map((e, i) => {
            const meta = auditTypeMeta[e.type];
            const isSel = selected?.id === e.id;
            return (
              <div key={e.id} onClick={() => onSelect(e)}
                style={{
                  display: "grid", gridTemplateColumns: "60px 32px 1fr auto",
                  alignItems: "flex-start", gap: 12,
                  padding: "10px 16px", cursor: "pointer",
                  background: isSel ? "var(--accent-soft)" : undefined,
                  borderLeft: isSel ? "2px solid var(--accent)" : "2px solid transparent",
                  transition: "background .12s",
                }}>
                <div className="mono" style={{
                  fontSize: 10.5, color: "var(--text-3)", textAlign: "right",
                  paddingTop: 4,
                }}>{e.t}</div>
                <div style={{
                  width: 32, height: 32, borderRadius: "50%",
                  background: `${meta.color}15`, border: `1px solid ${meta.color}40`,
                  display: "grid", placeItems: "center", color: meta.color,
                  position: "relative", zIndex: 1, flexShrink: 0,
                  boxShadow: isSel ? `0 0 0 4px ${meta.color}20` : "none",
                  transition: "box-shadow 0.2s",
                  ...(playing && isSel ? { animation: "glow-pulse 1.2s var(--ease-out) infinite" } : {})
                }}>
                  <Icon name={meta.icon} size={14}/>
                </div>
                <div style={{ paddingTop: 4 }}>
                  <div style={{ fontSize: 12.5, color: "var(--text-1)", lineHeight: 1.4 }}>
                    <span style={{ fontWeight: 500 }}>{e.actor}</span>
                    <span className="muted"> {e.action.toLowerCase()} </span>
                    <span style={{ color: "var(--text-1)" }}>{e.target}</span>
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-3)", marginTop: 3 }}>{e.meta}</div>
                </div>
                <Badge variant="default" dot>{meta.label}</Badge>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}

// ─── Event detail panel ──────────────────────────────────────────
function EventDetail({ event }) {
  if (!event) return null;
  const meta = auditTypeMeta[event.type];

  // Diff data (synthetic)
  const diffs = {
    approve: [
      { field: "status", before: "pending", after: "approved", actor: event.actor },
    ],
    match: [
      { field: "matched_to", before: "—", after: "PO-1124" },
      { field: "confidence", before: "—", after: "0.97" },
    ],
    exception: [
      { field: "status", before: "matching", after: "exception" },
      { field: "reason", before: "—", after: "amount_delta" },
    ],
    ocr: [
      { field: "ocr_status", before: "queued", after: "complete" },
      { field: "doc_count", before: "0", after: "12" },
    ],
    rule: [
      { field: "rule_id", before: "—", after: "r-44" },
      { field: "matched_count", before: "0", after: "18" },
    ],
    link: [
      { field: "vendor_link", before: "unlinked", after: "MERCHANT_847" },
    ],
    reverse: [
      { field: "status", before: "posted", after: "reversed" },
    ],
    system: [
      { field: "period_status", before: "open", after: "closed" },
    ],
  };
  const eventDiffs = diffs[event.type] || [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, position: "sticky", top: 16 }}>
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">
              <Icon name={meta.icon} size={14} style={{ color: meta.color }}/>
              {meta.label} event
            </div>
            <div className="card-subtitle">{event.date} at {event.t}</div>
          </div>
          <Badge dot style={{ color: meta.color }}>{event.actor}</Badge>
        </div>
        <div className="card-body" style={{ padding: 0 }}>
          {/* Header summary */}
          <div style={{ padding: "16px 16px 12px" }}>
            <div style={{ fontSize: 13, color: "var(--text-1)", lineHeight: 1.5 }}>
              <span style={{ fontWeight: 500 }}>{event.actor}</span>
              <span className="muted"> {event.action.toLowerCase()} </span>
              <span style={{ fontWeight: 500 }}>{event.target}</span>
            </div>
            <div style={{ fontSize: 11.5, color: "var(--text-3)", marginTop: 6 }}>{event.meta}</div>
          </div>

          {/* Field changes */}
          {eventDiffs.length > 0 && (
            <div style={{ borderTop: "1px solid var(--divider)" }}>
              <div style={{ padding: "10px 16px", fontSize: 10.5, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: 0.5 }}>
                Field changes
              </div>
              {eventDiffs.map((d, i) => (
                <div key={i} style={{ padding: "10px 16px", borderTop: "1px solid var(--divider)" }}>
                  <div className="mono" style={{ fontSize: 11, color: "var(--text-3)", marginBottom: 6 }}>{d.field}</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span className="mono" style={{ fontSize: 12, color: "var(--text-2)",
                      padding: "3px 8px", background: "rgba(242,107,123,0.08)", borderRadius: 4,
                      textDecoration: "line-through", textDecorationColor: "var(--danger)" }}>
                      {d.before}
                    </span>
                    <Icon name="arrowRight" size={12} style={{ color: "var(--text-4)" }}/>
                    <span className="mono" style={{ fontSize: 12, color: "var(--text-1)",
                      padding: "3px 8px", background: "rgba(52,215,160,0.08)", borderRadius: 4 }}>
                      {d.after}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Metadata */}
          <div style={{ borderTop: "1px solid var(--divider)", padding: 16, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, fontSize: 11.5 }}>
            <div>
              <div style={{ color: "var(--text-3)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 4 }}>Event ID</div>
              <div className="mono" style={{ color: "var(--text-1)" }}>evt_4f8a91e{event.id}</div>
            </div>
            <div>
              <div style={{ color: "var(--text-3)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 4 }}>Session</div>
              <div className="mono" style={{ color: "var(--text-1)" }}>sess_b821x4{event.id}f</div>
            </div>
            <div>
              <div style={{ color: "var(--text-3)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 4 }}>IP</div>
              <div className="mono" style={{ color: "var(--text-1)" }}>10.4.21.{18 + event.id}</div>
            </div>
            <div>
              <div style={{ color: "var(--text-3)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 4 }}>Source</div>
              <div className="mono" style={{ color: "var(--text-1)" }}>{event.actor === "System" ? "scheduler" : event.actor === "Auto-rule" ? "rules-engine" : "web-app"}</div>
            </div>
          </div>
        </div>
        <div className="card-footer" style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button className="btn btn-sm">
            <Icon name="copy" size={13}/>
            Copy JSON
          </button>
          <button className="btn btn-sm">
            <Icon name="link" size={13}/>
            Link
          </button>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { AuditPage });
