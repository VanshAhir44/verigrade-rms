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
import { useTheme } from "@/components/ThemeProvider";
import type { StudentSemesterResult } from "@/types/api";

export function PerformanceCharts({ semesters }: { semesters: StudentSemesterResult[] }) {
  const { theme } = useTheme();
  const isDark = theme === "dark";

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

  const axisColor = isDark ? "#94a3b8" : "#64748b";
  const gridColor = isDark ? "#1e293b" : "#e2e8f0";
  const tooltipStyle = {
    backgroundColor: isDark ? "#0f172a" : "#ffffff",
    borderColor: isDark ? "#334155" : "#e2e8f0",
    borderRadius: "0.5rem",
    fontSize: "12px",
    color: isDark ? "#f1f5f9" : "#0f172a",
  };

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="glass-card p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">
            SGPA and CGPA trend
          </h3>
          <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-brand-600 dark:bg-brand-400" />
              SGPA
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-slate-400 dark:bg-slate-500" />
              CGPA
            </span>
          </div>
        </div>
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trendData}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 12, fill: axisColor }}
                axisLine={{ stroke: gridColor }}
                tickLine={false}
              />
              <YAxis
                domain={[0, 10]}
                tick={{ fontSize: 12, fill: axisColor }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip contentStyle={tooltipStyle} />
              <Line
                type="monotone"
                dataKey="SGPA"
                stroke={isDark ? "#818cf8" : "#4f46e5"}
                strokeWidth={2.25}
                dot={{ r: 4, fill: isDark ? "#818cf8" : "#4f46e5" }}
              />
              <Line
                type="monotone"
                dataKey="CGPA"
                stroke={isDark ? "#64748b" : "#94a3b8"}
                strokeWidth={2}
                strokeDasharray="4 4"
                dot={{ r: 3.5, fill: isDark ? "#64748b" : "#94a3b8" }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="glass-card p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-100">
            Semester {latest.semester_number} marks breakdown
          </h3>
          <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-sm bg-brand-600 dark:bg-brand-400" />
              Internal
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-sm bg-slate-300 dark:bg-slate-600" />
              External
            </span>
          </div>
        </div>
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={subjectData} barSize={36}>
              <CartesianGrid strokeDasharray="3 3" stroke={gridColor} vertical={false} />
              <XAxis
                dataKey="code"
                tick={{ fontSize: 12, fill: axisColor }}
                axisLine={{ stroke: gridColor }}
                tickLine={false}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fontSize: 12, fill: axisColor }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip contentStyle={tooltipStyle} cursor={{ fill: isDark ? "rgba(148,163,184,0.08)" : "rgba(15,23,42,0.04)" }} />
              <Bar
                dataKey="Internal"
                stackId="marks"
                fill={isDark ? "#818cf8" : "#4f46e5"}
                radius={[0, 0, 4, 4]}
              />
              <Bar
                dataKey="External"
                stackId="marks"
                fill={isDark ? "#475569" : "#cbd5e1"}
                radius={[4, 4, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
