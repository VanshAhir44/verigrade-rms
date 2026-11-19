"use client";

import React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, AlertTriangle, Sparkles, X } from "lucide-react";

export function PageTransition({ children }: { children: React.ReactNode }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}

export function StaggerGrid({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={{
        hidden: {},
        visible: { transition: { staggerChildren: 0.07 } },
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export function FadeInCard({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      variants={{
        hidden: { opacity: 0, y: 14 },
        visible: { opacity: 1, y: 0, transition: { duration: 0.32 } },
      }}
      className={`glass-card ${className}`}
    >
      {children}
    </motion.div>
  );
}

export function ToastBanner({
  toast,
  onClose,
}: {
  toast: { type: "success" | "error" | "live"; message: string } | null;
  onClose: () => void;
}) {
  return (
    <AnimatePresence>
      {toast && (
        <motion.div
          initial={{ opacity: 0, y: -16, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -12, scale: 0.96 }}
          className={`fixed right-5 top-20 z-50 flex max-w-md items-center gap-3 rounded-xl border px-4 py-3 text-sm font-medium shadow-lg backdrop-blur-md ${
            toast.type === "error"
              ? "border-rose-300 bg-rose-50/95 text-rose-800 dark:border-rose-800 dark:bg-rose-950/90 dark:text-rose-200"
              : toast.type === "live"
              ? "border-indigo-300 bg-indigo-50/95 text-indigo-900 dark:border-indigo-700 dark:bg-indigo-950/90 dark:text-indigo-200"
              : "border-emerald-300 bg-emerald-50/95 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/90 dark:text-emerald-200"
          }`}
        >
          {toast.type === "error" ? (
            <AlertTriangle className="h-4 w-4 shrink-0" />
          ) : toast.type === "live" ? (
            <Sparkles className="h-4 w-4 shrink-0 text-indigo-500" />
          ) : (
            <CheckCircle2 className="h-4 w-4 shrink-0" />
          )}
          <span className="flex-1">{toast.message}</span>
          <button onClick={onClose} className="opacity-70 hover:opacity-100">
            <X className="h-4 w-4" />
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
