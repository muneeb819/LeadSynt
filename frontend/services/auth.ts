import { api, clearTokens, setTokens } from "@/lib/api-client";
import type { MeOut } from "@/types/api";

export async function login(email: string, password: string) {
  const body = await api<{ access_token: string; refresh_token: string }>(
    "/auth/login",
    { method: "POST", body: JSON.stringify({ email, password }) },
  );
  setTokens(body.access_token, body.refresh_token);
  return body;
}

export async function fetchMe(): Promise<MeOut | null> {
  try {
    return await api<MeOut>("/auth/me");
  } catch {
    clearTokens();
    return null;
  }
}

export function logout(): void {
  clearTokens();
}
