"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { TokenResponse, User } from "@/types/api";
import {
  ApiError,
  apiRequest,
  clearAuthSession,
  getStoredAccessToken,
  getStoredRefreshToken,
  saveAuthSession,
  TOKEN_REFRESHED_EVENT,
} from "@/lib/api";

interface AuthContextValue {
  user: User | null;
  accessToken: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // P1-8 fix: keep React accessToken state synchronized after background token refreshes
    const onTokenUpdated = (evt: Event) => {
      const custom = evt as CustomEvent<string | null>;
      setAccessToken(custom.detail ?? null);
    };
    window.addEventListener(TOKEN_REFRESHED_EVENT, onTokenUpdated);
    return () => window.removeEventListener(TOKEN_REFRESHED_EVENT, onTokenUpdated);
  }, []);

  useEffect(() => {
    const token = getStoredAccessToken();
    if (!token) {
      setLoading(false);
      return;
    }
    setAccessToken(token);
    apiRequest<User>("/auth/me")
      .then((profile) => {
        setUser(profile);
        setAccessToken(getStoredAccessToken());
      })
      .catch((err) => {
        // P2-15 fix: only wipe session on actual 401 Unauthorized, not transient network blips
        if (err instanceof ApiError && err.status === 401) {
          clearAuthSession();
          setUser(null);
          setAccessToken(null);
        }
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string): Promise<User> => {
    const data = await apiRequest<TokenResponse>("/auth/login", {
      method: "POST",
      skipAuth: true,
      body: JSON.stringify({ email, password }),
    });
    saveAuthSession(data);
    setUser(data.user);
    setAccessToken(data.access_token);
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    const refreshToken = getStoredRefreshToken();
    if (refreshToken) {
      try {
        // P2-17 fix: skipAuth prevents an expired access token from triggering a refresh before logout
        await apiRequest<void>("/auth/logout", {
          method: "POST",
          skipAuth: true,
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
      } catch {
        // always clear client state
      }
    }
    clearAuthSession();
    setUser(null);
    setAccessToken(null);
    router.push("/");
  }, [router]);

  return (
    <AuthContext.Provider value={{ user, accessToken, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
