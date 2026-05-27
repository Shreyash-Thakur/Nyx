// ─── Landing v2 — sections ──────────────────────────────────────────

const { useEffect: _useE2, useState: _useS2, useRef: _useR2 } = React;

// ─── Reveal-on-scroll hook ──────────────────────────────────────────
function useReveal2(threshold = 0.10) {
  const ref = _useR2(null);
  _useE2(() => {
    const el = ref.current; if (!el) return;
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => { if (e.isIntersecting) { el.classList.add("in"); io.unobserve(el); } });
    }, { threshold });
    io.observe(el);
    return () => io.disconnect();
  }, [threshold]);
  return ref;
}

// ─── Header ─────────────────────────────────────────────────────────
function Nav2() {
  return (
    <nav className="nav">
      <div className="shell nav-inner">
        <a href="#" className="nav-brand">
          <span className="brand-mark"/>
          <span>LedgerFlow</span>
        </a>
        <div className="nav-links">
          <a href="#product">Product</a>
          <a href="#method">Method</a>
          <a href="#customers">Customers</a>
          <a href="#pricing">Pricing</a>
          <a href="#docs">Docs</a>
          <a href="#changelog">Changelog</a>
        </div>
        <div className="nav-actions">
          <a href="LedgerFlow.html#auth" className="btn btn-sm btn-ghost">Sign in</a>
          <a href="LedgerFlow.html" className="btn btn-sm btn-primary">
            Open workspace
            <I.arrow s={12}/>
          </a>
        </div>
      </div>
    </nav>
  );
}

// ─── Hero ───────────────────────────────────────────────────────────
function Hero2() {
  const ref = useReveal2(0.05);
  return (
    <section className="hero">
      <div className="shell">
        <div ref={ref} className="reveal in hero-grid">
          <div className="hero-text">
            <a href="#changelog" className="hero-pill">
              <span className="pill-tag">New</span>
              <span>Anomaly detection in Analytics</span>
              <I.arrow s={11} style={{ color: "var(--ink-4)" }}/>
            </a>
            <h1 className="hero-title">
              Finance operations,
              <br/>
              <span className="accent-text">on autopilot.</span>
            </h1>
            <p className="hero-subtitle">
              An operating system for accounts payable, reconciliation, and audit.
              Built for finance teams who'd rather not be doing this by hand.
            </p>
            <div className="hero-cta-row">
              <a href="LedgerFlow.html" className="btn btn-lg btn-primary">
                Open the workspace
                <I.arrow s={13}/>
              </a>
              <a href="#product" className="btn btn-lg">
                See the product
              </a>
            </div>
            <div className="hero-meta">
              <span className="check"><I.check s={13}/> SOC 2 Type II</span>
              <span className="check"><I.check s={13}/> ISO 27001</span>
              <span className="check"><I.check s={13}/> SSO &amp; SCIM</span>
            </div>
          </div>

          {/* Stage — modular floating product fragments */}
          <div className="hero-stage">
            <ProductInbox
              style={{ left: 0, top: 0, transform: "rotate(-1.4deg)",
                ['--rot']: '-1.4deg', ['--dx']: '4px', ['--dy']: '-5px',
                animation: 'drift 18s var(--ease-soft) infinite' }}
            />
            <ProductInvoicePreview
              style={{ right: 0, top: 60, transform: "rotate(1.6deg)",
                ['--rot']: '1.6deg', ['--dx']: '-3px', ['--dy']: '4px',
                animation: 'drift 22s var(--ease-soft) infinite', zIndex: 2 }}
            />
            <ProductKPI
              style={{ left: 30, bottom: 0, transform: "rotate(-0.6deg)",
                ['--rot']: '-0.6deg', ['--dx']: '-4px', ['--dy']: '6px',
                animation: 'drift 24s var(--ease-soft) infinite' }}
              label="Auto-match rate"
              value="94.6%"
              delta="+1.8pp"
              sparkData={[88, 89, 88, 90, 91, 92, 91, 93, 93, 94, 94, 95]}
            />
            <ProductKPI
              style={{ right: 60, bottom: -20, transform: "rotate(2.2deg)",
                ['--rot']: '2.2deg', ['--dx']: '3px', ['--dy']: '-4px',
                animation: 'drift 20s var(--ease-soft) infinite' }}
              label="Open exceptions"
              value="342"
              delta="23"
              trend="down"
              sparkData={[520, 480, 460, 440, 410, 405, 380, 365, 370, 360, 348, 342]}
            />
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Live metrics strip ─────────────────────────────────────────────
function MetricsStrip() {
  return (
    <section className="metrics-strip">
      <div className="shell">
        <div className="metrics-row">
          <span className="metrics-status">
            <span className="dot"/>
            Live · production
          </span>
          <div className="metric-cell">
            <span className="v">$48.27<span className="u">M</span></span>
            <span className="l">processed · last 30 days</span>
          </div>
          <div className="metric-cell">
            <span className="v">12,847</span>
            <span className="l">invoices read</span>
          </div>
          <div className="metric-cell">
            <span className="v">94.6<span className="u">%</span></span>
            <span className="l">matched automatically</span>
          </div>
          <div className="metric-cell">
            <span className="v">1.84<span className="u">s</span></span>
            <span className="l">avg processing</span>
          </div>
          <a href="#" className="metrics-link">Status <I.arrow s={11}/></a>
        </div>
      </div>
    </section>
  );
}

// ─── Customer logo strip (right after metrics) ──────────────────────
function CustomerStrip() {
  return (
    <section style={{ padding: "32px 0", borderBottom: "1px solid var(--line)" }}>
      <div className="shell customers" style={{ borderTop: "0", padding: 0 }}>
        <span className="label">Trusted by</span>
        <span className="logo">Nasher</span>
        <span className="logo">Oakwell</span>
        <span className="logo">Starfield</span>
        <span className="logo">Harlow &amp; Co.</span>
        <span className="logo">Merritt</span>
        <span className="logo">Linden Park</span>
      </div>
    </section>
  );
}

// ─── Feature: Invoice intelligence ─────────────────────────────────
function FeatureInvoices() {
  const ref = useReveal2();
  return (
    <section className="section" id="product">
      <div className="shell">
        <div className="section-head">
          <div className="lead">
            <div className="eyebrow">Invoice intelligence</div>
            <h2 className="title">
              Every invoice, parsed in <span className="em">under two seconds.</span>
            </h2>
          </div>
          <p className="blurb">
            Drop a PDF, forward an email, or wire your AP inbox. The model extracts twenty-odd fields, tags each with a confidence, and queues anything ambiguous for review.
          </p>
        </div>

        <div ref={ref} className="reveal feature">
          <div className="feature-text">
            <div className="eyebrow">Inbox &nbsp;·&nbsp; Extraction &nbsp;·&nbsp; Validation</div>
            <h3>One inbox for every invoice.</h3>
            <p>
              PDFs, e-invoices, EDI, forwarded emails — all surfaced in a single sorted queue. Matched against POs and contracts the moment they land.
            </p>
            <ul>
              <li><I.check s={13}/> 32+ document types, including handwritten</li>
              <li><I.check s={13}/> Confidence-scored extraction with field-level audit trail</li>
              <li><I.check s={13}/> Vendor-aware learning improves over time</li>
            </ul>
          </div>
          <div className="feature-visual">
            <div style={{ position: "relative", width: "100%", maxWidth: 720, height: 420 }}>
              <ProductInbox
                style={{ position: "absolute", left: 0, top: 0,
                  ['--rot']: '-1deg', ['--dx']: '3px', ['--dy']: '-3px',
                  animation: 'drift 22s var(--ease-soft) infinite',
                  transform: 'rotate(-1deg)' }}/>
              <ProductInvoicePreview
                style={{ position: "absolute", right: 0, top: 30,
                  ['--rot']: '1.2deg', ['--dx']: '-3px', ['--dy']: '4px',
                  animation: 'drift 26s var(--ease-soft) infinite',
                  transform: 'rotate(1.2deg)', zIndex: 2 }}/>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Feature: Reconciliation ───────────────────────────────────────
function FeatureRecon() {
  const ref = useReveal2();
  return (
    <section className="section section-canvas">
      <div className="shell">
        <div className="section-head">
          <div className="lead">
            <div className="eyebrow">Reconciliation</div>
            <h2 className="title">
              Bank statements meet ledger entries. <span className="em">Discrepancies surface themselves.</span>
            </h2>
          </div>
          <p className="blurb">
            Every transaction matched to an invoice and a purchase order in real time. Tolerances you control. Exceptions queued with a suggested fix already attached.
          </p>
        </div>

        <div ref={ref} className="reveal feature feature-reverse">
          <div className="feature-visual">
            <div style={{ position: "relative", width: "100%", maxWidth: 720, height: 420 }}>
              <ProductRecon
                style={{ position: "absolute", left: "50%", top: 30, transform: "translateX(-50%) rotate(-1deg)",
                  ['--rot']: '-1deg', ['--dx']: '0px', ['--dy']: '-4px',
                  animation: 'drift 24s var(--ease-soft) infinite', zIndex: 2 }}/>
              <ProductKPI
                style={{ position: "absolute", left: 30, bottom: 40,
                  ['--rot']: '1.4deg', ['--dx']: '3px', ['--dy']: '4px',
                  animation: 'drift 28s var(--ease-soft) infinite',
                  transform: 'rotate(1.4deg)' }}
                label="Auto-match rate"
                value="94.6%"
                delta="+1.8pp"
                sparkData={[88, 89, 88, 90, 91, 92, 91, 93, 93, 94, 94, 95]}/>
            </div>
          </div>
          <div className="feature-text">
            <div className="eyebrow">Matching &nbsp;·&nbsp; Tolerances &nbsp;·&nbsp; AI Suggestions</div>
            <h3>The match engine,<br/>tuned to your books.</h3>
            <p>
              Configure tolerances by vendor, currency, or GL code. Anything outside policy lands in review with a model-generated rationale and a single-click resolution.
            </p>
            <ul>
              <li><I.check s={13}/> Multi-currency with FX-rounding tolerance</li>
              <li><I.check s={13}/> Three-way match (invoice · PO · bank)</li>
              <li><I.check s={13}/> Suggested fixes, not just flagged exceptions</li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Feature: Audit & analytics ────────────────────────────────────
function FeatureAudit() {
  const ref = useReveal2();
  return (
    <section className="section">
      <div className="shell">
        <div className="section-head">
          <div className="lead">
            <div className="eyebrow">Audit &amp; analytics</div>
            <h2 className="title">
              An immutable record. <span className="em">A clearer picture.</span>
            </h2>
          </div>
          <p className="blurb">
            Every change to the ledger is logged with the actor, the field diff, and the IP. Anomalies surface before they become quarter-end problems.
          </p>
        </div>

        <div ref={ref} className="reveal feature">
          <div className="feature-text">
            <div className="eyebrow">Audit &nbsp;·&nbsp; Anomalies &nbsp;·&nbsp; Forecasting</div>
            <h3>Audit-grade by default.</h3>
            <p>
              Streamed to your SIEM. Compliant with SOC 2, ISO 27001, and most internal-controls frameworks worth caring about. Reproducible to the second.
            </p>
            <ul>
              <li><I.check s={13}/> Immutable, hash-chained event log</li>
              <li><I.check s={13}/> Anomaly detection across vendor spend</li>
              <li><I.check s={13}/> Forecast bands on rolling 12-month trends</li>
            </ul>
          </div>
          <div className="feature-visual">
            <div style={{ position: "relative", width: "100%", maxWidth: 720, height: 420 }}>
              <ProductAudit
                style={{ position: "absolute", left: 10, top: 0,
                  ['--rot']: '-0.8deg', ['--dx']: '3px', ['--dy']: '-3px',
                  animation: 'drift 25s var(--ease-soft) infinite',
                  transform: 'rotate(-0.8deg)' }}/>
              <ProductAnalytics
                style={{ position: "absolute", right: 0, bottom: 0,
                  ['--rot']: '1.4deg', ['--dx']: '-3px', ['--dy']: '4px',
                  animation: 'drift 22s var(--ease-soft) infinite',
                  transform: 'rotate(1.4deg)', zIndex: 2 }}/>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Method (3-up modular) ─────────────────────────────────────────
function Method2() {
  const ref = useReveal2();
  return (
    <section className="section section-canvas" id="method">
      <div className="shell">
        <div className="section-head">
          <div className="lead">
            <div className="eyebrow">Method</div>
            <h2 className="title">
              Three motions, <span className="em">repeated until books close.</span>
            </h2>
          </div>
          <p className="blurb">
            Ingest the documents. Reason about what they say. Reconcile them against reality. Most of the month happens here, on its own.
          </p>
        </div>

        <div ref={ref} className="reveal method-grid">
          <MethodCard num="01" title="Ingest." body="Forwarded email, dropped PDFs, SFTP, e-invoice formats — anything addressed to your AP inbox.">
            <MiniInbox/>
          </MethodCard>
          <MethodCard num="02" title="Reason." body="The model extracts every field and tags it with a confidence. Below threshold, it asks. Above, it acts.">
            <MiniOCR/>
          </MethodCard>
          <MethodCard num="03" title="Reconcile." body="Invoices meet bank records meet purchase orders. What matches is posted. What doesn't, surfaces.">
            <MiniMatch/>
          </MethodCard>
        </div>
      </div>
    </section>
  );
}
function MethodCard({ num, title, body, children }) {
  return (
    <div className="method-card">
      <div className="num">{num} ─</div>
      <h4>{title}</h4>
      <p>{body}</p>
      <div className="visual">{children}</div>
    </div>
  );
}
function MiniInbox() {
  const rows = [
    { v: "Stripe Atlas", a: "$4,820", s: "var(--positive)" },
    { v: "AWS",          a: "$18,432", s: "var(--positive)" },
    { v: "Datadog",      a: "$7,894",  s: "var(--amber)" },
  ];
  return (
    <div style={{ padding: "10px 12px" }}>
      {rows.map((r, i) => (
        <div key={i} style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "6px 0",
          borderBottom: i < rows.length - 1 ? "1px solid var(--line)" : "none",
          fontSize: 11.5,
        }}>
          <span style={{ width: 4, height: 4, borderRadius: 50, background: r.s }}/>
          <span style={{ flex: 1, color: "var(--ink-1)" }}>{r.v}</span>
          <span className="mono" style={{ color: "var(--ink-2)" }}>{r.a}</span>
        </div>
      ))}
    </div>
  );
}
function MiniOCR() {
  return (
    <div style={{ padding: "10px 12px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px 14px", fontSize: 10.5 }}>
      {[
        { l: "Vendor",    v: "Datadog, Inc.", c: 0.99 },
        { l: "Invoice #", v: "INV-29484",     c: 1.0 },
        { l: "Date",      v: "Apr 23",         c: 0.97 },
        { l: "Total",     v: "$7,894.20",     c: 0.99 },
      ].map((r, i) => (
        <div key={i}>
          <div className="label-cap" style={{ fontSize: 9 }}>{r.l}</div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 2 }}>
            <span className="mono" style={{ color: "var(--ink-1)" }}>{r.v}</span>
            <span className="mono" style={{ color: "var(--accent)" }}>{Math.round(r.c * 100)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
function MiniMatch() {
  return (
    <div style={{ padding: "10px 12px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, height: "100%" }}>
      <div style={{ padding: "6px 8px", background: "var(--card)", border: "1px solid var(--line)", borderRadius: 6, flex: 1 }}>
        <div className="label-cap" style={{ fontSize: 9 }}>Invoice</div>
        <div className="mono" style={{ fontSize: 12, color: "var(--ink-1)", marginTop: 2 }}>$4,820</div>
      </div>
      <svg width="20" height="12" viewBox="0 0 20 12">
        <path d="M2 6 L 18 6" stroke="var(--positive)" strokeWidth="1.4"/>
        <circle cx="10" cy="6" r="3" fill="var(--positive)"/>
      </svg>
      <div style={{ padding: "6px 8px", background: "var(--card)", border: "1px solid var(--line)", borderRadius: 6, flex: 1 }}>
        <div className="label-cap" style={{ fontSize: 9 }}>Bank txn</div>
        <div className="mono" style={{ fontSize: 12, color: "var(--ink-1)", marginTop: 2 }}>$4,820</div>
      </div>
    </div>
  );
}

// ─── Audit ribbon ──────────────────────────────────────────────────
function RibbonSection() {
  const events = [
    { t: "10:42:18", who: "Priya M.",  v: "approved",  o: "Batch #418",            m: "$184,820.00", cls: "v" },
    { t: "10:41:02", who: "System",    v: "matched",   o: "INV-29481 → PO-1124",   m: "conf 0.97",   cls: "v" },
    { t: "10:38:47", who: "OCR",       v: "extracted", o: "12 documents",          m: "Batch #419",  cls: "v" },
    { t: "10:32:14", who: "Marcus T.", v: "linked",    o: "Stripe Atlas",          m: "merchant_847",cls: "v" },
    { t: "10:29:41", who: "System",    v: "flagged",   o: "INV-29476",             m: "Δ $48.20",    cls: "v-neg" },
    { t: "10:24:08", who: "Auto-rule", v: "applied",   o: "GL-4100",               m: "to 18 lines", cls: "v" },
    { t: "10:18:22", who: "Anaya K.",  v: "approved",  o: "wire · Datadog",        m: "$48,200.00",  cls: "v" },
    { t: "10:12:47", who: "System",    v: "reconciled",o: "JPM 4471",              m: "248 txns",    cls: "v-pos" },
  ];
  const loop = [...events, ...events];
  return (
    <section className="ribbon-section">
      <div className="shell ribbon-head">
        <div className="eyebrow"><span className="dot"/>Live audit · streaming from production</div>
        <a href="#" style={{ fontSize: 12.5, color: "var(--ink-3)", display: "inline-flex", alignItems: "center", gap: 6 }}>
          View timeline <I.arrow s={11}/>
        </a>
      </div>
      <div className="ribbon-marquee">
        {loop.map((e, i) => (
          <span key={i} className="ribbon-event">
            <span className="t">{e.t}</span>
            <span className="who">{e.who}</span>
            <span className="verb">{e.v}</span>
            <span className="obj">{e.o}</span>
            <span className={e.cls}>{e.m}</span>
            <span className="ribbon-sep">/</span>
          </span>
        ))}
      </div>
    </section>
  );
}

// ─── Workspace teaser ──────────────────────────────────────────────
function WorkspaceTeaser() {
  const ref = useReveal2();
  return (
    <section className="section">
      <div className="shell">
        <div className="section-head">
          <div className="lead">
            <div className="eyebrow">Workspace</div>
            <h2 className="title">
              One surface for the entire month-end. <span className="em">No tab-switching.</span>
            </h2>
          </div>
          <p className="blurb">
            Command-K to everything. Keyboard-first by default. Built for the analysts and controllers who actually live in the workflow.
          </p>
        </div>

        <div ref={ref} className="reveal" style={{
          position: "relative",
          background: "var(--canvas)",
          border: "1px solid var(--line)",
          borderRadius: 18,
          padding: "80px 40px",
          overflow: "hidden",
          minHeight: 480,
          display: "grid", placeItems: "center",
        }}>
          {/* Background grid */}
          <div style={{
            position: "absolute", inset: 0,
            backgroundImage: "linear-gradient(rgba(20,22,30,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(20,22,30,0.03) 1px, transparent 1px)",
            backgroundSize: "32px 32px",
            mask: "radial-gradient(ellipse 70% 60% at 50% 50%, black, transparent)",
          }}/>
          <div style={{ position: "relative", display: "grid", gridTemplateColumns: "auto auto auto", gap: 24, alignItems: "center" }}>
            <ProductPipeline
              style={{ transform: "rotate(-2deg)",
                ['--rot']: '-2deg', ['--dx']: '2px', ['--dy']: '-3px',
                animation: 'drift 22s var(--ease-soft) infinite' }}/>
            <ProductCommandPalette
              style={{ transform: "translateY(-20px) rotate(0deg)",
                ['--rot']: '0deg', ['--dx']: '-1px', ['--dy']: '4px',
                animation: 'drift 18s var(--ease-soft) infinite',
                zIndex: 3 }}/>
            <ProductAudit
              style={{ transform: "rotate(2deg)",
                ['--rot']: '2deg', ['--dx']: '-2px', ['--dy']: '3px',
                animation: 'drift 24s var(--ease-soft) infinite' }}/>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Quote + Customers ────────────────────────────────────────────
function QuoteCustomers() {
  const ref = useReveal2();
  return (
    <section className="section section-canvas" id="customers">
      <div className="shell">
        <div ref={ref} className="reveal quote-block">
          <blockquote>
            We closed the month <strong style={{ fontWeight: 500 }}>three days early</strong>,
            and our controller had time to actually <strong style={{ fontWeight: 500 }}>read</strong> the numbers.
            LedgerFlow earned its seat on day one.
          </blockquote>
          <div className="quote-cite">
            <div className="av">HV</div>
            <div className="meta">
              <div className="name">Helena Vance</div>
              <div className="role">VP Finance · Oakwell Holdings</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── CTA + Footer ─────────────────────────────────────────────────
function CTA2() {
  return (
    <section className="cta">
      <div className="shell">
        <div className="cta-card">
          <div>
            <h2>Open the workspace.<br/>Close the month sooner.</h2>
            <p>
              Pilot LedgerFlow for 14 days. Bring your own AP inbox. We'll have your first batch reconciled before you finish reading the docs.
            </p>
          </div>
          <div className="cta-actions">
            <a href="LedgerFlow.html" className="btn btn-accent btn-lg">
              Open the workspace
              <I.arrow s={13}/>
            </a>
            <a href="LedgerFlow.html#auth" className="btn btn-lg" style={{
              background: "transparent", color: "var(--paper)",
              border: "1px solid rgba(250,249,245,0.18)"
            }}>
              Sign in
            </a>
            <div className="note">14-day pilot · no card required</div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Footer2() {
  return (
    <footer className="foot">
      <div className="shell">
        <div className="foot-grid">
          <div className="foot-brand">
            <div className="brand-row">
              <span className="brand-mark"/>
              <span>LedgerFlow</span>
            </div>
            <p>An operating system for finance operations. Made by humans, in Brooklyn &amp; Mumbai.</p>
          </div>
          <div className="foot-col">
            <h5>Product</h5>
            <a href="LedgerFlow.html">Workspace</a>
            <a href="#">Invoice intelligence</a>
            <a href="#">Reconciliation</a>
            <a href="#">Audit timeline</a>
            <a href="#">Analytics</a>
          </div>
          <div className="foot-col">
            <h5>Company</h5>
            <a href="#">About</a>
            <a href="#">Customers</a>
            <a href="#">Manifesto</a>
            <a href="#">Careers</a>
            <a href="#">Press</a>
          </div>
          <div className="foot-col">
            <h5>Trust</h5>
            <a href="#">Security</a>
            <a href="#">SOC 2 · ISO 27001</a>
            <a href="#">Privacy</a>
            <a href="#">DPA</a>
            <a href="#">Status</a>
          </div>
          <div className="foot-col">
            <h5>Resources</h5>
            <a href="#">Docs</a>
            <a href="#">Changelog</a>
            <a href="#">API reference</a>
            <a href="#">Integrations</a>
          </div>
        </div>
        <div className="foot-meta">
          <span>© LedgerFlow Inc. 2026</span>
          <span>v2.4.1 · status: operational</span>
        </div>
      </div>
    </footer>
  );
}

Object.assign(window, {
  Nav2, Hero2, MetricsStrip, CustomerStrip,
  FeatureInvoices, FeatureRecon, FeatureAudit,
  Method2, RibbonSection, WorkspaceTeaser,
  QuoteCustomers, CTA2, Footer2,
});
