"""
Nova - Personal AI Assistant Backend
FastAPI + MongoDB + Claude (Sonnet 4.5) via Emergent Universal Key
MCP-style tool hub: Claude emits <tool_call>{...}</tool_call> blocks; server
executes tool and feeds result back until a plain text answer is produced.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import quote, quote_plus

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.cors import CORSMiddleware

from emergentintegrations.llm.chat import LlmChat, UserMessage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"

app = FastAPI(title="Nova Assistant")
api = APIRouter(prefix="/api")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("nova")


# ---------------------------------------------------------------------------
# MCP tool registry
# ---------------------------------------------------------------------------
TOOL_META: List[Dict[str, Any]] = []
TOOLS: Dict[str, Any] = {}


def tool(name: str, description: str, args_schema: Dict[str, str], mocked: bool = False, category: str = "general"):
    def wrapper(fn):
        TOOL_META.append(
            {
                "name": name,
                "description": description,
                "args": args_schema,
                "mocked": mocked,
                "enabled": True,
                "category": category,
            }
        )
        TOOLS[name] = fn
        return fn
    return wrapper


# --- Time / date -----------------------------------------------------------
@tool("get_time", "Get the current date and time (UTC ISO format).", {}, category="time")
async def _get_time(_):
    return datetime.now(timezone.utc).isoformat()


@tool(
    "datetime_convert",
    "Add/subtract time to a datetime, or convert between timezones. offset_hours can be +/- integer.",
    {"base_iso": "optional ISO datetime (defaults to now)", "offset_hours": "number, optional"},
    category="time",
)
async def _datetime_convert(args):
    base_iso = args.get("base_iso")
    try:
        base = datetime.fromisoformat(base_iso) if base_iso else datetime.now(timezone.utc)
    except Exception:
        base = datetime.now(timezone.utc)
    offset = float(args.get("offset_hours") or 0)
    result = base + timedelta(hours=offset)
    return json.dumps({"input": base.isoformat(), "offset_hours": offset, "result": result.isoformat()})


# --- Weather (REAL, free, no API key required via Open-Meteo) -------------
@tool(
    "get_weather",
    "Get current weather + next 24h forecast for a city. Uses free Open-Meteo API (no API key).",
    {"city": "string, required — city name"},
    category="info",
)
async def _get_weather(args):
    city = (args.get("city") or "").strip()
    if not city:
        return json.dumps({"error": "city is required"})
    async with httpx.AsyncClient(timeout=10) as c:
        geo = await c.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "en", "format": "json"},
        )
        g = geo.json()
        if not g.get("results"):
            return json.dumps({"error": f"could not find city '{city}'"})
        loc = g["results"][0]
        lat, lon = loc["latitude"], loc["longitude"]
        wx = await c.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
                "hourly": "temperature_2m,precipitation_probability",
                "forecast_days": 2,
                "timezone": "auto",
            },
        )
        w = wx.json()
    codes = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Fog", 48: "Rime fog", 51: "Light drizzle", 61: "Rain", 71: "Snow",
        80: "Rain showers", 95: "Thunderstorm",
    }
    cur = w.get("current", {})
    return json.dumps({
        "city": loc.get("name"),
        "country": loc.get("country"),
        "latitude": lat,
        "longitude": lon,
        "temperature_c": cur.get("temperature_2m"),
        "feels_like_c": cur.get("apparent_temperature"),
        "humidity": cur.get("relative_humidity_2m"),
        "wind_kmh": cur.get("wind_speed_10m"),
        "precipitation_mm": cur.get("precipitation"),
        "condition": codes.get(cur.get("weather_code"), "Unknown"),
        "source": "open-meteo (live)",
    })


# --- Web search (still mocked until key) + real Wikipedia search -----------
@tool(
    "web_search",
    "Search the web. Currently MOCKED — swap for Serper/Brave with API key.",
    {"query": "string, required"},
    mocked=True,
    category="info",
)
async def _web_search(args):
    q = args.get("query", "")
    return json.dumps({"query": q, "results": [
        {"title": f"Sample result 1 for '{q}'", "url": "https://example.com/a", "snippet": "Sample snippet A"},
        {"title": f"Sample result 2 for '{q}'", "url": "https://example.com/b", "snippet": "Sample snippet B"},
    ], "source": "mock"})


@tool(
    "wikipedia_search",
    "Search Wikipedia and return the top summary. Free, no API key needed.",
    {"query": "string, required"},
    category="info",
)
async def _wikipedia_search(args):
    q = (args.get("query") or "").strip()
    if not q:
        return json.dumps({"error": "query required"})
    async with httpx.AsyncClient(
        timeout=10,
        follow_redirects=True,
        headers={"User-Agent": "NovaBot/1.0 (https://nova.example.com; contact@example.com)"},
    ) as c:
        r = await c.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "query", "format": "json", "list": "search", "srsearch": q, "srlimit": 3},
        )
        data = r.json()
        hits = data.get("query", {}).get("search", [])
        if not hits:
            return json.dumps({"query": q, "results": []})
        top_title = hits[0]["title"]
        summ = await c.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(top_title, safe='')}")
        s = summ.json() if summ.status_code == 200 else {}
    return json.dumps({
        "query": q,
        "title": s.get("title") or top_title,
        "extract": s.get("extract", "")[:1200],
        "url": s.get("content_urls", {}).get("desktop", {}).get("page"),
        "related": [h["title"] for h in hits[1:]],
    })


# --- URL fetch / scrape ----------------------------------------------------
@tool(
    "fetch_url",
    "Fetch a URL and return its readable text (HTML is stripped, first 4000 chars).",
    {"url": "string, required"},
    category="info",
)
async def _fetch_url(args):
    url = (args.get("url") or "").strip()
    if not url.startswith(("http://", "https://")):
        return json.dumps({"error": "url must start with http:// or https://"})
    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=True, headers={"User-Agent": "NovaBot/1.0"}) as c:
            r = await c.get(url)
            content_type = r.headers.get("content-type", "")
            if "html" in content_type:
                soup = BeautifulSoup(r.text, "lxml")
                for t in soup(["script", "style", "noscript"]):
                    t.decompose()
                text = " ".join(soup.get_text(separator=" ").split())
            else:
                text = r.text
        return json.dumps({"url": url, "title": _extract_title(r.text if "html" in content_type else ""), "text": text[:4000]})
    except Exception as e:
        return json.dumps({"error": str(e)})


def _extract_title(html: str) -> str:
    try:
        soup = BeautifulSoup(html, "lxml")
        return (soup.title.string or "").strip() if soup.title else ""
    except Exception:
        return ""


# --- Calculator ------------------------------------------------------------
_SAFE_MATH = {k: getattr(math, k) for k in ("pi", "e", "sqrt", "log", "log10", "sin", "cos", "tan", "asin", "acos", "atan", "exp", "floor", "ceil", "fabs", "pow")}
_SAFE_MATH["abs"] = abs
_SAFE_MATH["round"] = round


@tool(
    "calculator",
    "Evaluate a math expression (supports +,-,*,/,**,sqrt,log,sin,cos,pi,e, etc.).",
    {"expression": "string, required"},
    category="utility",
)
async def _calculator(args):
    expr = (args.get("expression") or "").strip()
    if not expr:
        return json.dumps({"error": "expression required"})
    if re.search(r"[A-Za-z_]+\s*\(", expr):
        # only allow whitelisted function names
        for fn in re.findall(r"([A-Za-z_]+)\s*\(", expr):
            if fn not in _SAFE_MATH:
                return json.dumps({"error": f"function '{fn}' not allowed"})
    try:
        val = eval(expr, {"__builtins__": {}}, _SAFE_MATH)  # noqa: S307
        return json.dumps({"expression": expr, "result": val})
    except Exception as e:
        return json.dumps({"error": str(e)})


# --- Notes -----------------------------------------------------------------
@tool(
    "create_note",
    "Save a note with an optional title. Returns the stored note.",
    {"title": "string, optional", "content": "string, required"},
    category="productivity",
)
async def _create_note(args):
    content = (args.get("content") or "").strip()
    if not content:
        return json.dumps({"error": "content required"})
    doc = {
        "id": str(uuid.uuid4()),
        "title": (args.get("title") or content[:32]).strip(),
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.notes.insert_one(dict(doc))
    return json.dumps({"ok": True, "note": doc})


@tool(
    "list_notes",
    "List recent notes. Optional keyword filter.",
    {"query": "string, optional"},
    category="productivity",
)
async def _list_notes(args):
    q = (args.get("query") or "").lower()
    notes = await db.notes.find({}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
    if q:
        notes = [n for n in notes if q in (n.get("content", "") + n.get("title", "")).lower()]
    return json.dumps({"count": len(notes), "notes": notes[:10]})


@tool(
    "delete_note",
    "Delete a note by id.",
    {"id": "string, required"},
    category="productivity",
)
async def _delete_note(args):
    nid = args.get("id") or ""
    res = await db.notes.delete_one({"id": nid})
    return json.dumps({"deleted": res.deleted_count})


# --- Memory ----------------------------------------------------------------
@tool(
    "save_memory",
    "Save a long-term memory about the user (preference/fact).",
    {"content": "string, required"},
    category="memory",
)
async def _save_memory(args):
    content = (args.get("content") or "").strip()
    if not content:
        return json.dumps({"ok": False, "error": "content required"})
    doc = {"id": str(uuid.uuid4()), "content": content, "created_at": datetime.now(timezone.utc).isoformat()}
    await db.memories.insert_one(dict(doc))
    return json.dumps({"ok": True, "memory": doc})


@tool(
    "recall_memory",
    "Recall memories matching a keyword.",
    {"query": "string, optional"},
    category="memory",
)
async def _recall_memory(args):
    q = (args.get("query") or "").strip().lower()
    mems = await db.memories.find({}, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    if q:
        mems = [m for m in mems if q in m.get("content", "").lower()]
    return json.dumps({"query": q, "count": len(mems), "memories": mems[:10]})


@tool(
    "list_capabilities",
    "List all tools (capabilities) this assistant has.",
    {},
    category="meta",
)
async def _list_capabilities(_):
    return json.dumps([{"name": t["name"], "description": t["description"], "mocked": t["mocked"], "category": t["category"]} for t in TOOL_META])


# ---------------------------------------------------------------------------
# System prompt & tool loop
# ---------------------------------------------------------------------------
def build_system_prompt(memories_preview: str) -> str:
    tools_doc = "\n".join(
        f"- {t['name']}({', '.join(t['args'].keys()) or 'no args'}): {t['description']}"
        + (" [MOCKED]" if t["mocked"] else "")
        for t in TOOL_META
    )
    return f"""You are Nova, a warm, concise personal AI assistant with the power of an MCP tool server.
You sound like Google Assistant — helpful, friendly, to the point (2–5 sentences unless asked).

You have access to these MCP tools:
{tools_doc}

TOOL-USE PROTOCOL (strict):
- When a tool would help, respond with ONLY this block on its own:
  <tool_call>{{"name": "<tool_name>", "args": {{...}}}}</tool_call>
- Wait for a message starting with `TOOL_RESULT <tool_name>:` then continue.
- You may chain up to 4 tool calls per user turn. Prefer fewer.
- After your final tool result, answer in plain friendly language.

WHEN TO CALL WHICH TOOL:
- Weather question → get_weather (live Open-Meteo)
- "What is X" / facts / people / concepts → wikipedia_search
- Summarize / read a specific URL → fetch_url
- Math → calculator
- Current date/time or timezone math → get_time / datetime_convert
- "Make a note" / "note this" → create_note. "Show my notes" → list_notes.
- "Remember that I..." → save_memory. About-me questions → recall_memory.
- "What can you do" → list_capabilities.

RESPONSE STYLE:
- Warm, terse, never robotic.
- If a tool failed, say so plainly and suggest a fix.
- After your final answer, on a NEW line, emit up to 3 useful follow-up actions as:
  <suggest>["short action 1", "short action 2", "short action 3"]</suggest>
  Examples: "Save this as a note", "Get weather for tomorrow", "Summarize this article".
  Omit <suggest> if no meaningful follow-ups.

MEMORY CONTEXT (most recent saved memories about the user):
{memories_preview or "(none yet)"}
"""


TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
SUGGEST_RE = re.compile(r"<suggest>\s*(\[.*?\])\s*</suggest>", re.DOTALL)


async def execute_tool(name: str, args: Dict[str, Any]) -> str:
    fn = TOOLS.get(name)
    if not fn:
        return json.dumps({"error": f"unknown tool '{name}'"})
    try:
        result = await fn(args or {})
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:
        logger.exception("tool error: %s", name)
        return json.dumps({"error": str(e)})


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message: str
    session_id: Optional[str] = None
    conversation_id: Optional[str] = None


class ToolTrace(BaseModel):
    name: str
    args: Dict[str, Any]
    result: str


class ChatResponse(BaseModel):
    reply: str
    session_id: str
    conversation_id: str
    tool_trace: List[ToolTrace] = []
    suggestions: List[str] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def load_memories_preview(limit: int = 8) -> str:
    mems = await db.memories.find({}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return "\n".join(f"- {m['content']}" for m in mems) if mems else ""


async def ensure_conversation(cid: Optional[str], first_message: str) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    if cid:
        conv = await db.conversations.find_one({"id": cid}, {"_id": 0})
        if conv:
            return conv
    nid = cid or str(uuid.uuid4())
    title = (first_message[:48] + "…") if len(first_message) > 48 else (first_message or "New conversation")
    conv = {"id": nid, "title": title, "created_at": now, "updated_at": now, "message_count": 0}
    await db.conversations.insert_one(dict(conv))
    conv.pop("_id", None)
    return conv


async def append_message(conv_id: str, role: str, content: str, tool_trace=None, suggestions=None):
    msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conv_id,
        "role": role,
        "content": content,
        "tool_trace": tool_trace or None,
        "suggestions": suggestions or None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.messages.insert_one(dict(msg))
    await db.conversations.update_one(
        {"id": conv_id},
        {"$set": {"updated_at": msg["created_at"]}, "$inc": {"message_count": 1}},
    )
    msg.pop("_id", None)
    return msg


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@api.get("/")
async def root():
    return {"app": "Nova Assistant", "status": "ok"}


@api.get("/health")
async def health():
    return {"status": "ok", "llm_configured": bool(EMERGENT_LLM_KEY), "model": CLAUDE_MODEL, "tools": len(TOOL_META)}


@api.get("/tools")
async def list_tools():
    return {"tools": TOOL_META}


@api.get("/mcp/manifest")
async def mcp_manifest():
    """MCP-style manifest — advertises all tools with JSON schemas."""
    return {
        "protocol": "mcp-like/1.0",
        "server": "nova",
        "version": "1.0.0",
        "tools": [
            {
                "name": t["name"],
                "description": t["description"],
                "category": t["category"],
                "mocked": t["mocked"],
                "input_schema": {
                    "type": "object",
                    "properties": {k: {"type": "string", "description": v} for k, v in t["args"].items()},
                    "required": [k for k, v in t["args"].items() if "required" in v.lower()],
                },
            }
            for t in TOOL_META
        ],
    }


@api.post("/mcp/call")
async def mcp_call(body: Dict[str, Any]):
    """Directly invoke an MCP tool (for debugging / raw API access)."""
    name = body.get("name")
    args = body.get("args") or {}
    if not name or name not in TOOLS:
        raise HTTPException(404, f"unknown tool '{name}'")
    result = await execute_tool(name, args)
    try:
        parsed = json.loads(result)
    except Exception:
        parsed = result
    return {"name": name, "args": args, "result": parsed}


@api.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "EMERGENT_LLM_KEY not configured")
    if not req.message.strip():
        raise HTTPException(400, "message is required")

    conv = await ensure_conversation(req.conversation_id, req.message)
    session_id = req.session_id or conv["id"]

    history = await db.messages.find({"conversation_id": conv["id"]}, {"_id": 0}).sort("created_at", 1).to_list(200)
    memories_preview = await load_memories_preview()
    system_prompt = build_system_prompt(memories_preview)

    # Compose recap of prior turns for context (avoids replay issues with LlmChat)
    if history:
        recap_lines = []
        for m in history[-10:]:
            tag = "User" if m["role"] == "user" else "Nova"
            recap_lines.append(f"{tag}: {m['content']}")
        recap = "Prior conversation (context only, do NOT respond to these):\n" + "\n".join(recap_lines)
        system_prompt = system_prompt + "\n\n" + recap

    chat_client = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=system_prompt,
    ).with_model("anthropic", CLAUDE_MODEL)

    await append_message(conv["id"], "user", req.message)

    trace: List[Dict[str, Any]] = []
    current_input = req.message
    final_reply = ""
    suggestions: List[str] = []

    for step in range(5):
        response = await chat_client.send_message(UserMessage(text=current_input))
        text = response if isinstance(response, str) else str(response)

        # Extract suggestion block regardless
        sm = SUGGEST_RE.search(text)
        if sm:
            try:
                suggestions = [s for s in json.loads(sm.group(1)) if isinstance(s, str)][:3]
            except Exception:
                suggestions = []
            text = SUGGEST_RE.sub("", text).strip()

        match = TOOL_CALL_RE.search(text)
        if not match:
            final_reply = text.strip()
            break

        try:
            payload = json.loads(match.group(1))
            tool_name = payload.get("name") or ""
            tool_args = payload.get("args") or {}
        except json.JSONDecodeError:
            final_reply = "Sorry — I tried to call a tool but produced malformed JSON."
            break

        tool_result = await execute_tool(tool_name, tool_args)
        trace.append({"name": tool_name, "args": tool_args, "result": tool_result})
        current_input = f"TOOL_RESULT {tool_name}: {tool_result}"

        if step == 4:
            current_input += "\n\nTool-call limit reached. Provide your final answer now in plain text."

    if not final_reply:
        final_reply = "I wasn't able to produce a final answer. Please try again."

    await append_message(conv["id"], "assistant", final_reply, trace, suggestions)

    return ChatResponse(
        reply=final_reply,
        session_id=session_id,
        conversation_id=conv["id"],
        tool_trace=[ToolTrace(**t) for t in trace],
        suggestions=suggestions,
    )


@api.get("/conversations")
async def list_conversations():
    convs = await db.conversations.find({}, {"_id": 0}).sort("updated_at", -1).to_list(200)
    return {"conversations": convs}


@api.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    conv = await db.conversations.find_one({"id": conv_id}, {"_id": 0})
    if not conv:
        raise HTTPException(404, "conversation not found")
    messages = await db.messages.find({"conversation_id": conv_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return {"conversation": conv, "messages": messages}


@api.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    await db.messages.delete_many({"conversation_id": conv_id})
    res = await db.conversations.delete_one({"id": conv_id})
    return {"deleted": res.deleted_count}


@api.get("/memories")
async def list_memories():
    mems = await db.memories.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"memories": mems}


@api.delete("/memories")
async def clear_memories():
    res = await db.memories.delete_many({})
    return {"deleted": res.deleted_count}


@api.delete("/memories/{mem_id}")
async def delete_memory(mem_id: str):
    res = await db.memories.delete_one({"id": mem_id})
    return {"deleted": res.deleted_count}


@api.get("/notes")
async def list_notes_ep():
    notes = await db.notes.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return {"notes": notes}


@api.delete("/notes/{nid}")
async def delete_note_ep(nid: str):
    res = await db.notes.delete_one({"id": nid})
    return {"deleted": res.deleted_count}


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def _shutdown():
    client.close()
