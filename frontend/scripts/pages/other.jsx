// ─── Auth / Login screen ───────────────────────────────────────────
// Premium full-bleed login with workspace-aware sidebar.

const { useState: _useStateAuth } = React;

function AuthPage({ onSignIn }) {
  const [email, setEmail] = _useStateAuth("aanya@nasher.co");
  const [pwd, setPwd]     = _useStateAuth("••••••••••••");
  const [loading, setLoading] = _useStateAuth(false);

  const submit = () => {
    setLoading(true);
    setTimeout(() => onSignIn?.(), 900);
  };

  return (
    <div data-screen-label="auth" style={{
      display: "grid",
      gridTemplateColumns: "1fr 1.1fr",
      height: "100vh",
      background: "var(--bg-0)",
      color: "var(--text-1)",
      position: "relative",
      overflow: "hidden",
    }}>
      {/* LEFT — form column */}
      <div style={{
        position: "relative", zIndex: 2,
        display: "flex", flexDirection: "column",
        padding: "32px 56px",
        background: "linear-gradient(180deg, var(--bg-1) 0%, var(--bg-0) 100%)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div className="brand-mark" style={{ width: 32, height: 32 }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 6h16M4 12h10M4 18h16"/>
            </svg>
          </div>
          <div>
            <div className="brand-name" style={{ fontSize: 15 }}>LedgerFlow</div>
            <div className="brand-tag">Ops</div>
          </div>
        </div>

        <div style={{ flex: 1, display: "flex", flexDirection: "column", justifyContent: "center", maxWidth: 380 }}>
          <div style={{ marginBottom: 28 }}>
            <Badge variant="accent" dot>SOC 2 Type II · ISO 27001</Badge>
          </div>
          <h1 style={{ fontSize: 32, fontWeight: 600, letterSpacing: "-0.03em", color: "var(--text-1)", marginBottom: 10 }}>
            Welcome back, Aanya
          </h1>
          <p style={{ fontSize: 14, color: "var(--text-2)", marginBottom: 32, lineHeight: 1.5 }}>
            Sign in to your workspace to continue.
            <br/>You have <span style={{ color: "var(--text-1)", fontWeight: 500 }}>342 open exceptions</span> waiting for review.
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <FormField label="Work email">
              <input className="input" style={{ width: "100%" }} value={email} onChange={e => setEmail(e.target.value)}/>
            </FormField>
            <FormField label="Password" hint={<a style={{ color: "var(--accent)" }} href="#">Forgot?</a>}>
              <input className="input" type="password" style={{ width: "100%" }} value={pwd} onChange={e => setPwd(e.target.value)}/>
            </FormField>

            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, color: "var(--text-2)", marginTop: 4 }}>
              <input type="checkbox" defaultChecked style={{ accentColor: "var(--accent)" }}/>
              Keep me signed in on this device
            </label>

            <button className="btn btn-primary btn-lg" onClick={submit} disabled={loading}
              style={{ marginTop: 6, width: "100%", justifyContent: "center" }}>
              {loading ? (
                <>
                  <Icon name="refresh" size={14} style={{ animation: "spin 1s linear infinite" }}/>
                  Authenticating…
                </>
              ) : (
                <>
                  Continue
                  <Icon name="arrowRight" size={14}/>
                </>
              )}
            </button>

            <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "6px 0", fontSize: 11, color: "var(--text-3)" }}>
              <span style={{ flex: 1, height: 1, background: "var(--divider)" }}/>
              <span>or continue with</span>
              <span style={{ flex: 1, height: 1, background: "var(--divider)" }}/>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
              <SSOButton label="SSO" sub="SAML"/>
              <SSOButton label="Google" sub="Workspace"/>
              <SSOButton label="Okta" sub="OIDC"/>
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 11, color: "var(--text-3)" }}>
          <span>© 2026 LedgerFlow Inc.</span>
          <div style={{ display: "flex", gap: 14 }}>
            <a href="#">Status</a>
            <a href="#">Docs</a>
            <a href="#">Privacy</a>
          </div>
        </div>
      </div>

      {/* RIGHT — operations panel */}
      <div style={{
        position: "relative", overflow: "hidden",
        background: "radial-gradient(ellipse 60% 50% at 50% 30%, rgba(124,107,255,0.18), transparent 60%), linear-gradient(180deg, #0E121C 0%, #06070A 100%)",
        borderLeft: "1px solid var(--border)",
        display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center",
        padding: 60,
      }}>
        <AuthIllustration/>
      </div>
    </div>
  );
}

function FormField({ label, hint, children }) {
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 5 }}>
        <label style={{ fontSize: 11, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: 0.6, fontWeight: 500 }}>{label}</label>
        {hint && <span style={{ fontSize: 11 }}>{hint}</span>}
      </div>
      {children}
    </div>
  );
}

function SSOButton({ label, sub }) {
  return (
    <button className="btn" style={{ height: 50, flexDirection: "column", gap: 1, padding: "0 8px" }}>
      <span style={{ fontSize: 12.5, color: "var(--text-1)", fontWeight: 500 }}>{label}</span>
      <span style={{ fontSize: 10, color: "var(--text-3)" }}>{sub}</span>
    </button>
  );
}

// ─── Right-side illustration — synthetic ops dashboard preview ──
function AuthIllustration() {
  // Floating stacked card preview
  return (
    <div style={{ position: "relative", width: "100%", maxWidth: 560, perspective: "1400px" }}>
      {/* Background grid */}
      <div style={{
        position: "absolute", inset: -80,
        background: `
          linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px) 0 0 / 32px 32px,
          linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px) 0 0 / 32px 32px
        `,
        mask: "radial-gradient(ellipse 60% 60% at 50% 50%, black, transparent)",
      }}/>

      <div style={{
        transform: "rotateX(8deg) rotateY(-14deg)",
        transformStyle: "preserve-3d",
        display: "grid", gap: 14,
      }}>
        {/* Top card */}
        <div className="card" style={{
          padding: 14, transform: "translateZ(40px)",
          boxShadow: "0 40px 80px rgba(0,0,0,0.6), 0 0 0 1px var(--border)",
        }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Icon name="flow" size={13} style={{ color: "var(--accent)" }}/>
              <span style={{ fontSize: 11.5, color: "var(--text-1)", fontWeight: 500 }}>Reconciliation throughput</span>
            </div>
            <Badge variant="success" dot>Live</Badge>
          </div>
          <Sparkline data={[12, 18, 14, 24, 22, 32, 28, 38, 36, 44, 48, 56, 52, 64, 62, 72]} width={500} height={70} color="var(--accent)"/>
        </div>

        {/* Middle row */}
        <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 14, transform: "translateZ(20px)" }}>
          <div className="card" style={{ padding: 14, boxShadow: "0 30px 60px rgba(0,0,0,0.4), 0 0 0 1px var(--border)" }}>
            <div style={{ fontSize: 10.5, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>Processed MTD</div>
            <div className="mono" style={{ fontSize: 24, fontWeight: 600, letterSpacing: "-0.02em" }}>$48.27M</div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 6 }}>
              <span className="trend up"><Icon name="arrowUp" size={11}/> +12.4%</span>
              <span className="dim" style={{ fontSize: 11 }}>vs last month</span>
            </div>
          </div>
          <div className="card" style={{ padding: 14, boxShadow: "0 30px 60px rgba(0,0,0,0.4), 0 0 0 1px var(--border)" }}>
            <div style={{ fontSize: 10.5, color: "var(--text-3)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>Auto-match</div>
            <div className="mono" style={{ fontSize: 24, fontWeight: 600, letterSpacing: "-0.02em" }}>94.6%</div>
            <div style={{ marginTop: 8, height: 4, background: "var(--bg-3)", borderRadius: 999, overflow: "hidden" }}>
              <div style={{ width: "94.6%", height: "100%", background: "linear-gradient(90deg, var(--accent), var(--c2))" }}/>
            </div>
          </div>
        </div>

        {/* Bottom row — activity */}
        <div className="card" style={{ padding: "10px 14px", transform: "translateZ(0px)", boxShadow: "0 20px 40px rgba(0,0,0,0.4), 0 0 0 1px var(--border)" }}>
          {[
            { type: "match", text: "System auto-matched INV-29478", amount: "$12,840" },
            { type: "approve", text: "Priya M. approved batch #418", amount: "$184,820" },
            { type: "exception", text: "Exception raised — INV-29476", amount: "Δ $48.20" },
          ].map((a, i) => {
            const c = a.type === "match" ? "var(--c1)" : a.type === "approve" ? "var(--success)" : "var(--danger)";
            return (
              <div key={i} style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "8px 0", borderBottom: i < 2 ? "1px solid var(--divider)" : "none",
              }}>
                <div style={{ width: 18, height: 18, borderRadius: 5, background: `${c}18`, border: `1px solid ${c}40`, display: "grid", placeItems: "center", color: c }}>
                  <Icon name={a.type === "match" ? "link" : a.type === "approve" ? "check" : "alert"} size={10}/>
                </div>
                <span style={{ flex: 1, fontSize: 11, color: "var(--text-1)" }}>{a.text}</span>
                <span className="mono" style={{ fontSize: 10.5, color: "var(--text-3)" }}>{a.amount}</span>
              </div>
            );
          })}
        </div>
      </div>

      <div style={{ marginTop: 40, textAlign: "center" }}>
        <div style={{ fontSize: 14, color: "var(--text-2)", marginBottom: 6 }}>Trusted by ops teams at</div>
        <div style={{ display: "flex", justifyContent: "center", gap: 28, color: "var(--text-3)", fontWeight: 600, fontSize: 13, letterSpacing: "-0.01em", opacity: 0.8 }}>
          <span>NASHER</span>
          <span>·</span>
          <span>OAKWELL</span>
          <span>·</span>
          <span>STARFIELD</span>
          <span>·</span>
          <span>HARLOW &amp; CO</span>
        </div>
      </div>
    </div>
  );
}

// ─── Other pages — Vendors / Ledgers / Rules / Teams / Settings ──
// Lightweight but polished — sub-screens that exist to make sidebar nav feel complete.

function VendorsPage() {
  return (
    <div className="page" data-screen-label="vendors">
      <div className="page-header">
        <div>
          <h1 className="page-title">Vendors</h1>
          <p className="page-subtitle">253 active · 24 newly added this month</p>
        </div>
        <div className="page-actions">
          <button className="btn btn-sm"><Icon name="filter" size={13}/>Filter</button>
          <button className="btn btn-sm btn-primary"><Icon name="plus" size={13}/>Add vendor</button>
        </div>
      </div>
      <div className="card">
        <div style={{ overflowX: "auto" }}>
          <table className="tbl">
            <thead>
              <tr>
                <th>Vendor</th>
                <th>Status</th>
                <th>Tax ID</th>
                <th style={{ textAlign: "right" }}>MTD spend</th>
                <th style={{ textAlign: "center" }}>Invoices</th>
                <th style={{ textAlign: "center" }}>On-time</th>
                <th>Last invoice</th>
              </tr>
            </thead>
            <tbody>
              {vendorPerformance.map((v, i) => (
                <tr key={v.vendor}>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div style={{ width: 28, height: 28, borderRadius: 6, background: `var(--c${(i % 7) + 1})`, display: "grid", placeItems: "center", fontSize: 10.5, fontWeight: 600, color: "rgba(0,0,0,0.7)" }}>
                        {v.vendor.slice(0,2).toUpperCase()}
                      </div>
                      <div>
                        <div className="primary">{v.vendor}</div>
                        <div style={{ fontSize: 10.5, color: "var(--text-3)" }}>vendor_{i + 1}{i + 4}{i + 7}</div>
                      </div>
                    </div>
                  </td>
                  <td><Badge variant="success" dot>Active</Badge></td>
                  <td className="mono" style={{ fontSize: 11.5 }}>EIN 47-841{2300 + i}</td>
                  <td className="num">{fmtUsd(v.spend, { cents: false })}</td>
                  <td style={{ textAlign: "center" }} className="mono">{v.invoices}</td>
                  <td style={{ textAlign: "center" }}>
                    <span className="mono" style={{ color: v.onTime >= 99 ? "var(--success)" : "var(--warning)" }}>{v.onTime}%</span>
                  </td>
                  <td>Apr {20 + (i % 4)}, 2026</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function PlaceholderPage({ label, screenLabel, icon, body }) {
  return (
    <div className="page" data-screen-label={screenLabel}>
      <div className="page-header">
        <div>
          <h1 className="page-title">{label}</h1>
          <p className="page-subtitle">{body}</p>
        </div>
      </div>
      <div className="card">
        <div className="card-body">
          <EmptyState icon={icon} title={`${label} coming online`} body="This section is wired up in production. Toggle Tweaks to switch the demo workspace."/>
        </div>
      </div>
    </div>
  );
}

const LedgersPage  = () => <PlaceholderPage label="Ledgers"       screenLabel="ledgers"  icon="database" body="GL accounts, sub-ledgers and posting policies."/>;
const RulesPage    = () => <PlaceholderPage label="Rules engine"  screenLabel="rules"    icon="bolt"     body="Automation rules — matching tolerances, posting templates, escalations."/>;
const TeamsPage    = () => <PlaceholderPage label="Team"          screenLabel="teams"    icon="teams"    body="24 seats · roles, approval matrix, segregation of duties."/>;
const SettingsPage = () => <PlaceholderPage label="Settings"      screenLabel="settings" icon="settings" body="Workspace, integrations, security, branding."/>;

Object.assign(window, { AuthPage, VendorsPage, LedgersPage, RulesPage, TeamsPage, SettingsPage });
