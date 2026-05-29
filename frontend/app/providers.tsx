"use client"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ReactQueryDevtools } from "@tanstack/react-query-devtools"
import { Toaster } from "react-hot-toast"
import { useState } from "react"

export function Providers({ children }: { children: React.ReactNode }) {
  const [qc] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: 2, refetchOnWindowFocus: false },
          mutations: { retry: 0 },
        },
      })
  )

  return (
    <QueryClientProvider client={qc}>
      {children}
      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: "var(--bg-4)",
            color: "var(--text-1)",
            border: "1px solid var(--border-strong)",
            fontSize: "13px",
            borderRadius: "8px",
          },
          success: { iconTheme: { primary: "var(--success)", secondary: "var(--bg-4)" } },
          error: { iconTheme: { primary: "var(--danger)", secondary: "var(--bg-4)" } },
        }}
      />
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  )
}
