"use client"
import { useState } from "react"
import { useAuthStore } from "@/store/auth.store"
import { useLogout } from "@/hooks/useAuth"

export default function SettingsPage() {
  const user = useAuthStore((s) => s.user)
  const logout = useLogout()
  const [apiUrl] = useState(process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000")

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-title">Settings</div>
          <div className="page-subtitle">Account and workspace configuration</div>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 600 }}>
        {/* Profile card */}
        <div className="card">
          <div className="card-header"><span className="card-title">Profile</span></div>
          <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <label style={{ fontSize: 11.5, color: "var(--text-3)", display: "block", marginBottom: 4 }}>Full name</label>
              <input defaultValue={user?.full_name ?? ""} disabled
                style={{ width: "100%", height: 34, padding: "0 10px", background: "var(--bg-3)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13, color: "var(--text-2)", outline: "none" }}/>
            </div>
            <div>
              <label style={{ fontSize: 11.5, color: "var(--text-3)", display: "block", marginBottom: 4 }}>Email</label>
              <input defaultValue={user?.email ?? ""} disabled
                style={{ width: "100%", height: 34, padding: "0 10px", background: "var(--bg-3)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13, color: "var(--text-2)", outline: "none" }}/>
            </div>
            <div>
              <label style={{ fontSize: 11.5, color: "var(--text-3)", display: "block", marginBottom: 4 }}>Role</label>
              <div style={{ height: 34, padding: "0 10px", background: "var(--bg-3)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 13, color: "var(--text-2)", display: "flex", alignItems: "center", textTransform: "capitalize" }}>
                {user?.role ?? "—"}
              </div>
            </div>
          </div>
        </div>

        {/* API config */}
        <div className="card">
          <div className="card-header"><span className="card-title">API Connection</span></div>
          <div className="card-body">
            <div style={{ fontSize: 12.5, color: "var(--text-3)", marginBottom: 8 }}>Backend URL</div>
            <div className="mono" style={{ fontSize: 12, color: "var(--text-2)", padding: "8px 10px", background: "var(--bg-2)", borderRadius: 6, border: "1px solid var(--border)" }}>
              {apiUrl}
            </div>
            <div style={{ fontSize: 11.5, color: "var(--text-4)", marginTop: 6 }}>Configure via NEXT_PUBLIC_API_URL environment variable</div>
          </div>
        </div>

        {/* Danger zone */}
        <div className="card" style={{ borderColor: "rgba(242,107,123,0.2)" }}>
          <div className="card-header"><span className="card-title" style={{ color: "var(--danger)" }}>Session</span></div>
          <div className="card-body">
            <button className="btn btn-danger" onClick={logout}>Sign out of LedgerFlow</button>
          </div>
        </div>
      </div>
    </div>
  )
}
