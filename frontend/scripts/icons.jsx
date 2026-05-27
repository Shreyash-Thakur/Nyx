// Icon library — feather/lucide-style 1.5px stroke icons.
// Single source. Reused everywhere.

const Icon = ({ name, size = 16, className = "", style = {}, ...rest }) => {
  const paths = ICONS[name];
  if (!paths) return null;
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      style={style}
      aria-hidden="true"
      {...rest}
    >
      {paths}
    </svg>
  );
};

const ICONS = {
  // Navigation
  dashboard: (<>
    <rect x="3" y="3" width="7" height="9" rx="1.5"/>
    <rect x="14" y="3" width="7" height="5" rx="1.5"/>
    <rect x="14" y="12" width="7" height="9" rx="1.5"/>
    <rect x="3" y="16" width="7" height="5" rx="1.5"/>
  </>),
  invoice: (<>
    <path d="M6 2h9l4 4v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1z"/>
    <path d="M15 2v4h4"/>
    <path d="M9 11h6M9 15h6M9 7h2"/>
  </>),
  reconcile: (<>
    <path d="M16 3l4 4-4 4"/>
    <path d="M20 7H8a4 4 0 0 0-4 4v0"/>
    <path d="M8 21l-4-4 4-4"/>
    <path d="M4 17h12a4 4 0 0 0 4-4v0"/>
  </>),
  audit: (<>
    <circle cx="12" cy="12" r="9"/>
    <path d="M12 7v5l3 2"/>
  </>),
  analytics: (<>
    <path d="M3 3v18h18"/>
    <path d="M7 14l3-3 4 4 5-6"/>
  </>),
  vendors: (<>
    <path d="M3 21V8l9-5 9 5v13"/>
    <path d="M9 21V12h6v9"/>
  </>),
  settings: (<>
    <circle cx="12" cy="12" r="3"/>
    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
  </>),
  teams: (<>
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
    <circle cx="9" cy="7" r="4"/>
    <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
    <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
  </>),
  // Status / actions
  check: (<path d="M5 13l4 4L19 7"/>),
  check2: (<>
    <circle cx="12" cy="12" r="9"/>
    <path d="M8 12l3 3 5-6"/>
  </>),
  x: (<><path d="M6 6l12 12M18 6L6 18"/></>),
  alert: (<>
    <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
    <path d="M12 9v4M12 17h.01"/>
  </>),
  info: (<><circle cx="12" cy="12" r="9"/><path d="M12 16v-4M12 8h.01"/></>),
  // Misc
  search: (<><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></>),
  bell: (<>
    <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/>
    <path d="M13.7 21a2 2 0 0 1-3.4 0"/>
  </>),
  command: (<>
    <path d="M18 3a3 3 0 0 0-3 3v12a3 3 0 0 0 3 3 3 3 0 0 0 3-3 3 3 0 0 0-3-3H6a3 3 0 0 0-3 3 3 3 0 0 0 3 3 3 3 0 0 0 3-3V6a3 3 0 0 0-3-3 3 3 0 0 0-3 3 3 3 0 0 0 3 3h12a3 3 0 0 0 3-3 3 3 0 0 0-3-3z"/>
  </>),
  chevDown: (<path d="M6 9l6 6 6-6"/>),
  chevRight: (<path d="M9 6l6 6-6 6"/>),
  chevLeft: (<path d="M15 6l-6 6 6 6"/>),
  chevUp: (<path d="M18 15l-6-6-6 6"/>),
  arrowUp: (<path d="M12 19V5M5 12l7-7 7 7"/>),
  arrowDown: (<path d="M12 5v14M19 12l-7 7-7-7"/>),
  arrowRight: (<><path d="M5 12h14"/><path d="M12 5l7 7-7 7"/></>),
  plus: (<><path d="M12 5v14M5 12h14"/></>),
  more: (<><circle cx="12" cy="12" r="1.2" fill="currentColor"/><circle cx="19" cy="12" r="1.2" fill="currentColor"/><circle cx="5" cy="12" r="1.2" fill="currentColor"/></>),
  download: (<><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M7 10l5 5 5-5"/><path d="M12 15V3"/></>),
  upload: (<><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M17 8l-5-5-5 5"/><path d="M12 3v12"/></>),
  filter: (<path d="M22 3H2l8 9.46V19l4 2v-8.54L22 3z"/>),
  sparkle: (<>
    <path d="M12 3l1.8 4.7L18.5 9l-4.7 1.8L12 15l-1.8-4.7L5.5 9l4.7-1.8L12 3z"/>
    <path d="M19 14l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7L19 14z"/>
  </>),
  zap: (<path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>),
  shield: (<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>),
  refresh: (<>
    <path d="M23 4v6h-6"/>
    <path d="M1 20v-6h6"/>
    <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
  </>),
  link: (<><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></>),
  eye: (<><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></>),
  file: (<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></>),
  filePdf: (<><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M9 13h.5a1.5 1.5 0 0 1 0 3H9v-3zM15 13v3M13 13h2.5M9 17v-4"/></>),
  brain: (<>
    <path d="M9.5 2A2.5 2.5 0 0 1 12 4.5v15A2.5 2.5 0 0 1 9.5 22 2.5 2.5 0 0 1 7 19.5 2.5 2.5 0 0 1 4.5 17 2.5 2.5 0 0 1 2 14.5a2.5 2.5 0 0 1 1.46-2.28A2.5 2.5 0 0 1 3 10.5 2.5 2.5 0 0 1 5.5 8 2.5 2.5 0 0 1 7 4.5 2.5 2.5 0 0 1 9.5 2z"/>
    <path d="M14.5 2A2.5 2.5 0 0 0 12 4.5v15a2.5 2.5 0 0 0 2.5 2.5 2.5 2.5 0 0 0 2.5-2.5 2.5 2.5 0 0 0 2.5-2.5 2.5 2.5 0 0 0 2.5-2.5 2.5 2.5 0 0 0-1.46-2.28A2.5 2.5 0 0 0 21 10.5 2.5 2.5 0 0 0 18.5 8 2.5 2.5 0 0 0 17 4.5 2.5 2.5 0 0 0 14.5 2z"/>
  </>),
  flow: (<>
    <circle cx="5" cy="5" r="2"/><circle cx="19" cy="5" r="2"/>
    <circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/>
    <path d="M7 5h10M5 7v10M19 7v10M7 19h10"/>
  </>),
  bolt: (<path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>),
  list: (<>
    <path d="M8 6h13M8 12h13M8 18h13"/>
    <circle cx="3.5" cy="6" r="1" fill="currentColor"/>
    <circle cx="3.5" cy="12" r="1" fill="currentColor"/>
    <circle cx="3.5" cy="18" r="1" fill="currentColor"/>
  </>),
  grid: (<>
    <rect x="3" y="3" width="7" height="7" rx="1"/>
    <rect x="14" y="3" width="7" height="7" rx="1"/>
    <rect x="3" y="14" width="7" height="7" rx="1"/>
    <rect x="14" y="14" width="7" height="7" rx="1"/>
  </>),
  flag: (<><path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><path d="M4 22V15"/></>),
  bank: (<>
    <path d="M3 21h18"/>
    <path d="M3 10h18"/>
    <path d="M5 10v11M19 10v11M9 10v11M15 10v11"/>
    <path d="M12 3L2 8h20L12 3z"/>
  </>),
  database: (<>
    <ellipse cx="12" cy="5" rx="9" ry="3"/>
    <path d="M3 5v6c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
    <path d="M3 11v6c0 1.66 4 3 9 3s9-1.34 9-3v-6"/>
  </>),
  globe: (<><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18 14 14 0 0 1 0-18z"/></>),
  user: (<>
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
    <circle cx="12" cy="7" r="4"/>
  </>),
  drag: (<><circle cx="9" cy="6" r="1.2" fill="currentColor"/><circle cx="9" cy="12" r="1.2" fill="currentColor"/><circle cx="9" cy="18" r="1.2" fill="currentColor"/><circle cx="15" cy="6" r="1.2" fill="currentColor"/><circle cx="15" cy="12" r="1.2" fill="currentColor"/><circle cx="15" cy="18" r="1.2" fill="currentColor"/></>),
  layers: (<><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></>),
  trend: (<>
    <path d="M22 7l-9 9-5-5L2 17"/>
    <path d="M16 7h6v6"/>
  </>),
  pause: (<><rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/></>),
  play: (<path d="M6 4l14 8-14 8V4z"/>),
  expand: (<><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></>),
  swap: (<><path d="M7 16V4M3 8l4-4 4 4M17 8v12M21 16l-4 4-4-4"/></>),
  copy: (<><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></>),
  receipt: (<>
    <path d="M4 2v20l2-2 2 2 2-2 2 2 2-2 2 2 2-2 2 2V2l-2 2-2-2-2 2-2-2-2 2-2-2-2 2-2-2z"/>
    <path d="M8 7h8M8 12h8M8 17h5"/>
  </>),
  scan: (<>
    <path d="M3 7V5a2 2 0 0 1 2-2h2"/>
    <path d="M17 3h2a2 2 0 0 1 2 2v2"/>
    <path d="M21 17v2a2 2 0 0 1-2 2h-2"/>
    <path d="M7 21H5a2 2 0 0 1-2-2v-2"/>
    <path d="M3 12h18"/>
  </>),
  cloud: (<path d="M18 10h-1.26A8 8 0 1 0 9 20h9a5 5 0 0 0 0-10z"/>),
  history: (<>
    <path d="M3 12a9 9 0 1 0 3-6.7L3 8"/>
    <path d="M3 3v5h5"/>
    <path d="M12 7v5l4 2"/>
  </>),
  branch: (<>
    <circle cx="6" cy="3" r="2"/><circle cx="6" cy="21" r="2"/><circle cx="18" cy="12" r="2"/>
    <path d="M6 5v14M6 11c0 3 3 3 6 3s6 0 6-3"/>
  </>),
};
