// ─── Main app — routing + shell + Tweaks ─────────────────────────

const { useState: _useStateApp, useEffect: _useEffectApp } = React;

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accent": "#7C6BFF",
  "density": "regular",
  "showAuth": false
}/*EDITMODE-END*/;

const ACCENT_OPTIONS = [
  "#7C6BFF",  // violet (default)
  "#5DDBC9",  // mint  (linear-ish)
  "#F4A04F",  // amber (ramp-ish)
  "#FF6B9C",  // coral
];
const ACCENT_DARK = {
  "#7C6BFF": "#5B49E6",
  "#5DDBC9": "#3DBAA8",
  "#F4A04F": "#D2802F",
  "#FF6B9C": "#D9527E",
};

function hexToRgba(hex, a) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${a})`;
}

function applyTheme(t) {
  const root = document.documentElement.style;
  root.setProperty("--accent", t.accent);
  root.setProperty("--accent-2", ACCENT_DARK[t.accent] || t.accent);
  root.setProperty("--accent-glow", hexToRgba(t.accent, 0.22));
  root.setProperty("--accent-soft", hexToRgba(t.accent, 0.10));
  root.setProperty("--c1", t.accent);

  if (t.density === "compact") {
    root.setProperty("--topbar-h", "48px");
  } else if (t.density === "comfy") {
    root.setProperty("--topbar-h", "64px");
  } else {
    root.setProperty("--topbar-h", "56px");
  }
}

const PAGE_COMPONENT = {
  dashboard:      DashboardPage,
  invoices:       InvoicesPage,
  reconciliation: ReconciliationPage,
  audit:          AuditPage,
  analytics:      AnalyticsPage,
  vendors:        VendorsPage,
  ledgers:        LedgersPage,
  rules:          RulesPage,
  teams:          TeamsPage,
  settings:       SettingsPage,
};

function getInitialPage() {
  const h = window.location.hash.replace(/^#/, "");
  return PAGE_COMPONENT[h] ? h : "dashboard";
}

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [page, setPage] = _useStateApp(getInitialPage());
  const [showAuth, setShowAuth] = _useStateApp(false);

  // hash routing
  _useEffectApp(() => {
    const onHash = () => {
      const h = window.location.hash.replace(/^#/, "");
      if (h === "auth") { setShowAuth(true); return; }
      if (PAGE_COMPONENT[h]) {
        setPage(h);
        setShowAuth(false);
      }
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  _useEffectApp(() => { applyTheme(t); }, [t.accent, t.density]);
  _useEffectApp(() => { setShowAuth(!!t.showAuth); }, [t.showAuth]);

  const nav = (id) => {
    if (id === page) return;
    setPage(id);
    history.replaceState(null, "", `#${id}`);
  };

  if (showAuth) {
    return (
      <>
        <AuthPage onSignIn={() => { setShowAuth(false); setTweak("showAuth", false); }}/>
        <TweaksPanel>
          <TweaksContents t={t} setTweak={setTweak}/>
        </TweaksPanel>
      </>
    );
  }

  const PageComp = PAGE_COMPONENT[page] || DashboardPage;

  return (
    <>
      <div className="app-shell">
        <Sidebar current={page} onNav={nav}/>
        <main className="app-main">
          <Topbar current={page}/>
          <div className="app-canvas" key={page}>
            <PageComp/>
          </div>
        </main>
      </div>
      <TweaksPanel>
        <TweaksContents t={t} setTweak={setTweak}/>
      </TweaksPanel>
    </>
  );
}

function TweaksContents({ t, setTweak }) {
  return (
    <>
      <TweakSection label="Theme"/>
      <TweakColor
        label="Accent color"
        value={t.accent}
        options={ACCENT_OPTIONS}
        onChange={v => setTweak("accent", v)}
      />
      <TweakRadio
        label="Density"
        value={t.density}
        options={["compact", "regular", "comfy"]}
        onChange={v => setTweak("density", v)}
      />
      <TweakSection label="Screens"/>
      <TweakToggle
        label="Show login screen"
        value={!!t.showAuth}
        onChange={v => setTweak("showAuth", v)}
      />
    </>
  );
}

// Mount
const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App/>);
