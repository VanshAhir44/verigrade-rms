"use client";

interface AnimatedCounterProps {
  value: number;
  decimals?: number;
  suffix?: string;
  className?: string;
}

/**
 * Renders an exact authoritative metric immediately without counting up from 0,
 * preventing transient misleading intermediate values (e.g. 0.58 instead of 8.14).
 */
export function AnimatedCounter({
  value,
  decimals = 2,
  suffix = "",
  className = "",
}: AnimatedCounterProps) {
  const safeValue = Number.isFinite(value) ? value : 0;

  return (
    <span className={`tabular-nums ${className}`.trim()}>
      {safeValue.toFixed(decimals)}
      {suffix}
    </span>
  );
}
