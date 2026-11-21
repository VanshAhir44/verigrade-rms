"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Lock, Mail, ShieldCheck, Search, ArrowRight } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { PageTransition } from "@/components/MotionPrimitives";
import { LoadingOverlay } from "@/components/LoadingOverlay";
import { useAuth } from "@/lib/auth-context";
import { ApiError } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();
  const { user, loading, login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [verifyId, setVerifyId] = useState("");
  const [verifyingNav, setVerifyingNav] = useState(false);

  useEffect(() => {
    if (!loading && user) {
      router.replace(`/${user.role}`);
    }
  }, [loading, user, router]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const loggedIn = await login(email, password);
      router.push(`/${loggedIn.role}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Authentication failed");
      setSubmitting(false);
    }
  };

  const handleVerifyLookup = (e: React.FormEvent) => {
    e.preventDefault();
    const cleaned = verifyId.trim();
    if (cleaned) {
      setVerifyingNav(true);
      router.push(`/verify/${encodeURIComponent(cleaned)}`);
    }
  };

  return (
    <div className="min-h-screen">
      <LoadingOverlay
        open={submitting || loading || verifyingNav}
        variant={verifyingNav ? "blockchain" : "auth"}
        title={
          verifyingNav
            ? "Opening On-Chain Verifier..."
            : submitting
            ? "Signing you in..."
            : "Checking your session..."
        }
        subtitle={
          verifyingNav
            ? "Preparing cryptographic SHA-256 verification lookup"
            : submitting
            ? "Authenticating your university credentials and preparing your portal"
            : "Restoring your authenticated portal session"
        }
      />
      <Navbar />
      <PageTransition>
        <main className="mx-auto grid max-w-6xl items-center gap-10 px-4 py-14 sm:px-6 lg:grid-cols-2">
          <div className="space-y-6">
            <span className="inline-flex items-center gap-2 rounded-full border border-brand-200 bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-700 dark:border-brand-800 dark:bg-brand-950/60 dark:text-brand-300">
              <ShieldCheck className="h-3.5 w-3.5" />
              Blockchain-Anchored Academic Transcripts
            </span>
            <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
              Real-Time Verified Student Results
            </h1>
            <p className="text-base leading-relaxed text-slate-600 dark:text-slate-300">
              Enter marks with instant validation, publish semester results live over WebSockets,
              anchor SHA-256 digests on-chain via Solidity, and let employers or universities
              verify PDF marksheets publicly in one click.
            </p>

            <form onSubmit={handleVerifyLookup} className="glass-card p-5">
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                Public Verifier (No Login Required)
              </p>
              <div className="flex flex-col gap-2 sm:flex-row">
                <div className="relative flex-1">
                  <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                  <input
                    type="text"
                    value={verifyId}
                    onChange={(e) => setVerifyId(e.target.value)}
                    placeholder="Paste Result UUID from PDF or QR..."
                    className="w-full rounded-xl border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm outline-none focus:border-brand-500 dark:border-slate-700 dark:bg-slate-900"
                  />
                </div>
                <motion.button
                  whileTap={{ scale: 0.97 }}
                  type="submit"
                  className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
                >
                  Verify On-Chain
                  <ArrowRight className="h-4 w-4" />
                </motion.button>
              </div>
            </form>
          </div>

          <div className="glass-card p-7 sm:p-8">
            <h2 className="text-xl font-semibold">Sign in to Portal</h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              Admin, Faculty, and Student accounts authenticate with JWT RBAC.
            </p>

            <form onSubmit={handleLogin} className="mt-6 space-y-4">
              <div>
                <label className="mb-1.5 block text-xs font-medium text-slate-600 dark:text-slate-300">
                  University Email
                </label>
                <div className="relative">
                  <Mail className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="admin@university.edu"
                    className="w-full rounded-xl border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm outline-none focus:border-brand-500 dark:border-slate-700 dark:bg-slate-900"
                  />
                </div>
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-medium text-slate-600 dark:text-slate-300">
                  Password
                </label>
                <div className="relative">
                  <Lock className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                  <input
                    type="password"
                    required
                    minLength={8}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    className="w-full rounded-xl border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm outline-none focus:border-brand-500 dark:border-slate-700 dark:bg-slate-900"
                  />
                </div>
              </div>

              {error && (
                <div className="rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-xs font-medium text-rose-700 dark:border-rose-800 dark:bg-rose-950/60 dark:text-rose-300">
                  {error}
                </div>
              )}

              <motion.button
                whileTap={{ scale: 0.98 }}
                disabled={submitting}
                type="submit"
                className="w-full rounded-xl bg-brand-600 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700 disabled:opacity-60"
              >
                {submitting ? "Signing in..." : "Sign In"}
              </motion.button>
            </form>
          </div>
        </main>
      </PageTransition>
    </div>
  );
}
