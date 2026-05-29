"use client"
import { useQuery } from "@tanstack/react-query"
import { auditService } from "@/services/audit.service"
import type { AuditFilters } from "@/types/api"

export function useAuditLogs(filters: AuditFilters = {}) {
  return useQuery({
    queryKey: ["audit", filters],
    queryFn: () => auditService.list(filters),
    staleTime: 10_000,
    refetchInterval: 15_000,
  })
}
