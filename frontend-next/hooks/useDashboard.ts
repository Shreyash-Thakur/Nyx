"use client"
import { useQuery } from "@tanstack/react-query"
import { dashboardService } from "@/services/dashboard.service"

export const DASHBOARD_KEYS = {
  overview: ["dashboard", "overview"] as const,
  queue: ["dashboard", "queue"] as const,
  trends: ["dashboard", "trends"] as const,
}

export function useDashboardOverview() {
  return useQuery({
    queryKey: DASHBOARD_KEYS.overview,
    queryFn: dashboardService.overview,
    refetchInterval: 30_000,
    staleTime: 20_000,
  })
}

export function useQueueStatus() {
  return useQuery({
    queryKey: DASHBOARD_KEYS.queue,
    queryFn: dashboardService.queueStatus,
    refetchInterval: 10_000,
    staleTime: 8_000,
  })
}

export function useTrends() {
  return useQuery({
    queryKey: DASHBOARD_KEYS.trends,
    queryFn: dashboardService.trends,
    staleTime: 5 * 60_000,
  })
}
