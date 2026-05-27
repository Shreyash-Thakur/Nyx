import { Badge } from "@/components/ui/Badge"
import type { InvoiceStatus, PaymentStatus } from "@/types/api"

const STATUS_MAP: Record<string, { label: string; variant: "success" | "warning" | "danger" | "info" | "accent" | "default" }> = {
  uploaded:   { label: "Uploaded",   variant: "default" },
  queued:     { label: "Queued",     variant: "info" },
  processing: { label: "Processing", variant: "accent" },
  extracted:  { label: "Extracted",  variant: "info" },
  validated:  { label: "Validated",  variant: "warning" },
  reconciled: { label: "Reconciled", variant: "success" },
  failed:     { label: "Failed",     variant: "danger" },
  duplicate:  { label: "Duplicate",  variant: "warning" },
  pending:    { label: "Pending",    variant: "warning" },
  paid:       { label: "Paid",       variant: "success" },
  overdue:    { label: "Overdue",    variant: "danger" },
  partial:    { label: "Partial",    variant: "warning" },
  cancelled:  { label: "Cancelled",  variant: "default" },
}

export function InvoiceStatusBadge({ status }: { status: InvoiceStatus | PaymentStatus }) {
  const meta = STATUS_MAP[status] ?? { label: status, variant: "default" as const }
  return <Badge variant={meta.variant} dot>{meta.label}</Badge>
}
