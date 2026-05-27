import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const fmtUsd = (n: number | string, cents = true) => {
  const num = typeof n === "string" ? parseFloat(n) : n
  if (isNaN(num)) return "—"
  return num.toLocaleString("en-US", {
    style: "currency", currency: "USD",
    minimumFractionDigits: cents ? 2 : 0,
    maximumFractionDigits: cents ? 2 : 0,
  })
}

export const fmtNum = (n: number) => n.toLocaleString("en-US")

export const fmtPct = (n: number, decimals = 1) => `${n.toFixed(decimals)}%`

export const fmtDate = (iso: string | null) => {
  if (!iso) return "—"
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
}

export const fmtTime = (iso: string) => {
  return new Date(iso).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })
}

export const relativeTime = (iso: string) => {
  const diff = Date.now() - new Date(iso).getTime()
  const s = Math.floor(diff / 1000)
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return fmtDate(iso)
}

export const statusColor: Record<string, string> = {
  uploaded: "var(--text-3)",
  queued: "var(--info)",
  processing: "var(--accent)",
  extracted: "var(--info)",
  validated: "var(--warning)",
  reconciled: "var(--success)",
  failed: "var(--danger)",
  duplicate: "var(--warning)",
  matched: "var(--success)",
  partial_match: "var(--warning)",
  unmatched: "var(--text-3)",
  discrepancy: "var(--danger)",
  manually_resolved: "var(--info)",
  pending: "var(--warning)",
  paid: "var(--success)",
  overdue: "var(--danger)",
  partial: "var(--warning)",
  cancelled: "var(--text-3)",
}

export const statusLabel: Record<string, string> = {
  uploaded: "Uploaded", queued: "Queued", processing: "Processing",
  extracted: "Extracted", validated: "Validated", reconciled: "Reconciled",
  failed: "Failed", duplicate: "Duplicate", matched: "Matched",
  partial_match: "Partial", unmatched: "Unmatched", discrepancy: "Discrepancy",
  manually_resolved: "Resolved", pending: "Pending", paid: "Paid",
  overdue: "Overdue", partial: "Partial", cancelled: "Cancelled",
}

export const confidenceColor = (v: number) =>
  v >= 0.95 ? "var(--success)"
  : v >= 0.85 ? "var(--info)"
  : v >= 0.7  ? "var(--warning)"
  : "var(--danger)"

export const fileSizeFmt = (bytes: number | null) => {
  if (!bytes) return "—"
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
