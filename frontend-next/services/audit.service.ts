import { api } from "@/lib/api"
import type { AuditFilters, AuditLog, PaginatedResponse } from "@/types/api"

export const auditService = {
  list: (filters: AuditFilters = {}) =>
    api.get<PaginatedResponse<AuditLog>>("/audit", filters as Record<string, unknown>),
}
