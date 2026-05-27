// ─── Reconciliation Center ─────────────────────────────────────────
// Side-by-side invoice ↔ bank-txn matching, discrepancy highlighting.

const { useState: _useStateRec } = React;

function ReconciliationPage() {
  const [filter, setFilter] = _useStateRec("all");
  const pairs = filter === "all" ? reconPairs : reconPairs.filter(p => p.status === filter);
  const [selected, setSelected] = _useStateRec(reconPairs[2]); // the figma discrepancy

  return (
    <div className="page" data-screen-label="reconciliation" style={{ maxWidth: 1700 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">
            Reconciliation center
            <Badge variant="warning" dot>3 discrepancies</Badge>
          </h1>
          <p className="page-subtitle">
            JPM Operating · acct ****4471 ·
            <span className="mono"> 248 transactions </span>
            ·{" "}
            <span style={{ color: "var(--success)" }}>94.6% auto-matched</span>
          </p>
        </div>
        <div className="page-actions">
          <button className="btn btn-sm">
            <Icon name="filter" size={13}/>
            Date: Apr 21-24
          </button>
          <button className="btn btn-sm">
            <Icon name="bank" size={13}/>
            JPM ****4471
          </button>
          <button className="btn btn-sm">
            <Icon name="download" size={13}/>
            Export
          </button>
          <button className="btn btn-sm btn-primary">
            <Icon name="sparkle" size={13}/>
            Run matcher
          </button>
        </div>
      </div>

      {/* Stat strip */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10, marginBottom: 14 }}>
        <ReconStat label="Bank statements" value="248" sub="loaded" icon="bank"/>
        <ReconStat label="Invoices" value="247" sub="loaded" icon="invoice"/>
        <ReconStat label="Matched" value="234" sub="94.6%" tone="success" icon="check2"/>
        <ReconStat label="Discrepancies" value="11" sub="needs review" tone="warning" icon="alert"/>
        <ReconStat label="Unmatched" value="3" sub="orphan txns" tone="danger" icon="x"/>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 14, alignItems: "start" }}>
        <ReconList pairs={pairs} selected={selected} onSelect={setSelected} filter={filter} setFilter={setFilter}/>
        <ReconDetail pair={selected}/>
      </div>
    </div>
  );
}

function ReconStat({ label, value, sub, tone, icon }) {
  const color = tone === "success" ? "var(--success)" : tone === "warning" ? "var(--warning)" : tone === "danger" ? "var(--danger)" : "var(--text-1)";
  return (
    <div className="card" style={{ padding: 14 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <span style={{ fontSize: 11.5, color: "var(--text-3)" }}>{label}</span>
        <Icon name={icon} size={13} style={{ color: "var(--text-4)" }}/>
      </div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
        <span className="mono" style={{ fontSize: 22, fontWeight: 600, color, letterSpacing: "-0.02em" }}>{value}</span>
        <span style={{ fontSize: 11, color: "var(--text-3)" }}>{sub}</span>
      </div>
    </div>
  );
}

// ─── Matching list — invoice ↔ bank pairs ────────────────────────
function ReconList({ pairs, selected, onSelect, filter, setFilter }) {
  const statusMeta = {
    matched:     { label: "Matched",     variant: "success" },
    discrepancy: { label: "Discrepancy", variant: "warning" },
    unmatched:   { label: "Unmatched",   variant: "danger" },
  };

  return (
    <div className="card">
      <div className="card-header" style={{ flexWrap: "wrap", gap: 10 }}>
        <div className="tabs" style={{ border: 0, gap: 0 }}>
          {["all", "matched", "discrepancy", "unmatched"].map(t => (
            <div key={t} className={`tab ${filter === t ? "active" : ""}`} onClick={() => setFilter(t)}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
              <span style={{ marginLeft: 6, fontSize: 10, color: "var(--text-4)" }}>
                ({t === "all" ? reconPairs.length : reconPairs.filter(p => p.status === t).length})
              </span>
            </div>
          ))}
        </div>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table className="tbl">
          <thead>
            <tr>
              <th style={{ width: 28 }}>
                <input type="checkbox" style={{ accentColor: "var(--accent)" }}/>
              </th>
              <th>Invoice</th>
              <th>Bank transaction</th>
              <th>Δ</th>
              <th>Confidence</th>
              <th style={{ width: 40 }}></th>
            </tr>
          </thead>
          <tbody>
            {pairs.map(p => {
              const meta = statusMeta[p.status];
              const isSel = selected?.id === p.id;
              return (
                <tr key={p.id} onClick={() => onSelect(p)}
                  className={isSel ? "selected" : ""}
                  style={{ cursor: "pointer" }}>
                  <td><input type="checkbox" style={{ accentColor: "var(--accent)" }}/></td>
                  <td>
                    {p.invoice ? (
                      <div>
                        <div className="primary">{p.invoice.vendor}</div>
                        <div style={{ display: "flex", gap: 8, marginTop: 2 }}>
                          <span className="mono" style={{ fontSize: 10.5, color: "var(--text-3)" }}>{p.invoice.id}</span>
                          <span className="mono" style={{ fontSize: 11, color: "var(--text-1)" }}>{fmtUsd(p.invoice.amount)}</span>
                        </div>
                      </div>
                    ) : (
                      <span className="muted" style={{ fontStyle: "italic" }}>— no invoice —</span>
                    )}
                  </td>
                  <td>
                    {p.bank ? (
                      <div>
                        <div className="primary">{p.bank.desc}</div>
                        <div style={{ display: "flex", gap: 8, marginTop: 2 }}>
                          <span className="mono" style={{ fontSize: 10.5, color: "var(--text-3)" }}>{p.bank.id}</span>
                          <span className="mono" style={{ fontSize: 11, color: "var(--text-1)" }}>{fmtUsd(p.bank.amount)}</span>
                        </div>
                      </div>
                    ) : (
                      <span className="muted" style={{ fontStyle: "italic" }}>— no transaction —</span>
                    )}
                  </td>
                  <td>
                    {p.delta ? (
                      <span className="mono" style={{ color: p.delta < 0 ? "var(--danger)" : "var(--warning)", fontWeight: 500 }}>
                        {p.delta > 0 ? "+" : ""}{fmtUsd(p.delta)}
                      </span>
                    ) : p.status === "matched" ? (
                      <span style={{ color: "var(--success)" }}>—</span>
                    ) : (
                      <span style={{ color: "var(--text-4)" }}>n/a</span>
                    )}
                  </td>
                  <td><Badge variant={meta.variant} dot>{meta.label}</Badge></td>
                  <td><Icon name="chevRight" size={13} style={{ color: "var(--text-3)" }}/></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Detail comparison view ──────────────────────────────────────
function ReconDetail({ pair }) {
  if (!pair) {
    return (
      <div className="card">
        <div className="card-body">
          <EmptyState icon="reconcile" title="Select a pair" body="Choose a record from the table to inspect matching details."/>
        </div>
      </div>
    );
  }

  const hasDelta = pair.delta !== undefined;
  const ratio = pair.invoice && pair.bank ? (pair.bank.amount / pair.invoice.amount) : 0;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, position: "sticky", top: 16 }}>
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">
              <Icon name="link" size={14} style={{ color: "var(--accent)" }}/>
              Matching detail
            </div>
            <div className="card-subtitle">Pair #{pair.id} · {pair.status}</div>
          </div>
          <Badge variant={pair.status === "matched" ? "success" : pair.status === "discrepancy" ? "warning" : "danger"} dot>
            {Math.round(pair.conf * 100)}% confidence
          </Badge>
        </div>
        <div className="card-body" style={{ padding: 0 }}>
          {/* Compare cards */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr auto 1fr", alignItems: "center", padding: 16, gap: 16 }}>
            <CompareSide title="Invoice" record={pair.invoice} side="left" hasDelta={hasDelta}/>
            <MatchConnector status={pair.status}/>
            <CompareSide title="Bank txn" record={pair.bank} side="right" hasDelta={hasDelta}/>
          </div>

          {/* Discrepancy callout */}
          {pair.delta && (
            <div style={{
              margin: "0 16px 16px", padding: "12px 14px",
              background: "rgba(245,194,107,0.05)",
              border: "1px solid rgba(245,194,107,0.2)",
              borderRadius: 10,
              display: "flex", alignItems: "flex-start", gap: 10,
            }}>
              <Icon name="alert" size={16} style={{ color: "var(--warning)", marginTop: 2 }}/>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12.5, color: "var(--text-1)", fontWeight: 500 }}>
                  Amount mismatch detected
                </div>
                <div style={{ fontSize: 11.5, color: "var(--text-2)", marginTop: 4 }}>
                  Bank amount is{" "}
                  <span className="mono" style={{ color: "var(--warning)" }}>
                    {pair.delta > 0 ? "+" : ""}{fmtUsd(pair.delta)}
                  </span>{" "}
                  vs invoice. Likely cause: <strong>FX rounding</strong> or partial credit memo.
                </div>
              </div>
            </div>
          )}

          {/* AI suggestion */}
          <div style={{
            margin: "0 16px 16px", padding: "12px 14px",
            background: "var(--accent-soft)", border: "1px solid rgba(124,107,255,0.2)",
            borderRadius: 10, display: "flex", gap: 10,
          }}>
            <div style={{ width: 24, height: 24, borderRadius: 6,
              background: "linear-gradient(135deg, var(--accent), var(--c6))",
              display: "grid", placeItems: "center", flexShrink: 0,
            }}><Icon name="sparkle" size={13} style={{ color: "white" }}/></div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 12, color: "var(--text-1)", fontWeight: 500 }}>
                AI recommendation
              </div>
              <div style={{ fontSize: 11.5, color: "var(--text-2)", marginTop: 3 }}>
                {pair.status === "matched"
                  ? "All fields aligned. Safe to auto-post."
                  : pair.status === "discrepancy"
                  ? "Apply tolerance override (≤ $50) and approve, or request credit note from vendor."
                  : "No matching invoice. Likely an inbound refund — create a credit memo."
                }
              </div>
            </div>
          </div>
        </div>
        <div className="card-footer" style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button className="btn btn-sm">
            <Icon name="x" size={13}/>
            Reject
          </button>
          <button className="btn btn-sm">
            <Icon name="user" size={13}/>
            Assign
          </button>
          <button className="btn btn-sm btn-primary">
            <Icon name="check" size={13}/>
            Approve match
          </button>
        </div>
      </div>

      {/* Vendor sidebar */}
      {pair.invoice && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <Icon name="vendors" size={14} style={{ color: "var(--accent)" }}/>
              {pair.invoice.vendor}
            </div>
            <button className="btn btn-sm btn-ghost">
              <Icon name="arrowRight" size={13}/>
            </button>
          </div>
          <div className="card-body" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, fontSize: 12 }}>
            <KV label="On-time rate" value="100%" tone="success"/>
            <KV label="Avg invoice" value={fmtUsd(4820, { cents: false })}/>
            <KV label="MTD spend" value={fmtUsd(48200, { cents: false })}/>
            <KV label="Linked PO" value="PO-1124"/>
            <KV label="Tax ID" value="EIN 47-8412334"/>
            <KV label="Risk" value="Low" tone="success"/>
          </div>
        </div>
      )}
    </div>
  );
}

function KV({ label, value, tone }) {
  return (
    <div>
      <div style={{ fontSize: 10.5, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: 0.5 }}>{label}</div>
      <div className="mono" style={{ fontSize: 13, color: tone === "success" ? "var(--success)" : "var(--text-1)", marginTop: 2 }}>{value}</div>
    </div>
  );
}

function CompareSide({ title, record, hasDelta }) {
  return (
    <div style={{
      padding: 12, background: "var(--bg-3)", borderRadius: 10,
      border: "1px solid var(--border)",
    }}>
      <div style={{ fontSize: 10, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 8 }}>{title}</div>
      {record ? (
        <>
          <div style={{ fontSize: 13, color: "var(--text-1)", fontWeight: 500 }}>{record.vendor || record.desc}</div>
          <div className="mono" style={{ fontSize: 11, color: "var(--text-3)", marginTop: 2 }}>{record.id}</div>
          <div className="mono" style={{
            fontSize: 18, color: hasDelta ? "var(--warning)" : "var(--text-1)",
            marginTop: 10, fontWeight: 600, letterSpacing: "-0.02em",
          }}>{fmtUsd(record.amount)}</div>
          <div className="mono" style={{ fontSize: 10.5, color: "var(--text-3)", marginTop: 2 }}>{record.date}</div>
        </>
      ) : (
        <div style={{ fontSize: 12, color: "var(--text-3)", fontStyle: "italic" }}>No record</div>
      )}
    </div>
  );
}

function MatchConnector({ status }) {
  const color = status === "matched" ? "var(--success)" : status === "discrepancy" ? "var(--warning)" : "var(--danger)";
  const icon  = status === "matched" ? "check" : status === "discrepancy" ? "alert" : "x";
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
      <svg width="60" height="36" viewBox="0 0 60 36">
        <defs>
          <linearGradient id="mc-grad" x1="0" x2="1">
            <stop offset="0" stopColor="var(--border-strong)"/>
            <stop offset="0.5" stopColor={color}/>
            <stop offset="1" stopColor="var(--border-strong)"/>
          </linearGradient>
        </defs>
        <path d="M0 18 C 20 18, 40 18, 60 18" stroke="url(#mc-grad)" strokeWidth="1.5" fill="none"
          strokeDasharray="4 3" style={{ animation: "flow 1.4s linear infinite" }}/>
      </svg>
      <div style={{
        width: 28, height: 28, borderRadius: "50%",
        background: `${color}20`, border: `1px solid ${color}`,
        display: "grid", placeItems: "center", color,
        boxShadow: `0 0 12px ${color}40`,
      }}>
        <Icon name={icon} size={14}/>
      </div>
    </div>
  );
}

Object.assign(window, { ReconciliationPage });
