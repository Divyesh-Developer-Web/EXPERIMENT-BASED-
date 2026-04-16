import React, { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { motion } from "framer-motion";
import { health } from "@/lib/api";

const NAV = [
  { to: "/", label: "Assistant", testid: "nav-assistant" },
  { to: "/tools", label: "Tools", testid: "nav-tools" },
  { to: "/history", label: "History", testid: "nav-history" },
  { to: "/architecture", label: "Architecture", testid: "nav-architecture" },
  { to: "/settings", label: "Settings", testid: "nav-settings" },
];

export default function AppShell() {
  const [online, setOnline] = useState(false);
  const [model, setModel] = useState("");

  useEffect(() => {
    let alive = true;
    const ping = async () => {
      try {
        const h = await health();
        if (!alive) return;
        setOnline(h.llm_configured);
        setModel(h.model);
      } catch {
        if (alive) setOnline(false);
      }
    };
    ping();
    const id = setInterval(ping, 15000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="min-h-screen flex flex-col">
      <div className="nova-noise" aria-hidden />

      {/* System-tray style header */}
      <header className="fixed top-0 inset-x-0 z-40 h-14 flex items-center justify-between px-6 md:px-10 nova-glass"
        data-testid="app-header">
        <div className="flex items-center gap-3">
          <div
            className="w-6 h-6 rounded-full"
            style={{
              background:
                "radial-gradient(circle at 30% 30%, #F43F5E 0%, #9D4CDD 50%, #3B82F6 100%)",
              boxShadow: "0 0 18px rgba(244,63,94,0.6)",
            }}
            aria-hidden
          />
          <span className="font-display text-xl font-bold tracking-tight">Nova</span>
          <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-white/30 hidden sm:inline">
            personal ai
          </span>
        </div>

        <nav className="hidden md:flex items-center gap-1" data-testid="nav-primary">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              data-testid={item.testid}
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-md font-mono text-xs uppercase tracking-widest transition ${
                  isActive
                    ? "bg-white/10 text-white"
                    : "text-white/40 hover:text-white hover:bg-white/5"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-3" data-testid="connection-status">
          <motion.span
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: online ? "#10B981" : "#F43F5E" }}
            animate={{ opacity: [0.5, 1, 0.5] }}
            transition={{ duration: 2, repeat: Infinity }}
          />
          <span className="font-mono text-[10px] uppercase tracking-[0.25em] text-white/50">
            {online ? model?.split("-").slice(0, 3).join(" ") || "online" : "offline"}
          </span>
        </div>
      </header>
      <div className="nova-hairline fixed top-14 inset-x-0 z-40" aria-hidden />

      {/* Mobile nav bar */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 z-40 nova-glass border-t border-white/10 flex items-center justify-around py-2">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              `font-mono text-[10px] uppercase tracking-widest px-2 py-1 rounded ${
                isActive ? "text-white bg-white/10" : "text-white/40"
              }`
            }
          >
            {item.label.slice(0, 4)}
          </NavLink>
        ))}
      </nav>

      <main className="pt-14 pb-20 md:pb-8 flex-1 flex flex-col">
        <Outlet />
      </main>
    </div>
  );
}
