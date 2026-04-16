"""
Backend tests for Nova Assistant — Iteration 2.
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
    return requests.post(f"{API}{path}", json=json_body, timeout=180, **kw)


def delete(path: str, **kw) -> requests.Response:
    return requests.delete(f"{API}{path}", timeout=60, **kw)


def tool_names(trace: List[Dict[str, Any]]) -> List[str]:
    return [x.get("name") for x in (trace or [])]


def trace_has_tool(trace: List[Dict[str, Any]], name: str) -> bool:
    return name in tool_names(trace)


def main() -> int:
    print(f"Target: {API}\n")

    # Clean slate
    try:
        delete("/memories")
    except Exception as e:
        print(f"(warn) unable to clear memories: {e}")
    # Delete any existing notes
    try:
        notes = get("/notes").json().get("notes", [])
        for n in notes:
            delete(f"/notes/{n['id']}")
    except Exception as e:
        print(f"(warn) unable to clear notes: {e}")

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
        t.check("health.tools == 13", data.get("tools") == 13, f"got tools={data.get('tools')}")

    # 2) Tools — ensure all 13 tools (old + new)
    r = get("/tools")
    t.check("GET /api/tools 200", r.status_code == 200, r.text[:200])
    expected_tools = {
        "get_time", "datetime_convert",
        "get_weather", "web_search", "wikipedia_search", "fetch_url",
        "calculator",
        "create_note", "list_notes", "delete_note",
        "save_memory", "recall_memory",
        "list_capabilities",
    }
    tools_list: List[Dict[str, Any]] = []
    if r.status_code == 200:
        tools_list = r.json().get("tools", [])
        names = {tm["name"] for tm in tools_list}
        missing = expected_tools - names
        t.check("tools contains all 13 required", not missing, f"missing={missing}")
        # get_weather must be live (mocked==False)
        gw_meta = next((x for x in tools_list if x["name"] == "get_weather"), None)
        t.check("get_weather meta present", gw_meta is not None, "tool missing")
        if gw_meta:
            t.check("get_weather.mocked is False (LIVE)", gw_meta.get("mocked") is False, f"meta={gw_meta}")
        # web_search still mocked
        ws_meta = next((x for x in tools_list if x["name"] == "web_search"), None)
        if ws_meta:
            t.check("web_search.mocked is True (expected mocked)", ws_meta.get("mocked") is True, f"meta={ws_meta}")
        # category field present
        t.check("tools have category field", all("category" in tm for tm in tools_list), "missing category")

    # 3) MCP manifest
    r = get("/mcp/manifest")
    t.check("GET /api/mcp/manifest 200", r.status_code == 200, r.text[:200])
    if r.status_code == 200:
        mani = r.json()
        t.check("manifest.protocol == mcp-like/1.0", mani.get("protocol") == "mcp-like/1.0", str(mani)[:200])
        t.check("manifest.server == nova", mani.get("server") == "nova", str(mani)[:200])
        t.check("manifest.version present", bool(mani.get("version")), str(mani)[:200])
        tools = mani.get("tools", [])
        t.check("manifest has 13 tools", len(tools) == 13, f"count={len(tools)}")
        # Each tool has input_schema
        ok_schema = all(isinstance(x.get("input_schema"), dict) and x["input_schema"].get("type") == "object" for x in tools)
        t.check("every tool has JSON input_schema", ok_schema, "some tool missing schema")

    # 4) MCP call — calculator 2+2*3 == 8
    r = post("/mcp/call", {"name": "calculator", "args": {"expression": "2+2*3"}})
    t.check("POST /api/mcp/call calculator 200", r.status_code == 200, r.text[:200])
    if r.status_code == 200:
        body = r.json()
        result = body.get("result")
        # result is parsed JSON dict
        inner = result.get("result") if isinstance(result, dict) else None
        t.check("mcp calculator result == 8", inner == 8, f"body={body}")

    # 5) MCP call — unknown tool -> 404
    r = post("/mcp/call", {"name": "no_such_tool_xyz", "args": {}})
    t.check("POST /api/mcp/call unknown -> 404", r.status_code == 404, f"got {r.status_code}: {r.text[:200]}")

    # 6) MCP call wikipedia directly (smoke test for outbound HTTP)
    r = post("/mcp/call", {"name": "wikipedia_search", "args": {"query": "Alan Turing"}})
    t.check("POST /api/mcp/call wikipedia 200", r.status_code == 200, r.text[:200])
    if r.status_code == 200:
        inner = r.json().get("result")
        t.check(
            "wikipedia returns extract",
            isinstance(inner, dict) and bool(inner.get("extract")),
            f"result={str(inner)[:200]}",
        )

    # 7) MCP call get_weather directly (confirm outbound to Open-Meteo works)
    r = post("/mcp/call", {"name": "get_weather", "args": {"city": "London"}})
    t.check("POST /api/mcp/call get_weather 200", r.status_code == 200, r.text[:200])
    if r.status_code == 200:
        inner = r.json().get("result")
        t.check(
            "get_weather live result has temperature_c",
            isinstance(inner, dict) and ("temperature_c" in inner) and (inner.get("source") == "open-meteo (live)"),
            f"result={str(inner)[:200]}",
        )

    # 8) Chat: empty -> 400
    r = post("/chat", {"message": "   "})
    t.check("POST /api/chat empty -> 400", r.status_code == 400, f"got {r.status_code}: {r.text[:200]}")

    # 9) Chat: Calculator math
    r = post("/chat", {"message": "Calculate sqrt(144) * 3"})
    t.check("POST /api/chat calculator 200", r.status_code == 200, r.text[:300])
    calc_conv_id = None
    if r.status_code == 200:
        data = r.json()
        calc_conv_id = data.get("conversation_id")
        trace = data.get("tool_trace", [])
        t.check("calculator tool called for math", trace_has_tool(trace, "calculator"), f"tools={tool_names(trace)}")
        reply = (data.get("reply") or "")
        t.check("calculator reply mentions 36", "36" in reply, f"reply={reply[:200]}")
        t.check("chat response has suggestions field (list)", isinstance(data.get("suggestions"), list), str(data)[:200])

    # 10) Chat: Wikipedia — Alan Turing
    r = post("/chat", {"message": "Who was Alan Turing? Answer in one sentence."})
    t.check("POST /api/chat wikipedia 200", r.status_code == 200, r.text[:300])
    if r.status_code == 200:
        data = r.json()
        trace = data.get("tool_trace", [])
        t.check("wikipedia_search tool called", trace_has_tool(trace, "wikipedia_search"), f"tools={tool_names(trace)}")
        reply = (data.get("reply") or "").lower()
        t.check("wiki reply mentions turing/computer/math",
                any(k in reply for k in ["turing", "mathematician", "computer", "british", "cryptanalyst"]),
                f"reply={reply[:250]}")

    # 11) Chat: Weather in Nagpur (LIVE)
    r = post("/chat", {"message": "Weather in Nagpur"})
    t.check("POST /api/chat weather 200", r.status_code == 200, r.text[:300])
    if r.status_code == 200:
        data = r.json()
        trace = data.get("tool_trace", [])
        t.check("get_weather tool called", trace_has_tool(trace, "get_weather"), f"tools={tool_names(trace)}")
        gw = next((x for x in trace if x.get("name") == "get_weather"), None)
        if gw:
            # The raw result should not contain "mock" and should have temperature_c
            res_raw = gw.get("result") or ""
            try:
                parsed = json.loads(res_raw) if isinstance(res_raw, str) else res_raw
            except Exception:
                parsed = {}
            t.check("weather result is LIVE (no 'mock')", "mock" not in (res_raw.lower() if isinstance(res_raw, str) else ""), f"raw={str(res_raw)[:200]}")
            t.check("weather result has temperature_c (live)",
                    isinstance(parsed, dict) and parsed.get("temperature_c") is not None,
                    f"parsed={str(parsed)[:200]}")
        reply = (data.get("reply") or "").lower()
        t.check("weather reply mentions temperature/weather",
                any(k in reply for k in ["weather", "temperature", "°c", "degrees", "cloud", "humid", "nagpur"]),
                f"reply={reply[:250]}")

    # 12) Chat: fetch_url — summarize example.com
    r = post("/chat", {"message": "Summarize https://example.com"})
    t.check("POST /api/chat fetch_url 200", r.status_code == 200, r.text[:300])
    if r.status_code == 200:
        data = r.json()
        trace = data.get("tool_trace", [])
        t.check("fetch_url tool called", trace_has_tool(trace, "fetch_url"), f"tools={tool_names(trace)}")
        fu = next((x for x in trace if x.get("name") == "fetch_url"), None)
        if fu:
            url_arg = (fu.get("args") or {}).get("url", "")
            t.check("fetch_url args include example.com url", "example.com" in url_arg, f"args={fu.get('args')}")

    # 13) Chat: create_note — groceries
    r = post("/chat", {"message": "Make a note: buy groceries tomorrow"})
    t.check("POST /api/chat create_note 200", r.status_code == 200, r.text[:300])
    if r.status_code == 200:
        data = r.json()
        trace = data.get("tool_trace", [])
        t.check("create_note tool called", trace_has_tool(trace, "create_note"), f"tools={tool_names(trace)}")

    # 14) GET /api/notes contains 'groceries'
    time.sleep(1)
    r = get("/notes")
    t.check("GET /api/notes 200", r.status_code == 200, r.text[:200])
    saved_note_id: Optional[str] = None
    if r.status_code == 200:
        notes = r.json().get("notes", [])
        found = [n for n in notes if "groceries" in ((n.get("content") or "") + (n.get("title") or "")).lower()]
        t.check("notes list contains groceries", bool(found), f"notes={[(n.get('title'), n.get('content')) for n in notes]}")
        if found:
            saved_note_id = found[0].get("id")

    # 15) Chat: list_notes — 'show my notes'
    r = post("/chat", {"message": "show my notes"})
    t.check("POST /api/chat list_notes 200", r.status_code == 200, r.text[:300])
    if r.status_code == 200:
        data = r.json()
        trace = data.get("tool_trace", [])
        t.check("list_notes tool called", trace_has_tool(trace, "list_notes"), f"tools={tool_names(trace)}")
        reply = (data.get("reply") or "").lower()
        t.check("list_notes reply mentions groceries", "groceries" in reply, f"reply={reply[:250]}")

    # 16) DELETE /api/notes/{id}
    if saved_note_id:
        r = delete(f"/notes/{saved_note_id}")
        t.check("DELETE /api/notes/{id} 200", r.status_code == 200, r.text[:200])
        if r.status_code == 200:
            t.check("note delete count>=1", r.json().get("deleted", 0) >= 1, r.text[:200])
        # verify gone
        r = get("/notes")
        if r.status_code == 200:
            still = [n for n in r.json().get("notes", []) if n.get("id") == saved_note_id]
            t.check("note actually removed", not still, f"still present: {still}")

    # 17) Suggestions populated for typical queries
    r = post("/chat", {"message": "Calculate 5*5"})
    t.check("POST /api/chat suggestions calc 200", r.status_code == 200, r.text[:300])
    if r.status_code == 200:
        d = r.json()
        t.check("suggestions is a list (calc)", isinstance(d.get("suggestions"), list), str(d)[:200])
        # be lenient — may be empty; just log
        print(f"  (info) suggestions for calc: {d.get('suggestions')}")

    r = post("/chat", {"message": "Weather in London"})
    t.check("POST /api/chat suggestions weather 200", r.status_code == 200, r.text[:300])
    if r.status_code == 200:
        d = r.json()
        t.check("suggestions is a list (weather)", isinstance(d.get("suggestions"), list), str(d)[:200])
        print(f"  (info) suggestions for weather: {d.get('suggestions')}")

    # 18) Iteration-1 regression: save_memory + recall
    r = post("/chat", {"message": "Remember that I love cold brew coffee"})
    t.check("POST /api/chat save_memory 200", r.status_code == 200, r.text[:300])
    if r.status_code == 200:
        trace = r.json().get("tool_trace", [])
        t.check("save_memory tool called", trace_has_tool(trace, "save_memory"), f"tools={tool_names(trace)}")

    time.sleep(1)
    r = get("/memories")
    t.check("GET /api/memories 200", r.status_code == 200, r.text[:200])
    saved_mem_id: Optional[str] = None
    if r.status_code == 200:
        mems = r.json().get("memories", [])
        found = [m for m in mems if "cold brew" in (m.get("content") or "").lower()]
        t.check("memories contains cold brew", bool(found), f"memories={[m.get('content') for m in mems]}")
        if found:
            saved_mem_id = found[0].get("id")

    # 19) Conversations list + fetch by id
    r = get("/conversations")
    t.check("GET /api/conversations 200", r.status_code == 200, r.text[:200])
    if r.status_code == 200:
        convs = r.json().get("conversations", [])
        t.check("conversations list non-empty", len(convs) > 0, f"count={len(convs)}")
    target_conv = calc_conv_id
    if target_conv:
        r = get(f"/conversations/{target_conv}")
        t.check("GET /api/conversations/{id} 200", r.status_code == 200, r.text[:200])
        if r.status_code == 200:
            body = r.json()
            t.check("conversation object present", bool(body.get("conversation")), str(body)[:200])
            t.check("messages list present", isinstance(body.get("messages"), list), str(body)[:200])

    # 20) DELETE a memory + clear all memories
    if saved_mem_id:
        r = delete(f"/memories/{saved_mem_id}")
        t.check("DELETE /api/memories/{id} 200", r.status_code == 200, r.text[:200])
    r = delete("/memories")
    t.check("DELETE /api/memories clear 200", r.status_code == 200, r.text[:200])

    # 21) Delete conversation
    if target_conv:
        r = delete(f"/conversations/{target_conv}")
        t.check("DELETE /api/conversations/{id} 200", r.status_code == 200, r.text[:200])
        r = get(f"/conversations/{target_conv}")
        t.check("deleted conversation 404", r.status_code == 404, f"got {r.status_code}: {r.text[:200]}")

    return t.summary()


if __name__ == "__main__":
    sys.exit(main())
