"""
Backend tests for Nova Assistant.
Exercises the full API surface against the public REACT_APP_BACKEND_URL.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests


def load_public_url() -> str:
    env_path = Path("/app/frontend/.env")
    for line in env_path.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


BASE = load_public_url().rstrip("/")
API = f"{BASE}/api"


class Tester:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures: List[Dict[str, Any]] = []

    def check(self, name: str, cond: bool, detail: str = ""):
        if cond:
            self.passed += 1
            print(f"PASS  {name}")
        else:
            self.failed += 1
            self.failures.append({"test": name, "detail": detail})
            print(f"FAIL  {name} :: {detail}")

    def summary(self) -> int:
        total = self.passed + self.failed
        print(f"\n====== {self.passed}/{total} passed ======")
        if self.failures:
            print("Failures:")
            for f in self.failures:
                print(" -", f)
        return 0 if self.failed == 0 else 1


t = Tester()


def get(path: str, **kw) -> requests.Response:
    return requests.get(f"{API}{path}", timeout=60, **kw)


def post(path: str, json_body: Dict[str, Any], **kw) -> requests.Response:
    return requests.post(f"{API}{path}", json=json_body, timeout=120, **kw)


def delete(path: str, **kw) -> requests.Response:
    return requests.delete(f"{API}{path}", timeout=60, **kw)


def tool_names(trace: List[Dict[str, Any]]) -> List[str]:
    return [x.get("name") for x in (trace or [])]


def trace_has_tool(trace: List[Dict[str, Any]], name: str) -> bool:
    return name in tool_names(trace)


def main() -> int:
    print(f"Target: {API}\n")

    # Clean slate for memories
    try:
        delete("/memories")
    except Exception as e:
        print(f"(warn) unable to clear memories: {e}")

    # 1) Health
    r = get("/health")
    t.check("GET /api/health 200", r.status_code == 200, f"got {r.status_code}: {r.text[:200]}")
    if r.status_code == 200:
        data = r.json()
        t.check("health.llm_configured true", data.get("llm_configured") is True, str(data))
        t.check(
            "health.model == claude-sonnet-4-5-20250929",
            data.get("model") == "claude-sonnet-4-5-20250929",
            str(data),
        )
        t.check("health.tools >= 6", isinstance(data.get("tools"), int) and data["tools"] >= 6, str(data))

    # 2) Tools
    r = get("/tools")
    t.check("GET /api/tools 200", r.status_code == 200, r.text[:200])
    expected_tools = {"get_time", "get_weather", "web_search", "save_memory", "recall_memory", "list_capabilities"}
    if r.status_code == 200:
        names = {tm["name"] for tm in r.json().get("tools", [])}
        missing = expected_tools - names
        t.check("tools contains all required", not missing, f"missing={missing}; got={names}")

    # 3) Chat: empty message -> 400
    r = post("/chat", {"message": "   "})
    t.check("POST /api/chat empty -> 400", r.status_code == 400, f"got {r.status_code}: {r.text[:200]}")

    # 4) Chat: time
    r = post("/chat", {"message": "What time is it?"})
    t.check("POST /api/chat time 200", r.status_code == 200, r.text[:300])
    time_conv_id = None
    if r.status_code == 200:
        data = r.json()
        t.check("chat time has reply", bool(data.get("reply")), str(data)[:300])
        t.check("chat time has session_id", bool(data.get("session_id")), str(data)[:200])
        t.check("chat time has conversation_id", bool(data.get("conversation_id")), str(data)[:200])
        time_conv_id = data.get("conversation_id")
        # Per context note: LLM may answer without calling get_time; be lenient.
        print(f"  (info) time tool_trace tools: {tool_names(data.get('tool_trace', []))}")

    # 5) Chat: weather -> must call get_weather
    r = post("/chat", {"message": "What is the weather in Nagpur?"})
    t.check("POST /api/chat weather 200", r.status_code == 200, r.text[:300])
    weather_conv_id = None
    if r.status_code == 200:
        data = r.json()
        weather_conv_id = data.get("conversation_id")
        trace = data.get("tool_trace", [])
        t.check("weather tool_trace has get_weather", trace_has_tool(trace, "get_weather"), f"tools={tool_names(trace)}")
        # verify city arg
        gw = next((x for x in trace if x.get("name") == "get_weather"), None)
        if gw:
            city = (gw.get("args") or {}).get("city", "")
            t.check("get_weather.args.city mentions Nagpur", "nagpur" in city.lower(), f"args={gw.get('args')}")
        reply = (data.get("reply") or "").lower()
        t.check(
            "weather reply mentions weather/temp",
            any(k in reply for k in ["weather", "temperature", "cloud", "humid", "°c", "degrees", "nagpur"]),
            f"reply={reply[:200]}",
        )

    # 6) Chat: save_memory
    r = post("/chat", {"message": "Remember that I love cold brew coffee"})
    t.check("POST /api/chat save_memory 200", r.status_code == 200, r.text[:300])
    save_conv_id = None
    if r.status_code == 200:
        data = r.json()
        save_conv_id = data.get("conversation_id")
        trace = data.get("tool_trace", [])
        t.check("save_memory tool called", trace_has_tool(trace, "save_memory"), f"tools={tool_names(trace)}")

    # 7) GET /memories contains cold brew
    time.sleep(1)
    r = get("/memories")
    t.check("GET /api/memories 200", r.status_code == 200, r.text[:200])
    saved_mem_id: Optional[str] = None
    if r.status_code == 200:
        mems = r.json().get("memories", [])
        found = [m for m in mems if "cold brew" in (m.get("content") or "").lower()]
        t.check("memories contains 'cold brew'", bool(found), f"memories={[m.get('content') for m in mems]}")
        if found:
            saved_mem_id = found[0].get("id")

    # 8) Chat: recall
    r = post("/chat", {"message": "What do you know about me?"})
    t.check("POST /api/chat recall 200", r.status_code == 200, r.text[:300])
    if r.status_code == 200:
        data = r.json()
        trace = data.get("tool_trace", [])
        t.check("recall_memory tool called", trace_has_tool(trace, "recall_memory"), f"tools={tool_names(trace)}")
        reply = (data.get("reply") or "").lower()
        t.check("recall reply references cold brew", "cold brew" in reply, f"reply={reply[:300]}")

    # 9) Multi-turn with shared conversation_id
    r1 = post("/chat", {"message": "My favorite color is teal."})
    t.check("multi-turn #1 200", r1.status_code == 200, r1.text[:200])
    conv_id = r1.json().get("conversation_id") if r1.status_code == 200 else None
    if conv_id:
        r2 = post("/chat", {"message": "What color did I just mention?", "conversation_id": conv_id})
        t.check("multi-turn #2 200", r2.status_code == 200, r2.text[:200])
        if r2.status_code == 200:
            reply2 = (r2.json().get("reply") or "").lower()
            t.check("multi-turn context remembers teal", "teal" in reply2, f"reply={reply2[:300]}")
            t.check(
                "multi-turn reuses conversation_id",
                r2.json().get("conversation_id") == conv_id,
                f"got={r2.json().get('conversation_id')} expected={conv_id}",
            )

    # 10) List conversations
    r = get("/conversations")
    t.check("GET /api/conversations 200", r.status_code == 200, r.text[:200])
    conv_ids_seen: List[str] = []
    if r.status_code == 200:
        convs = r.json().get("conversations", [])
        conv_ids_seen = [c.get("id") for c in convs]
        t.check("conversations list non-empty", len(convs) > 0, f"count={len(convs)}")

    # 11) Get specific conversation with messages
    target_conv = conv_id or weather_conv_id or time_conv_id or (conv_ids_seen[0] if conv_ids_seen else None)
    if target_conv:
        r = get(f"/conversations/{target_conv}")
        t.check("GET /api/conversations/{id} 200", r.status_code == 200, r.text[:200])
        if r.status_code == 200:
            body = r.json()
            t.check("conversation object present", bool(body.get("conversation")), str(body)[:200])
            t.check("messages list present", isinstance(body.get("messages"), list), str(body)[:200])
            t.check("messages non-empty", len(body.get("messages", [])) > 0, f"n={len(body.get('messages', []))}")

    # 12) No-tool reply
    r = post("/chat", {"message": "Say hi in one word"})
    t.check("POST /api/chat no-tool 200", r.status_code == 200, r.text[:300])
    if r.status_code == 200:
        data = r.json()
        trace = data.get("tool_trace", [])
        t.check("no-tool trace is empty list", trace == [], f"trace={trace}")
        t.check("no-tool reply non-empty", bool((data.get("reply") or "").strip()), str(data)[:200])

    # 13) Delete a specific memory
    if saved_mem_id:
        r = delete(f"/memories/{saved_mem_id}")
        t.check("DELETE /api/memories/{id} 200", r.status_code == 200, r.text[:200])
        if r.status_code == 200:
            t.check("delete memory count>=1", r.json().get("deleted", 0) >= 1, r.text[:200])

    # 14) Clear all memories
    r = delete("/memories")
    t.check("DELETE /api/memories clear 200", r.status_code == 200, r.text[:200])
    r = get("/memories")
    if r.status_code == 200:
        t.check("memories cleared", r.json().get("memories") == [], r.text[:200])

    # 15) Delete conversation cascades messages
    if target_conv:
        r = delete(f"/conversations/{target_conv}")
        t.check("DELETE /api/conversations/{id} 200", r.status_code == 200, r.text[:200])
        r = get(f"/conversations/{target_conv}")
        t.check(
            "deleted conversation 404",
            r.status_code == 404,
            f"got {r.status_code}: {r.text[:200]}",
        )

    return t.summary()


if __name__ == "__main__":
    sys.exit(main())
