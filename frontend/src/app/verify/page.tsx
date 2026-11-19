"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { ShieldCheck, Search } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { PageTransition } from "@/components/MotionPrimitives";

export default function VerifyIndexPage() {
  const router = useRouter();
  const [resultId, setResultId] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (resultId.trim()) {
      router.push(`/verify/${encodeURIComponent(resultId.trim())}`);
    }
  };

  return (
    <div className="min-h-screen">
      <Navbar />
      <PageTransition>
        <main className="mx-auto max-w-2xl px-4 py-16 sm:px-6">
          <div className="glass-card p-8 text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
              <ShieldCheck className="h-7 w-7" />
            </div>
            <h1 className="text-2xl font-bold">Public Blockchain Result Verifier</h1>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
              Enter a Result ID or scan the QR code on an official PDF marksheet. We recompute
              the SHA-256 digest live and check it against the immutable{" "}
              <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs dark:bg-slate-800">
                ResultRegistry.sol
              </code>{" "}
              smart contract.
            </p>
            <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-3 sm:flex-row">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" />
                <input
                  type="text"
                  required
                  value={resultId}
                  onChange={(e) => setResultId(e.target.value)}
                  placeholder="Enter Result UUID..."
                  className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-9 pr-3 text-sm outline-none focus:border-brand-500 dark:border-slate-700 dark:bg-slate-900"
                />
              </div>
              <motion.button
                whileTap={{ scale: 0.97 }}
                type="submit"
                className="rounded-xl bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-brand-700"
              >
                Verify Proof
              </motion.button>
            </form>
          </div>
        </main>
      </PageTransition>
    </div>
  );
}
