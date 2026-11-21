"use client";

import { useState } from "react";
import Link from "next/link";
import { ShieldCheck, Sun, Moon, LogOut, Radio } from "lucide-react";
import { motion } from "framer-motion";
import { useAuth } from "@/lib/auth-context";
import { useTheme } from "@/components/ThemeProvider";
import { LoadingOverlay } from "@/components/LoadingOverlay";
import type { WsStatus } from "@/hooks/useResultWebSocket";

interface NavbarProps {
  wsStatus?: WsStatus;
}

export function Navbar({ wsStatus }: NavbarProps) {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [signingOut, setSigningOut] = useState(false);

  const handleLogout = async () => {
    setSigningOut(true);
    try {
      await logout();
    } finally {
      setSigningOut(false);
    }
  };

  return (
    <>
      <LoadingOverlay
        open={signingOut}
        variant="auth"
        title="Signing you out..."
        subtitle="Closing your session securely"
      />
      <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/80 backdrop-blur-md dark:border-slate-800/80 dark:bg-slate-950/80">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
        <Link href={user ? `/${user.role}` : "/"} className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-600 text-white shadow-sm">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold tracking-tight">VeriGrade RMS</p>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              On-Chain Verified Results
            </p>
          </div>
        </Link>

        <div className="flex items-center gap-3">
          {wsStatus && (
            <div
              className={`hidden items-center gap-2 rounded-full px-3 py-1 text-xs font-medium sm:flex ${
                wsStatus === "connected"
                  ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300"
                  : wsStatus === "connecting"
                  ? "bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300"
                  : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400"
              }`}
            >
              <span className="relative flex h-2 w-2">
                {wsStatus === "connected" && (
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                )}
                <span
                  className={`relative inline-flex h-2 w-2 rounded-full ${
                    wsStatus === "connected"
                      ? "bg-emerald-500"
                      : wsStatus === "connecting"
                      ? "bg-amber-500"
                      : "bg-slate-400"
                  }`}
                />
              </span>
              <Radio className="h-3.5 w-3.5" />
              {wsStatus === "connected"
                ? "Live Connected"
                : wsStatus === "connecting"
                ? "Connecting..."
                : "Offline"}
            </div>
          )}

          <Link
            href="/verify"
            className="rounded-lg px-3 py-1.5 text-xs font-medium text-slate-600 transition hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            Public Verify
          </Link>

          <motion.button
            whileTap={{ scale: 0.92 }}
            onClick={toggleTheme}
            aria-label="Toggle dark mode"
            className="rounded-lg border border-slate-200 p-2 text-slate-600 transition hover:bg-slate-100 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </motion.button>

          {user && (
            <div className="flex items-center gap-2.5 pl-1">
              <div className="hidden text-right md:block">
                <p className="text-xs font-semibold leading-tight">{user.full_name}</p>
                <p className="text-[11px] uppercase tracking-wider text-brand-600 dark:text-brand-400">
                  {user.role}
                </p>
              </div>
              <motion.button
                whileTap={{ scale: 0.95 }}
                disabled={signingOut}
                onClick={handleLogout}
                className="flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-rose-50 hover:text-rose-700 disabled:opacity-60 dark:border-slate-700 dark:text-slate-200 dark:hover:bg-rose-950/50 dark:hover:text-rose-300"
              >
                <LogOut className="h-3.5 w-3.5" />
                Sign Out
              </motion.button>
            </div>
          )}
        </div>
      </div>
    </header>
    </>
  );
}
