"use client"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import toast from "react-hot-toast"
import { reconciliationService } from "@/services/reconciliation.service"
import type { ReconciliationRequest, ResolveRequest } from "@/types/api"

export function useReconciliation(params: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: ["reconciliation", params],
    queryFn: () => reconciliationService.list(params),
    staleTime: 20_000,
    refetchInterval: 30_000,
  })
}

export function useReconcile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: ReconciliationRequest) => reconciliationService.reconcile(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["reconciliation"] })
      qc.invalidateQueries({ queryKey: ["invoices"] })
      qc.invalidateQueries({ queryKey: ["dashboard"] })
      toast.success("Reconciliation complete")
    },
    onError: (e: Error) => toast.error(e.message || "Reconciliation failed"),
  })
}

export function useResolve() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ResolveRequest }) =>
      reconciliationService.resolve(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["reconciliation"] })
      toast.success("Discrepancy resolved")
    },
    onError: () => toast.error("Failed to resolve"),
  })
}
