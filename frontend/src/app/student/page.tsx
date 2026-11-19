"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
  Download,
  ShieldCheck,
  Sparkles,
  CheckCircle2,
  Clock,
  FileText,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import {
  FadeInCard,
  PageTransition,
  StaggerGrid,
  ToastBanner,
} from "@/components/MotionPrimitives";
import { AnimatedCounter } from "@/components/AnimatedCounter";
import { PerformanceCharts } from "@/components/PerformanceCharts";
import { useAuth } from "@/lib/auth-context";
import { apiRequest, ApiError, downloadPdfMarksheet } from "@/lib/api";
import { useResultWebSocket } from "@/hooks/useResultWebSocket";
import type { LiveWsEvent, StudentDashboardResponse } from "@/types/api";

export default function StudentDashboardPage() {
  const router = useRouter();
  const { user, accessToken, loading } = useAuth();
  const [dashboard, setDashboard] = useState<StudentDashboardResponse | null>(null);
  const [liveRevealBanner, setLiveRevealBanner] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [toast, setToast] = useState<{ type: "success" | "error" | "live"; message: string } | null>(null);

  const showToast = useCallback((type: "success" | "error" | "live", message: string) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 6000);
  }, []);

  const loadDashboard = useCallback(async () => {
    try {
      const data = await apiRequest<StudentDashboardResponse>("/student/results");
      setDashboard(data);
    } catch (err) {
      showToast("error", err instanceof ApiError ? err.message : "Failed to load results");
    }
  }, [showToast]);

  const handleWsEvent = useCallback(
    (evt: LiveWsEvent) => {
      if (evt.event === "RESULT_PUBLISHED") {
        const msg = `Semester ${String(evt.semester_number)} results just published live! SGPA: ${String(evt.sgpa)}`;
        setLiveRevealBanner(msg);
        showToast("live", msg);
        loadDashboard();
      } else if (evt.event === "STATUS_UPDATED") {
        showToast("live", `Subject ${String(evt.subject_code)} moved to Under Review`);
        loadDashboard();
      }
    },
    [loadDashboard, showToast]
  );

  const { status: wsStatus } = useResultWebSocket(accessToken, handleWsEvent);

  useEffect(() => {
    if (!loading && (!user || user.role !== "student")) {
      router.replace("/");
    } else if (!loading && user?.role === "student") {
      loadDashboard();
    }
  }, [loading, user, router, loadDashboard]);

  const handleDownloadPdf = async (resultId: string, semNum: number) => {
    setDownloadingId(resultId);
    try {
      await downloadPdfMarksheet(
        resultId,
        `marksheet_${dashboard?.enrollment_no ?? "student"}_sem${semNum}.pdf`
      );
      showToast("success", "Official QR-verified PDF marksheet downloaded");
    } catch (err) {
      showToast("error", err instanceof ApiError ? err.message : "PDF download failed");
    } finally {
      setDownloadingId(null);
    }
  };

  if (loading || !user || !dashboard) return null;

  const publishedSemesters = dashboard.semesters.filter((s) => s.result_status === "published");
  const latestSem = publishedSemesters[publishedSemesters.length - 1];

  return (
    <div className="min-h-screen">
      <Navbar wsStatus={wsStatus} />
      <ToastBanner toast={toast} onClose={() => setToast(null)} />

      <PageTransition>
        <main className="mx-auto max-w-6xl space-y-6 px-4 py-8 sm:px-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold tracking-tight">{dashboard.full_name}</h1>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Enrollment: <span className="font-mono font-medium">{dashboard.enrollment_no}</span>
              </p>
            </div>
          </div>

          {/* Celebratory Live Result Reveal Banner */}
          <AnimatePresence>
            {liveRevealBanner && (
              <motion.div
                initial={{ opacity: 0, scale: 0.94, y: -10 }}
                animate={{ opacity: 1, scale: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ type: "spring", stiffness: 260, damping: 20 }}
                className="flex items-center justify-between gap-4 rounded-2xl border border-emerald-300 bg-gradient-to-r from-emerald-50 via-teal-50 to-indigo-50 p-5 shadow-sm dark:border-emerald-800 dark:from-emerald-950/70 dark:to-indigo-950/70"
              >
                <div className="flex items-center gap-3">
                  <Sparkles className="h-6 w-6 text-emerald-600" />
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-300">
                      Live Blockchain Publication Received
                    </p>
                    <p className="text-sm font-bold">{liveRevealBanner}</p>
                  </div>
                </div>
                <button
                  onClick={() => setLiveRevealBanner(null)}
                  className="text-xs font-medium underline opacity-75 hover:opacity-100"
                >
                  Dismiss
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Animated KPI Cards */}
          <StaggerGrid className="grid gap-4 sm:grid-cols-3">
            <FadeInCard className="p-5">
              <p className="text-xs font-medium text-slate-500">Cumulative CGPA</p>
              <div className="mt-2 text-3xl font-bold text-brand-600 dark:text-brand-400">
                {dashboard.latest_cgpa ? (
                  <AnimatedCounter value={Number(dashboard.latest_cgpa)} />
                ) : (
                  "—"
                )}
              </div>
            </FadeInCard>
            <FadeInCard className="p-5">
              <p className="text-xs font-medium text-slate-500">Latest Semester SGPA</p>
              <div className="mt-2 text-3xl font-bold text-emerald-600 dark:text-emerald-400">
                {latestSem?.sgpa ? <AnimatedCounter value={Number(latestSem.sgpa)} /> : "—"}
              </div>
            </FadeInCard>
            <FadeInCard className="p-5">
              <p className="text-xs font-medium text-slate-500">Published Semesters</p>
              <div className="mt-2 text-3xl font-bold">
                <AnimatedCounter value={publishedSemesters.length} decimals={0} />
              </div>
            </FadeInCard>
          </StaggerGrid>

          {/* Real-Time Recharts Analytics */}
          <PerformanceCharts semesters={dashboard.semesters} />

          {/* Semester Cards */}
          <div className="space-y-6">
            {dashboard.semesters.map((sem) => {
              const stepIdx =
                sem.result_status === "published"
                  ? 2
                  : sem.result_status === "under_review"
                  ? 1
                  : 0;

              return (
                <div key={sem.semester_id} className="glass-card overflow-hidden">
                  <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 px-6 py-4 dark:border-slate-800">
                    <div>
                      <h2 className="text-base font-bold">
                        {sem.course_name} — Semester {sem.semester_number}
                      </h2>
                      <p className="text-xs text-slate-500">Academic Year {sem.academic_year}</p>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      {(["Draft", "Under Review", "Published"] as const).map((label, idx) => (
                        <span
                          key={label}
                          className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold ${
                            idx <= stepIdx
                              ? idx === 2
                                ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                                : "bg-brand-100 text-brand-800 dark:bg-brand-950 dark:text-brand-300"
                              : "bg-slate-100 text-slate-400 dark:bg-slate-800"
                          }`}
                        >
                          {idx === 2 ? (
                            <CheckCircle2 className="h-3.5 w-3.5" />
                          ) : idx === 1 ? (
                            <Clock className="h-3.5 w-3.5" />
                          ) : (
                            <FileText className="h-3.5 w-3.5" />
                          )}
                          {label}
                        </span>
                      ))}
                    </div>
                  </div>

                  {sem.result_status === "published" && sem.result_id ? (
                    <div className="space-y-4 p-6">
                      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 px-4 py-3 text-xs dark:bg-slate-800/60">
                        <div className="space-y-0.5">
                          <p className="font-semibold">
                            SGPA: {sem.sgpa} &bull; CGPA: {sem.cgpa} &bull; Status:{" "}
                            <span
                              className={
                                sem.overall_status === "PASS"
                                  ? "text-emerald-600"
                                  : "text-rose-600"
                              }
                            >
                              {sem.overall_status}
                            </span>
                          </p>
                          <p className="font-mono text-[11px] text-slate-500">
                            Block #{sem.block_number ?? "-"} &bull; SHA-256{" "}
                            {sem.result_hash_sha256?.slice(0, 18)}...
                          </p>
                        </div>

                        <div className="flex flex-wrap gap-2">
                          <Link
                            href={`/verify/${sem.result_id}`}
                            className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-300 bg-emerald-50 px-3.5 py-2 text-xs font-semibold text-emerald-800 hover:bg-emerald-100 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                          >
                            <ShieldCheck className="h-4 w-4" />
                            Verify On-Chain
                          </Link>
                          <motion.button
                            whileTap={{ scale: 0.97 }}
                            disabled={downloadingId === sem.result_id}
                            onClick={() =>
                              handleDownloadPdf(sem.result_id!, sem.semester_number)
                            }
                            className="inline-flex items-center gap-1.5 rounded-xl bg-brand-600 px-3.5 py-2 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                          >
                            <Download className="h-4 w-4" />
                            {downloadingId === sem.result_id
                              ? "Generating PDF..."
                              : "Download QR PDF"}
                          </motion.button>
                        </div>
                      </div>

                      <div className="overflow-x-auto">
                        <table className="w-full text-left text-sm">
                          <thead className="border-b border-slate-200 text-xs uppercase text-slate-500 dark:border-slate-800">
                            <tr>
                              <th className="py-2 pr-4">Code</th>
                              <th className="py-2 pr-4">Subject</th>
                              <th className="py-2 pr-4">Credits</th>
                              <th className="py-2 pr-4">Internal</th>
                              <th className="py-2 pr-4">External</th>
                              <th className="py-2 pr-4">Total</th>
                              <th className="py-2 pr-4">Grade</th>
                              <th className="py-2">GP</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                            {sem.subjects.map((sub) => (
                              <tr key={sub.subject_code}>
                                <td className="py-2.5 pr-4 font-mono text-xs font-semibold">
                                  {sub.subject_code}
                                </td>
                                <td className="py-2.5 pr-4">{sub.subject_name}</td>
                                <td className="py-2.5 pr-4">{sub.credits}</td>
                                <td className="py-2.5 pr-4">{sub.internal_marks}</td>
                                <td className="py-2.5 pr-4">{sub.external_marks}</td>
                                <td className="py-2.5 pr-4 font-semibold">
                                  {sub.total} / {sub.max_total}
                                </td>
                                <td className="py-2.5 pr-4 font-bold text-brand-600 dark:text-brand-400">
                                  {sub.grade}
                                </td>
                                <td className="py-2.5">{sub.grade_point}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ) : (
                    <div className="px-6 py-8 text-center text-sm text-slate-500">
                      {sem.result_status === "under_review"
                        ? "Marks have been submitted by Faculty and are awaiting Controller of Examinations publication. Keep this tab open to receive your result live."
                        : "Marks entry is currently in progress. Status will update automatically in real time."}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </main>
      </PageTransition>
    </div>
  );
}
