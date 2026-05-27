// ─── Landing — floating product fragments ─────────────────────────
// Realistic product surfaces that drift in the page background.
// These are simplified, on-brand renderings of dashboard cards / invoices.

const { useEffect: _useEff, useState: _useSt, useRef: _useRef } = React;

// ─── Floating Invoice (paper card with OCR overlay) ───────────────
function FloatingInvoice({ style, rot = -2, dx = 6, dy = -8, scale = 1, narrow = false }) {
  return (
    <div
      className="doc-card drift"
      style={{
        width: narrow ? 280 : 360,
        ['--rot']: `${rot}deg`,
        ['--dx']: `${dx}px`,
        ['--dy']: `${dy}px`,
        ['--rotDelta']: '0.5deg',
        animation: `drift 14s var(--ease-soft) infinite`,
        transform: `rotate(${rot}deg) scale(${scale})`,
        ...style
      }}
    >
      <div style={{ padding: "20px 22px", fontFamily: "var(--f-mono)", fontSize: 9, color: "#888", lineHeight: 1.5 }}>
        <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid #E5DECE", paddingBottom: 12 }}>
          <div>
            <div style={{ fontFamily: "var(--f-serif)", fontSize: 17, fontWeight: 400, color: "var(--ink)", marginBottom: 4, letterSpacing: "-0.01em" }}>
              Datadog, Inc.
            </div>
            <div>620 8th Avenue</div>
            <div>New York, NY 10018</div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: "var(--ink)", letterSpacing: "0.08em" }}>INVOICE</div>
            <div>#&nbsp;INV-29484</div>
            <div>Apr 23, 2026</div>
          </div>
        </div>
        <div style={{ marginTop: 14, color: "#999", textTransform: "uppercase", letterSpacing: "0.06em", fontSize: 8 }}>BILL TO</div>
        <div style={{ color: "var(--ink)", fontFamily: "var(--f-serif)", fontSize: 12, marginTop: 2 }}>Nasher Capital LLC</div>
        <div>200 Park Ave, NY 10166</div>

        <table style={{ width: "100%", marginTop: 18, fontSize: 8.5, borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid #d4cfc4" }}>
              <th style={{ textAlign: "left", padding: 4, fontWeight: 500, color: "#999" }}>DESCRIPTION</th>
              <th style={{ textAlign: "right", padding: 4, fontWeight: 500, color: "#999" }}>QTY</th>
              <th style={{ textAlign: "right", padding: 4, fontWeight: 500, color: "#999" }}>AMOUNT</th>
            </tr>
          </thead>
          <tbody>
            <tr><td style={{ padding: "5px 4px", color: "var(--ink-soft)" }}>Observability Pro — monthly</td><td style={{ textAlign: "right" }}>1</td><td style={{ textAlign: "right" }}>$3,947.10</td></tr>
            <tr><td style={{ padding: "5px 4px", color: "var(--ink-soft)" }}>APM hosts (additional)</td><td style={{ textAlign: "right" }}>14</td><td style={{ textAlign: "right" }}>$3,168.27</td></tr>
            <tr><td style={{ padding: "5px 4px", color: "var(--ink-soft)" }}>Log ingestion overage</td><td style={{ textAlign: "right" }}>—</td><td style={{ textAlign: "right" }}>$778.83</td></tr>
          </tbody>
        </table>

        <div style={{ marginTop: 18, display: "flex", justifyContent: "flex-end" }}>
          <div style={{ minWidth: 160 }}>
            <div style={{ display: "flex", justifyContent: "space-between", padding: "3px 0", color: "#888" }}>
              <span>Subtotal</span><span>$7,894.20</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", padding: "3px 0", color: "#888" }}>
              <span>Tax</span><span>$0.00</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0 4px", borderTop: "1px solid #d4cfc4", fontFamily: "var(--f-serif)", fontSize: 13, color: "var(--ink)" }}>
              <span>Total Due</span><span>$7,894.20</span>
            </div>
          </div>
        </div>
      </div>

      {/* OCR overlay — minimal */}
      <FragmentOCR/>
    </div>
  );
}

function FragmentOCR() {
  const boxes = [
    { x: 6,  y: 7,  w: 38, h: 8,  label: "vendor" },
    { x: 60, y: 9,  w: 32, h: 5,  label: "invoice_no" },
    { x: 60, y: 15, w: 32, h: 4,  label: "issue_date" },
    { x: 6,  y: 78, w: 80, h: 4,  label: "" },
    { x: 70, y: 86, w: 22, h: 6,  label: "total_due" },
  ];
  return (
    <>
      {boxes.map((b, i) => (
        <div key={i} style={{
          position: "absolute",
          left: `${b.x}%`, top: `${b.y}%`, width: `${b.w}%`, height: `${b.h}%`,
          border: `0.5px solid var(--indigo)`,
          borderRadius: 2,
          background: `rgba(31, 52, 71, 0.04)`,
          opacity: 0,
          animation: `ocr-flash 6s ${i * 0.7 + 1.4}s infinite`,
          pointerEvents: "none",
        }}>
          {b.label && (
            <div style={{
              position: "absolute", top: -13, left: -1,
              fontFamily: "var(--f-mono)", fontSize: 7.5,
              letterSpacing: "0.08em", textTransform: "uppercase",
              color: "var(--indigo)", whiteSpace: "nowrap",
              background: "var(--paper)", padding: "1px 5px",
              borderRadius: 2,
            }}>{b.label}</div>
          )}
        </div>
      ))}
      <style>{`
        @keyframes ocr-flash {
          0%, 15% { opacity: 0; }
          22%, 70% { opacity: 1; }
          85%, 100% { opacity: 0; }
        }
      `}</style>
    </>
  );
}

// ─── Floating mini chart card (sparkline + kpi) ────────────────────
function FloatingKPI({ style, rot = 2, label, value, delta }) {
  return (
    <div className="doc-card drift" style={{
      width: 240, padding: "16px 18px",
      ['--rot']: `${rot}deg`,
      ['--dx']: '-5px',
      ['--dy']: '7px',
      animation: 'drift 18s var(--ease-soft) infinite',
      transform: `rotate(${rot}deg)`,
      ...style
    }}>
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 9.5, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--ink-faint)" }}>{label}</div>
      <div style={{ fontFamily: "var(--f-serif)", fontStyle: "italic", fontSize: 36, lineHeight: 1, color: "var(--ink)", marginTop: 8, letterSpacing: "-0.02em" }}>
        {value}
      </div>
      {delta && (
        <div style={{ fontFamily: "var(--f-mono)", fontSize: 10.5, color: "var(--moss)", marginTop: 8 }}>{delta}</div>
      )}
      <svg width="100%" height="32" viewBox="0 0 200 32" style={{ marginTop: 10, opacity: 0.7 }}>
        <path d="M0 24 Q 20 18, 36 22 T 72 16 T 108 20 T 144 10 T 180 14 L 200 8"
          stroke="var(--ink)" strokeWidth="1.25" fill="none"/>
        <circle cx="200" cy="8" r="2.5" fill="var(--ink)"/>
      </svg>
    </div>
  );
}

// ─── Floating "audit ribbon" card — micro version ──────────────────
function FloatingAudit({ style }) {
  const lines = [
    { t: "10:42:18", who: "Priya M.", verb: "approved", obj: "Batch #418" },
    { t: "10:41:02", who: "System",   verb: "matched",  obj: "INV-29481" },
    { t: "10:38:47", who: "System",   verb: "extracted", obj: "12 docs" },
    { t: "10:32:14", who: "Marcus T.", verb: "linked",   obj: "MERCHANT_847" },
  ];
  return (
    <div className="doc-card drift" style={{
      width: 320, padding: "18px 22px",
      ['--rot']: '-1.5deg',
      ['--dx']: '4px',
      ['--dy']: '-6px',
      animation: 'drift 22s var(--ease-soft) infinite',
      transform: 'rotate(-1.5deg)',
      ...style
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
        <div style={{ fontFamily: "var(--f-mono)", fontSize: 9.5, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--ink-faint)" }}>Audit log · Apr 24</div>
        <span style={{ width: 6, height: 6, borderRadius: 50, background: "var(--ember)" }}/>
      </div>
      {lines.map((l, i) => (
        <div key={i} style={{
          display: "grid", gridTemplateColumns: "50px 1fr", gap: 10,
          padding: "6px 0",
          borderTop: i === 0 ? "none" : "1px solid var(--ink-hair)",
          fontSize: 11,
        }}>
          <div style={{ fontFamily: "var(--f-mono)", color: "var(--ink-faint)", fontSize: 10 }}>{l.t}</div>
          <div>
            <span style={{ color: "var(--ink)" }}>{l.who}</span>
            <span style={{ color: "var(--ink-mute)" }}> {l.verb} </span>
            <span style={{ color: "var(--ink)", fontFamily: "var(--f-mono)", fontSize: 10.5 }}>{l.obj}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── Reconciliation match fragment ─────────────────────────────────
function FloatingMatch({ style }) {
  return (
    <div className="doc-card drift" style={{
      width: 320, padding: "20px 22px",
      ['--rot']: '1.2deg',
      ['--dx']: '-6px',
      ['--dy']: '5px',
      animation: 'drift 20s var(--ease-soft) infinite',
      transform: 'rotate(1.2deg)',
      ...style
    }}>
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 9.5, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--ink-faint)", marginBottom: 14 }}>
        Reconciliation · Pair #3
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", alignItems: "center", gap: 12 }}>
        <Side title="Invoice" name="Figma, Inc." amount="$720.00"/>
        <Connector/>
        <Side title="Bank txn" name="FIGMA INC ACH" amount="$671.80" diff/>
      </div>
      <div style={{
        marginTop: 14, padding: "8px 10px",
        background: "rgba(184, 74, 26, 0.06)",
        border: "1px solid rgba(184, 74, 26, 0.18)",
        borderRadius: 4,
        fontFamily: "var(--f-mono)", fontSize: 10, color: "var(--ember)",
        display: "flex", alignItems: "center", gap: 6,
      }}>
        <span>△</span><span>Delta −$48.20 · likely FX rounding</span>
      </div>
    </div>
  );
}
function Side({ title, name, amount, diff }) {
  return (
    <div style={{ padding: "8px 10px", background: "var(--paper)", borderRadius: 4 }}>
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 8.5, letterSpacing: "0.08em", color: "var(--ink-faint)", textTransform: "uppercase" }}>{title}</div>
      <div style={{ fontSize: 11, color: "var(--ink)", marginTop: 4 }}>{name}</div>
      <div style={{
        fontFamily: "var(--f-serif)", fontStyle: "italic",
        fontSize: 18, color: diff ? "var(--ember)" : "var(--ink)",
        marginTop: 4, letterSpacing: "-0.01em",
      }}>{amount}</div>
    </div>
  );
}
function Connector() {
  return (
    <svg width="32" height="20" viewBox="0 0 32 20">
      <path d="M0 10 Q 16 10, 32 10" stroke="var(--ink-faint)" strokeWidth="0.8" strokeDasharray="2 2" fill="none"/>
      <circle cx="16" cy="10" r="6" fill="var(--paper)" stroke="var(--ember)" strokeWidth="0.8"/>
      <text x="16" y="13" textAnchor="middle" fontSize="8" fill="var(--ember)" fontFamily="var(--f-mono)">△</text>
    </svg>
  );
}

// ─── Inbox stack fragment ──────────────────────────────────────────
function FloatingInbox({ style }) {
  const inbox = [
    { v: "Stripe Atlas",  a: "$4,820.00",  s: "matched" },
    { v: "AWS",           a: "$18,432.55", s: "matched" },
    { v: "Notion Labs",   a: "$1,200.00",  s: "approved" },
    { v: "Datadog",       a: "$7,894.20",  s: "review" },
    { v: "Linear",        a: "$480.00",    s: "matched" },
  ];
  const statusColor = { matched: "var(--moss)", approved: "var(--indigo)", review: "var(--gold)" };
  return (
    <div className="doc-card drift" style={{
      width: 340, padding: "18px 0 6px",
      ['--rot']: '-0.5deg',
      ['--dx']: '5px',
      ['--dy']: '-4px',
      animation: 'drift 26s var(--ease-soft) infinite',
      transform: 'rotate(-0.5deg)',
      ...style
    }}>
      <div style={{ padding: "0 22px 12px", fontFamily: "var(--f-mono)", fontSize: 9.5, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--ink-faint)", display: "flex", justifyContent: "space-between" }}>
        <span>Inbox</span><span>10 of 12,847</span>
      </div>
      {inbox.map((it, i) => (
        <div key={i} style={{
          display: "grid", gridTemplateColumns: "16px 1fr auto",
          alignItems: "center", gap: 12,
          padding: "10px 22px",
          borderTop: "1px solid var(--ink-hair)",
        }}>
          <span style={{ width: 6, height: 6, borderRadius: 50, background: statusColor[it.s] }}/>
          <div>
            <div style={{ fontSize: 12, color: "var(--ink)" }}>{it.v}</div>
            <div style={{ fontFamily: "var(--f-mono)", fontSize: 9.5, color: "var(--ink-faint)", marginTop: 2, textTransform: "uppercase", letterSpacing: "0.05em" }}>{it.s}</div>
          </div>
          <div style={{ fontFamily: "var(--f-serif)", fontStyle: "italic", fontSize: 15, color: "var(--ink)", letterSpacing: "-0.01em" }}>{it.a}</div>
        </div>
      ))}
    </div>
  );
}

Object.assign(window, { FloatingInvoice, FloatingKPI, FloatingAudit, FloatingMatch, FloatingInbox });
