import { api } from "@/lib/api"
import type { LoginRequest, RegisterRequest, TokenResponse, UserResponse } from "@/types/api"

export const authService = {
  login: (data: LoginRequest) => api.post<TokenResponse>("/auth/login", data),
  register: (data: RegisterRequest) => api.post<UserResponse>("/auth/register", data),
  refresh: (refresh_token: string) => api.post<TokenResponse>("/auth/refresh", { refresh_token }),
  me: () => api.get<UserResponse>("/auth/me"),
  changePassword: (current_password: string, new_password: string) =>
    api.post("/auth/change-password", { current_password, new_password }),
}
