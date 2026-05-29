import { api } from "@/lib/api"
import type { AnalyticsTrend, DashboardOverview, DiscrepancySummary, InvoiceCountSummary, QueueStatus } from "@/types/api"

export const dashboardService = {
  overview: () => api.get<DashboardOverview>("/dashboard/overview"),
  invoiceSummary: () => api.get<InvoiceCountSummary>("/dashboard/invoices/summary"),
  discrepancySummary: () => api.get<DiscrepancySummary>("/dashboard/discrepancies/summary"),
  queueStatus: () => api.get<QueueStatus>("/dashboard/queue/status"),
  trends: () => api.get<AnalyticsTrend[]>("/dashboard/analytics/trends"),
}
