import React from "react";
import { motion, AnimatePresence } from "framer-motion";

/**
 * VoiceOrb — 4 animation states
 * state: 'idle' | 'listening' | 'thinking' | 'speaking'
 */
const COLORS = {
  idle: "#9D4CDD",
  listening: "#10B981",
  thinking: "#3B82F6",
  speaking: "#F43F5E",
};

const LABELS = {
  idle: "Idle",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
};

export default function VoiceOrb({ state = "idle", size = 280, onClick }) {
  const color = COLORS[state] || COLORS.idle;

  return (
    <div
      data-testid="voice-orb"
      data-orb-state={state}
      onClick={onClick}
      className="relative flex items-center justify-center select-none"
      style={{ width: size, height: size, cursor: onClick ? "pointer" : "default" }}
    >
      {/* Ambient glow */}
      <motion.div
        aria-hidden
        className="absolute rounded-full"
        style={{
          width: size * 1.4,
          height: size * 1.4,
          background: `radial-gradient(circle, ${color}55 0%, ${color}00 60%)`,
          filter: "blur(30px)",
          mixBlendMode: "screen",
        }}
        animate={{ opacity: state === "idle" ? [0.35, 0.65, 0.35] : 0.65 }}
        transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
      />

      {/* Listening ripple rings */}
      <AnimatePresence>
        {state === "listening" &&
          [0, 0.4, 0.8].map((delay) => (
            <motion.div
              key={delay}
              aria-hidden
              className="absolute rounded-full"
              style={{
                width: size * 0.9,
                height: size * 0.9,
                border: `1.5px solid ${color}`,
                boxShadow: `0 0 40px ${color}66`,
              }}
              initial={{ scale: 0.9, opacity: 0.6 }}
              animate={{ scale: 2.4, opacity: 0 }}
              transition={{ duration: 1.8, repeat: Infinity, delay, ease: "easeOut" }}
              exit={{ opacity: 0 }}
            />
          ))}
      </AnimatePresence>

      {/* Thinking rotating arc */}
      {state === "thinking" && (
        <motion.div
          aria-hidden
          className="absolute rounded-full"
          style={{
            width: size * 1.05,
            height: size * 1.05,
            border: "2px solid transparent",
            borderTopColor: color,
            borderRightColor: `${color}80`,
            boxShadow: `0 0 40px ${color}66`,
          }}
          animate={{ rotate: 360 }}
          transition={{ duration: 1.6, repeat: Infinity, ease: "linear" }}
        />
      )}

      {/* Core orb */}
      <motion.div
        aria-hidden
        className="relative rounded-full"
        style={{
          width: size * 0.65,
          height: size * 0.65,
          background: `radial-gradient(circle at 30% 30%, ${color}ff 0%, ${color}c0 50%, ${color}80 100%)`,
          boxShadow: `inset 0 0 40px ${color}80, 0 0 60px ${color}66`,
        }}
        animate={
          state === "idle"
            ? { scale: [0.96, 1.04, 0.96] }
            : state === "thinking"
              ? { scale: [1, 1.02, 1] }
              : state === "speaking"
                ? { scale: [1, 1.05, 1] }
                : { scale: 1 }
        }
        transition={{
          duration: state === "idle" ? 4 : state === "thinking" ? 1.2 : 0.3,
          repeat: Infinity,
          ease: "easeInOut",
        }}
      >
        {/* Thinking dots */}
        {state === "thinking" && (
          <div className="absolute inset-0 flex items-center justify-center gap-2">
            {[0, 1, 2].map((i) => (
              <motion.span
                key={i}
                className="block rounded-full bg-white"
                style={{ width: 10, height: 10 }}
                animate={{ opacity: [0.3, 1, 0.3] }}
                transition={{ duration: 1.1, repeat: Infinity, delay: i * 0.18 }}
              />
            ))}
          </div>
        )}

        {/* Speaking waveform bars */}
        {state === "speaking" && (
          <div className="absolute inset-0 flex items-center justify-center gap-1.5">
            {[0, 1, 2, 3, 4].map((i) => (
              <motion.span
                key={i}
                className="block rounded-full bg-white"
                style={{ width: 6, height: size * 0.22, originY: 0.5 }}
                animate={{ scaleY: [0.3, 1.1, 0.5, 1.3, 0.4] }}
                transition={{
                  duration: 0.9 + i * 0.05,
                  repeat: Infinity,
                  ease: "easeInOut",
                }}
              />
            ))}
          </div>
        )}

        {/* Listening mic dot */}
        {state === "listening" && (
          <div className="absolute inset-0 flex items-center justify-center">
            <motion.div
              className="rounded-full bg-white"
              style={{ width: 14, height: 14 }}
              animate={{ scale: [1, 1.4, 1] }}
              transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
            />
          </div>
        )}
      </motion.div>

      {/* State label under orb */}
      <div
        data-testid="orb-status"
        className="absolute left-1/2 -translate-x-1/2 font-mono uppercase tracking-[0.35em] text-[10px]"
        style={{ bottom: -28, color: color }}
      >
        {LABELS[state]}
      </div>
    </div>
  );
}

export { COLORS as ORB_COLORS };
