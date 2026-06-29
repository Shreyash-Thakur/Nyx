"use client"
import { useQuery } from "@tanstack/react-query"
import { activityService } from "@/services/activity.service"

export const ACTIVITY_KEYS = {
  list: (limit: number) => ["activity", limit] as const,
}

export function useActivity(limit = 20) {
  return useQuery({
    queryKey: ACTIVITY_KEYS.list(limit),
    queryFn: () => activityService.list(limit),
    refetchInterval: 15_000,
    staleTime: 10_000,
  })
}
