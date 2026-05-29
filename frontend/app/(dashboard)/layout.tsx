"use client"
import { useEffect } from "react"
import { useRouter } from "next/navigation"
import { Sidebar } from "@/components/shell/Sidebar"
import { Topbar } from "@/components/shell/Topbar"
import { useAuthStore } from "@/store/auth.store"
import { useMe } from "@/hooks/useAuth"

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const { isAuthenticated, setUser } = useAuthStore()
  const { data: user } = useMe()

  useEffect(() => {
    if (!isAuthenticated) router.replace("/login")
  }, [isAuthenticated, router])

  useEffect(() => {
    if (user) setUser(user)
  }, [user, setUser])

  if (!isAuthenticated) return null

  return (
    <div className="app-shell">
      <Sidebar/>
      <main className="app-main">
        <Topbar/>
        <div className="app-canvas">
          {children}
        </div>
      </main>
    </div>
  )
}
