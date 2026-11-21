"use client";

import React, { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Blocks, FileText, Loader2, ShieldCheck } from "lucide-react";

type LoadingVariant = "auth" | "blockchain" | "pdf" | "default";

interface LoadingOverlayProps {
  open: boolean;
  title?: string;
  subtitle?: string;
  variant?: LoadingVariant;
}

const VARIANT_CONFIG: Record<
  LoadingVariant,
  {
    icon: React.ComponentType<{ className?: string }>;
    ringAccent: string;
    badgeBg: string;
    barColor: string;
  }
> = {
  auth: {
    icon: ShieldCheck,
    ringAccent: "border-t-brand-600 dark:border-t-brand-400",
    badgeBg: "bg-brand-600 text-white",
    barColor: "bg-brand-600 dark:bg-brand-400",
  },
  blockchain: {
    icon: Blocks,
    ringAccent: "border-t-emerald-600 dark:border-t-emerald-400",
    badgeBg: "bg-emerald-600 text-white",
    barColor: "bg-emerald-600 dark:bg-emerald-400",
  },
  pdf: {
    icon: FileText,
    ringAccent: "border-t-brand-600 dark:border-t-brand-400",
    badgeBg: "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900",
    barColor: "bg-brand-600 dark:bg-brand-400",
  },
  default: {
    icon: Loader2,
    ringAccent: "border-t-brand-600 dark:border-t-brand-400",
    badgeBg: "bg-brand-600 text-white",
    barColor: "bg-brand-600 dark:bg-brand-400",
  },
};

export function LoadingOverlay({
  open,
  title = "Please wait...",
  subtitle = "Processing your request",
  variant = "default",
}: LoadingOverlayProps) {
  const [showColdStartHint, setShowColdStartHint] = useState(false);

  useEffect(() => {
    if (!open) {
      setShowColdStartHint(false);
      return;
    }
    const timer = setTimeout(() => {
      setShowColdStartHint(true);
    }, 5000);
    return () => clearTimeout(timer);
  }, [open]);

  const config = VARIANT_CONFIG[variant];
  const Icon = config.icon;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          role="status"
          aria-live="polite"
          aria-busy="true"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.18 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/55 px-4 backdrop-blur-sm"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.97, y: 4 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-7 text-center shadow-[0_8px_30px_rgba(15,23,42,0.12)] dark:border-slate-800 dark:bg-slate-900 dark:shadow-[0_12px_36px_rgba(0,0,0,0.45)]"
          >
            {/* Disciplined orbital ring + center icon */}
            <div className="relative mx-auto mb-5 flex h-16 w-16 items-center justify-center">
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1.05, repeat: Infinity, ease: "linear" }}
                className={`absolute inset-0 rounded-full border-2 border-slate-200 dark:border-slate-800 ${config.ringAccent}`}
              />
              <div
                className={`relative flex h-10 w-10 items-center justify-center rounded-lg ${config.badgeBg}`}
              >
                <Icon
                  className={`h-5 w-5 ${variant === "default" ? "animate-spin" : ""}`}
                />
              </div>
            </div>

            <h3 className="text-base font-semibold tracking-tight text-slate-900 dark:text-slate-100">
              {title}
            </h3>
            <p className="mt-1.5 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
              {subtitle}
            </p>

            {/* Clean indeterminate progress bar */}
            <div className="relative mt-5 h-1 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
              <motion.div
                initial={{ x: "-100%" }}
                animate={{ x: "200%" }}
                transition={{ duration: 1.3, repeat: Infinity, ease: "easeInOut" }}
                className={`h-full w-1/2 rounded-full ${config.barColor}`}
              />
            </div>

            <AnimatePresence>
              {showColdStartHint && (
                <motion.p
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="mt-4 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] font-medium text-amber-800 dark:text-amber-200"
                >
                  Server is waking up — first load can take a few seconds. Please stay on this page.
                </motion.p>
              )}
            </AnimatePresence>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
