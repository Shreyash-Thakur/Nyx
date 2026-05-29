import { cn } from "@/lib/utils"

type Variant = "default" | "success" | "warning" | "danger" | "info" | "accent"

interface BadgeProps {
  variant?: Variant
  dot?: boolean
  children: React.ReactNode
  className?: string
}

export function Badge({ variant = "default", dot, children, className }: BadgeProps) {
  return (
    <span className={cn("badge", variant !== "default" && `badge-${variant}`, className)}>
      {dot && <span className="dot"/>}
      {children}
    </span>
  )
}
