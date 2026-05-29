import { api } from "@/lib/api"
import type { Invoice, InvoiceDetail, InvoiceFilters, InvoiceUpdate, PaginatedResponse, ProcessingJob } from "@/types/api"

export const invoiceService = {
  list: (filters: InvoiceFilters = {}) =>
    api.get<PaginatedResponse<Invoice>>("/invoices", filters as Record<string, unknown>),

  get: (id: string) => api.get<InvoiceDetail>(`/invoices/${id}`),

  upload: (file: File, onProgress?: (pct: number) => void) => {
    const fd = new FormData()
    fd.append("file", file)
    return api.upload<Invoice>("/invoices", fd, onProgress)
  },

  update: (id: string, data: InvoiceUpdate) => api.patch<Invoice>(`/invoices/${id}`, data),

  jobs: (id: string) => api.get<ProcessingJob[]>(`/invoices/${id}/jobs`),
}
