// ─── Landing — sections ─────────────────────────────────────────────

const { useEffect: _uE, useState: _uS, useRef: _uR, useLayoutEffect: _uLE } = React;

// ─── Reveal-on-scroll hook ──────────────────────────────────────────
function useReveal(threshold = 0.15) {
  const ref = _uR(null);
  _uE(() => {
    const el = ref.current; if (!el) return;
    const io = new IntersectionObserver((entries) => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          el.classList.add("in");
          io.unobserve(el);
        }
      });
    }, { threshold });
    io.observe(el);
    return () => io.disconnect();
  }, [threshold]);
  return ref;
}

// ─── Counter that animates value when revealed ──────────────────────
function CountedNumber({ to, format = (v) => Math.round(v).toLocaleString(), duration = 1800, suffix = "", prefix = "" }) {
  const ref = _uR(null);
  const [v, setV] = _uS(0);
  _uE(() => {
    const el = ref.current; if (!el) return;
    let raf, start;
    const io = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return;
      const step = (ts) => {
        if (!start) start = ts;
        const p = Math.min(1, (ts - start) / duration);
        const eased = 1 - Math.pow(1 - p, 3);
        setV(to * eased);
        if (p < 1) raf = requestAnimationFrame(step);
      };
      raf = requestAnimationFrame(step);
      io.disconnect();
    }, { threshold: 0.3 });
    io.observe(el);
    return () => { io.disconnect(); cancelAnimationFrame(raf); };
  }, [to, duration]);
  return <span ref={ref}>{prefix}{format(v)}{suffix}</span>;
}

// ─── Nav ────────────────────────────────────────────────────────────
function LandingNav() {
  return (
    <nav className="nav">
      <div className="shell nav-inner">
        <div className="nav-brand">
          <span className="glyph"/>
          <span>LedgerFlow</span>
        </div>
        <div className="nav-links">
          <a href="#method">Method</a>
          <a href="#manifesto">Manifesto</a>
          <a href="#customers">Customers</a>
          <a href="#pricing">Pricing</a>
          <a href="LedgerFlow.html" className="nav-enter">
            Enter workspace
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12h14M13 5l7 7-7 7"/></svg>
          </a>
        </div>
      </div>
    </nav>
  );
}

// ─── Hero ───────────────────────────────────────────────────────────
function Hero() {
  const ref = useReveal(0.05);
  return (
    <section className="hero">
      <div className="shell">
        <div ref={ref} className="reveal in hero-grid">
          <h1 className="hero-headline">
            <span className="line">The ledger</span>
            <span className="line"><span className="em">that</span> closes</span>
            <span className="line indent"><span className="italic">itself.</span></span>
          </h1>
          <aside className="hero-meta">
            <div className="hero-meta-label">Volume 04 · 2026</div>
            <div className="hero-meta-value">
              A workspace for finance
              operations &mdash; reading
              invoices, reconciling books,
              quietly closing the month.
            </div>
          </aside>

          <div className="hero-footer">
            <div className="hero-tag">
              <div className="eyebrow"><span className="dot"/>$48.27M reconciled today</div>
              <p className="lede" style={{ marginTop: 14 }}>
                For finance teams who would rather not be doing this by hand.
              </p>
            </div>
            <div className="hero-cta-row">
              <a href="LedgerFlow.html" className="hero-cta">
                Open the workspace
                <span className="hero-cta-arrow">
                  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M5 12h14M13 5l7 7-7 7"/>
                  </svg>
                </span>
              </a>
              <a href="#method" className="hero-ghost-cta">
                See how it works
              </a>
            </div>
          </div>
        </div>

        {/* Floating fragments */}
        <FloatingInvoice
          style={{ position: "absolute", right: -40, top: 80, zIndex: 1, opacity: 0.95 }}
          rot={2.4} dx={6} dy={-10}
        />
        <FloatingKPI
          style={{ position: "absolute", right: 280, top: 460, zIndex: 1 }}
          rot={-3}
          label="Auto-match rate"
          value="94.6%"
          delta="↑ +1.8pp · 30-day"
        />
      </div>
    </section>
  );
}

// ─── Numbers in poetry ──────────────────────────────────────────────
function Numbers() {
  const ref = useReveal(0.1);
  return (
    <section className="numbers" id="manifesto">
      <div className="shell">
        <div ref={ref} className="reveal numbers-grid">
          <div className="num-prelude">
            <div className="eyebrow">§01 · Last 30 days</div>
            <p className="lede">
              Eight people. <span className="t-italic" style={{ fontFamily: "var(--f-serif)" }}>One workspace.</span> The receipts of a month that mostly happened on its own.
            </p>
          </div>

          <div className="num-block" style={{ gridColumn: "6 / span 6", marginTop: 0 }}>
            <span className="digits huge">
              $<CountedNumber to={48.27} format={(v) => v.toFixed(2)}/>M
            </span>
            <div className="caption-line">processed volume · across 312 vendors and 41 ledgers</div>
            <div className="delta">↑ +12.4% vs March</div>
          </div>

          <div className="num-block" style={{ gridColumn: "2 / span 4" }}>
            <span className="digits large">
              <CountedNumber to={12847} duration={2200}/>
            </span>
            <div className="caption-line">invoices read, parsed, validated, posted — this month</div>
          </div>

          <div className="num-block" style={{ gridColumn: "7 / span 4" }}>
            <span className="digits medium">
              <CountedNumber to={94.6} format={(v) => v.toFixed(1)}/>%
            </span>
            <div className="caption-line">matched without a human touching them</div>
            <div className="delta">↑ +1.8pp · trailing 90 days</div>
          </div>

          <div className="num-block" style={{ gridColumn: "1 / span 4" }}>
            <span className="digits large">
              <CountedNumber to={1.84} format={(v) => v.toFixed(2)}/>s
            </span>
            <div className="caption-line">average time from inbox to general ledger</div>
          </div>

          <div className="num-block" style={{ gridColumn: "8 / span 4", paddingTop: 64 }}>
            <span className="digits medium">
              <CountedNumber to={342}/>
            </span>
            <div className="caption-line">items still waiting for a decision — and shrinking</div>
            <div className="delta down">↓ 23 since yesterday</div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Live ribbon (audit ticker) ─────────────────────────────────────
function Ribbon() {
  // Build a long sequence we can scroll
  const events = [
    { t: "10:42:18", who: "Priya M.",  v: "approved Batch #418",   amt: "$184,820.00" },
    { t: "10:41:02", who: "System",    v: "matched INV-29481 → PO-1124", amt: "conf 0.97" },
    { t: "10:38:47", who: "OCR",       v: "extracted 12 docs",     amt: "Batch #419" },
    { t: "10:32:14", who: "Marcus T.", v: "linked Stripe Atlas",   amt: "MERCHANT_847" },
    { t: "10:29:41", who: "System",    v: "flagged exception INV-29476", amt: "Δ $48.20", neg: true },
    { t: "10:24:08", who: "Auto-rule", v: "applied GL-4100",       amt: "to 18 lines" },
    { t: "10:18:22", who: "Anaya K.",  v: "approved wire Datadog", amt: "$48,200.00" },
    { t: "10:12:47", who: "System",    v: "reconciled JPM 4471",   amt: "248 txns", pos: true },
    { t: "09:54:33", who: "Aanya S.",  v: "created policy",        amt: "FX-tolerance > 0.5%" },
    { t: "09:48:11", who: "System",    v: "closed period",         amt: "Apr 23 · 14m 22s" },
  ];
  // Duplicate for seamless loop
  const loop = [...events, ...events];
  return (
    <section className="ribbon">
      <div className="ribbon-eyebrow">
        <span className="pulse"/>
        <span>Live · audit log streaming</span>
      </div>
      <div className="ribbon-track">
        {loop.map((e, i) => (
          <div key={i} className="ribbon-item">
            <span className="t">{e.t}</span>
            <span className="v">{e.who} <span style={{ color: "rgba(241,236,223,0.55)" }}>{e.v}</span></span>
            <span className={e.pos ? "pos" : e.neg ? "neg" : "v"}>{e.amt}</span>
            <span className="sep">/</span>
          </div>
        ))}
      </div>
    </section>
  );
}

// ─── Product breathing — single drifting invoice + paragraph ────────
function ProductBreathing() {
  const ref = useReveal(0.15);
  return (
    <section className="breathe">
      <div className="shell">
        <div ref={ref} className="reveal breathe-grid">
          <div className="breathe-text">
            <div className="eyebrow">§02 · A single document</div>
            <h2 className="title">
              An invoice arrives.<br/>
              <span className="italic">It reads itself.</span>
            </h2>
            <p className="body">
              Forwarded by email or dropped into a folder &mdash; it doesn&rsquo;t matter. Within seconds it has been parsed, matched against a purchase order, validated against three policies, and queued for approval. You did nothing.
            </p>
            <div style={{ display: "flex", gap: 24, marginTop: 32, paddingTop: 24, borderTop: "1px solid var(--ink-line)" }}>
              <Stat n="0.84s" l="to read"/>
              <Stat n="0.96" l="confidence"/>
              <Stat n="3 of 3" l="policies passed"/>
            </div>
          </div>
          <div className="breathe-stage">
            <FloatingInvoice
              style={{ position: "absolute", right: 60, top: 0 }}
              rot={-2.5} dx={4} dy={-6}
            />
            <FloatingAudit
              style={{ position: "absolute", right: -10, top: 360 }}
            />
          </div>
        </div>
      </div>
    </section>
  );
}
function Stat({ n, l }) {
  return (
    <div>
      <div style={{ fontFamily: "var(--f-serif)", fontStyle: "italic", fontSize: 28, color: "var(--ink)", letterSpacing: "-0.02em", lineHeight: 1 }}>{n}</div>
      <div style={{ fontFamily: "var(--f-mono)", fontSize: 10.5, color: "var(--ink-mute)", marginTop: 6, letterSpacing: "0.02em", textTransform: "uppercase" }}>{l}</div>
    </div>
  );
}

// ─── Method ─────────────────────────────────────────────────────────
function Method() {
  const introRef = useReveal(0.1);
  return (
    <section className="method" id="method">
      <div className="shell">
        <div ref={introRef} className="reveal method-intro">
          <div className="eyebrow">§03 · Method</div>
          <h2 className="title">
            Three motions,
            <span className="italic"> repeated until books close.</span>
          </h2>
        </div>
        <div className="method-stack">
          <MethodStep
            num="01"
            title={<>Ingest<span className="italic">.</span></>}
            body="Email, SFTP, dropped PDFs, e-invoice formats — anything addressed to your AP inbox. We pick it up, normalize it, and put it where it needs to be."
            visual={<FloatingInbox style={{ transform: 'rotate(-2deg)', boxShadow: '0 30px 60px -20px rgba(24,24,22,0.18)' }}/>}
          />
          <MethodStep
            num="02"
            title={<>Reason<span className="italic">.</span></>}
            body="The model extracts twenty-odd fields and tags every one with a confidence. Below threshold, it asks a person. Above, it acts."
            visual={<FloatingInvoice narrow rot={2.5} dx={3} dy={-5}/>}
          />
          <MethodStep
            num="03"
            title={<>Reconcile<span className="italic">.</span></>}
            body="Invoices meet bank records meet purchase orders. What matches is posted. What doesn’t surfaces — with a suggested fix already attached."
            visual={<FloatingMatch/>}
          />
        </div>
      </div>
    </section>
  );
}
function MethodStep({ num, title, body, visual }) {
  const ref = useReveal(0.15);
  return (
    <div ref={ref} className="reveal method-step">
      <div className="method-step-num">{num} ─</div>
      <div className="method-step-title">{title}</div>
      <div className="method-step-body">{body}</div>
      <div className="method-step-visual">{visual}</div>
    </div>
  );
}

// ─── Trust / quote ─────────────────────────────────────────────────
function Trust() {
  const ref = useReveal(0.1);
  return (
    <section className="trust" id="customers">
      <div className="shell">
        <div ref={ref} className="reveal trust-grid">
          <blockquote className="trust-quote">
            “We closed the month
            <span className="italic"> three days early</span>,
            and our controller had time to actually
            <span className="italic"> read</span> the numbers.”
          </blockquote>
          <div className="trust-cite">
            <div className="name">Helena Vance</div>
            <div className="title">VP Finance · Oakwell Holdings</div>
          </div>
        </div>

        <div className="logo-row">
          <span>Nasher</span>
          <span className="sep">&mdash;</span>
          <span>Oakwell</span>
          <span className="sep">&mdash;</span>
          <span>Starfield</span>
          <span className="sep">&mdash;</span>
          <span>Harlow &amp; Co.</span>
          <span className="sep">&mdash;</span>
          <span>Merritt</span>
          <span className="sep">&mdash;</span>
          <span>Linden Park</span>
        </div>
      </div>
    </section>
  );
}

// ─── Closing ───────────────────────────────────────────────────────
function Closing() {
  const ref = useReveal(0.15);
  return (
    <section className="closing">
      <div className="shell">
        <div ref={ref} className="reveal closing-grid">
          <h2 className="closing-title">
            Close the books.
            <br/>
            <span className="italic">Then close the laptop.</span>
          </h2>
          <div className="closing-cta">
            <a href="LedgerFlow.html" className="closing-cta-link">
              Enter the workspace
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12h14M13 5l7 7-7 7"/>
              </svg>
            </a>
            <div className="closing-sub">14-day pilot · No card</div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Footer ────────────────────────────────────────────────────────
function Footer() {
  return (
    <footer>
      <div className="shell">
        <div className="foot">
          <div className="foot-brand">
            <div className="name">LedgerFlow</div>
            <div>Books that reconcile themselves.</div>
            <div style={{ marginTop: 14, fontFamily: "var(--f-serif)", fontStyle: "italic", color: "var(--ink-soft)", fontSize: 13 }}>
              Made by humans, in Brooklyn &amp; Mumbai.
            </div>
          </div>
          <div className="foot-col" style={{ gridColumn: "6 / span 2" }}>
            <h4>Product</h4>
            <a href="LedgerFlow.html">Workspace</a>
            <a href="#method">Method</a>
            <a href="#">Integrations</a>
            <a href="#">Changelog</a>
          </div>
          <div className="foot-col" style={{ gridColumn: "8 / span 2" }}>
            <h4>Company</h4>
            <a href="#">Manifesto</a>
            <a href="#">Careers</a>
            <a href="#">Press</a>
          </div>
          <div className="foot-col" style={{ gridColumn: "10 / span 2" }}>
            <h4>Trust</h4>
            <a href="#">Security</a>
            <a href="#">SOC 2 · ISO 27001</a>
            <a href="#">Status</a>
          </div>
          <div className="foot-col" style={{ gridColumn: "12 / span 1" }}>
            <h4>—</h4>
            <a href="#">Privacy</a>
            <a href="#">Terms</a>
          </div>
          <div className="foot-meta">
            <span>© LedgerFlow Inc. 2026</span>
            <span>Volume 04 · Issue 16 · Spring</span>
          </div>
        </div>
      </div>
    </footer>
  );
}

Object.assign(window, { LandingNav, Hero, Numbers, Ribbon, ProductBreathing, Method, Trust, Closing, Footer });
