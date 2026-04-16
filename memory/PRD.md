# Nova — Personal AI Assistant · PRD

## Original problem statement
Build a personal AI assistant (Google-Assistant style) for PC with:
- 5-layer architecture (App Shell, Voice Pipeline, Brain, MCP Tools, External APIs)
- Voice orb with 4 animation states (Idle=purple breathing, Listening=green ripple, Thinking=blue rotating arc, Speaking=coral waveform)
- Optional text input; voice as primary modality
- Personal MCP server + external API tools
- Teach the user what each component is, why we use it, and how they interconnect

## Delivery chosen
Full web app (React + FastAPI + MongoDB) served at the public preview URL.
Reasoning: runs instantly in the browser; the user can later wrap the same UI in Electron/Tauri for a `.exe`.

## User personas
- **The builder** — a developer who wants to LEARN how a Jarvis/Google-Assistant stack is wired end-to-end.
- **The end user** — anyone wanting a voice-first personal assistant on their PC.

## Core requirements (static)
- Dark cinematic UI (not AI-slop). Fonts: Bricolage Grotesque + JetBrains Mono.
- Voice orb MUST have exactly the 4 specified state animations/colors.
- MCP-style tool hub (Claude decides which tool to call).
- Conversation + memory persisted in MongoDB.
- Dedicated teaching/architecture page.
- Optional text input always available.

## Architecture implemented
**Backend (`/app/backend/server.py`)**
- FastAPI + Motor MongoDB
- `emergentintegrations.llm.chat.LlmChat` → Claude **claude-sonnet-4-5-20250929** via **EMERGENT_LLM_KEY**
- MCP-style tool loop: Claude emits `<tool_call>{"name","args"}</tool_call>`; server executes, feeds `TOOL_RESULT` back, up to 3 tool calls per turn
- Tools: `get_time`, `get_weather` (mock), `web_search` (mock), `save_memory`, `recall_memory`, `list_capabilities`
- Collections: `conversations`, `messages`, `memories`
- Endpoints: `/api/health`, `/api/tools`, `/api/chat`, `/api/conversations` (list/get/delete), `/api/memories` (list/delete/clear)

**Frontend (`/app/frontend/src`)**
- React 19 + framer-motion + lucide-react
- Routes: `/` Assistant · `/tools` · `/history` · `/architecture` · `/settings`
- `VoiceOrb` component with 4 exact states
- `useSpeech` hook wrapping Web Speech API (SpeechRecognition + SpeechSynthesis)
- Cinematic noise overlay, glassmorphism panels, asymmetric layout

## What's been implemented (2026-01)
- ✅ Full 5-layer stack working end-to-end
- ✅ Voice orb with 4 animation states (framer-motion, 60fps)
- ✅ Push-to-talk STT + TTS via browser
- ✅ Claude Sonnet 4.5 brain with MCP tool-call loop
- ✅ 6 MCP tools (2 mocked, 4 live)
- ✅ Conversation + semantic-ish memory in MongoDB
- ✅ Teaching/Architecture page with orb demo + bento grid
- ✅ Tools, History, Settings pages
- ✅ Tested: 40/41 backend assertions passing

## Known limitations / notes
- No true wake-word ("Hey Nova") — requires Electron + Picovoice; UI has a push-to-talk mic instead. Wake-word phrase stored in Settings for future use.
- `get_weather` and `web_search` are MOCKED — return sample JSON. Swap for OpenWeatherMap + Serper/Brave keys when ready.
- Calendar / Email / PC control / Smart-home tools are NOT included (require OS/OAuth access and cannot run from a web backend).

## Prioritized backlog
- **P1** — Replace mocked `get_weather` with OpenWeatherMap (user provides API key)
- **P1** — Replace mocked `web_search` with Serper.dev or Brave Search
- **P2** — Google Calendar + Gmail MCP tools (via Emergent-managed Google Auth)
- **P2** — Vector-embedding memory (ChromaDB or pgvector) for semantic recall
- **P2** — Streaming responses for faster perceived latency
- **P3** — Electron wrapper folder for `.exe` builds + Picovoice wake-word
- **P3** — Proactive morning briefing (scheduled task)
- **P3** — Local-LLM fallback via Ollama

## Next tasks
1. Ask user which real API keys they want to plug in first (Weather / Search)
2. Build Electron wrapper scaffold once core is stable
