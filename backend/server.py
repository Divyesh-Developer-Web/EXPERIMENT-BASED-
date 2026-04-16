"""
Nova - Personal AI Assistant Backend
FastAPI + MongoDB + Claude (Sonnet 4.5) via Emergent Universal Key
MCP-style tool hub: Claude emits <tool_call>{...}</tool_call> blocks; server
executes tool and feeds result back until a plain text answer is produced.
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, ConfigDict, Field
from starlette.middleware.cors import CORSMiddleware

# LLM integration
from emergentintegrations.llm.chat import LlmChat, UserMessage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
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
# MCP tools
# Each tool is a function (async or sync) registered in TOOLS.
# ---------------------------------------------------------------------------
TOOL_META: List[Dict[str, Any]] = []
TOOLS: Dict[str, Any] = {}


def tool(name: str, description: str, args_schema: Dict[str, str], mocked: bool = False):
    """Decorator to register an MCP tool."""

    def wrapper(fn):
        TOOL_META.append(
            {
                "name": name,
                "description": description,
                "args": args_schema,
                "mocked": mocked,
                "enabled": True,
            }
        )
        TOOLS[name] = fn
        return fn

    return wrapper


@tool(
    name="get_time",
    description="Get the current date and time in ISO format (UTC).",
    args_schema={},
)
async def _get_time(_: Dict[str, Any]) -> str:
    return datetime.now(timezone.utc).isoformat()


@tool(
    name="get_weather",
    description="Get current weather for a city. (Mocked — returns sample data.)",
    args_schema={"city": "string, required"},
    mocked=True,
)
async def _get_weather(args: Dict[str, Any]) -> str:
    city = args.get("city", "Nagpur")
    # Deterministic mock so responses feel real
    sample = {
        "city": city,
        "temperature_c": 29,
        "condition": "Partly cloudy",
        "humidity": 58,
        "wind_kmh": 12,
        "source": "mock",
    }
    return json.dumps(sample)


@tool(
    name="web_search",
    description="Search the web and return top 3 results. (Mocked — returns sample results.)",
    args_schema={"query": "string, required"},
    mocked=True,
)
async def _web_search(args: Dict[str, Any]) -> str:
    q = args.get("query", "")
    results = [
        {"title": f"Result 1 for '{q}'", "snippet": "Sample snippet A", "url": "https://example.com/a"},
        {"title": f"Result 2 for '{q}'", "snippet": "Sample snippet B", "url": "https://example.com/b"},
        {"title": f"Result 3 for '{q}'", "snippet": "Sample snippet C", "url": "https://example.com/c"},
    ]
    return json.dumps({"query": q, "results": results, "source": "mock"})


@tool(
    name="save_memory",
    description="Save a long-term memory note about the user (preference, fact, project).",
    args_schema={"content": "string, required — the fact/preference to remember"},
)
async def _save_memory(args: Dict[str, Any]) -> str:
    content = (args.get("content") or "").strip()
    if not content:
        return json.dumps({"ok": False, "error": "content is required"})
    doc = {
        "id": str(uuid.uuid4()),
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.memories.insert_one(doc)
    doc.pop("_id", None)
    return json.dumps({"ok": True, "memory": doc})


@tool(
    name="recall_memory",
    description="Recall memories matching a keyword. Returns matching stored memories.",
    args_schema={"query": "string, optional — keyword to search for"},
)
async def _recall_memory(args: Dict[str, Any]) -> str:
    query = (args.get("query") or "").strip()
    cursor = db.memories.find({}, {"_id": 0}).sort("created_at", -1).limit(50)
    memories = await cursor.to_list(50)
    if query:
        q = query.lower()
        memories = [m for m in memories if q in m.get("content", "").lower()]
    return json.dumps({"query": query, "count": len(memories), "memories": memories[:10]})


@tool(
    name="list_capabilities",
    description="List all tools (capabilities) this assistant has.",
    args_schema={},
)
async def _list_capabilities(_: Dict[str, Any]) -> str:
    return json.dumps([{"name": t["name"], "description": t["description"], "mocked": t["mocked"]} for t in TOOL_META])


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
def build_system_prompt(memories_preview: str) -> str:
    tools_doc = "\n".join(
        f"- {t['name']}({', '.join(t['args'].keys()) or 'no args'}): {t['description']}"
        + (" [MOCKED]" if t["mocked"] else "")
        for t in TOOL_META
    )
    return f"""You are Nova, a warm, concise personal AI assistant that lives on the user's PC.
You sound like Google Assistant — helpful, friendly, and to the point (2–4 sentences unless asked).

You have access to these MCP tools:
{tools_doc}

TOOL-USE PROTOCOL (strict):
- When you need a tool, respond with a SINGLE block on its own line:
  <tool_call>{{"name": "<tool_name>", "args": {{...}}}}</tool_call>
- Do not include anything else in a tool-call turn. Wait for the tool result.
- You will then receive a message that begins with `TOOL_RESULT <tool_name>:` followed by JSON.
- You may call up to 3 tools per user turn. After that, produce the final natural-language answer.
- When you have all info you need, just reply in plain friendly language (no tool tags).

MEMORY CONTEXT (most recent saved memories about the user):
{memories_preview or "(none yet)"}

Rules:
- If the user asks you to remember something, call save_memory.
- If the question might depend on past preferences, call recall_memory first.
- For weather, always call get_weather. For current events or facts you're unsure about, call web_search.
- Never invent tool names. Never wrap normal answers in tool_call tags.
"""


TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)


async def execute_tool(name: str, args: Dict[str, Any]) -> str:
    fn = TOOLS.get(name)
    if not fn:
        return json.dumps({"error": f"unknown tool '{name}'"})
    try:
        result = await fn(args or {})
        return result if isinstance(result, str) else json.dumps(result)
    except Exception as e:  # noqa: BLE001
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


class MessageModel(BaseModel):
    id: str
    role: str  # "user" | "assistant"
    content: str
    created_at: str
    tool_trace: Optional[List[ToolTrace]] = None


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def load_memories_preview(limit: int = 8) -> str:
    cursor = db.memories.find({}, {"_id": 0}).sort("created_at", -1).limit(limit)
    mems = await cursor.to_list(limit)
    if not mems:
        return ""
    return "\n".join(f"- {m['content']}" for m in mems)


async def ensure_conversation(conversation_id: Optional[str], first_message: str) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    if conversation_id:
        conv = await db.conversations.find_one({"id": conversation_id}, {"_id": 0})
        if conv:
            return conv
    new_id = conversation_id or str(uuid.uuid4())
    title = (first_message[:48] + "…") if len(first_message) > 48 else first_message
    conv = {
        "id": new_id,
        "title": title or "New conversation",
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
    }
    await db.conversations.insert_one(dict(conv))
    conv.pop("_id", None)
    return conv


async def append_message(conv_id: str, role: str, content: str, tool_trace: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    msg = {
        "id": str(uuid.uuid4()),
        "conversation_id": conv_id,
        "role": role,
        "content": content,
        "tool_trace": tool_trace or None,
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
    return {
        "status": "ok",
        "llm_configured": bool(EMERGENT_LLM_KEY),
        "model": CLAUDE_MODEL,
        "tools": len(TOOL_META),
    }


@api.get("/tools")
async def list_tools():
    return {"tools": TOOL_META}


@api.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not EMERGENT_LLM_KEY:
        raise HTTPException(500, "EMERGENT_LLM_KEY not configured")
    if not req.message.strip():
        raise HTTPException(400, "message is required")

    conv = await ensure_conversation(req.conversation_id, req.message)
    session_id = req.session_id or conv["id"]

    # Load history for this conversation to rebuild context
    history = await db.messages.find({"conversation_id": conv["id"]}, {"_id": 0}).sort("created_at", 1).to_list(200)

    memories_preview = await load_memories_preview()
    system_prompt = build_system_prompt(memories_preview)

    chat_client = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=system_prompt,
    ).with_model("anthropic", CLAUDE_MODEL)

    # Replay prior conversation turns so Claude has context
    for m in history:
        if m["role"] == "user":
            await chat_client.send_message(UserMessage(text=m["content"]))
            # We don't need the reply, we only want to push history.
            # However LlmChat enforces turn order; easiest is to skip replay and
            # prepend a compact recap in the first user message instead.
            break  # only the first loop is needed to avoid double-calls; actual recap below
    # Build a recap of prior turns (cheap + reliable)
    if history:
        recap_lines = []
        for m in history[-10:]:
            tag = "User" if m["role"] == "user" else "Nova"
            recap_lines.append(f"{tag}: {m['content']}")
        recap = "Prior conversation (for context only, do NOT respond to these):\n" + "\n".join(recap_lines)
        # Reset chat client to skip the replay hack above
        chat_client = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=session_id,
            system_message=system_prompt + "\n\n" + recap,
        ).with_model("anthropic", CLAUDE_MODEL)

    # Persist user message
    await append_message(conv["id"], "user", req.message)

    trace: List[Dict[str, Any]] = []
    current_input = req.message
    final_reply = ""

    for step in range(4):  # up to 3 tool calls + 1 final text
        response = await chat_client.send_message(UserMessage(text=current_input))
        text = response if isinstance(response, str) else str(response)

        match = TOOL_CALL_RE.search(text)
        if not match:
            final_reply = text.strip()
            break

        try:
            payload = json.loads(match.group(1))
            tool_name = payload.get("name") or ""
            tool_args = payload.get("args") or {}
        except json.JSONDecodeError:
            final_reply = "Sorry, I tried to use a tool but produced malformed JSON."
            break

        tool_result = await execute_tool(tool_name, tool_args)
        trace.append({"name": tool_name, "args": tool_args, "result": tool_result})
        current_input = f"TOOL_RESULT {tool_name}: {tool_result}"

        if step == 3:
            # Force final answer
            current_input += "\n\nYou have reached the tool call limit. Provide your final answer now in plain text."

    if not final_reply:
        final_reply = "I wasn't able to produce a final answer. Please try again."

    await append_message(conv["id"], "assistant", final_reply, trace)

    return ChatResponse(
        reply=final_reply,
        session_id=session_id,
        conversation_id=conv["id"],
        tool_trace=[ToolTrace(**t) for t in trace],
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
