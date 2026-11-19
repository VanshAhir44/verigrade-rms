"use client";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  BarChart,
  Bar,
} from "recharts";
import type { StudentSemesterResult } from "@/types/api";

export function PerformanceCharts({ semesters }: { semesters: StudentSemesterResult[] }) {
  const published = semesters.filter((s) => s.result_status === "published" && s.sgpa);
  if (published.length === 0) return null;

  const trendData = published.map((s) => ({
    label: `Sem ${s.semester_number}`,
    SGPA: Number(s.sgpa),
    CGPA: Number(s.cgpa ?? s.sgpa),
  }));

  const latest = published[published.length - 1];
  const subjectData = latest.subjects.map((sub) => ({
    code: sub.subject_code,
    Internal: Number(sub.internal_marks),
    External: Number(sub.external_marks),
    Total: Number(sub.total),
  }));

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="glass-card p-5">
        <h3 className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-200">
          SGPA &amp; CGPA Trajectory
        </h3>
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#94a3b8" opacity={0.2} />
              <XAxis dataKey="label" tick={{ fontSize: 12 }} />
              <YAxis domain={[0, 10]} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="SGPA"
                stroke="#4f46e5"
                strokeWidth={2.5}
                dot={{ r: 4 }}
              />
              <Line
                type="monotone"
                dataKey="CGPA"
                stroke="#10b981"
                strokeWidth={2.5}
                dot={{ r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="glass-card p-5">
        <h3 className="mb-4 text-sm font-semibold text-slate-700 dark:text-slate-200">
          Semester {latest.semester_number} Subject Breakdown (Internal vs External)
        </h3>
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={subjectData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#94a3b8" opacity={0.2} />
              <XAxis dataKey="code" tick={{ fontSize: 12 }} />
              <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="Internal" stackId="marks" fill="#6366f1" radius={[0, 0, 4, 4]} />
              <Bar dataKey="External" stackId="marks" fill="#0ea5e9" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
