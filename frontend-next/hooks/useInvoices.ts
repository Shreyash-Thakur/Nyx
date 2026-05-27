"use client"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import toast from "react-hot-toast"
import { invoiceService } from "@/services/invoice.service"
import type { InvoiceFilters, InvoiceUpdate } from "@/types/api"

export function useInvoices(filters: InvoiceFilters = {}) {
  return useQuery({
    queryKey: ["invoices", filters],
    queryFn: () => invoiceService.list(filters),
    staleTime: 15_000,
  })
}

export function useInvoice(id: string) {
  return useQuery({
    queryKey: ["invoice", id],
    queryFn: () => invoiceService.get(id),
    enabled: !!id,
  })
}

export function useInvoiceJobs(id: string, enabled = false) {
  return useQuery({
    queryKey: ["invoice-jobs", id],
    queryFn: () => invoiceService.jobs(id),
    enabled,
    refetchInterval: (query) => {
      const jobs = query.state.data
      const hasActive = jobs?.some((j) => ["queued", "started"].includes(j.status))
      return hasActive ? 3_000 : false
    },
  })
}

export function useUploadInvoice() {
  const qc = useQueryClient()
  const [progress, setProgress] = useState(0)

  const mutation = useMutation({
    mutationFn: (file: File) => invoiceService.upload(file, setProgress),
    onSuccess: () => {
      toast.success("Invoice uploaded — processing in background")
      qc.invalidateQueries({ queryKey: ["invoices"] })
      setProgress(0)
    },
    onError: (e: Error) => {
      toast.error(e.message || "Upload failed")
      setProgress(0)
    },
  })

  return { ...mutation, progress }
}

export function useUpdateInvoice() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: InvoiceUpdate }) =>
      invoiceService.update(id, data),
    onSuccess: (inv) => {
      qc.invalidateQueries({ queryKey: ["invoices"] })
      qc.invalidateQueries({ queryKey: ["invoice", inv.id] })
      toast.success("Invoice updated")
    },
    onError: () => toast.error("Update failed"),
  })
}
