import React, { useEffect, useState } from "react";
import { listConversations, getConversation, deleteConversation } from "@/lib/api";
import { Trash2, MessageSquare } from "lucide-react";

export default function HistoryView() {
  const [convos, setConvos] = useState([]);
  const [active, setActive] = useState(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const c = await listConversations();
      setConvos(c || []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const open = async (id) => {
    const data = await getConversation(id);
    setActive(data);
  };

  const remove = async (id, e) => {
    e.stopPropagation();
    await deleteConversation(id);
    if (active?.conversation?.id === id) setActive(null);
    load();
  };

  return (
    <div className="px-6 md:px-10 lg:px-16 pt-8 max-w-6xl mx-auto w-full">
      <div className="mb-8">
        <div className="font-mono text-[10px] uppercase tracking-[0.35em] text-white/30 mb-2">
          Memory · Conversation log
        </div>
        <h1 className="font-display text-4xl md:text-5xl font-bold tracking-tight">
          Your past chats.
        </h1>
      </div>

      <div className="grid md:grid-cols-[320px_1fr] gap-6">
        <div className="space-y-2" data-testid="conversations-list">
          {loading && <div className="font-mono text-white/40">Loading…</div>}
          {!loading && convos.length === 0 && (
            <div className="font-mono text-sm text-white/30 italic">No conversations yet.</div>
          )}
          {convos.map((c) => (
            <button
              key={c.id}
              data-testid={`conv-${c.id}`}
              onClick={() => open(c.id)}
              className={`w-full text-left nova-glass rounded-xl px-4 py-3 flex items-start gap-3 transition ${
                active?.conversation?.id === c.id
                  ? "border-white/30 bg-white/10"
                  : "hover:border-white/20"
              }`}
            >
              <MessageSquare size={14} className="mt-1 text-white/40 shrink-0" />
              <div className="min-w-0 flex-1">
                <div className="font-mono text-sm text-white truncate">{c.title}</div>
                <div className="font-mono text-[10px] uppercase tracking-widest text-white/30 mt-1">
                  {new Date(c.updated_at).toLocaleString()} · {c.message_count} msgs
                </div>
              </div>
              <Trash2
                size={14}
                onClick={(e) => remove(c.id, e)}
                className="text-white/30 hover:text-rose-400 transition shrink-0"
              />
            </button>
          ))}
        </div>

        <div className="nova-glass rounded-xl p-6 min-h-[40vh]" data-testid="conv-detail">
          {!active ? (
            <div className="h-full flex items-center justify-center font-mono text-xs uppercase tracking-[0.3em] text-white/30">
              Select a conversation
            </div>
          ) : (
            <div className="space-y-4">
              <h2 className="font-display text-xl font-bold">{active.conversation.title}</h2>
              <div className="space-y-3">
                {active.messages.map((m) => (
                  <div
                    key={m.id}
                    className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[85%] rounded-2xl px-4 py-3 font-mono text-[13px] ${
                        m.role === "user"
                          ? "bg-white/5 border border-white/10"
                          : "bg-[#0f0f10]"
                      }`}
                    >
                      <div className="text-[10px] uppercase tracking-widest text-white/30 mb-1">
                        {m.role}
                      </div>
                      <div className="whitespace-pre-wrap text-white/90">{m.content}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
