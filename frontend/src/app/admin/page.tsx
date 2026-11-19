"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  Rocket,
  Users,
  BookOpen,
  ScrollText,
  Upload,
  CheckCircle2,
  ExternalLink,
  RefreshCw,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { PageTransition, ToastBanner } from "@/components/MotionPrimitives";
import { useAuth } from "@/lib/auth-context";
import { apiRequest, ApiError } from "@/lib/api";
import { formatIST } from "@/lib/date";
import { useResultWebSocket } from "@/hooks/useResultWebSocket";
import type {
  AuditLog,
  BulkCsvImportResponse,
  Course,
  Department,
  LiveWsEvent,
  Semester,
  SemesterPublishResponse,
  Subject,
  User,
  UserRole,
} from "@/types/api";

type TabKey = "publish" | "academics" | "users" | "audit";

export default function AdminDashboardPage() {
  const router = useRouter();
  const { user, accessToken, loading } = useAuth();
  const [tab, setTab] = useState<TabKey>("publish");
  const [toast, setToast] = useState<{ type: "success" | "error" | "live"; message: string } | null>(null);

  const [departments, setDepartments] = useState<Department[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [semesters, setSemesters] = useState<Semester[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [roleFilter, setRoleFilter] = useState<string>("all");
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [publishingId, setPublishingId] = useState<string | null>(null);
  const [lastPublish, setLastPublish] = useState<SemesterPublishResponse | null>(null);
  const [csvResult, setCsvResult] = useState<BulkCsvImportResponse | null>(null);

  // Forms
  const [deptForm, setDeptForm] = useState({ code: "", name: "" });
  const [userForm, setUserForm] = useState({
    email: "",
    full_name: "",
    role: "student" as UserRole,
    password: "",
    enrollment_no: "",
  });

  const showToast = useCallback((type: "success" | "error" | "live", message: string) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 5000);
  }, []);

  const loadAll = useCallback(async () => {
    try {
      const [d, c, s, sub, u, a] = await Promise.all([
        apiRequest<Department[]>("/admin/departments"),
        apiRequest<Course[]>("/admin/courses"),
        apiRequest<Semester[]>("/admin/semesters"),
        apiRequest<Subject[]>("/admin/subjects"),
        apiRequest<User[]>("/auth/users"),
        apiRequest<AuditLog[]>("/admin/audit-logs?limit=100"),
      ]);
      setDepartments(d);
      setCourses(c);
      setSemesters(s);
      setSubjects(sub);
      setUsers(u);
      setAuditLogs(a);
    } catch (err) {
      showToast("error", err instanceof ApiError ? err.message : "Failed to load admin data");
    }
  }, [showToast]);

  const handleWsEvent = useCallback(
    (evt: LiveWsEvent) => {
      if (evt.event === "MARKS_SUBMITTED") {
        showToast(
          "live",
          `Faculty submitted marks for ${String(evt.subject_code)} (${String(evt.submitted_count)} records ready for publish)`
        );
        loadAll();
      }
    },
    [showToast, loadAll]
  );

  const { status: wsStatus } = useResultWebSocket(
    user?.role === "admin" ? accessToken : null,
    handleWsEvent
  );

  useEffect(() => {
    if (!loading && (!user || user.role !== "admin")) {
      router.replace("/");
    } else if (!loading && user?.role === "admin") {
      loadAll();
    }
  }, [loading, user, router, loadAll]);

  const handlePublishSemester = async (semesterId: string) => {
    if (
      !window.confirm(
        "Publish this semester's results on-chain? This action permanently anchors SHA-256 hashes on the blockchain and cannot be undone."
      )
    ) {
      return;
    }
    setPublishingId(semesterId);
    try {
      const res = await apiRequest<SemesterPublishResponse>(
        `/admin/semesters/${semesterId}/publish`,
        { method: "POST" }
      );
      setLastPublish(res);
      showToast(
        "success",
        `Published ${res.published_count} student results on-chain and broadcasted live via WebSocket.`
      );
      await loadAll();
    } catch (err) {
      showToast("error", err instanceof ApiError ? err.message : "Live publish failed");
    } finally {
      setPublishingId(null);
    }
  };

  const handleCreateDept = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiRequest<Department>("/admin/departments", {
        method: "POST",
        body: JSON.stringify(deptForm),
      });
      setDeptForm({ code: "", name: "" });
      showToast("success", "Department created");
      await loadAll();
    } catch (err) {
      showToast("error", err instanceof ApiError ? err.message : "Failed to create department");
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiRequest<User>("/auth/users", {
        method: "POST",
        body: JSON.stringify({
          ...userForm,
          enrollment_no: userForm.role === "student" ? userForm.enrollment_no : null,
        }),
      });
      setUserForm({ email: "", full_name: "", role: "student", password: "", enrollment_no: "" });
      showToast("success", "Account created and audit-logged");
      await loadAll();
    } catch (err) {
      showToast("error", err instanceof ApiError ? err.message : "Failed to create account");
    }
  };

  const handleCsvUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await apiRequest<BulkCsvImportResponse>("/admin/users/bulk-csv", {
        method: "POST",
        body: formData,
      });
      setCsvResult(res);
      showToast("success", `Bulk CSV imported ${res.created_count} accounts`);
      await loadAll();
    } catch (err) {
      showToast("error", err instanceof ApiError ? err.message : "CSV import failed");
    }
    e.target.value = "";
  };

  const filteredUsers =
    roleFilter === "all" ? users : users.filter((u) => u.role === roleFilter);

  if (loading || !user || user.role !== "admin") return null;

  return (
    <div className="min-h-screen">
      <Navbar wsStatus={wsStatus} />
      <ToastBanner toast={toast} onClose={() => setToast(null)} />

      <PageTransition>
        <main className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Controller of Examinations</h1>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Manage academics, import accounts, publish results on-chain, and inspect audit logs.
              </p>
            </div>
            <button
              onClick={loadAll}
              className="inline-flex items-center gap-1.5 self-start rounded-xl border border-slate-200 px-3.5 py-2 text-xs font-medium hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Refresh
            </button>
          </div>

          {/* Navigation Tabs */}
          <div className="flex flex-wrap gap-2">
            {(
              [
                { key: "publish", label: "Live Publish", icon: Rocket },
                { key: "academics", label: "Academics", icon: BookOpen },
                { key: "users", label: "Users & CSV", icon: Users },
                { key: "audit", label: "Audit Logs", icon: ScrollText },
              ] as const
            ).map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setTab(key)}
                className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition ${
                  tab === key
                    ? "bg-brand-600 text-white shadow-sm"
                    : "glass-card text-slate-600 hover:text-slate-900 dark:text-slate-300"
                }`}
              >
                <Icon className="h-4 w-4" />
                {label}
              </button>
            ))}
          </div>

          {/* TAB 1: LIVE PUBLISH */}
          {tab === "publish" && (
            <div className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2">
                {semesters.map((sem) => {
                  const course = courses.find((c) => c.id === sem.course_id);
                  const semSubjects = subjects.filter((s) => s.semester_id === sem.id);
                  return (
                    <div key={sem.id} className="glass-card flex flex-col justify-between p-6">
                      <div>
                        <span className="rounded-full bg-brand-50 px-2.5 py-1 text-xs font-semibold text-brand-700 dark:bg-brand-950 dark:text-brand-300">
                          {sem.academic_year}
                        </span>
                        <h2 className="mt-3 text-lg font-bold">
                          {course?.name ?? "Course"} — Semester {sem.number}
                        </h2>
                        <p className="mt-1 text-xs text-slate-500">
                          {semSubjects.length} subjects configured
                        </p>
                      </div>
                      <div className="mt-5">
                        <motion.button
                          whileTap={{ scale: 0.97 }}
                          disabled={publishingId === sem.id}
                          onClick={() => handlePublishSemester(sem.id)}
                          className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-emerald-700 disabled:opacity-60"
                        >
                          <Rocket className="h-4 w-4" />
                          {publishingId === sem.id
                            ? "Anchoring On-Chain & Broadcasting..."
                            : "One-Click Live Publish"}
                        </motion.button>
                      </div>
                    </div>
                  );
                })}
              </div>

              {lastPublish && (
                <div className="glass-card border-emerald-300 p-6 dark:border-emerald-800">
                  <div className="mb-4 flex items-center gap-2 text-emerald-700 dark:text-emerald-300">
                    <CheckCircle2 className="h-5 w-5" />
                    <h3 className="text-base font-bold">
                      Published {lastPublish.published_count} Results On-Chain
                    </h3>
                  </div>
                  <div className="space-y-2 text-xs">
                    {lastPublish.results.map((r) => (
                      <div
                        key={r.id}
                        className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-slate-50 px-3.5 py-2.5 dark:bg-slate-800/70"
                      >
                        <div>
                          <span className="font-semibold">SGPA {r.sgpa}</span> &bull;{" "}
                          <span className="font-mono text-slate-500">
                            Block #{r.block_number ?? "-"} &bull; Tx {r.blockchain_tx_hash?.slice(0, 14)}...
                          </span>
                        </div>
                        <Link
                          href={`/verify/${r.id}`}
                          className="inline-flex items-center gap-1 font-semibold text-brand-600 hover:underline dark:text-brand-400"
                        >
                          Verify On-Chain <ExternalLink className="h-3.5 w-3.5" />
                        </Link>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 2: ACADEMICS */}
          {tab === "academics" && (
            <div className="grid gap-6 lg:grid-cols-2">
              <form onSubmit={handleCreateDept} className="glass-card space-y-4 p-6">
                <h2 className="text-base font-semibold">Add Department</h2>
                <div className="grid gap-3 sm:grid-cols-2">
                  <input
                    required
                    placeholder="Code (e.g. IT)"
                    value={deptForm.code}
                    onChange={(e) => setDeptForm({ ...deptForm, code: e.target.value })}
                    className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
                  />
                  <input
                    required
                    placeholder="Department Name"
                    value={deptForm.name}
                    onChange={(e) => setDeptForm({ ...deptForm, name: e.target.value })}
                    className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
                  />
                </div>
                <button
                  type="submit"
                  className="rounded-xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
                >
                  Create Department
                </button>
                <div className="pt-2 text-xs text-slate-500">
                  Existing: {departments.map((d) => `${d.code} (${d.name})`).join(", ")}
                </div>
              </form>

              <div className="glass-card p-6">
                <h2 className="mb-3 text-base font-semibold">Configured Subjects ({subjects.length})</h2>
                <div className="space-y-2 text-sm">
                  {subjects.map((sub) => (
                    <div
                      key={sub.id}
                      className="flex items-center justify-between rounded-xl border border-slate-200/70 px-3.5 py-2 dark:border-slate-800"
                    >
                      <div>
                        <span className="font-mono text-xs font-semibold text-brand-600">
                          {sub.code}
                        </span>{" "}
                        {sub.name}
                      </div>
                      <span className="text-xs text-slate-500">
                        {sub.credits} cr &bull; {sub.max_internal}/{sub.max_external}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: USERS & BULK CSV */}
          {tab === "users" && (
            <div className="space-y-6">
              <div className="grid gap-6 lg:grid-cols-2">
                <form onSubmit={handleCreateUser} className="glass-card space-y-3 p-6">
                  <h2 className="text-base font-semibold">Create Account</h2>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <input
                      required
                      type="email"
                      placeholder="Email"
                      value={userForm.email}
                      onChange={(e) => setUserForm({ ...userForm, email: e.target.value })}
                      className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
                    />
                    <input
                      required
                      placeholder="Full Name"
                      value={userForm.full_name}
                      onChange={(e) => setUserForm({ ...userForm, full_name: e.target.value })}
                      className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
                    />
                    <select
                      value={userForm.role}
                      onChange={(e) =>
                        setUserForm({ ...userForm, role: e.target.value as UserRole })
                      }
                      className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
                    >
                      <option value="student">Student</option>
                      <option value="faculty">Faculty</option>
                      <option value="admin">Admin</option>
                    </select>
                    <input
                      required
                      type="password"
                      minLength={8}
                      placeholder="Initial Password (8+ chars)"
                      value={userForm.password}
                      onChange={(e) => setUserForm({ ...userForm, password: e.target.value })}
                      className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
                    />
                  </div>
                  {userForm.role === "student" && (
                    <input
                      required
                      placeholder="Enrollment Number (e.g. ENR2026CS010)"
                      value={userForm.enrollment_no}
                      onChange={(e) =>
                        setUserForm({ ...userForm, enrollment_no: e.target.value })
                      }
                      className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
                    />
                  )}
                  <button
                    type="submit"
                    className="rounded-xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
                  >
                    Create User
                  </button>
                </form>

                <div className="glass-card flex flex-col justify-between p-6">
                  <div>
                    <h2 className="text-base font-semibold">Bulk CSV Import</h2>
                    <p className="mt-1 text-xs text-slate-500">
                      Required headers: <code>email,full_name,role,password,enrollment_no</code>
                    </p>
                    <label className="mt-4 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 p-6 text-center transition hover:border-brand-500 dark:border-slate-700">
                      <Upload className="mb-2 h-6 w-6 text-brand-600" />
                      <span className="text-sm font-medium">Choose CSV file to import</span>
                      <input
                        type="file"
                        accept=".csv,text/csv"
                        onChange={handleCsvUpload}
                        className="hidden"
                      />
                    </label>
                  </div>
                  {csvResult && (
                    <div className="mt-4 rounded-xl bg-slate-50 p-3 text-xs dark:bg-slate-800">
                      <p className="font-semibold text-emerald-700 dark:text-emerald-300">
                        Created: {csvResult.created_count}
                      </p>
                      {csvResult.errors.length > 0 && (
                        <ul className="mt-1 list-disc pl-4 text-rose-600">
                          {csvResult.errors.map((err) => (
                            <li key={err.row}>
                              Row {err.row}: {err.error}
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </div>
              </div>

              <div className="glass-card overflow-hidden">
                <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3 dark:border-slate-800">
                  <h3 className="text-sm font-semibold">Accounts ({filteredUsers.length})</h3>
                  <select
                    value={roleFilter}
                    onChange={(e) => setRoleFilter(e.target.value)}
                    className="rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs dark:border-slate-700 dark:bg-slate-900"
                  >
                    <option value="all">All Roles</option>
                    <option value="admin">Admin</option>
                    <option value="faculty">Faculty</option>
                    <option value="student">Student</option>
                  </select>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-900">
                      <tr>
                        <th className="px-4 py-2.5">Name</th>
                        <th className="px-4 py-2.5">Email</th>
                        <th className="px-4 py-2.5">Role</th>
                        <th className="px-4 py-2.5">Enrollment</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                      {filteredUsers.map((u) => (
                        <tr key={u.id}>
                          <td className="px-4 py-2.5 font-medium">{u.full_name}</td>
                          <td className="px-4 py-2.5 text-slate-500">{u.email}</td>
                          <td className="px-4 py-2.5 uppercase">{u.role}</td>
                          <td className="px-4 py-2.5 font-mono text-xs">{u.enrollment_no ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: AUDIT LOGS */}
          {tab === "audit" && (
            <div className="glass-card overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-slate-200 bg-slate-50 uppercase text-slate-500 dark:border-slate-800 dark:bg-slate-900">
                    <tr>
                      <th className="px-4 py-3">Timestamp</th>
                      <th className="px-4 py-3">Action</th>
                      <th className="px-4 py-3">Entity</th>
                      <th className="px-4 py-3">Details</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                    {auditLogs.map((log) => (
                      <tr key={log.id}>
                        <td className="whitespace-nowrap px-4 py-2.5 font-mono text-slate-500">
                          {formatIST(log.timestamp)}
                        </td>
                        <td className="px-4 py-2.5 font-semibold text-brand-600 dark:text-brand-400">
                          {log.action}
                        </td>
                        <td className="px-4 py-2.5">
                          {log.entity_type} ({log.entity_id.slice(0, 8)})
                        </td>
                        <td className="max-w-md truncate px-4 py-2.5 font-mono text-slate-500">
                          {JSON.stringify(log.new_value_json)}
                        </td>
                      </tr>
                    ))}
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
