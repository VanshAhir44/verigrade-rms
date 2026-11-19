import type { TokenResponse } from "@/types/api";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export const WS_BASE_URL =
  process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";

const ACCESS_KEY = "rms_access_token";
const REFRESH_KEY = "rms_refresh_token";
const USER_KEY = "rms_user";

export function getStoredAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_KEY);
}

export function getStoredRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

export function saveAuthSession(data: TokenResponse): void {
  localStorage.setItem(ACCESS_KEY, data.access_token);
  localStorage.setItem(REFRESH_KEY, data.refresh_token);
  localStorage.setItem(USER_KEY, JSON.stringify(data.user));
}

export function clearAuthSession(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
}

async function tryRefreshSession(): Promise<string | null> {
  const refreshToken = getStoredRefreshToken();
  if (!refreshToken) return null;

  const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!res.ok) {
    clearAuthSession();
    return null;
  }

  const refreshed: TokenResponse = await res.json();
  saveAuthSession(refreshed);
  return refreshed.access_token;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit & { skipAuth?: boolean } = {}
): Promise<T> {
  const { skipAuth = false, headers: customHeaders, ...rest } = options;

  const buildHeaders = (token: string | null): HeadersInit => {
    const h: Record<string, string> = {};
    if (!(rest.body instanceof FormData)) {
      h["Content-Type"] = "application/json";
    }
    if (!skipAuth && token) {
      h["Authorization"] = `Bearer ${token}`;
    }
    return { ...h, ...(customHeaders as Record<string, string>) };
  };

  let token = getStoredAccessToken();
  let res = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: buildHeaders(token),
  });

  if (res.status === 401 && !skipAuth) {
    const newToken = await tryRefreshSession();
    if (newToken) {
      res = await fetch(`${API_BASE_URL}${path}`, {
        ...rest,
        headers: buildHeaders(newToken),
      });
    }
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const errBody = await res.json();
      if (typeof errBody?.detail === "string") {
        detail = errBody.detail;
      }
    } catch {
      // keep status message
    }
    throw new ApiError(detail, res.status);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

export async function downloadPdfMarksheet(resultId: string, filename: string): Promise<void> {
  const token = getStoredAccessToken();
  const res = await fetch(`${API_BASE_URL}/student/results/${resultId}/pdf`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    throw new ApiError("Failed to download PDF marksheet", res.status);
  }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
