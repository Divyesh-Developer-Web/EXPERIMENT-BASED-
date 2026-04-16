# Nova — Personal AI Assistant · PRD

## Original problem statement
Build a personal AI assistant (Google-Assistant style) for PC with:
- 5-layer architecture (App Shell, Voice Pipeline, Brain, MCP Tools, External APIs)
- Voice orb with 4 animation states (Idle=purple breathing, Listening=green ripple, Thinking=blue rotating arc, Speaking=coral waveform)
- Optional text input; voice as primary modality
- Personal MCP server + external API tools
- Teach the user what each component is and how they interconnect
- Later user asked: "make it an AI Assistant with the power of MCP server" + PiP mode + suggestions

## Delivery
Full web app (React + FastAPI + MongoDB) served at the public preview URL.
Runs in any browser; Electron wrapper deferred.

## User personas
- **The builder** — a developer who wants to LEARN how a Jarvis/Google-Assistant stack is wired end-to-end.
- **The end user** — wants a voice-first personal assistant.

## Core requirements (static)
- Dark cinematic UI (not AI-slop). Fonts: Bricolage Grotesque + JetBrains Mono.
- Voice orb with 4 specified state animations/colors.
- MCP-style tool hub (Claude decides which tool to call).
- Conversation + memory persisted in MongoDB.
- Dedicated teaching/architecture page.
- Optional text input always available.

## Architecture implemented
**Backend (`/app/backend/server.py`)**
- FastAPI + Motor MongoDB + httpx + BeautifulSoup4
- `emergentintegrations.llm.chat.LlmChat` → Claude **claude-sonnet-4-5-20250929** via **EMERGENT_LLM_KEY**
- MCP-style tool loop: Claude emits `<tool_call>{"name","args"}</tool_call>`; server executes, feeds `TOOL_RESULT` back, up to 4 tool calls per turn
- `<suggest>[...]</suggest>` blocks parsed and returned as `suggestions` in every chat response
- **13 registered MCP tools** across 6 categories:
  - time: `get_time`, `datetime_convert`
  - info: `get_weather` (LIVE · Open-Meteo · free, no key), `web_search` (MOCKED), `wikipedia_search` (LIVE), `fetch_url` (LIVE · httpx + BeautifulSoup)
  - utility: `calculator`
  - productivity: `create_note`, `list_notes`, `delete_note`
  - memory: `save_memory`, `recall_memory`
  - meta: `list_capabilities`
- Collections: `conversations`, `messages`, `memories`, `notes`
- Endpoints: `/api/health`, `/api/tools`, `/api/mcp/manifest` (spec-style), `/api/mcp/call` (direct tool invoke), `/api/chat`, `/api/conversations` (list/get/delete), `/api/memories` (list/delete/clear), `/api/notes` (list/delete)

**Frontend (`/app/frontend/src`)**
- React 19 + framer-motion + lucide-react
- Routes: `/` Assistant · `/tools` · `/history` · `/architecture` · `/settings`
- `VoiceOrb` component with 4 exact states (framer-motion, 60fps)
- `useSpeech` hook (Web Speech API SpeechRecognition + SpeechSynthesis)
- **Picture-in-Picture (Document PiP API)** floating mini-Nova — orb + quick input chat, works in Chrome 116+/Edge
- **Suggestion chips** under every assistant reply (follow-up actions Claude proposes)
- **Notes section** on Tools page + tool category grouping
- Cinematic noise overlay, glassmorphism panels, asymmetric layout

## What's been implemented

### Iteration 1 (2026-01)
- Full 5-layer stack working end-to-end
- Voice orb with 4 animation states
- Push-to-talk STT + TTS via browser
- Claude Sonnet 4.5 brain with MCP tool-call loop
- 6 initial MCP tools
- Conversation + memory in MongoDB
- Teaching/Architecture page
- Tools, History, Settings pages
- **Testing: 40/41 backend assertions passing**

### Iteration 2 (2026-01) — MCP power-up
- Expanded to **13 tools**; swapped `get_weather` from mock → LIVE (Open-Meteo)
- New real tools: `wikipedia_search`, `fetch_url`, `calculator`, `create_note`/`list_notes`/`delete_note`, `datetime_convert`
- `/api/mcp/manifest` and `/api/mcp/call` endpoints (MCP-spec style)
- Suggestions returned with every chat response
- Picture-in-Picture floating mini-Nova
- Suggestion chips in chat UI
- Notes section on Tools page
- **Testing: 66/66 backend assertions passing**

## Known limitations
- `web_search` still MOCKED (needs Serper.dev or Brave key)
- No true wake-word — push-to-talk mic instead. Phrase saved in Settings.
- Calendar / Email / PC file access / Spotify / Smart-home — not possible from a browser sandbox. Requires Electron wrapper or a local companion agent.

## Prioritized backlog
- **P1** — Wire Serper.dev or Brave Search (user provides key)
- **P1** — Sentiment-colored orb (tint accent by user emotion)
- **P2** — Graphical artifact modal (charts/tables in pop-up when tool returns structured data)
- **P2** — Google Calendar + Gmail via Emergent-managed Google Auth
- **P2** — Vector-embedding memory (ChromaDB or OpenAI embeddings) for semantic recall
- **P3** — Electron wrapper scaffold + Picovoice wake-word ("Hey Nova") + file/app permission UI + local OS tools (MCP stdio servers from awesome-mcp-servers)
- **P3** — "Nova Companion" Python mini-agent option (alternative to Electron)
- **P3** — Streaming responses, proactive morning briefing, local-LLM fallback (Ollama)

## Next tasks
1. Ask user for OpenWeatherMap key if they want more detailed weather, or Serper/Brave key for live web search
2. Decide direction for desktop access: Electron wrapper vs local Python companion
3. Add sentiment-coloured orb
