"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertTriangle,
  Download,
  ShieldCheck,
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
import { LoadingOverlay } from "@/components/LoadingOverlay";
import { PerformanceCharts } from "@/components/PerformanceCharts";
import { useAuth } from "@/lib/auth-context";
import { apiRequest, ApiError, downloadPdfMarksheet } from "@/lib/api";
import { useResultWebSocket } from "@/hooks/useResultWebSocket";
import type {
  LiveWsEvent,
  StudentDashboardResponse,
  StudentSemesterResult,
} from "@/types/api";

function formatGpa(raw: string | null | undefined): string | null {
  if (raw === null || raw === undefined || raw === "") return null;
  const num = Number(raw);
  return Number.isFinite(num) ? num.toFixed(2) : null;
}

function deriveAuthoritativeMetrics(semesters: StudentSemesterResult[]) {
  const sortedSemesters = [...semesters].sort((a, b) => {
    const yearCmp = a.academic_year.localeCompare(b.academic_year);
    return yearCmp !== 0 ? yearCmp : a.semester_number - b.semester_number;
  });

  const publishedSemesters = sortedSemesters.filter(
    (s) =>
      s.result_status === "published" &&
      Boolean(s.result_id) &&
      s.sgpa !== null &&
      s.cgpa !== null
  );

  const latestPublished =
    publishedSemesters.length > 0
      ? publishedSemesters[publishedSemesters.length - 1]
      : null;

  return {
    sortedSemesters,
    publishedSemesters,
    publishedCount: publishedSemesters.length,
    latestSgpa: formatGpa(latestPublished?.sgpa),
    cumulativeCgpa: formatGpa(latestPublished?.cgpa),
  };
}

function DashboardSkeleton() {
  return (
    <main
      aria-busy="true"
      aria-label="Loading student results"
      className="mx-auto max-w-6xl space-y-6 px-4 py-8 sm:px-6"
    >
      <div className="space-y-2">
        <div className="h-7 w-48 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
        <div className="h-4 w-40 animate-pulse rounded bg-slate-200/80 dark:bg-slate-800/80" />
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="glass-card space-y-3 p-5">
            <div className="h-3.5 w-28 animate-pulse rounded bg-slate-200 dark:bg-slate-800" />
            <div className="h-9 w-20 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
          </div>
        ))}
      </div>

      <div className="glass-card space-y-4 p-6">
        <div className="flex items-center justify-between">
          <div className="h-5 w-64 animate-pulse rounded bg-slate-200 dark:bg-slate-800" />
          <div className="h-7 w-52 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
        </div>
        <div className="h-40 w-full animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800/60" />
      </div>
    </main>
  );
}

export default function StudentDashboardPage() {
  const router = useRouter();
  const { user, accessToken, loading } = useAuth();
  const [dashboard, setDashboard] = useState<StudentDashboardResponse | null>(null);
  const [isFetching, setIsFetching] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [liveRevealBanner, setLiveRevealBanner] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [toast, setToast] = useState<{
    type: "success" | "error" | "live";
    message: string;
  } | null>(null);

  const requestSeqRef = useRef(0);
  const activeUserIdRef = useRef<string | null>(null);

  const showToast = useCallback((type: "success" | "error" | "live", message: string) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 6000);
  }, []);

  const loadDashboard = useCallback(
    async (expectedUserId?: string) => {
      const targetUserId = expectedUserId ?? activeUserIdRef.current;
      const reqId = ++requestSeqRef.current;
      setIsFetching(true);
      setLoadError(null);
      try {
        const data = await apiRequest<StudentDashboardResponse>("/student/results");
        // Ignore stale in-flight responses if user switched accounts or a newer fetch started
        if (reqId !== requestSeqRef.current) return;
        if (targetUserId && data.student_id !== targetUserId) return;
        setDashboard(data);
      } catch (err) {
        if (reqId !== requestSeqRef.current) return;
        const msg = err instanceof ApiError ? err.message : "Failed to load results";
        setLoadError(msg);
        showToast("error", msg);
      } finally {
        if (reqId === requestSeqRef.current) {
          setIsFetching(false);
        }
      }
    },
    [showToast]
  );

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

  const { status: wsStatus } = useResultWebSocket(
    user?.role === "student" ? accessToken : null,
    handleWsEvent
  );

  // Reset and invalidate any previous student's cached state whenever the authenticated user changes
  useEffect(() => {
    activeUserIdRef.current = user?.id ?? null;
    if (loading) return;

    if (!user || user.role !== "student") {
      requestSeqRef.current += 1;
      setDashboard(null);
      setLoadError(null);
      setLiveRevealBanner(null);
      setIsFetching(false);
      router.replace("/");
      return;
    }

    setDashboard(null);
    setLoadError(null);
    setLiveRevealBanner(null);
    loadDashboard(user.id);
  }, [loading, user?.id, user?.role, router, loadDashboard]);

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

  const hasMatchingDashboard = Boolean(
    user && dashboard && dashboard.student_id === user.id
  );

  const metrics = useMemo(
    () => deriveAuthoritativeMetrics(hasMatchingDashboard && dashboard ? dashboard.semesters : []),
    [hasMatchingDashboard, dashboard]
  );

  if (loading) {
    return (
      <div className="min-h-screen">
        <LoadingOverlay
          open
          variant="auth"
          title="Verifying Student Session..."
          subtitle="Opening your academic results portal"
        />
      </div>
    );
  }

  if (!user || user.role !== "student") return null;

  // Distinct Loading State (never show 0 or placeholder numeric GPA before authoritative data arrives)
  if (!hasMatchingDashboard && !loadError) {
    return (
      <div className="min-h-screen">
        <LoadingOverlay
          open={isFetching}
          variant="default"
          title="Loading Your Results..."
          subtitle="Fetching published transcripts, GPA trends, and on-chain proofs"
        />
        <Navbar wsStatus={wsStatus} />
        <ToastBanner toast={toast} onClose={() => setToast(null)} />
        <DashboardSkeleton />
      </div>
    );
  }

  // Distinct Error State (never conflated with loading or zero-result empty state)
  if (loadError && !hasMatchingDashboard) {
    return (
      <div className="min-h-screen">
        <Navbar wsStatus={wsStatus} />
        <ToastBanner toast={toast} onClose={() => setToast(null)} />
        <main className="mx-auto max-w-2xl px-4 py-16 text-center">
          <div className="glass-card border-rose-500/30 p-8">
            <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-rose-500/10 text-rose-600 dark:text-rose-400">
              <AlertTriangle className="h-6 w-6" />
            </div>
            <h1 className="text-base font-semibold text-slate-900 dark:text-slate-100">
              Unable to load academic results
            </h1>
            <p className="mt-1.5 text-sm text-slate-600 dark:text-slate-400">{loadError}</p>
            <button
              onClick={() => loadDashboard(user.id)}
              className="mt-5 rounded-lg bg-brand-600 px-4 py-2 text-xs font-semibold text-white hover:bg-brand-700"
            >
              Try again
            </button>
          </div>
        </main>
      </div>
    );
  }

  // Authoritative loaded dashboard for the current authenticated student
  const activeDashboard = dashboard!;

  return (
    <div className="min-h-screen">
      <LoadingOverlay
        open={Boolean(downloadingId)}
        variant="pdf"
        title="Generating QR-Verified PDF..."
        subtitle="Building your official marksheet with embedded blockchain verification QR"
      />
      <Navbar wsStatus={wsStatus} />
      <ToastBanner toast={toast} onClose={() => setToast(null)} />

      <PageTransition>
        <main className="mx-auto max-w-6xl space-y-6 px-4 py-8 sm:px-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold tracking-tight">{activeDashboard.full_name}</h1>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Enrollment:{" "}
                <span className="font-mono font-medium">{activeDashboard.enrollment_no}</span>
              </p>
            </div>
          </div>

          {/* Inline Error Banner if a background refresh fails while existing data is visible */}
          {loadError && (
            <div className="flex items-center justify-between gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-xs text-rose-700 dark:text-rose-300">
              <span>Could not refresh latest results: {loadError}</span>
              <button
                onClick={() => loadDashboard(user.id)}
                className="font-semibold underline hover:opacity-80"
              >
                Retry
              </button>
            </div>
          )}

          {/* Live Result Publication Banner */}
          <AnimatePresence>
            {liveRevealBanner && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.2 }}
                className="flex items-center justify-between gap-4 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4"
              >
                <div className="flex items-center gap-3">
                  <CheckCircle2 className="h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                  <div>
                    <p className="text-xs font-medium text-emerald-700 dark:text-emerald-300">
                      New result published on-chain
                    </p>
                    <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                      {liveRevealBanner}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setLiveRevealBanner(null)}
                  className="text-xs font-medium text-slate-600 underline hover:text-slate-900 dark:text-slate-300 dark:hover:text-white"
                >
                  Dismiss
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Authoritative Academic KPI Summary (computed from the exact same published records as transcript cards) */}
          <StaggerGrid className="grid gap-4 sm:grid-cols-3">
            <FadeInCard className="p-5">
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
                Cumulative CGPA
              </p>
              <div className="mt-2 text-3xl font-bold tabular-nums text-brand-600 dark:text-brand-400">
                {metrics.cumulativeCgpa ?? "—"}
              </div>
              {metrics.publishedCount === 0 && (
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  No published results yet
                </p>
              )}
            </FadeInCard>
            <FadeInCard className="p-5">
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
                Latest semester SGPA
              </p>
              <div className="mt-2 text-3xl font-bold tabular-nums text-slate-900 dark:text-slate-50">
                {metrics.latestSgpa ?? "—"}
              </div>
              {metrics.publishedCount === 0 && (
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Awaiting publication
                </p>
              )}
            </FadeInCard>
            <FadeInCard className="p-5">
              <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
                Published semesters
              </p>
              <div className="mt-2 text-3xl font-bold tabular-nums text-slate-900 dark:text-slate-50">
                {metrics.publishedCount}
              </div>
              {metrics.publishedCount === 0 && (
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  No transcripts published
                </p>
              )}
            </FadeInCard>
          </StaggerGrid>

          {/* Real-Time Recharts Analytics */}
          <PerformanceCharts semesters={metrics.sortedSemesters} />

          {/* Clear Empty State when student has no enrolled semesters */}
          {metrics.sortedSemesters.length === 0 ? (
            <div className="glass-card p-10 text-center">
              <FileText className="mx-auto mb-3 h-8 w-8 text-slate-400" />
              <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                No academic results available yet
              </h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                Your semester transcripts will appear here automatically once faculty marks are
                published by the Controller of Examinations.
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {metrics.sortedSemesters.map((sem) => {
                const stepIdx =
                  sem.result_status === "published"
                    ? 2
                    : sem.result_status === "under_review"
                    ? 1
                    : 0;

                const formattedSgpa = formatGpa(sem.sgpa) ?? "—";
                const formattedCgpa = formatGpa(sem.cgpa) ?? "—";

                return (
                  <div key={sem.semester_id} className="glass-card overflow-hidden">
                    <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-200 px-6 py-4 dark:border-slate-800">
                      <div>
                        <h2 className="text-base font-bold">
                          {sem.course_name} — Semester {sem.semester_number}
                        </h2>
                        <p className="text-xs text-slate-500">
                          Academic Year {sem.academic_year}
                        </p>
                      </div>

                      <div
                        aria-label="Result publication status"
                        className="inline-flex flex-wrap items-center gap-1.5 rounded-xl border border-slate-200/80 bg-slate-50/80 p-1.5 dark:border-slate-800 dark:bg-slate-950/60"
                      >
                        {(["Draft", "Under Review", "Published"] as const).map((label, idx) => {
                          const isCompleted = idx < stepIdx;
                          const isCurrent = idx === stepIdx;

                          const pillStyle = isCurrent
                            ? idx === 2
                              ? "border border-emerald-500/30 bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
                              : idx === 1
                              ? "border border-amber-500/30 bg-amber-500/15 text-amber-700 dark:text-amber-300"
                              : "border border-brand-500/30 bg-brand-500/15 text-brand-700 dark:text-brand-300"
                            : isCompleted
                            ? "text-slate-600 dark:text-slate-400"
                            : "text-slate-400 dark:text-slate-600";

                          return (
                            <React.Fragment key={label}>
                              <span
                                className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium transition ${pillStyle}`}
                              >
                                {isCompleted || (isCurrent && idx === 2) ? (
                                  <CheckCircle2
                                    className={`h-3.5 w-3.5 ${
                                      isCurrent
                                        ? "text-emerald-600 dark:text-emerald-400"
                                        : "text-emerald-600/70 dark:text-emerald-500/70"
                                    }`}
                                  />
                                ) : idx === 1 ? (
                                  <Clock className="h-3.5 w-3.5" />
                                ) : (
                                  <FileText className="h-3.5 w-3.5" />
                                )}
                                {label}
                              </span>
                              {idx < 2 && (
                                <span
                                  aria-hidden="true"
                                  className={`h-px w-3.5 ${
                                    idx < stepIdx
                                      ? "bg-emerald-500/40"
                                      : "bg-slate-300 dark:bg-slate-700"
                                  }`}
                                />
                              )}
                            </React.Fragment>
                          );
                        })}
                      </div>
                    </div>

                    {sem.result_status === "published" && sem.result_id ? (
                      <div className="space-y-4 p-6">
                        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-50 px-4 py-3 text-xs dark:bg-slate-800/60">
                          <div className="space-y-0.5 tabular-nums">
                            <p className="font-semibold">
                              SGPA: {formattedSgpa} &bull; CGPA: {formattedCgpa} &bull; Status:{" "}
                              <span
                                className={
                                  sem.overall_status === "PASS"
                                    ? "text-emerald-600 dark:text-emerald-400"
                                    : "text-rose-600 dark:text-rose-400"
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
                          <table className="w-full text-left text-sm tabular-nums">
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
          )}
        </main>
      </PageTransition>
    </div>
  );
}
