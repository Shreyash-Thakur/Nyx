import { api } from "@/lib/api"
import type { PaginatedResponse, Vendor, VendorCreate } from "@/types/api"

export const vendorService = {
  list: (search?: string, page = 1, page_size = 20) =>
    api.get<PaginatedResponse<Vendor>>("/vendors", { search, page, page_size }),
  get: (id: string) => api.get<Vendor>(`/vendors/${id}`),
  create: (data: VendorCreate) => api.post<Vendor>("/vendors", data),
  update: (id: string, data: Partial<VendorCreate>) => api.patch<Vendor>(`/vendors/${id}`, data),
}
