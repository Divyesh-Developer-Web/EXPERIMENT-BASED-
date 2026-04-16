import React, { useEffect, useState } from "react";
import { health } from "@/lib/api";

export default function SettingsView() {
  const [info, setInfo] = useState(null);
  const [voiceEnabled, setVoiceEnabled] = useState(() =>
    localStorage.getItem("nova.voice") !== "off",
  );
  const [wakeWord, setWakeWord] = useState(() => localStorage.getItem("nova.wake") || "Hey Nova");
  const [voices, setVoices] = useState([]);
  const [selectedVoice, setSelectedVoice] = useState(
    localStorage.getItem("nova.voiceName") || "",
  );

  useEffect(() => {
    (async () => {
      try {
        setInfo(await health());
      } catch {}
    })();
    const load = () => setVoices(window.speechSynthesis?.getVoices?.() || []);
    load();
    if ("speechSynthesis" in window) window.speechSynthesis.onvoiceschanged = load;
  }, []);

  useEffect(() => {
    localStorage.setItem("nova.voice", voiceEnabled ? "on" : "off");
  }, [voiceEnabled]);
  useEffect(() => {
    localStorage.setItem("nova.wake", wakeWord);
  }, [wakeWord]);
  useEffect(() => {
    localStorage.setItem("nova.voiceName", selectedVoice);
  }, [selectedVoice]);

  return (
    <div className="px-6 md:px-10 lg:px-16 pt-8 max-w-3xl mx-auto w-full">
      <div className="mb-8">
        <div className="font-mono text-[10px] uppercase tracking-[0.35em] text-white/30 mb-2">
          Preferences
        </div>
        <h1 className="font-display text-4xl font-bold tracking-tight">Settings</h1>
      </div>

      <div className="space-y-4" data-testid="settings-list">
        <Row label="Voice output">
          <ToggleRow
            testid="setting-voice"
            value={voiceEnabled}
            onChange={setVoiceEnabled}
            labels={["Enabled", "Muted"]}
          />
        </Row>

        <Row label="Wake word (future)">
          <input
            data-testid="setting-wake"
            value={wakeWord}
            onChange={(e) => setWakeWord(e.target.value)}
            className="w-full h-10 rounded-lg bg-white/5 border border-white/10 focus:border-white/30 outline-none px-3 font-mono text-sm"
          />
          <p className="font-mono text-[11px] text-white/40 mt-2">
            Wake-word detection (Porcupine) requires the native desktop build. This phrase is
            saved for future use.
          </p>
        </Row>

        <Row label="TTS voice">
          <select
            data-testid="setting-tts-voice"
            value={selectedVoice}
            onChange={(e) => setSelectedVoice(e.target.value)}
            className="w-full h-10 rounded-lg bg-white/5 border border-white/10 focus:border-white/30 outline-none px-3 font-mono text-sm"
          >
            <option value="">Automatic (browser default)</option>
            {voices.map((v) => (
              <option key={v.name} value={v.name}>
                {v.name} — {v.lang}
              </option>
            ))}
          </select>
        </Row>

        <Row label="Model">
          <div className="font-mono text-sm text-white/70">
            {info?.model || "claude-sonnet-4-5-20250929"}{" "}
            <span className="text-white/30">· via Emergent Universal Key</span>
          </div>
        </Row>

        <Row label="Backend status">
          <div className="flex items-center gap-2">
            <span
              className="w-2 h-2 rounded-full"
              style={{ background: info ? "#10B981" : "#F43F5E" }}
            />
            <span className="font-mono text-sm text-white/70">
              {info ? `OK · ${info.tools} tools registered` : "Offline"}
            </span>
          </div>
        </Row>
      </div>
    </div>
  );
}

function Row({ label, children }) {
  return (
    <div className="nova-glass rounded-xl p-5">
      <div className="font-mono text-[10px] uppercase tracking-[0.35em] text-white/40 mb-3">
        {label}
      </div>
      {children}
    </div>
  );
}

function ToggleRow({ value, onChange, labels, testid }) {
  return (
    <button
      data-testid={testid}
      onClick={() => onChange(!value)}
      className="flex items-center gap-3"
    >
      <span
        className="relative w-12 h-6 rounded-full transition"
        style={{ background: value ? "#10B981" : "rgba(255,255,255,0.1)" }}
      >
        <span
          className="absolute top-0.5 w-5 h-5 rounded-full bg-white transition"
          style={{ left: value ? 26 : 2 }}
        />
      </span>
      <span className="font-mono text-sm">{value ? labels[0] : labels[1]}</span>
    </button>
  );
}
