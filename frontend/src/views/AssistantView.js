import React, { useCallback, useEffect, useRef, useState } from "react";
import ReactDOM from "react-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Mic, MicOff, Send, Volume2, VolumeX, Sparkles, Wrench, PictureInPicture2, X,
} from "lucide-react";
import VoiceOrb from "@/components/VoiceOrb";
import useSpeech from "@/hooks/useSpeech";
import { chat } from "@/lib/api";

const EXAMPLES = [
  "What can you do?",
  "Remember I love cold brew",
  "Weather in Nagpur",
  "Who is Alan Turing?",
  "Summarize https://example.com",
  "Calculate sqrt(144) * 3",
];

export default function AssistantView() {
  const [orbState, setOrbState] = useState("idle");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState(null);
  const [speakEnabled, setSpeakEnabled] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [pipActive, setPipActive] = useState(false);
  const scrollRef = useRef(null);
  const pipWindowRef = useRef(null);
  const speech = useSpeech();

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, orbState]);

  const sendMessage = useCallback(
    async (text) => {
      const trimmed = (text || "").trim();
      if (!trimmed || sending) return;
      setError("");
      const userMsg = { id: `u-${Date.now()}`, role: "user", content: trimmed };
      setMessages((m) => [...m, userMsg]);
      setInput("");
      setSending(true);
      setOrbState("thinking");
      try {
        const data = await chat({ message: trimmed, conversation_id: conversationId });
        setConversationId(data.conversation_id);
        const assistantMsg = {
          id: `a-${Date.now()}`,
          role: "assistant",
          content: data.reply,
          tool_trace: data.tool_trace || [],
          suggestions: data.suggestions || [],
        };
        setMessages((m) => [...m, assistantMsg]);

        if (speakEnabled && speech.supported.tts) {
          setOrbState("speaking");
          speech.speak(data.reply, { onEnd: () => setOrbState("idle") });
        } else {
          setOrbState("idle");
        }
      } catch (e) {
        setError(e?.response?.data?.detail || e.message || "Something went wrong");
        setOrbState("idle");
      } finally {
        setSending(false);
      }
    },
    [conversationId, sending, speakEnabled, speech],
  );

  const handleMic = useCallback(() => {
    if (!speech.supported.stt) {
      setError("Your browser does not support speech recognition. Try Chrome.");
      return;
    }
    if (speech.listening) {
      speech.stopListening();
      setOrbState("idle");
      return;
    }
    speech.cancelSpeech();
    setOrbState("listening");
    speech.startListening((finalText) => {
      setOrbState("thinking");
      sendMessage(finalText);
    });
  }, [speech, sendMessage]);

  const onSubmit = (e) => {
    e.preventDefault();
    sendMessage(input);
  };

  // ---- Picture-in-Picture ----
  const openPiP = useCallback(async () => {
    if (!("documentPictureInPicture" in window)) {
      setError("Picture-in-Picture isn't supported in this browser. Try Chrome 116+ or Edge.");
      return;
    }
    try {
      const pipWin = await window.documentPictureInPicture.requestWindow({ width: 360, height: 440 });
      pipWindowRef.current = pipWin;
      // Copy stylesheets into PiP window
      Array.from(document.styleSheets).forEach((sheet) => {
        try {
          const linkEl = sheet.ownerNode?.cloneNode?.(true);
          if (linkEl) pipWin.document.head.appendChild(linkEl);
        } catch {}
      });
      // Inject base styles
      const style = pipWin.document.createElement("style");
      style.textContent = `html,body{margin:0;background:#050505;color:#fff;font-family:"JetBrains Mono",monospace;height:100%;overflow:hidden;}`;
      pipWin.document.head.appendChild(style);
      // Mount point that React portal targets
      const mount = pipWin.document.createElement("div");
      mount.id = "pip-root";
      mount.style.cssText = "height:100%;display:flex;flex-direction:column;";
      pipWin.document.body.appendChild(mount);
      pipWin.addEventListener("pagehide", () => {
        setPipActive(false);
        pipWindowRef.current = null;
      });
      setPipActive(true);
    } catch (e) {
      setError("Could not open PiP: " + (e.message || e));
    }
  }, []);

  const closePiP = useCallback(() => {
    try {
      pipWindowRef.current?.close();
    } catch {}
    pipWindowRef.current = null;
    setPipActive(false);
  }, []);

  return (
    <div className="flex-1 flex flex-col lg:flex-row gap-8 px-6 md:px-10 lg:px-16 pt-6">
      {/* Left: Hero + orb */}
      <section className="lg:w-[44%] flex flex-col items-center lg:items-start lg:pt-6">
        <div className="mb-4 flex items-center gap-3">
          <span className="font-mono text-[10px] uppercase tracking-[0.35em] text-white/30">
            Personal AI · MCP-powered
          </span>
          <button
            onClick={pipActive ? closePiP : openPiP}
            data-testid="pip-button"
            className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest px-2 py-1 rounded border border-white/10 hover:border-white/30 hover:bg-white/5 text-white/60 hover:text-white transition"
            title={pipActive ? "Close Picture-in-Picture" : "Open floating Nova (PiP)"}
          >
            {pipActive ? <X size={11} /> : <PictureInPicture2 size={11} />}
            {pipActive ? "close pip" : "floating nova"}
          </button>
        </div>
        <h1 className="font-display text-5xl md:text-6xl font-bold leading-[0.95] tracking-tight mb-6">
          Hey, I'm <span style={{ color: "#F43F5E" }}>Nova</span>.
          <br />
          <span className="text-white/50">Ask me anything.</span>
        </h1>

        <div className="flex flex-col items-center lg:items-start gap-8 w-full">
          <div className="mx-auto lg:mx-0 mt-2">
            <VoiceOrb state={orbState} size={280} onClick={handleMic} />
          </div>

          {speech.interim && (
            <div data-testid="interim-transcript" className="font-mono text-sm text-white/60 italic max-w-md">
              "{speech.interim}"
            </div>
          )}

          <div className="flex flex-wrap gap-2 max-w-xl">
            {EXAMPLES.map((ex) => (
              <button
                key={ex}
                data-testid={`example-${ex.slice(0, 10).replace(/\s/g, "-").toLowerCase()}`}
                onClick={() => sendMessage(ex)}
                disabled={sending}
                className="font-mono text-xs px-3 py-1.5 rounded-full border border-white/10 hover:border-white/30 hover:bg-white/5 text-white/70 hover:text-white transition disabled:opacity-40"
              >
                {ex}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* Right: Chat panel */}
      <section className="flex-1 flex flex-col min-h-[60vh]">
        <div
          ref={scrollRef}
          data-testid="chat-scroll"
          className="flex-1 nova-glass rounded-2xl p-4 md:p-6 overflow-y-auto space-y-4"
          style={{ maxHeight: "70vh" }}
        >
          {messages.length === 0 && (
            <div className="h-full flex items-center justify-center text-center font-mono text-xs text-white/30 uppercase tracking-[0.3em]">
              Conversation will appear here
            </div>
          )}
          <AnimatePresence initial={false}>
            {messages.map((m) => (
              <motion.div
                key={m.id}
                data-testid={`msg-${m.role}`}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.25 }}
                className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 font-mono text-[13.5px] leading-relaxed ${
                    m.role === "user"
                      ? "bg-white/5 border border-white/10 text-white"
                      : "bg-[#0f0f10] text-white/90"
                  }`}
                >
                  {m.role === "assistant" && m.tool_trace && m.tool_trace.length > 0 && (
                    <div className="mb-2 flex flex-wrap gap-1.5">
                      {m.tool_trace.map((t, i) => (
                        <span
                          key={i}
                          data-testid="tool-chip"
                          className="inline-flex items-center gap-1 text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-full border border-white/10 bg-white/5 text-white/60"
                        >
                          <Wrench size={10} /> {t.name}
                        </span>
                      ))}
                    </div>
                  )}
                  <div className="whitespace-pre-wrap">{m.content}</div>
                </div>
                {m.role === "assistant" && m.suggestions && m.suggestions.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5" data-testid="suggestions">
                    {m.suggestions.map((s, i) => (
                      <button
                        key={i}
                        onClick={() => sendMessage(s)}
                        data-testid={`suggestion-${i}`}
                        className="inline-flex items-center gap-1 font-mono text-[11px] px-2.5 py-1 rounded-full border border-white/10 hover:border-rose-500/40 hover:text-rose-300 text-white/60 transition"
                      >
                        <Sparkles size={11} /> {s}
                      </button>
                    ))}
                  </div>
                )}
              </motion.div>
            ))}
          </AnimatePresence>
          {sending && (
            <div className="flex justify-start">
              <div className="bg-[#0f0f10] rounded-2xl px-4 py-3 font-mono text-[13px] text-white/50 flex items-center gap-2">
                <Sparkles size={12} /> Nova is thinking…
              </div>
            </div>
          )}
        </div>

        {error && (
          <div
            data-testid="error-banner"
            className="mt-3 font-mono text-xs text-rose-400 bg-rose-500/10 border border-rose-500/30 rounded-lg px-3 py-2"
          >
            {error}
          </div>
        )}

        <form onSubmit={onSubmit} className="mt-4 flex items-center gap-2" data-testid="chat-form">
          <button
            type="button"
            onClick={() => setSpeakEnabled((s) => !s)}
            data-testid="toggle-speak"
            aria-label={speakEnabled ? "Disable voice output" : "Enable voice output"}
            className="h-12 w-12 shrink-0 rounded-xl border border-white/10 hover:border-white/30 hover:bg-white/5 flex items-center justify-center text-white/70 hover:text-white transition"
          >
            {speakEnabled ? <Volume2 size={18} /> : <VolumeX size={18} />}
          </button>

          <div className="flex-1 relative">
            <input
              data-testid="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type a command or press the mic…"
              disabled={sending}
              className="w-full h-12 rounded-xl bg-white/5 border border-white/10 focus:border-white/30 focus:bg-white/10 outline-none px-4 font-mono text-sm text-white placeholder:text-white/30 transition"
            />
          </div>

          <button
            type="button"
            onClick={handleMic}
            data-testid="mic-button"
            aria-label={speech.listening ? "Stop listening" : "Start listening"}
            className="h-12 w-12 shrink-0 rounded-xl flex items-center justify-center transition"
            style={{
              background: speech.listening ? "#10B98133" : "rgba(255,255,255,0.05)",
              border: `1px solid ${speech.listening ? "#10B981" : "rgba(255,255,255,0.1)"}`,
              color: speech.listening ? "#10B981" : "white",
            }}
          >
            {speech.listening ? <MicOff size={18} /> : <Mic size={18} />}
          </button>

          <button
            type="submit"
            data-testid="send-button"
            disabled={!input.trim() || sending}
            className="h-12 px-5 rounded-xl bg-white text-black font-mono text-xs uppercase tracking-widest disabled:opacity-30 hover:bg-white/90 transition flex items-center gap-2"
          >
            <Send size={14} /> Send
          </button>
        </form>

        <div className="mt-2 font-mono text-[10px] uppercase tracking-[0.3em] text-white/25">
          {speech.supported.stt ? "stt: ready" : "stt: unsupported (use chrome)"}
          {" · "}
          {speech.supported.tts ? "tts: ready" : "tts: unsupported"}
          {pipActive && " · pip: floating"}
        </div>
      </section>

      {/* PiP portal */}
      {pipActive && pipWindowRef.current && (
        <PipPortal win={pipWindowRef.current}>
          <FloatingNova
            orbState={orbState}
            onMic={handleMic}
            listening={speech.listening}
            lastMessage={messages[messages.length - 1]}
            onSend={sendMessage}
            sending={sending}
          />
        </PipPortal>
      )}
    </div>
  );
}

// -- PiP portal helper --
function PipPortal({ win, children }) {
  const [container, setContainer] = useState(null);
  useEffect(() => {
    const el = win.document.getElementById("pip-root");
    setContainer(el);
  }, [win]);
  if (!container) return null;
  return ReactDOM.createPortal(children, container);
}

function FloatingNova({ orbState, onMic, listening, lastMessage, onSend, sending }) {
  const [text, setText] = useState("");
  return (
    <div style={{ padding: 16, height: "100%", display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ fontFamily: '"Bricolage Grotesque", sans-serif', fontWeight: 700, fontSize: 18 }}>
          Nova
        </div>
        <div style={{ fontSize: 10, letterSpacing: "0.3em", textTransform: "uppercase", opacity: 0.4 }}>
          floating
        </div>
      </div>
      <div style={{ display: "flex", justifyContent: "center", margin: "12px 0" }}>
        <VoiceOrb state={orbState} size={150} onClick={onMic} />
      </div>
      <div
        style={{
          flex: 1,
          overflow: "auto",
          background: "rgba(255,255,255,0.04)",
          borderRadius: 12,
          padding: 10,
          fontSize: 12,
          lineHeight: 1.5,
          color: "rgba(255,255,255,0.85)",
        }}
      >
        {lastMessage ? (
          <>
            <div style={{ opacity: 0.4, fontSize: 9, letterSpacing: "0.2em", textTransform: "uppercase", marginBottom: 4 }}>
              {lastMessage.role}
            </div>
            {lastMessage.content}
          </>
        ) : (
          <div style={{ opacity: 0.4 }}>Ask me anything…</div>
        )}
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (text.trim()) {
            onSend(text);
            setText("");
          }
        }}
        style={{ display: "flex", gap: 6 }}
      >
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="quick ask…"
          disabled={sending}
          style={{
            flex: 1,
            background: "rgba(255,255,255,0.06)",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 8,
            padding: "8px 10px",
            color: "#fff",
            fontFamily: '"JetBrains Mono", monospace',
            fontSize: 12,
            outline: "none",
          }}
        />
        <button
          type="button"
          onClick={onMic}
          style={{
            width: 36, height: 36, borderRadius: 8, cursor: "pointer",
            background: listening ? "#10B98133" : "rgba(255,255,255,0.05)",
            border: `1px solid ${listening ? "#10B981" : "rgba(255,255,255,0.1)"}`,
            color: listening ? "#10B981" : "#fff",
          }}
          aria-label="mic"
        >
          🎤
        </button>
      </form>
    </div>
  );
}
