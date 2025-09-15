"use client";
import { cn } from "@/lib/utils";
import { Transition } from "framer-motion";

type BorderTrailProps = {
  className?: string;
  size?: number;
  transition?: Transition;
  delay?: number;
  onAnimationComplete?: () => void;
  style?: React.CSSProperties;
};

export function BorderTrail({ className, style }: BorderTrailProps) {
  // Static white glow around the card border (no trail/animation)
  return (
    <div className="pointer-events-none absolute inset-0 rounded-[inherit]">
      {/* Thin subtle ring */}
      <div className="absolute inset-0 rounded-[inherit] ring-1 ring-white/25" />
      {/* Outer soft glow */}
      <div
        className={cn("absolute inset-0 rounded-[inherit]", className)}
        style={{
          boxShadow:
            "0 0 24px 6px rgba(255,255,255,0.08), 0 0 8px 1px rgba(255,255,255,0.15)",
          ...style,
        }}
      />
    </div>
  );
}