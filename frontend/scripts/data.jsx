// Mock operational data for LedgerFlow. Realistic finance-ops feel.
// All values are stable (seeded) so demo doesn't jitter between renders.

// Deterministic RNG so charts stay stable across renders
const seededRand = (seed) => {
  let s = seed;
  return () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
};

// ─── KPI tiles ─────────────────────────────────────────────────────
const kpiTiles = [
  {
    id: "processed",
    label: "Processed Volume",
    value: "$48.27M",
    raw: 48270000,
    trend: { dir: "up", value: "+12.4%", caption: "vs last month" },
    icon: "bank",
    spark: [12, 16, 14, 22, 20, 28, 26, 33, 31, 38, 42, 48],
  },
  {
    id: "invoices",
    label: "Invoices Processed",
    value: "12,847",
    raw: 12847,
    trend: { dir: "up", value: "+8.2%", caption: "this week" },
    icon: "invoice",
    spark: [820, 1100, 980, 1240, 1180, 1420, 1380, 1620, 1580, 1820, 1980, 2210],
  },
  {
    id: "match",
    label: "Auto-Match Rate",
    value: "94.6",
    unit: "%",
    trend: { dir: "up", value: "+1.8pp", caption: "30-day rolling" },
    icon: "reconcile",
    spark: [88, 89, 88, 90, 91, 92, 91, 93, 93, 94, 94, 95],
  },
  {
    id: "exceptions",
    label: "Open Exceptions",
    value: "342",
    trend: { dir: "down", value: "-23", caption: "since yesterday" },
    icon: "alert",
    spark: [520, 480, 460, 440, 410, 405, 380, 365, 370, 360, 348, 342],
    accent: "warning",
  },
];

// ─── Reconciliation throughput (sparkline / area) ───────────────────
const throughputData = (() => {
  const r = seededRand(42);
  const arr = [];
  for (let i = 0; i < 24; i++) {
    const t = i;
    const base = 280 + Math.sin(i / 3.5) * 80 + r() * 60;
    arr.push({
      t: `${String(i).padStart(2, "0")}:00`,
      matched: Math.round(base * (0.86 + r() * 0.08)),
      exceptions: Math.round((base * 0.06) + r() * 12),
      manual: Math.round((base * 0.04) + r() * 8),
    });
  }
  return arr;
})();

// ─── Live processing queue ─────────────────────────────────────────
const liveQueue = [
  { id: "INV-29481", vendor: "Stripe Atlas", amount: 4820.00, stage: "ocr", confidence: 0.97 },
  { id: "INV-29482", vendor: "AWS",          amount: 18432.55, stage: "match", confidence: 0.92 },
  { id: "INV-29483", vendor: "Notion Labs",  amount: 1200.00, stage: "approve", confidence: 0.99 },
  { id: "INV-29484", vendor: "Datadog",      amount: 7894.20, stage: "ocr", confidence: 0.84 },
  { id: "INV-29485", vendor: "Linear",       amount: 480.00,  stage: "match", confidence: 0.95 },
  { id: "INV-29486", vendor: "Vercel",       amount: 2200.00, stage: "post",  confidence: 0.99 },
  { id: "INV-29487", vendor: "Figma",        amount: 720.00,  stage: "ocr",   confidence: 0.91 },
];

// ─── Activity feed (realtime) ──────────────────────────────────────
const activityFeed = [
  { id: 1, who: "System", what: "auto-matched", detail: "INV-29478 → PO-1124", ts: "2s ago", type: "match", amount: "$12,840.00" },
  { id: 2, who: "Priya M.", what: "approved", detail: "Batch #418 (32 invoices)", ts: "14s ago", type: "approve" },
  { id: 3, who: "System", what: "flagged exception", detail: "INV-29476 — amount delta $48.20", ts: "47s ago", type: "exception" },
  { id: 4, who: "Marcus T.", what: "linked vendor", detail: "Stripe Atlas → MERCHANT_847", ts: "1m ago", type: "link" },
  { id: 5, who: "System", what: "OCR completed", detail: "12 documents in batch #419", ts: "1m ago", type: "ocr" },
  { id: 6, who: "Auto-rule", what: "applied tax code", detail: "GL-4100 → 18 line items", ts: "2m ago", type: "rule" },
  { id: 7, who: "Anaya K.", what: "approved", detail: "Wire transfer $48,200.00", ts: "3m ago", type: "approve" },
  { id: 8, who: "System", what: "reconciled", detail: "JPM 4471 — 248 transactions", ts: "4m ago", type: "match" },
];

// ─── Discrepancy heatmap ───────────────────────────────────────────
const heatmapDays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const heatmapHours = ["00", "02", "04", "06", "08", "10", "12", "14", "16", "18", "20", "22"];
const heatmapData = (() => {
  const r = seededRand(99);
  return heatmapDays.map((d, di) =>
    heatmapHours.map((h, hi) => {
      // Business-hour bias
      const bh = (hi >= 4 && hi <= 9) ? 1 : 0.25;
      const wk = (di >= 5) ? 0.3 : 1;
      return Math.round((r() * 8 + 1) * bh * wk);
    })
  );
})();

// ─── Vendor exposure (donut) ───────────────────────────────────────
const vendorExposure = [
  { name: "AWS",          value: 1284200, color: "var(--c1)" },
  { name: "Stripe",       value: 882000,  color: "var(--c2)" },
  { name: "Datadog",      value: 482300,  color: "var(--c3)" },
  { name: "Salesforce",   value: 384000,  color: "var(--c4)" },
  { name: "Notion",       value: 142000,  color: "var(--c5)" },
  { name: "248 others",   value: 612400,  color: "var(--c7)" },
];

// ─── Cashflow stacked bar ──────────────────────────────────────────
const cashflow = (() => {
  const months = ["Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun"];
  const r = seededRand(7);
  return months.map((m, i) => ({
    m,
    inflow: Math.round(3.8 + r() * 1.2 + i * 0.18) * 1.0,
    outflow: Math.round(2.4 + r() * 0.9 + i * 0.12) * 1.0,
  }));
})();

// ─── Invoices for inbox ────────────────────────────────────────────
const invoicesInbox = [
  { id: "INV-29481", vendor: "Stripe Atlas",  amount: 4820.00,  date: "Apr 24", po: "PO-1124", status: "matched", conf: 0.97, file: "stripe_atlas_q2.pdf" },
  { id: "INV-29482", vendor: "AWS",            amount: 18432.55, date: "Apr 24", po: "PO-1108", status: "matched", conf: 0.92, file: "aws_apr2026.pdf" },
  { id: "INV-29483", vendor: "Notion Labs",    amount: 1200.00,  date: "Apr 23", po: "PO-1132", status: "approved", conf: 0.99, file: "notion_team.pdf" },
  { id: "INV-29484", vendor: "Datadog",        amount: 7894.20,  date: "Apr 23", po: "PO-1101", status: "review", conf: 0.84, file: "datadog_observability.pdf" },
  { id: "INV-29485", vendor: "Linear",         amount: 480.00,   date: "Apr 23", po: "PO-1145", status: "matched", conf: 0.95, file: "linear_workspace.pdf" },
  { id: "INV-29486", vendor: "Vercel",         amount: 2200.00,  date: "Apr 22", po: "PO-1119", status: "posted", conf: 0.99, file: "vercel_pro.pdf" },
  { id: "INV-29487", vendor: "Figma",          amount: 720.00,   date: "Apr 22", po: "PO-1156", status: "exception", conf: 0.71, file: "figma_design.pdf" },
  { id: "INV-29488", vendor: "Mongo Atlas",    amount: 3120.40,  date: "Apr 22", po: "PO-1098", status: "matched", conf: 0.94, file: "mongo_atlas.pdf" },
  { id: "INV-29489", vendor: "Cloudflare",     amount: 980.00,   date: "Apr 21", po: "PO-1162", status: "approved", conf: 0.96, file: "cloudflare_pro.pdf" },
  { id: "INV-29490", vendor: "Twilio",         amount: 4248.75,  date: "Apr 21", po: "PO-1077", status: "exception", conf: 0.79, file: "twilio_messaging.pdf" },
];

const invoiceStatusMeta = {
  matched:   { label: "Matched",   variant: "success", dot: "success" },
  approved:  { label: "Approved",  variant: "info",    dot: "info" },
  posted:    { label: "Posted",    variant: "accent",  dot: "info" },
  review:    { label: "Review",    variant: "warning", dot: "warning" },
  exception: { label: "Exception", variant: "danger",  dot: "danger" },
};

// ─── Reconciliation matching pairs ────────────────────────────────
const reconPairs = [
  { id: 1, status: "matched", conf: 1.0,
    invoice: { id: "INV-29481", vendor: "Stripe Atlas", amount: 4820.00, date: "Apr 24" },
    bank:    { id: "TX-447921",  desc: "STRIPE ATLAS PMT", amount: 4820.00, date: "Apr 24" } },
  { id: 2, status: "matched", conf: 0.96,
    invoice: { id: "INV-29488", vendor: "MongoDB Atlas", amount: 3120.40, date: "Apr 22" },
    bank:    { id: "TX-447918",  desc: "MONGODB INC", amount: 3120.40, date: "Apr 22" } },
  { id: 3, status: "discrepancy", conf: 0.81, delta: -48.20,
    invoice: { id: "INV-29487", vendor: "Figma",    amount: 720.00, date: "Apr 22" },
    bank:    { id: "TX-447902",  desc: "FIGMA INC ACH", amount: 671.80, date: "Apr 22" } },
  { id: 4, status: "matched", conf: 0.99,
    invoice: { id: "INV-29486", vendor: "Vercel",  amount: 2200.00, date: "Apr 22" },
    bank:    { id: "TX-447895",  desc: "VERCEL HQ",     amount: 2200.00, date: "Apr 22" } },
  { id: 5, status: "unmatched", conf: 0.0,
    invoice: null,
    bank:    { id: "TX-447883",  desc: "REFUND VENDOR ACH", amount: 1840.00, date: "Apr 21" } },
  { id: 6, status: "discrepancy", conf: 0.74, delta: 200.00,
    invoice: { id: "INV-29490", vendor: "Twilio",  amount: 4248.75, date: "Apr 21" },
    bank:    { id: "TX-447874",  desc: "TWILIO MESSAGING", amount: 4448.75, date: "Apr 21" } },
];

// ─── Audit timeline events ────────────────────────────────────────
const auditEvents = [
  { id: 1, t: "10:42:18", date: "Apr 24", actor: "Priya M.",  action: "Approved batch", target: "Batch #418 (32 invoices)", meta: "$184,820.00", type: "approve" },
  { id: 2, t: "10:41:02", date: "Apr 24", actor: "System",    action: "Auto-matched", target: "INV-29481 → PO-1124", meta: "confidence 0.97", type: "match" },
  { id: 3, t: "10:38:47", date: "Apr 24", actor: "System",    action: "OCR extracted", target: "12 documents", meta: "Batch #419", type: "ocr" },
  { id: 4, t: "10:32:14", date: "Apr 24", actor: "Marcus T.", action: "Linked vendor",  target: "Stripe Atlas → MERCHANT_847", meta: "manual override", type: "link" },
  { id: 5, t: "10:29:41", date: "Apr 24", actor: "System",    action: "Flagged exception", target: "INV-29476", meta: "amount delta $48.20", type: "exception" },
  { id: 6, t: "10:24:08", date: "Apr 24", actor: "Auto-rule", action: "Applied tax code", target: "GL-4100 → 18 lines", meta: "rule #r-44", type: "rule" },
  { id: 7, t: "10:18:22", date: "Apr 24", actor: "Anaya K.",  action: "Approved wire",   target: "Vendor Datadog Inc.", meta: "$48,200.00", type: "approve" },
  { id: 8, t: "10:12:47", date: "Apr 24", actor: "System",    action: "Reconciled", target: "JPM 4471 ledger", meta: "248 transactions, 100% matched", type: "match" },
  { id: 9, t: "09:54:33", date: "Apr 24", actor: "Aanya S.",  action: "Created policy",  target: "FX-tolerance > 0.5%", meta: "policy #p-091", type: "rule" },
  { id: 10, t: "16:48:11", date: "Apr 23", actor: "System",    action: "Daily close",     target: "Apr 23 GL period", meta: "closed in 14m 22s", type: "system" },
  { id: 11, t: "15:32:08", date: "Apr 23", actor: "Marcus T.", action: "Reversed entry",  target: "JE-118832", meta: "duplicated by import job", type: "reverse" },
  { id: 12, t: "12:14:55", date: "Apr 23", actor: "Priya M.",  action: "Approved batch",  target: "Batch #417 (28 invoices)", meta: "$162,440.00", type: "approve" },
];

const auditTypeMeta = {
  approve:   { label: "Approval",   color: "var(--c2)", icon: "check2" },
  match:     { label: "Match",      color: "var(--c1)", icon: "link" },
  ocr:       { label: "OCR",        color: "var(--c3)", icon: "scan" },
  exception: { label: "Exception",  color: "var(--c5)", icon: "alert" },
  link:      { label: "Link",       color: "var(--c6)", icon: "link" },
  rule:      { label: "Rule",       color: "var(--c4)", icon: "bolt" },
  system:    { label: "System",     color: "var(--text-3)", icon: "shield" },
  reverse:   { label: "Reversal",   color: "var(--warning)", icon: "refresh" },
};

// ─── Analytics: vendor performance ─────────────────────────────────
const vendorPerformance = [
  { vendor: "AWS",         spend: 1284200, invoices: 84, avg: 15287, anomaly: 0, onTime: 100, change: +12.4 },
  { vendor: "Stripe",      spend: 882000,  invoices: 12, avg: 73500, anomaly: 1, onTime: 100, change: +8.1 },
  { vendor: "Datadog",     spend: 482300,  invoices: 28, avg: 17225, anomaly: 0, onTime: 96.4, change: +24.2 },
  { vendor: "Salesforce",  spend: 384000,  invoices: 4,  avg: 96000, anomaly: 0, onTime: 100, change: 0 },
  { vendor: "MongoDB",     spend: 248000,  invoices: 12, avg: 20667, anomaly: 0, onTime: 100, change: +5.3 },
  { vendor: "Cloudflare",  spend: 184000,  invoices: 12, avg: 15333, anomaly: 0, onTime: 100, change: -2.1 },
  { vendor: "Notion",      spend: 142000,  invoices: 18, avg: 7889,  anomaly: 0, onTime: 100, change: +14.7 },
  { vendor: "Twilio",      spend: 124000,  invoices: 26, avg: 4769,  anomaly: 2, onTime: 84.6, change: +48.2 },
  { vendor: "Figma",       spend: 86000,   invoices: 22, avg: 3909,  anomaly: 1, onTime: 95.4, change: +18.3 },
  { vendor: "Linear",      spend: 48000,   invoices: 14, avg: 3429,  anomaly: 0, onTime: 100, change: +6.4 },
];

// ─── Anomaly detection — used in analytics ─────────────────────────
const anomalies = [
  { id: 1, vendor: "Twilio",  desc: "Spend up 48.2% vs trailing avg",   severity: "high",   amount: "+$40.4k" },
  { id: 2, vendor: "Datadog", desc: "Two duplicate invoice numbers",     severity: "high",   amount: "$17.8k" },
  { id: 3, vendor: "Stripe",  desc: "Invoice arrived 11 days early",     severity: "medium", amount: "$73.5k" },
  { id: 4, vendor: "Figma",   desc: "User-seat count exceeds contract",  severity: "low",    amount: "+$0.4k" },
];

// ─── Sidebar nav ───────────────────────────────────────────────────
const navConfig = [
  { section: "Workspace", items: [
    { id: "dashboard",      label: "Dashboard",        icon: "dashboard" },
    { id: "invoices",       label: "Invoice Inbox",    icon: "invoice", badge: { value: "12", kind: "default" } },
    { id: "reconciliation", label: "Reconciliation",   icon: "reconcile", badge: { value: "3", kind: "danger" } },
    { id: "audit",          label: "Audit Timeline",   icon: "audit" },
    { id: "analytics",      label: "Analytics",        icon: "analytics" },
  ]},
  { section: "Records", items: [
    { id: "vendors",  label: "Vendors", icon: "vendors" },
    { id: "ledgers",  label: "Ledgers", icon: "database" },
    { id: "rules",    label: "Rules engine", icon: "bolt" },
  ]},
  { section: "Account", items: [
    { id: "teams",    label: "Team",     icon: "teams" },
    { id: "settings", label: "Settings", icon: "settings" },
  ]},
];

const breadcrumbs = {
  dashboard:      ["Workspace", "Dashboard"],
  invoices:       ["Workspace", "Invoice Inbox"],
  reconciliation: ["Workspace", "Reconciliation"],
  audit:          ["Workspace", "Audit Timeline"],
  analytics:      ["Workspace", "Analytics"],
  vendors:        ["Records", "Vendors"],
  ledgers:        ["Records", "Ledgers"],
  rules:          ["Records", "Rules engine"],
  teams:          ["Account", "Team"],
  settings:       ["Account", "Settings"],
};

// Currency formatter
const fmtUsd = (n, opts = {}) => {
  return n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: opts.cents === false ? 0 : 2, minimumFractionDigits: opts.cents === false ? 0 : 2 });
};
const fmtNum = (n) => n.toLocaleString("en-US");
const fmtPct = (n) => `${n.toFixed(1)}%`;

Object.assign(window, {
  kpiTiles, throughputData, liveQueue, activityFeed,
  heatmapDays, heatmapHours, heatmapData,
  vendorExposure, cashflow, invoicesInbox, invoiceStatusMeta,
  reconPairs, auditEvents, auditTypeMeta, vendorPerformance, anomalies,
  navConfig, breadcrumbs, fmtUsd, fmtNum, fmtPct, seededRand,
});
