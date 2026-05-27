// ─── Invoice Intelligence Page ─────────────────────────────────────
// Upload pipeline + OCR extraction visualization + side-by-side preview.

const { useState: _useStateInv, useEffect: _useEffectInv, useRef: _useRefInv } = React;

function InvoicesPage() {
  const [selected, setSelected] = _useStateInv(invoicesInbox[3]); // pick the one in review
  const [view, setView] = _useStateInv("inbox"); // inbox | upload
  return (
    <div className="page" data-screen-label="invoices" style={{ maxWidth: 1700 }}>
      <div className="page-header">
        <div>
          <h1 className="page-title">
            Invoice intelligence
            <Badge variant="accent" dot>OCR · v3.2</Badge>
          </h1>
          <p className="page-subtitle">
            12,847 documents processed this week ·
            <span className="mono" style={{ color: "var(--success)" }}> 94.6% </span>
            auto-extraction confidence
          </p>
        </div>
        <div className="page-actions">
          <div className="segment">
            <button className={view === "inbox" ? "active" : ""} onClick={() => setView("inbox")}>Inbox</button>
            <button className={view === "upload" ? "active" : ""} onClick={() => setView("upload")}>Upload</button>
          </div>
          <button className="btn btn-sm">
            <Icon name="filter" size={13}/>
            Filter
          </button>
          <button className="btn btn-sm btn-primary">
            <Icon name="upload" size={13}/>
            Upload invoices
          </button>
        </div>
      </div>

      {view === "upload" ? <UploadPipeline/> : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1.4fr", gap: 14, alignItems: "start" }}>
          <InvoiceList selected={selected} onSelect={setSelected}/>
          <InvoicePreview invoice={selected}/>
        </div>
      )}
    </div>
  );
}

// ─── Inbox list ───────────────────────────────────────────────────
function InvoiceList({ selected, onSelect }) {
  return (
    <div className="card" style={{ overflow: "hidden" }}>
      <div className="card-header">
        <div className="card-title">
          <Icon name="invoice" size={14} style={{ color: "var(--accent)" }}/>
          Inbox
          <Badge>10 of 12,847</Badge>
        </div>
        <div className="segment">
          <button className="active">All</button>
          <button>Review</button>
          <button>Exceptions</button>
        </div>
      </div>
      <div style={{ maxHeight: "calc(100vh - 240px)", overflow: "auto" }}>
        {invoicesInbox.map(inv => {
          const meta = invoiceStatusMeta[inv.status];
          const isSel = selected?.id === inv.id;
          return (
            <div key={inv.id}
              onClick={() => onSelect(inv)}
              style={{
                display: "flex", alignItems: "center", gap: 12,
                padding: "12px 16px", borderBottom: "1px solid var(--divider)",
                cursor: "pointer",
                background: isSel ? "var(--accent-soft)" : "transparent",
                borderLeft: isSel ? "2px solid var(--accent)" : "2px solid transparent",
                transition: "background .12s",
              }}>
              <div style={{
                width: 32, height: 40, borderRadius: 4,
                background: "var(--bg-3)", border: "1px solid var(--border)",
                display: "grid", placeItems: "center", flexShrink: 0,
                color: "var(--text-3)",
              }}>
                <Icon name="filePdf" size={14}/>
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 12.5, color: "var(--text-1)", fontWeight: 500 }}>{inv.vendor}</span>
                  <span className="mono" style={{ fontSize: 10.5, color: "var(--text-3)" }}>{inv.id}</span>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
                  <Badge variant={meta.variant} dot>{meta.label}</Badge>
                  <span style={{ fontSize: 11, color: "var(--text-3)" }}>{inv.date}</span>
                  <ConfidenceBar value={inv.conf} width={42}/>
                </div>
              </div>
              <div className="mono" style={{ fontSize: 13, color: "var(--text-1)", fontWeight: 500, textAlign: "right" }}>
                {fmtUsd(inv.amount)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Side-by-side preview with OCR overlay ───────────────────────
function InvoicePreview({ invoice }) {
  if (!invoice) return null;
  const meta = invoiceStatusMeta[invoice.status];

  // Synthetic OCR fields w/ confidences
  const fields = [
    { label: "Vendor",     value: invoice.vendor, conf: 0.99 },
    { label: "Invoice #",  value: invoice.id, conf: 1.0 },
    { label: "Issue date", value: invoice.date + ", 2026", conf: 0.97 },
    { label: "Due date",   value: "May 24, 2026", conf: 0.95 },
    { label: "PO match",   value: invoice.po, conf: 0.92 },
    { label: "Tax ID",     value: "EIN 47-8412334", conf: 0.88 },
    { label: "Subtotal",   value: fmtUsd(invoice.amount * 0.85), conf: 0.96 },
    { label: "Tax (15%)",  value: fmtUsd(invoice.amount * 0.15), conf: 0.94 },
    { label: "Total due",  value: fmtUsd(invoice.amount), conf: 0.99 },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {/* Document preview */}
      <div className="card" style={{ minHeight: 380 }}>
        <div className="card-header">
          <div>
            <div className="card-title">
              <Icon name="filePdf" size={14} style={{ color: "var(--accent)" }}/>
              {invoice.file}
              <Badge>page 1/1</Badge>
            </div>
            <div className="card-subtitle">2.4 MB · uploaded by Marcus T. · 23 min ago</div>
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <button className="btn btn-sm">
              <Icon name="scan" size={13}/>
              Re-scan
            </button>
            <button className="btn btn-sm">
              <Icon name="download" size={13}/>
            </button>
            <button className="btn btn-sm">
              <Icon name="more" size={13}/>
            </button>
          </div>
        </div>
        <div className="card-body" style={{ padding: 16 }}>
          <DocumentMockWithOverlay invoice={invoice}/>
        </div>
      </div>

      {/* Extracted data */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Icon name="sparkle" size={14} style={{ color: "var(--accent)" }}/>
            AI extraction
            <Badge variant="accent">{Math.round(invoice.conf * 100)}% avg confidence</Badge>
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <button className="btn btn-sm">
              <Icon name="copy" size={13}/>
              Copy as JSON
            </button>
            <button className="btn btn-sm btn-primary">
              <Icon name="check" size={13}/>
              Approve & post
            </button>
          </div>
        </div>
        <div className="card-body" style={{ padding: 0 }}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr" }}>
            {fields.map((f, i) => (
              <div key={i} style={{
                padding: "12px 16px",
                borderRight: i % 2 === 0 ? "1px solid var(--divider)" : "none",
                borderBottom: i < fields.length - 2 ? "1px solid var(--divider)" : "none",
              }}>
                <div style={{ fontSize: 10.5, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 4 }}>
                  {f.label}
                </div>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                  <span className="mono" style={{ fontSize: 13, color: "var(--text-1)" }}>{f.value}</span>
                  <ConfidenceBar value={f.conf} width={40}/>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="card-footer" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Icon name="info" size={13} style={{ color: "var(--info)" }}/>
            <span>Auto-validated against PO-{invoice.po.split("-")[1]} — 9 of 9 fields match.</span>
          </div>
          <a style={{ color: "var(--accent)" }} href="#">View audit trail →</a>
        </div>
      </div>
    </div>
  );
}

// ─── Document mock with OCR overlay bounding-boxes ───────────────
function DocumentMockWithOverlay({ invoice }) {
  // synthetic overlay boxes positioned relative to a 4:5 page
  const boxes = [
    { x: 8,  y: 4,   w: 38, h: 8,  label: invoice.vendor, color: "var(--c1)" },
    { x: 60, y: 4,   w: 32, h: 6,  label: invoice.id, color: "var(--c3)" },
    { x: 60, y: 12,  w: 32, h: 5,  label: invoice.date + ", 2026", color: "var(--c3)" },
    { x: 8,  y: 28,  w: 50, h: 4,  label: "Bill to: Nasher Capital", color: "var(--text-3)" },
    { x: 8,  y: 50,  w: 84, h: 18, label: "Line items table", color: "var(--c2)" },
    { x: 64, y: 76,  w: 28, h: 6,  label: fmtUsd(invoice.amount), color: "var(--success)" },
  ];

  return (
    <div style={{
      position: "relative",
      aspectRatio: "5/4",
      background: "linear-gradient(180deg, #1A1F2C 0%, #14182A 100%)",
      borderRadius: 8,
      border: "1px solid var(--border)",
      overflow: "hidden",
    }}>
      {/* Fake document content */}
      <div style={{
        position: "absolute", inset: 12,
        background: "#F4F0E8", borderRadius: 4, padding: "20px 24px",
        color: "#1a1a1a", fontFamily: "var(--font-mono)", fontSize: 9, lineHeight: 1.4,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", borderBottom: "1px solid #d4cfc4", paddingBottom: 8 }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "#000", fontFamily: "var(--font-sans)", marginBottom: 2 }}>
              {invoice.vendor}
            </div>
            <div style={{ color: "#666" }}>1455 Market Street, Floor 6</div>
            <div style={{ color: "#666" }}>San Francisco, CA 94103</div>
          </div>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "#000" }}>INVOICE</div>
            <div style={{ color: "#666" }}># {invoice.id}</div>
            <div style={{ color: "#666" }}>{invoice.date}, 2026</div>
          </div>
        </div>
        <div style={{ marginTop: 12, color: "#666" }}>BILL TO</div>
        <div style={{ color: "#000" }}>Nasher Capital LLC</div>
        <div style={{ color: "#666" }}>200 Park Ave, NY 10166</div>
        <table style={{ width: "100%", marginTop: 20, fontSize: 8, borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid #999" }}>
              <th style={{ textAlign: "left", padding: 4 }}>DESCRIPTION</th>
              <th style={{ textAlign: "right", padding: 4 }}>QTY</th>
              <th style={{ textAlign: "right", padding: 4 }}>UNIT</th>
              <th style={{ textAlign: "right", padding: 4 }}>AMOUNT</th>
            </tr>
          </thead>
          <tbody>
            <tr><td style={{ padding: 4 }}>Monthly subscription — Pro tier</td><td style={{ textAlign: "right" }}>1</td><td style={{ textAlign: "right" }}>{fmtUsd(invoice.amount * 0.5)}</td><td style={{ textAlign: "right" }}>{fmtUsd(invoice.amount * 0.5)}</td></tr>
            <tr><td style={{ padding: 4 }}>API usage — premium</td><td style={{ textAlign: "right" }}>4</td><td style={{ textAlign: "right" }}>{fmtUsd(invoice.amount * 0.08)}</td><td style={{ textAlign: "right" }}>{fmtUsd(invoice.amount * 0.32)}</td></tr>
            <tr><td style={{ padding: 4 }}>Storage overage</td><td style={{ textAlign: "right" }}>1</td><td style={{ textAlign: "right" }}>{fmtUsd(invoice.amount * 0.03)}</td><td style={{ textAlign: "right" }}>{fmtUsd(invoice.amount * 0.03)}</td></tr>
          </tbody>
        </table>
        <div style={{ marginTop: 16, display: "flex", justifyContent: "flex-end" }}>
          <div style={{ minWidth: 160 }}>
            <div style={{ display: "flex", justifyContent: "space-between", padding: "2px 0", color: "#666" }}>
              <span>Subtotal</span><span>{fmtUsd(invoice.amount * 0.85)}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", padding: "2px 0", color: "#666" }}>
              <span>Tax (15%)</span><span>{fmtUsd(invoice.amount * 0.15)}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderTop: "1px solid #999", fontWeight: 600, fontSize: 10, color: "#000" }}>
              <span>Total Due</span><span>{fmtUsd(invoice.amount)}</span>
            </div>
          </div>
        </div>
      </div>

      {/* OCR overlay */}
      {boxes.map((b, i) => (
        <div key={i} style={{
          position: "absolute",
          left: `${b.x}%`, top: `${b.y}%`, width: `${b.w}%`, height: `${b.h}%`,
          border: `1px solid ${b.color}`,
          borderRadius: 3,
          background: `${b.color}10`,
          animation: `fade-in 0.4s ${0.15 * i + 0.2}s var(--ease-out) both`,
          boxShadow: `0 0 12px ${b.color}40`,
        }}>
          <div style={{
            position: "absolute", top: -16, left: 0, fontSize: 8,
            color: b.color, fontFamily: "var(--font-mono)", whiteSpace: "nowrap",
            background: "var(--bg-1)", padding: "1px 5px", borderRadius: 3,
            border: `1px solid ${b.color}40`,
          }}>{b.label}</div>
        </div>
      ))}

      {/* Scanning line effect */}
      <div style={{
        position: "absolute", left: 0, right: 0,
        height: 2, background: "linear-gradient(90deg, transparent, var(--accent), transparent)",
        boxShadow: "0 0 20px var(--accent-glow)",
        animation: "scan-line 3.5s ease-in-out infinite",
        opacity: 0.7,
      }}/>
      <style>{`
        @keyframes scan-line {
          0%, 100% { top: 8%; opacity: 0; }
          15%, 85% { opacity: 0.7; }
          50% { top: 92%; }
        }
      `}</style>
    </div>
  );
}

// ─── Upload pipeline visualization ───────────────────────────────
function UploadPipeline() {
  const [files, setFiles] = _useStateInv([
    { id: 1, name: "aws_april_2026.pdf", size: "2.4 MB", stage: 4, conf: 0.98 },
    { id: 2, name: "stripe_atlas_q2.pdf", size: "184 KB", stage: 4, conf: 0.97 },
    { id: 3, name: "notion_team_invoice.pdf", size: "112 KB", stage: 3, conf: 0.99 },
    { id: 4, name: "datadog_observability.pdf", size: "1.8 MB", stage: 2, conf: 0.84 },
    { id: 5, name: "vercel_pro_apr.pdf", size: "96 KB", stage: 1, conf: 0 },
  ]);
  const [dragOver, setDragOver] = _useStateInv(false);

  // Auto-advance stages for demo
  _useEffectInv(() => {
    const id = setInterval(() => {
      setFiles(fs => fs.map(f => f.stage < 4 ? { ...f, stage: f.stage + 1, conf: f.stage === 1 ? 0.88 + Math.random() * 0.1 : f.conf } : f));
    }, 2200);
    return () => clearInterval(id);
  }, []);

  const stages = ["Upload", "OCR scan", "AI extract", "Validate", "Posted"];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1.6fr", gap: 14 }}>
      <div className="card"
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => { e.preventDefault(); setDragOver(false); }}
        style={{
          minHeight: 420, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
          gap: 16, padding: 28,
          borderStyle: "dashed",
          borderColor: dragOver ? "var(--accent)" : "var(--border-strong)",
          background: dragOver ? "var(--accent-soft)" : undefined,
          transition: "all 0.2s",
        }}>
        <div style={{
          width: 64, height: 64, borderRadius: 16,
          background: "linear-gradient(135deg, var(--accent), var(--c3))",
          display: "grid", placeItems: "center",
          boxShadow: "0 8px 28px var(--accent-glow)",
          position: "relative",
        }}>
          <Icon name="cloud" size={28} style={{ color: "white" }}/>
          <span style={{ position: "absolute", inset: -4, borderRadius: 18, border: "1px solid var(--accent)", opacity: 0.4, animation: "ping 2s var(--ease-out) infinite" }}/>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 16, fontWeight: 500, color: "var(--text-1)" }}>Drop invoices to begin</div>
          <div style={{ fontSize: 12, color: "var(--text-3)", marginTop: 6, maxWidth: 280 }}>
            PDF, PNG, JPG, EML, or e-invoice formats. Up to 200 files per batch.
            Auto-routes to OCR → extraction → validation.
          </div>
        </div>
        <button className="btn btn-primary">
          <Icon name="upload" size={13}/>
          Browse files
        </button>
        <div style={{ display: "flex", gap: 12, fontSize: 10.5, color: "var(--text-3)" }}>
          <span><Icon name="check" size={11} style={{ verticalAlign: -1, color: "var(--success)" }}/> SOC2</span>
          <span><Icon name="check" size={11} style={{ verticalAlign: -1, color: "var(--success)" }}/> Encrypted in transit</span>
          <span><Icon name="check" size={11} style={{ verticalAlign: -1, color: "var(--success)" }}/> No data retention</span>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <Icon name="flow" size={14} style={{ color: "var(--accent)" }}/>
            Processing pipeline
            <Badge variant="accent" dot>Live</Badge>
          </div>
          <div className="card-subtitle">{files.length} files in flight</div>
        </div>
        <div className="card-body" style={{ padding: 0 }}>
          {/* Stage header */}
          <div style={{ display: "grid", gridTemplateColumns: "1.6fr repeat(5, 1fr)", padding: "12px 16px", gap: 8, borderBottom: "1px solid var(--divider)" }}>
            <div style={{ fontSize: 10.5, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: 0.5 }}>File</div>
            {stages.map((s, i) => (
              <div key={i} style={{ fontSize: 10.5, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: 0.5, textAlign: "center" }}>{s}</div>
            ))}
          </div>
          {files.map(f => (
            <div key={f.id} style={{
              display: "grid", gridTemplateColumns: "1.6fr repeat(5, 1fr)",
              padding: "14px 16px", gap: 8, alignItems: "center",
              borderBottom: "1px solid var(--divider)",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
                <Icon name="filePdf" size={14} style={{ color: "var(--text-3)" }}/>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 12, color: "var(--text-1)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.name}</div>
                  <div style={{ fontSize: 10.5, color: "var(--text-3)" }}>{f.size}</div>
                </div>
              </div>
              {stages.map((_, i) => (
                <PipelineStageCell key={i} stage={i} current={f.stage} conf={i === 2 || i === 3 ? f.conf : 0}/>
              ))}
            </div>
          ))}
        </div>
        <div className="card-footer" style={{ display: "flex", justifyContent: "space-between" }}>
          <span>Avg latency: <span className="mono" style={{ color: "var(--text-1)" }}>1.84s / doc</span></span>
          <span>Batch ETA: <span className="mono" style={{ color: "var(--text-1)" }}>4.2 min</span></span>
        </div>
      </div>
    </div>
  );
}

function PipelineStageCell({ stage, current, conf }) {
  const done = stage < current;
  const active = stage === current;
  const pending = stage > current;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, position: "relative" }}>
      <div style={{
        width: 24, height: 24, borderRadius: "50%",
        background: done ? "var(--success)" : active ? "var(--accent)" : "var(--bg-3)",
        border: `1px solid ${done ? "var(--success)" : active ? "var(--accent)" : "var(--border-strong)"}`,
        display: "grid", placeItems: "center",
        boxShadow: active ? "0 0 0 4px var(--accent-soft)" : "none",
        animation: active ? "glow-pulse 1.4s var(--ease-out) infinite" : undefined,
        color: done || active ? "white" : "var(--text-3)",
      }}>
        {done ? <Icon name="check" size={12}/> :
         active ? <Icon name="refresh" size={11} style={{ animation: "spin 1.4s linear infinite" }}/> :
         <span style={{ width: 4, height: 4, borderRadius: 50, background: "var(--text-4)" }}/>}
      </div>
      {conf > 0 && (done || active) && (
        <div className="mono" style={{ fontSize: 9, color: done ? "var(--success)" : "var(--accent)" }}>
          {Math.round(conf * 100)}%
        </div>
      )}
    </div>
  );
}

Object.assign(window, { InvoicesPage });
