"use client";

import React, { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Blocks, FileText, ShieldCheck, Sparkles } from "lucide-react";

export type LoadingVariant = "auth" | "blockchain" | "pdf" | "default";

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
    barGradient: string;
  }
> = {
  auth: {
    icon: ShieldCheck,
    ringAccent: "border-t-brand-500 border-r-indigo-400",
    badgeBg: "bg-brand-600 text-white shadow-brand-500/30",
    barGradient: "from-brand-500 via-indigo-400 to-brand-600",
  },
  blockchain: {
    icon: Blocks,
    ringAccent: "border-t-emerald-500 border-r-teal-400",
    badgeBg: "bg-emerald-600 text-white shadow-emerald-500/30",
    barGradient: "from-emerald-500 via-teal-400 to-brand-500",
  },
  pdf: {
    icon: FileText,
    ringAccent: "border-t-sky-500 border-r-brand-400",
    badgeBg: "bg-sky-600 text-white shadow-sky-500/30",
    barGradient: "from-sky-500 via-brand-400 to-indigo-500",
  },
  default: {
    icon: Sparkles,
    ringAccent: "border-t-brand-500 border-r-violet-400",
    badgeBg: "bg-brand-600 text-white shadow-brand-500/30",
    barGradient: "from-brand-500 via-violet-400 to-indigo-500",
  },
};

export function LoadingOverlay({
  open,
  title = "Please wait...",
  subtitle = "Processing your request securely",
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
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 px-4 backdrop-blur-md"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.92, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 8 }}
            transition={{ type: "spring", stiffness: 320, damping: 26 }}
            className="relative w-full max-w-sm overflow-hidden rounded-2xl border border-slate-200/80 bg-white/95 p-7 text-center shadow-2xl dark:border-slate-700/80 dark:bg-slate-900/95"
          >
            {/* Subtle top ambient glow */}
            <div className="pointer-events-none absolute -top-16 left-1/2 h-32 w-56 -translate-x-1/2 rounded-full bg-brand-500/15 blur-2xl" />

            {/* Dual Orbital Spinner + Central Icon */}
            <div className="relative mx-auto mb-5 flex h-20 w-20 items-center justify-center">
              {/* Soft pulse aura */}
              <motion.div
                animate={{ scale: [1, 1.18, 1], opacity: [0.35, 0.12, 0.35] }}
                transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                className="absolute inset-0 rounded-full bg-brand-500/20"
              />

              {/* Outer rotating ring */}
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 1.15, repeat: Infinity, ease: "linear" }}
                className={`absolute inset-0 rounded-full border-[3px] border-slate-200/40 dark:border-slate-700/50 ${config.ringAccent}`}
              />

              {/* Inner counter-rotating ring */}
              <motion.div
                animate={{ rotate: -360 }}
                transition={{ duration: 1.8, repeat: Infinity, ease: "linear" }}
                className="absolute inset-2 rounded-full border-2 border-transparent border-b-brand-400/70 border-l-indigo-400/50"
              />

              {/* Center icon badge */}
              <motion.div
                animate={{ scale: [1, 1.06, 1] }}
                transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
                className={`relative flex h-11 w-11 items-center justify-center rounded-xl shadow-lg ${config.badgeBg}`}
              >
                <Icon className="h-5 w-5" />
              </motion.div>
            </div>

            {/* Title & Subtitle */}
            <h3 className="text-base font-semibold tracking-tight text-slate-900 dark:text-white">
              {title}
            </h3>
            <p className="mt-1.5 text-xs leading-relaxed text-slate-500 dark:text-slate-400">
              {subtitle}
            </p>

            {/* Animated indeterminate shimmer progress bar */}
            <div className="relative mt-5 h-1.5 w-full overflow-hidden rounded-full bg-slate-200/80 dark:bg-slate-800">
              <motion.div
                initial={{ x: "-100%" }}
                animate={{ x: "200%" }}
                transition={{ duration: 1.35, repeat: Infinity, ease: "easeInOut" }}
                className={`h-full w-1/2 rounded-full bg-gradient-to-r ${config.barGradient}`}
              />
            </div>

            {/* Cold-start reassurance note (appears smoothly if request takes >5s) */}
            <AnimatePresence>
              {showColdStartHint && (
                <motion.p
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="mt-4 rounded-lg border border-amber-200/70 bg-amber-50/80 px-3 py-2 text-[11px] font-medium text-amber-800 dark:border-amber-800/60 dark:bg-amber-950/50 dark:text-amber-200"
                >
                  Server is waking up — this can take a few seconds on first load. Please stay on this page.
                </motion.p>
              )}
            </AnimatePresence>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
