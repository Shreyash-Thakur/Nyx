import type { Metadata } from "next"
import { Inter, JetBrains_Mono } from "next/font/google"
import "./globals.css"
import { Providers } from "./providers"

const geistSans = Inter({
  subsets: ["latin"],
  variable: "--font-geist-sans",
  display: "swap",
})

const geistMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
  display: "swap",
})

export const metadata: Metadata = {
  title: { default: "LedgerFlow", template: "%s · LedgerFlow" },
  description: "Finance operations and invoice reconciliation platform",
  robots: "noindex",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`} suppressHydrationWarning>
      <body style={{ fontFamily: "var(--font-geist-sans, ui-sans-serif)" }}>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
