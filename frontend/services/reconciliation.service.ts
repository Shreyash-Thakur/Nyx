import { api } from "@/lib/api"
import type { PaginatedResponse, ReconciliationRecord, ReconciliationRequest, ResolveRequest } from "@/types/api"

export const reconciliationService = {
  list: (params: Record<string, unknown> = {}) =>
    api.get<PaginatedResponse<ReconciliationRecord>>("/reconciliation", params),
  forInvoice: (invoiceId: string) =>
    api.get<ReconciliationRecord[]>(`/reconciliation/invoice/${invoiceId}`),
  reconcile: (data: ReconciliationRequest) =>
    api.post<ReconciliationRecord>("/reconciliation", data),
  resolve: (id: string, data: ResolveRequest) =>
    api.post<ReconciliationRecord>(`/reconciliation/${id}/resolve`, data),
}
