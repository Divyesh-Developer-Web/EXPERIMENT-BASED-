import React from "react";
import { motion } from "framer-motion";
import VoiceOrb from "@/components/VoiceOrb";

const LAYERS = [
  {
    n: 1,
    name: "App Shell",
    tagline: "Electron / Tauri — or just the browser",
    color: "#9D4CDD",
    why:
      "A wrapper that turns a web UI (React + Tailwind) into a PC app. Electron uses Chromium; Tauri uses Rust+WebView and ships smaller binaries. In this build we serve the same UI from the browser so you can try it instantly.",
    parts: ["Voice orb UI", "Text input", "Response renderer", "System tray header"],
  },
  {
    n: 2,
    name: "Voice Pipeline",
    tagline: "Speech in → text → AI → text → speech out",
    color: "#10B981",
    why:
      "Four sub-stages: (1) Wake word — a tiny always-on model like Picovoice Porcupine catches 'Hey Nova'. (2) VAD detects when you stop talking. (3) STT (Whisper) converts audio to text. (4) TTS (ElevenLabs or browser) reads answers aloud. We use browser SpeechRecognition + SpeechSynthesis for zero setup.",
    parts: ["Wake word (skipped for v1)", "VAD (browser handled)", "STT · Web Speech API", "TTS · SpeechSynthesis"],
  },
  {
    n: 3,
    name: "Brain — Claude + MCP",
    tagline: "Reasoning · memory · tool routing",
    color: "#3B82F6",
    why:
      "Claude Sonnet 4.5 is the brain. We pass the user message + tool catalogue. Claude decides: reply directly, or emit a <tool_call> block. Our server parses it, runs the tool, feeds the result back. Memory sits in MongoDB so Nova recalls past sessions.",
    parts: ["Claude API", "MCP tool loop", "Conversation store", "Memory store"],
  },
  {
    n: 4,
    name: "MCP Tools",
    tagline: "What the assistant can do",
    color: "#F59E0B",
    why:
      "Each tool is a small Python function registered on the backend. It takes args, does work, returns JSON. Add a new one and Claude automatically learns to call it. You can build a Calendar, Email, PC control, Smart-home, Spotify tool this way.",
    parts: ["get_time", "get_weather (mock)", "web_search (mock)", "save/recall memory"],
  },
  {
    n: 5,
    name: "External APIs",
    tagline: "Third-party data & capabilities",
    color: "#F43F5E",
    why:
      "Real-world data sources you'd wire your tools to. Each needs its own API key stored in the .env file — never in code. Swap mocks for real services when ready.",
    parts: ["OpenWeatherMap", "Serper / Brave Search", "Google Calendar", "Home Assistant", "Spotify"],
  },
];

const ORB_STATES = [
  { s: "idle", label: "Idle", note: "slow breathing pulse · purple" },
  { s: "listening", label: "Listening", note: "expanding ripple rings · green" },
  { s: "thinking", label: "Thinking", note: "rotating arc + dots · blue" },
  { s: "speaking", label: "Speaking", note: "waveform bars · coral" },
];

export default function ArchitectureView() {
  return (
    <div className="px-6 md:px-10 lg:px-16 pt-8 pb-16 max-w-6xl mx-auto w-full" data-testid="architecture-view">
      <div className="mb-12">
        <div className="font-mono text-[10px] uppercase tracking-[0.35em] text-white/30 mb-2">
          Teaching · 5-layer stack
        </div>
        <h1 className="font-display text-4xl md:text-6xl font-bold tracking-tight leading-[0.95]">
          How Nova actually works.
        </h1>
        <p className="font-mono text-sm text-white/55 mt-5 max-w-2xl">
          Five layers, one conversation cycle. You speak, the orb listens, Claude
          reasons, a tool runs, the orb speaks back. Everything here is swappable —
          this is your blueprint.
        </p>
      </div>

      {/* Orb states strip */}
      <div className="nova-glass rounded-2xl p-6 md:p-8 mb-12">
        <div className="font-mono text-[10px] uppercase tracking-[0.35em] text-white/30 mb-6">
          Voice orb · 4 animation states
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {ORB_STATES.map((o) => (
            <div key={o.s} className="flex flex-col items-center text-center">
              <VoiceOrb state={o.s} size={120} />
              <div className="mt-10 font-display text-lg font-bold">{o.label}</div>
              <div className="font-mono text-[11px] text-white/45 mt-1">{o.note}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Layer bento grid */}
      <div className="grid md:grid-cols-2 gap-4" data-testid="layers-grid">
        {LAYERS.map((l, i) => (
          <motion.div
            key={l.n}
            initial={{ opacity: 0, y: 14 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, amount: 0.2 }}
            transition={{ delay: i * 0.06, duration: 0.5 }}
            className="relative rounded-2xl p-6 border border-white/5 bg-[#0A0A0A] overflow-hidden"
            style={{
              boxShadow: `inset 0 0 40px ${l.color}12`,
            }}
          >
            <div
              className="absolute -top-20 -right-20 w-60 h-60 rounded-full"
              style={{
                background: `radial-gradient(circle, ${l.color}30 0%, transparent 65%)`,
                filter: "blur(20px)",
              }}
              aria-hidden
            />
            <div className="relative">
              <div className="flex items-center gap-3 mb-3">
                <span
                  className="font-mono text-[10px] uppercase tracking-[0.3em] px-2 py-0.5 rounded"
                  style={{ background: `${l.color}20`, color: l.color }}
                >
                  Layer {l.n}
                </span>
              </div>
              <h3 className="font-display text-2xl font-bold tracking-tight mb-1">
                {l.name}
              </h3>
              <div className="font-mono text-xs text-white/45 mb-4">{l.tagline}</div>
              <p className="font-mono text-sm text-white/70 leading-relaxed mb-4">
                {l.why}
              </p>
              <div className="flex flex-wrap gap-1.5">
                {l.parts.map((p) => (
                  <span
                    key={p}
                    className="font-mono text-[10px] px-2 py-1 rounded border border-white/10 text-white/60"
                  >
                    {p}
                  </span>
                ))}
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Flow */}
      <div className="mt-14 nova-glass rounded-2xl p-6 md:p-8">
        <div className="font-mono text-[10px] uppercase tracking-[0.35em] text-white/30 mb-4">
          One conversation cycle
        </div>
        <ol className="space-y-3 font-mono text-sm text-white/75 list-decimal list-inside">
          <li>
            You say or type a command → the orb switches to{" "}
            <span style={{ color: "#10B981" }}>listening green</span>.
          </li>
          <li>
            Browser STT converts audio → text → POST to <code>/api/chat</code> → orb goes{" "}
            <span style={{ color: "#3B82F6" }}>thinking blue</span>.
          </li>
          <li>
            Claude receives message + tool catalog. It either replies or emits{" "}
            <code>&lt;tool_call&gt;</code>. Server runs the tool, feeds result back (up to 3 loops).
          </li>
          <li>
            Final text returns to the UI → orb switches to{" "}
            <span style={{ color: "#F43F5E" }}>speaking coral</span> → SpeechSynthesis reads it
            aloud.
          </li>
          <li>
            Speech ends → orb returns to{" "}
            <span style={{ color: "#9D4CDD" }}>idle purple</span>. Conversation + any saved memory
            are persisted in MongoDB.
          </li>
        </ol>
      </div>
    </div>
  );
}
