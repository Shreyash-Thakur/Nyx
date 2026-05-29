"use client"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useRouter } from "next/navigation"
import toast from "react-hot-toast"
import { authService } from "@/services/auth.service"
import { useAuthStore } from "@/store/auth.store"

export function useLogin() {
  const router = useRouter()
  const { setTokens, setUser } = useAuthStore()
  return useMutation({
    mutationFn: authService.login,
    onSuccess: async (tokens) => {
      setTokens(tokens.access_token, tokens.refresh_token)
      const user = await authService.me()
      setUser(user)
      router.replace("/")
    },
    onError: () => toast.error("Invalid email or password"),
  })
}

export function useLogout() {
  const router = useRouter()
  const { logout } = useAuthStore()
  const qc = useQueryClient()
  return () => {
    logout()
    qc.clear()
    router.replace("/login")
  }
}

export function useMe() {
  const { isAuthenticated } = useAuthStore()
  return useQuery({
    queryKey: ["me"],
    queryFn: authService.me,
    enabled: isAuthenticated,
    staleTime: 5 * 60 * 1000,
  })
}
