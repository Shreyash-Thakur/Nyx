"use client"
import { useState } from "react"
import { motion } from "framer-motion"
import { Plus, Search } from "lucide-react"
import { useQuery } from "@tanstack/react-query"
import { vendorService } from "@/services/vendor.service"
import { TableSkeleton } from "@/components/ui/Skeleton"
import { Badge } from "@/components/ui/Badge"
import { fmtDate } from "@/lib/utils"

export default function VendorsPage() {
  const [search, setSearch] = useState("")
  const [page, setPage] = useState(1)

  const { data, isLoading } = useQuery({
    queryKey: ["vendors", search, page],
    queryFn: () => vendorService.list(search || undefined, page, 20),
    staleTime: 30_000,
  })

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <div className="page-title">Vendors</div>
          <div className="page-subtitle">{data ? `${data.total} vendors` : "Loading…"}</div>
        </div>
        <button className="btn btn-sm btn-primary">
          <Plus size={13}/>
          Add vendor
        </button>
      </div>

      <div style={{ marginBottom: 16 }}>
        <div className="search-bar" style={{ maxWidth: 320 }}>
          <Search size={13}/>
          <input placeholder="Search by name or GST…" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1) }}/>
        </div>
      </div>

      <div className="card">
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>GST number</th>
                <th>Email</th>
                <th>Phone</th>
                <th>Status</th>
                <th>Added</th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr><td colSpan={6} style={{ padding: 0 }}><TableSkeleton rows={6}/></td></tr>
              ) : !data?.items.length ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", padding: "40px 16px", color: "var(--text-3)" }}>
                    No vendors yet — upload invoices to auto-detect vendors
                  </td>
                </tr>
              ) : data.items.map((v, i) => (
                <motion.tr key={v.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: i * 0.03 }}>
                  <td style={{ fontWeight: 500 }}>{v.name}</td>
                  <td><span className="mono" style={{ fontSize: 12 }}>{v.gst_number ?? "—"}</span></td>
                  <td style={{ color: "var(--text-2)" }}>{v.email ?? "—"}</td>
                  <td style={{ color: "var(--text-2)" }}>{v.phone ?? "—"}</td>
                  <td><Badge variant={v.is_active ? "success" : "default"} dot>{v.is_active ? "Active" : "Inactive"}</Badge></td>
                  <td><span style={{ fontSize: 11.5, color: "var(--text-3)" }}>{fmtDate(v.created_at)}</span></td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
