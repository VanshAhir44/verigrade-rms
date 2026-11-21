"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Save, Send, Lock, AlertCircle } from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { PageTransition, ToastBanner } from "@/components/MotionPrimitives";
import { LoadingOverlay } from "@/components/LoadingOverlay";
import { useAuth } from "@/lib/auth-context";
import { apiRequest, ApiError } from "@/lib/api";
import { useResultWebSocket } from "@/hooks/useResultWebSocket";
import type { FacultySubjectRoster } from "@/types/api";

interface DraftScore {
  internal: string;
  external: string;
}

function buildDraftMap(roster: FacultySubjectRoster): Record<string, DraftScore> {
  const map: Record<string, DraftScore> = {};
  roster.students.forEach((st) => {
    map[st.student_id] = {
      internal: st.internal_marks ?? "",
      external: st.external_marks ?? "",
    };
  });
  return map;
}

export default function FacultyDashboardPage() {
  const router = useRouter();
  const { user, accessToken, loading } = useAuth();
  const [rosters, setRosters] = useState<FacultySubjectRoster[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const selectedIdRef = useRef<string>("");
  const [drafts, setDrafts] = useState<Record<string, DraftScore>>({});
  const [isDirty, setIsDirty] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<{ type: "success" | "error" | "live"; message: string } | null>(null);

  const { status: wsStatus } = useResultWebSocket(
    user?.role === "faculty" ? accessToken : null
  );

  const showToast = useCallback((type: "success" | "error" | "live", message: string) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 5000);
  }, []);

  // P2-16 fix: loadRosters no longer depends on selectedId (eliminates double fetch on mount)
  const loadRosters = useCallback(async () => {
    try {
      const data = await apiRequest<FacultySubjectRoster[]>("/faculty/subjects");
      setRosters(data);
      if (data.length > 0) {
        const activeId = selectedIdRef.current || data[0].subject.id;
        selectedIdRef.current = activeId;
        setSelectedId(activeId);
        const active = data.find((r) => r.subject.id === activeId) ?? data[0];
        setDrafts(buildDraftMap(active));
        setIsDirty(false);
      }
    } catch (err) {
      showToast("error", err instanceof ApiError ? err.message : "Failed to load subjects");
    } finally {
      setInitialLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    if (!loading && (!user || user.role !== "faculty")) {
      router.replace("/");
    } else if (!loading && user?.role === "faculty") {
      loadRosters();
    }
  }, [loading, user, router, loadRosters]);

  const activeRoster = rosters.find((r) => r.subject.id === selectedId);
  const maxInt = activeRoster ? Number(activeRoster.subject.max_internal) : 30;
  const maxExt = activeRoster ? Number(activeRoster.subject.max_external) : 70;
  const isLocked = activeRoster
    ? activeRoster.students.some((s) => s.status === "under_review" || s.status === "published")
    : false;

  const selectSubject = (id: string) => {
    if (id === selectedId) return;
    if (isDirty && !window.confirm("You have unsaved marks for this subject. Discard unsaved changes?")) {
      return;
    }
    selectedIdRef.current = id;
    setSelectedId(id);
    const found = rosters.find((r) => r.subject.id === id);
    if (found) {
      setDrafts(buildDraftMap(found));
      setIsDirty(false);
    }
  };

  const hasValidationError = activeRoster
    ? activeRoster.students.some((st) => {
        const d = drafts[st.student_id];
        if (!d || d.internal === "" || d.external === "") return false;
        const i = Number(d.internal);
        const e = Number(d.external);
        return Number.isNaN(i) || Number.isNaN(e) || i < 0 || e < 0 || i > maxInt || e > maxExt;
      })
    : false;

  const persistCurrentDrafts = async (): Promise<boolean> => {
    if (!activeRoster || hasValidationError) return false;
    const entries = activeRoster.students
      .filter((st) => {
        const d = drafts[st.student_id];
        return d && d.internal !== "" && d.external !== "";
      })
      .map((st) => ({
        student_id: st.student_id,
        internal_marks: Number(drafts[st.student_id].internal),
        external_marks: Number(drafts[st.student_id].external),
      }));

    if (entries.length === 0) {
      showToast("error", "Enter marks for at least one student before saving");
      return false;
    }

    await apiRequest(`/faculty/subjects/${activeRoster.subject.id}/marks`, {
      method: "PUT",
      body: JSON.stringify({ entries }),
    });
    setIsDirty(false);
    return true;
  };

  const handleSaveMarks = async () => {
    setSaving(true);
    try {
      const ok = await persistCurrentDrafts();
      if (ok) {
        showToast("success", "Saved draft mark entries");
        await loadRosters();
      }
    } catch (err) {
      showToast("error", err instanceof ApiError ? err.message : "Failed to save marks");
    } finally {
      setSaving(false);
    }
  };

  // P1-9 fix: auto-save unsaved edits BEFORE locking so faculty never locks stale values
  const handleSubmitMarks = async () => {
    if (!activeRoster || hasValidationError) return;
    setSubmitting(true);
    try {
      if (isDirty) {
        const saved = await persistCurrentDrafts();
        if (!saved) return;
      }
      await apiRequest(`/faculty/subjects/${activeRoster.subject.id}/submit`, {
        method: "POST",
      });
      showToast("success", "Marks saved, submitted, and locked for Controller of Examinations review");
      await loadRosters();
    } catch (err) {
      showToast("error", err instanceof ApiError ? err.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen">
        <LoadingOverlay
          open
          variant="auth"
          title="Verifying Faculty Session..."
          subtitle="Opening your marks entry workbench"
        />
      </div>
    );
  }

  if (!user || user.role !== "faculty") return null;

  return (
    <div className="min-h-screen">
      <LoadingOverlay
        open={initialLoading || saving || submitting}
        variant={submitting ? "auth" : "default"}
        title={
          submitting
            ? "Submitting & Locking Marks..."
            : saving
            ? "Saving Draft Marks..."
            : "Loading Faculty Workbench..."
        }
        subtitle={
          submitting
            ? "Finalizing scores and notifying the Controller of Examinations"
            : saving
            ? "Validating bounds and saving your draft mark entries"
            : "Fetching assigned subjects and student rosters"
        }
      />
      <Navbar wsStatus={wsStatus} />
      <ToastBanner toast={toast} onClose={() => setToast(null)} />

      <PageTransition>
        <main className="mx-auto max-w-6xl space-y-6 px-4 py-8 sm:px-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Faculty Marks Workbench</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Enter internal &amp; external marks with real-time bounds validation, then submit to lock for Admin approval.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            {rosters.map((r) => (
              <button
                key={r.subject.id}
                onClick={() => selectSubject(r.subject.id)}
                className={`rounded-xl px-4 py-2 text-left text-sm transition ${
                  r.subject.id === selectedId
                    ? "bg-brand-600 text-white shadow-sm"
                    : "glass-card text-slate-700 dark:text-slate-200"
                }`}
              >
                <span className="font-mono text-xs font-bold">{r.subject.code}</span>{" "}
                <span className="font-medium">{r.subject.name}</span>
              </button>
            ))}
          </div>

          {activeRoster && (
            <div className="glass-card overflow-hidden">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-6 py-4 dark:border-slate-800">
                <div>
                  <h2 className="text-base font-bold">
                    {activeRoster.subject.code} — {activeRoster.subject.name}
                  </h2>
                  <p className="text-xs text-slate-500">
                    Semester {activeRoster.semester_number} ({activeRoster.academic_year}) &bull; Max
                    Internal: {maxInt} &bull; Max External: {maxExt}
                    {isDirty && !isLocked && (
                      <span className="ml-2 font-semibold text-amber-600">• Unsaved changes</span>
                    )}
                  </p>
                </div>

                {isLocked ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                    <Lock className="h-3.5 w-3.5" />
                    Locked for Review / Published
                  </span>
                ) : (
                  <div className="flex gap-2">
                    <motion.button
                      whileTap={{ scale: 0.97 }}
                      disabled={saving || submitting || hasValidationError}
                      onClick={handleSaveMarks}
                      className="inline-flex items-center gap-1.5 rounded-xl bg-slate-900 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-800 disabled:opacity-50 dark:bg-white dark:text-slate-900"
                    >
                      <Save className="h-3.5 w-3.5" />
                      {saving ? "Saving..." : "Save Draft"}
                    </motion.button>
                    <motion.button
                      whileTap={{ scale: 0.97 }}
                      disabled={submitting || saving || hasValidationError}
                      onClick={handleSubmitMarks}
                      className="inline-flex items-center gap-1.5 rounded-xl bg-brand-600 px-4 py-2 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
                    >
                      <Send className="h-3.5 w-3.5" />
                      {submitting ? "Submitting..." : "Submit & Lock"}
                    </motion.button>
                  </div>
                )}
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-900">
                    <tr>
                      <th className="px-5 py-3">Enrollment</th>
                      <th className="px-5 py-3">Student</th>
                      <th className="px-5 py-3">Internal (/{maxInt})</th>
                      <th className="px-5 py-3">External (/{maxExt})</th>
                      <th className="px-5 py-3">Total</th>
                      <th className="px-5 py-3">Grade</th>
                      <th className="px-5 py-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                    {activeRoster.students.map((st) => {
                      const d = drafts[st.student_id] ?? { internal: "", external: "" };
                      const intVal = Number(d.internal);
                      const extVal = Number(d.external);
                      const intBad = d.internal !== "" && (intVal < 0 || intVal > maxInt);
                      const extBad = d.external !== "" && (extVal < 0 || extVal > maxExt);
                      const previewTotal =
                        d.internal !== "" && d.external !== "" && !intBad && !extBad
                          ? (intVal + extVal).toFixed(1)
                          : "—";

                      return (
                        <tr key={st.student_id}>
                          <td className="px-5 py-3 font-mono text-xs">{st.enrollment_no}</td>
                          <td className="px-5 py-3 font-medium">{st.student_name}</td>
                          <td className="px-5 py-3">
                            <input
                              type="number"
                              step="0.5"
                              disabled={isLocked}
                              value={d.internal}
                              onChange={(e) => {
                                setIsDirty(true);
                                setDrafts((prev) => ({
                                  ...prev,
                                  [st.student_id]: { ...d, internal: e.target.value },
                                }));
                              }}
                              className={`w-24 rounded-lg border px-2.5 py-1.5 text-sm outline-none dark:bg-slate-900 ${
                                intBad
                                  ? "border-rose-500 bg-rose-50 text-rose-700"
                                  : "border-slate-200 dark:border-slate-700"
                              }`}
                            />
                            {intBad && (
                              <p className="mt-1 flex items-center gap-1 text-[11px] text-rose-600">
                                <AlertCircle className="h-3 w-3" /> Max {maxInt}
                              </p>
                            )}
                          </td>
                          <td className="px-5 py-3">
                            <input
                              type="number"
                              step="0.5"
                              disabled={isLocked}
                              value={d.external}
                              onChange={(e) => {
                                setIsDirty(true);
                                setDrafts((prev) => ({
                                  ...prev,
                                  [st.student_id]: { ...d, external: e.target.value },
                                }));
                              }}
                              className={`w-24 rounded-lg border px-2.5 py-1.5 text-sm outline-none dark:bg-slate-900 ${
                                extBad
                                  ? "border-rose-500 bg-rose-50 text-rose-700"
                                  : "border-slate-200 dark:border-slate-700"
                              }`}
                            />
                            {extBad && (
                              <p className="mt-1 flex items-center gap-1 text-[11px] text-rose-600">
                                <AlertCircle className="h-3 w-3" /> Max {maxExt}
                              </p>
                            )}
                          </td>
                          <td className="px-5 py-3 font-semibold">{previewTotal}</td>
                          <td className="px-5 py-3 font-semibold text-brand-600">
                            {st.grade ?? "—"}
                          </td>
                          <td className="px-5 py-3 text-xs uppercase text-slate-500">
                            {st.status ?? "draft"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </main>
      </PageTransition>
    </div>
  );
}
