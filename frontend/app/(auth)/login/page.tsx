"use client"
import { useState } from "react"
import { motion } from "framer-motion"
import { Eye, EyeOff, Loader } from "lucide-react"
import { useLogin } from "@/hooks/useAuth"

export default function LoginPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPw, setShowPw] = useState(false)
  const { mutate: login, isPending } = useLogin()

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    login({ email, password })
  }

  return (
    <div style={{
      minHeight: "100dvh", background: "var(--bg-0)", display: "flex",
      alignItems: "center", justifyContent: "center",
      fontFamily: "var(--font-geist-sans, ui-sans-serif)",
    }}>
      {/* ambient */}
      <div style={{
        position: "fixed", inset: 0, pointerEvents: "none",
        background: "radial-gradient(ellipse 60% 60% at 50% 0%, rgba(124,107,255,0.12), transparent 70%)",
      }}/>

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
        style={{ width: 380, position: "relative", zIndex: 1 }}
      >
        {/* Brand */}
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 40, justifyContent: "center" }}>
          <div style={{
            width: 32, height: 32, borderRadius: 9,
            background: "linear-gradient(135deg, var(--accent) 0%, #C99BFF 50%, var(--success) 100%)",
            display: "grid", placeItems: "center",
            boxShadow: "0 4px 20px var(--accent-glow)",
          }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M4 6h16M4 12h10M4 18h16"/>
            </svg>
          </div>
          <span style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.02em", color: "var(--text-1)" }}>Nyx</span>
        </div>

        {/* Card */}
        <div style={{
          background: "var(--bg-2)", border: "1px solid var(--border)",
          borderRadius: 16, padding: "32px 28px",
          boxShadow: "0 1px 0 rgba(255,255,255,0.04) inset, 0 24px 64px rgba(0,0,0,0.6)",
        }}>
          <div style={{ marginBottom: 24 }}>
            <div style={{ fontSize: 17, fontWeight: 600, color: "var(--text-1)", letterSpacing: "-0.02em" }}>Sign in</div>
            <div style={{ fontSize: 12.5, color: "var(--text-3)", marginTop: 4 }}>Finance operations platform</div>
          </div>

          <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div>
              <label style={{ fontSize: 11.5, color: "var(--text-3)", display: "block", marginBottom: 5 }}>Email</label>
              <input
                type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                required autoFocus autoComplete="email"
                placeholder="you@company.com"
                style={{
                  width: "100%", height: 36, padding: "0 12px",
                  background: "var(--bg-3)", border: "1px solid var(--border)",
                  borderRadius: 8, fontSize: 13, color: "var(--text-1)", outline: "none",
                  transition: "border-color 0.15s",
                }}
                onFocus={(e) => { e.target.style.borderColor = "var(--accent)"; e.target.style.boxShadow = "0 0 0 3px var(--accent-soft)" }}
                onBlur={(e) => { e.target.style.borderColor = "var(--border)"; e.target.style.boxShadow = "none" }}
              />
            </div>
            <div>
              <label style={{ fontSize: 11.5, color: "var(--text-3)", display: "block", marginBottom: 5 }}>Password</label>
              <div style={{ position: "relative" }}>
                <input
                  type={showPw ? "text" : "password"} value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required autoComplete="current-password" placeholder="••••••••"
                  style={{
                    width: "100%", height: 36, padding: "0 36px 0 12px",
                    background: "var(--bg-3)", border: "1px solid var(--border)",
                    borderRadius: 8, fontSize: 13, color: "var(--text-1)", outline: "none",
                    transition: "border-color 0.15s",
                  }}
                  onFocus={(e) => { e.target.style.borderColor = "var(--accent)"; e.target.style.boxShadow = "0 0 0 3px var(--accent-soft)" }}
                  onBlur={(e) => { e.target.style.borderColor = "var(--border)"; e.target.style.boxShadow = "none" }}
                />
                <button type="button" onClick={() => setShowPw(!showPw)}
                  style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)", color: "var(--text-3)" }}>
                  {showPw ? <EyeOff size={14}/> : <Eye size={14}/>}
                </button>
              </div>
            </div>

            <button
              type="submit" disabled={isPending}
              style={{
                marginTop: 4, height: 36, borderRadius: 8, background: "var(--accent)",
                border: "1px solid var(--accent-2)", color: "white", fontSize: 13, fontWeight: 500,
                display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                cursor: isPending ? "not-allowed" : "pointer", opacity: isPending ? 0.7 : 1,
                transition: "opacity 0.15s",
                boxShadow: "0 1px 0 rgba(255,255,255,0.12) inset",
              }}
            >
              {isPending ? <><Loader size={13} style={{ animation: "spin 1s linear infinite" }}/>Signing in…</> : "Sign in"}
            </button>
          </form>
        </div>

        <div style={{ textAlign: "center", marginTop: 20, fontSize: 12, color: "var(--text-4)" }}>
          Nyx · Finance Operations Platform
        </div>
      </motion.div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}
