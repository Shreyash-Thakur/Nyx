import { api } from "@/lib/api"
import type { ActivityEvent } from "@/types/api"

export const activityService = {
  list: (limit = 20) => api.get<ActivityEvent[]>("/activity", { limit }),
}
