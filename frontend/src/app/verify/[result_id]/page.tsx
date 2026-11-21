"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { motion } from "framer-motion";
import { ShieldCheck, ShieldAlert, Hash, Blocks, Clock, ArrowLeft } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { PageTransition } from "@/components/MotionPrimitives";
import { LoadingOverlay } from "@/components/LoadingOverlay";
import { AnimatedCounter } from "@/components/AnimatedCounter";
import { apiRequest, ApiError } from "@/lib/api";
import { formatIST } from "@/lib/date";
import type { PublicVerificationResponse } from "@/types/api";

export default function VerifyResultPage() {
  const params = useParams<{ result_id: string }>();
  const resultId = params?.result_id;
  const [data, setData] = useState<PublicVerificationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!resultId) return;
    setLoading(true);
    setError(null);
    apiRequest<PublicVerificationResponse>(`/verify/${encodeURIComponent(resultId)}`, {
      skipAuth: true,
    })
      .then(setData)
      .catch((err) =>
        setError(err instanceof ApiError ? err.message : "Could not verify result")
      )
      .finally(() => setLoading(false));
  }, [resultId]);

  return (
    <div className="min-h-screen">
      <LoadingOverlay
        open={loading}
        variant="blockchain"
        title="Verifying On-Chain Proof..."
        subtitle="Recomputing SHA-256 digest and checking the immutable ResultRegistry smart contract"
      />
      <Navbar />
      <PageTransition>
        <main className="mx-auto max-w-4xl px-4 py-10 sm:px-6">
          <Link
            href="/verify"
            className="mb-6 inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-900 dark:hover:text-white"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Verify another result
          </Link>

          {loading && (
            <div className="glass-card p-10 text-center text-sm text-slate-500">
              Recomputing SHA-256 digest and querying on-chain ResultRegistry...
            </div>
          )}

          {error && (
            <div className="glass-card border-rose-300 bg-rose-50/70 p-8 text-center dark:border-rose-800 dark:bg-rose-950/50">
              <ShieldAlert className="mx-auto mb-3 h-10 w-10 text-rose-600" />
              <h1 className="text-lg font-bold text-rose-800 dark:text-rose-200">
                Verification Failed
              </h1>
              <p className="mt-1 text-sm text-rose-700 dark:text-rose-300">{error}</p>
            </div>
          )}

          {data && (
            <div className="space-y-6">
              <motion.div
                initial={{ scale: 0.94, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ type: "spring", stiffness: 260, damping: 20 }}
                className={`rounded-2xl border p-6 shadow-sm ${
                  data.is_valid
                    ? "border-emerald-300 bg-emerald-50/90 dark:border-emerald-800 dark:bg-emerald-950/60"
                    : "border-rose-300 bg-rose-50/90 dark:border-rose-800 dark:bg-rose-950/60"
                }`}
              >
                <div className="flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-center">
                  <div className="flex items-center gap-4">
                    <motion.div
                      initial={{ rotate: -15, scale: 0.8 }}
                      animate={{ rotate: 0, scale: 1 }}
                      transition={{ duration: 0.45 }}
                      className={`flex h-14 w-14 items-center justify-center rounded-2xl ${
                        data.is_valid
                          ? "bg-emerald-600 text-white"
                          : "bg-rose-600 text-white"
                      }`}
                    >
                      {data.is_valid ? (
                        <ShieldCheck className="h-8 w-8" />
                      ) : (
                        <ShieldAlert className="h-8 w-8" />
                      )}
                    </motion.div>
                    <div>
                      <span className="text-xs font-semibold uppercase tracking-wider opacity-75">
                        Cryptographic Integrity Status
                      </span>
                      <h1
                        className={`text-2xl font-bold ${
                          data.is_valid
                            ? "text-emerald-800 dark:text-emerald-200"
                            : "text-rose-800 dark:text-rose-200"
                        }`}
                      >
                        {data.verification_status}
                      </h1>
                    </div>
                  </div>
                  <div className="flex gap-6">
                    <div>
                      <p className="text-xs text-slate-500 dark:text-slate-400">SGPA</p>
                      <AnimatedCounter
                        value={Number(data.sgpa)}
                        className="text-2xl font-bold"
                      />
                    </div>
                    <div>
                      <p className="text-xs text-slate-500 dark:text-slate-400">CGPA</p>
                      <AnimatedCounter
                        value={Number(data.cgpa)}
                        className="text-2xl font-bold"
                      />
                    </div>
                  </div>
                </div>
              </motion.div>

              <div className="glass-card grid gap-4 p-6 sm:grid-cols-2">
                <div>
                  <p className="text-xs text-slate-500">Student</p>
                  <p className="text-base font-semibold">{data.student_name}</p>
                  <p className="text-xs text-slate-500">{data.enrollment_no}</p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">Program &amp; Session</p>
                  <p className="text-base font-semibold">{data.course_name}</p>
                  <p className="text-xs text-slate-500">
                    {data.department_name} &bull; Semester {data.semester_number} ({data.academic_year})
                  </p>
                </div>
              </div>

              <div className="glass-card space-y-3 p-6 text-xs">
                <h2 className="text-sm font-semibold">On-Chain Proof Metadata</h2>
                <div className="flex items-start gap-2">
                  <Hash className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" />
                  <div className="min-w-0 flex-1">
                    <p className="text-slate-500">Recomputed SHA-256 Digest</p>
                    <p className="break-all font-mono">{data.recomputed_hash_sha256}</p>
                  </div>
                </div>
                <div className="flex items-start gap-2">
                  <Hash className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                  <div className="min-w-0 flex-1">
                    <p className="text-slate-500">On-Chain Stored SHA-256 Digest</p>
                    <p className="break-all font-mono">{data.on_chain_hash_sha256}</p>
                  </div>
                </div>
                <div className="grid gap-3 pt-2 sm:grid-cols-3">
                  <div className="flex items-center gap-2">
                    <Blocks className="h-4 w-4 text-slate-400" />
                    <div>
                      <p className="text-slate-500">Block Number</p>
                      <p className="font-mono font-semibold">{data.block_number ?? "N/A"}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Clock className="h-4 w-4 text-slate-400" />
                    <div>
                      <p className="text-slate-500">On-Chain Timestamp (IST)</p>
                      <p className="font-mono font-semibold">
                        {data.on_chain_timestamp
                          ? formatIST(data.on_chain_timestamp * 1000)
                          : "N/A"}
                      </p>
                    </div>
                  </div>
                  <div className="min-w-0">
                    <p className="text-slate-500">Transaction Hash</p>
                    <p className="truncate font-mono font-semibold">
                      {data.blockchain_tx_hash ?? "N/A"}
                    </p>
                  </div>
                </div>
              </div>

              <div className="glass-card overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase text-slate-500 dark:border-slate-800 dark:bg-slate-900">
                      <tr>
                        <th className="px-4 py-3">Code</th>
                        <th className="px-4 py-3">Subject</th>
                        <th className="px-4 py-3">Credits</th>
                        <th className="px-4 py-3">Internal</th>
                        <th className="px-4 py-3">External</th>
                        <th className="px-4 py-3">Total</th>
                        <th className="px-4 py-3">Grade</th>
                        <th className="px-4 py-3">GP</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                      {data.subjects.map((sub) => (
                        <tr key={sub.subject_code}>
                          <td className="px-4 py-3 font-mono font-medium">{sub.subject_code}</td>
                          <td className="px-4 py-3">{sub.subject_name}</td>
                          <td className="px-4 py-3">{sub.credits}</td>
                          <td className="px-4 py-3">{sub.internal_marks}</td>
                          <td className="px-4 py-3">{sub.external_marks}</td>
                          <td className="px-4 py-3 font-semibold">
                            {sub.total} / {sub.max_total}
                          </td>
                          <td className="px-4 py-3 font-semibold text-brand-600 dark:text-brand-400">
                            {sub.grade}
                          </td>
                          <td className="px-4 py-3">{sub.grade_point}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </main>
      </PageTransition>
    </div>
  );
}
