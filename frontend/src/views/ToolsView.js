import React, { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Wrench, CircleDot, FileText, Trash2 } from "lucide-react";
import {
  listTools, listMemories, clearMemories, deleteMemory, listNotes, deleteNote,
} from "@/lib/api";

const CAT_ORDER = ["info", "productivity", "memory", "utility", "time", "meta", "general"];
const CAT_LABEL = {
  info: "Information",
  productivity: "Productivity",
  memory: "Memory",
  utility: "Utility",
  time: "Time",
  meta: "Meta",
  general: "General",
};

export default function ToolsView() {
  const [tools, setTools] = useState([]);
  const [memories, setMemories] = useState([]);
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [t, m, n] = await Promise.all([listTools(), listMemories(), listNotes()]);
      setTools(t || []);
      setMemories(m || []);
      setNotes(n || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const grouped = {};
  for (const t of tools) {
    const c = t.category || "general";
    (grouped[c] = grouped[c] || []).push(t);
  }

  return (
    <div className="px-6 md:px-10 lg:px-16 pt-8 max-w-6xl mx-auto w-full">
      <div className="mb-10">
        <div className="font-mono text-[10px] uppercase tracking-[0.35em] text-white/30 mb-2">
          Layer 4 · MCP Tool Hub
        </div>
        <h1 className="font-display text-4xl md:text-5xl font-bold tracking-tight">
          Tool hub.
          <span className="text-white/40"> {tools.length} capabilities live.</span>
        </h1>
        <p className="font-mono text-sm text-white/50 mt-4 max-w-2xl">
          Each tool is a function Nova's backend exposes. Claude decides which one to call.
          See <code className="text-white/80">/api/mcp/manifest</code> for the full MCP-style schema.
        </p>
      </div>

      {loading && <div className="font-mono text-white/40">Loading…</div>}

      {CAT_ORDER.filter((c) => grouped[c]).map((cat) => (
        <div key={cat} className="mb-10" data-testid={`category-${cat}`}>
          <div className="font-mono text-[10px] uppercase tracking-[0.35em] text-white/40 mb-3">
            {CAT_LABEL[cat]}
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            {grouped[cat].map((t, i) => (
              <motion.div
                key={t.name}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
                data-testid={`tool-${t.name}`}
                className="nova-glass rounded-xl p-5 flex items-start gap-4"
              >
                <div
                  className="mt-1 w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
                  style={{
                    background: t.mocked ? "rgba(244,63,94,0.15)" : "rgba(16,185,129,0.15)",
                    color: t.mocked ? "#F43F5E" : "#10B981",
                  }}
                >
                  <Wrench size={16} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono text-sm font-medium">{t.name}</span>
                    <span
                      className="inline-flex items-center gap-1 text-[9px] uppercase tracking-widest px-1.5 py-0.5 rounded"
                      style={{
                        background: t.mocked ? "rgba(244,63,94,0.1)" : "rgba(16,185,129,0.1)",
                        color: t.mocked ? "#F43F5E" : "#10B981",
                      }}
                    >
                      <CircleDot size={8} /> {t.mocked ? "mocked" : "live"}
                    </span>
                  </div>
                  <div className="font-mono text-xs text-white/60 leading-relaxed">{t.description}</div>
                  {Object.keys(t.args || {}).length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {Object.entries(t.args).map(([k, v]) => (
                        <span
                          key={k}
                          className="font-mono text-[10px] text-white/40 border border-white/10 rounded px-1.5 py-0.5"
                        >
                          {k}: {v}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      ))}

      {/* Notes */}
      <div className="mt-16 mb-4 flex items-end justify-between">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.35em] text-white/30 mb-2">
            Productivity · Notes
          </div>
          <h2 className="font-display text-2xl font-bold tracking-tight">Your notes</h2>
        </div>
        <div className="font-mono text-xs text-white/40">{notes.length} saved</div>
      </div>
      <div className="space-y-2 mb-12" data-testid="notes-list">
        {notes.length === 0 ? (
          <div className="font-mono text-sm text-white/30 italic">
            No notes. Say "Make a note: …" to save one.
          </div>
        ) : (
          notes.map((n) => (
            <div
              key={n.id}
              className="nova-glass rounded-xl px-4 py-3 flex items-start justify-between gap-4"
              data-testid={`note-${n.id}`}
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <FileText size={12} className="text-white/40" />
                  <span className="font-mono text-sm font-medium truncate">{n.title}</span>
                </div>
                <div className="font-mono text-xs text-white/60 whitespace-pre-wrap">{n.content}</div>
                <div className="font-mono text-[10px] uppercase tracking-widest text-white/30 mt-2">
                  {new Date(n.created_at).toLocaleString()}
                </div>
              </div>
              <button
                onClick={async () => { await deleteNote(n.id); load(); }}
                className="text-white/40 hover:text-rose-400 transition shrink-0"
                aria-label="Delete note"
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))
        )}
      </div>

      {/* Memories */}
      <div className="mb-4 flex items-end justify-between">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.35em] text-white/30 mb-2">
            Memory · Long-term
          </div>
          <h2 className="font-display text-2xl font-bold tracking-tight">What Nova remembers</h2>
        </div>
        {memories.length > 0 && (
          <button
            data-testid="clear-memories"
            onClick={async () => { await clearMemories(); load(); }}
            className="font-mono text-[10px] uppercase tracking-widest px-3 py-1.5 rounded border border-white/10 text-white/60 hover:text-white hover:border-white/30 transition"
          >
            Clear all
          </button>
        )}
      </div>

      <div className="space-y-2" data-testid="memories-list">
        {memories.length === 0 ? (
          <div className="font-mono text-sm text-white/30 italic">
            No memories yet. Say "Remember that I …" to teach Nova.
          </div>
        ) : (
          memories.map((m) => (
            <div
              key={m.id}
              className="nova-glass rounded-xl px-4 py-3 flex items-center justify-between gap-4"
              data-testid={`memory-${m.id}`}
            >
              <div className="min-w-0">
                <div className="font-mono text-sm text-white/85 truncate">{m.content}</div>
                <div className="font-mono text-[10px] uppercase tracking-widest text-white/30 mt-1">
                  {new Date(m.created_at).toLocaleString()}
                </div>
              </div>
              <button
                onClick={async () => { await deleteMemory(m.id); load(); }}
                className="font-mono text-[10px] uppercase tracking-widest text-white/40 hover:text-rose-400 transition"
              >
                forget
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
