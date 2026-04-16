import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import AppShell from "@/components/AppShell";
import AssistantView from "@/views/AssistantView";
import ToolsView from "@/views/ToolsView";
import HistoryView from "@/views/HistoryView";
import ArchitectureView from "@/views/ArchitectureView";
import SettingsView from "@/views/SettingsView";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/" element={<AssistantView />} />
            <Route path="/tools" element={<ToolsView />} />
            <Route path="/history" element={<HistoryView />} />
            <Route path="/architecture" element={<ArchitectureView />} />
            <Route path="/settings" element={<SettingsView />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
