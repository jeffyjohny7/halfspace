"""Serve the Halfspace web app, with the fans' Ask desk behind POST /api/ask.

    uv run scripts/export_web.py          # first: build web/data/match.json from the latest broadcast run
    uv run scripts/serve_web.py           # then open http://localhost:8080
    uv run scripts/serve_web.py --port 9000
    uv run scripts/serve_web.py --offline # the app only; Ask explains that it needs Foundry
    uv run scripts/serve_web.py --trace   # each Ask question becomes a trace on the Foundry Tracing page
    uv run scripts/serve_web.py --trace-content   # ... with the question, tool results and answer in it

Ask uses the same Foundry deployment as the broadcast (FOUNDRY_PROJECT_ENDPOINT / FOUNDRY_MODEL in .env,
keyless via az login). The agent sees the league only through the MCP tools, without the live-match
tools, and every number in an answer is checked against the tool results before a fan sees it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from starlette.applications import Starlette  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import JSONResponse  # noqa: E402
from starlette.routing import Mount, Route  # noqa: E402
from starlette.staticfiles import StaticFiles  # noqa: E402

WEB = ROOT / "web"
OFFLINE_TEXT = ("Ask is switched off: the server was started with --offline. Restart it without --offline "
                "(and with az login done) to ask questions.")


def create_app(data_dir: str = "data", mode: str = "foundry", client=None, reasoning_effort: str | None = None,
               log_path: Path | None = None, trace: bool = False, trace_content: bool = False) -> Starlette:
    """client: optional chat client override (tests pass a scripted one)."""

    @asynccontextmanager
    async def lifespan(app: Starlette):
        app.state.desk, app.state.why = None, OFFLINE_TEXT
        app.state.fans = app.state.alerts = app.state.analyst = None
        async with AsyncExitStack() as stack:
            # Fan profiles and alerts work without Foundry too (alerts then use the plain templates).
            try:
                from agents.fans import AlertService, FanStore, Notifier
                from agents.verifier import Verifier
                from analytics.api import Analyst

                analyst = Analyst(data_dir)
                store = analyst.store
                verifier = Verifier({n: "" for n in store.player_names.values()}, list(store.club_names.values()))
                app.state.analyst = analyst
                app.state.fans = FanStore(Path(data_dir) / "runtime" / "fans", analyst)
                app.state.alerts = AlertService(app.state.fans, analyst, Notifier(None, verifier))
            except Exception as e:
                print(f"Fan profiles are off ({type(e).__name__}: {str(e)[:200]}).", flush=True)
            if (mode != "offline" or client is not None) and app.state.analyst is not None:
                try:
                    from agents.desk import FanDesk, desk_tool
                    from agents.fans import MemoryKeeper, Notifier
                    from agents.llm import make_client

                    chat = client if client is not None else make_client("foundry", max_function_calls=8)
                    if trace and client is None:
                        from agents.telemetry import enable_foundry_tracing
                        if await enable_foundry_tracing(chat, sensitive=trace_content):
                            print("Tracing on: Ask questions appear on the Foundry project's Tracing page.", flush=True)
                    tool = await stack.enter_async_context(desk_tool(data_dir))
                    app.state.desk = FanDesk(chat, [tool], verifier, reasoning_effort=reasoning_effort,
                                             analyst=analyst, fans=app.state.fans,
                                             memory=MemoryKeeper(chat, reasoning_effort=reasoning_effort))
                    app.state.alerts.notifier = Notifier(chat, verifier, reasoning_effort=reasoning_effort)
                    print(f"Ask desk ready ({'scripted model' if client is not None else 'Foundry'}).", flush=True)
                except Exception as e:      # the app still works without Ask
                    app.state.why = (f"Ask couldn't start ({type(e).__name__}: {str(e)[:200]}). "
                                     "Check az login and .env, then restart scripts/serve_web.py.")
                    print(app.state.why, flush=True)
            yield

    async def api_ask(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError):
            return JSONResponse({"error": True, "answer": "The request wasn't valid JSON."}, status_code=400)
        desk = request.app.state.desk
        if desk is None:
            return JSONResponse({"error": True, "answer": request.app.state.why})
        t0 = time.time()
        try:
            clock = float(body.get("clock_s") or 0) or None
        except (TypeError, ValueError):
            clock = None
        reply = await desk.answer(body.get("question", ""), body.get("language", "en"), body.get("history") or [],
                                  clock_s=clock, fan_id=str(body.get("fan_id") or "") or None)
        log = reply.pop("log", [])
        if log_path is not None:
            with log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"question": body.get("question"), "language": body.get("language"),
                                    "seconds": round(time.time() - t0, 1), "reply": reply, "log": log},
                                   ensure_ascii=False) + "\n")
        return JSONResponse(reply)

    # My Halfspace: the fan's profile
    async def _body(request: Request) -> dict:
        try:
            body = await request.json()
            return body if isinstance(body, dict) else {}
        except (json.JSONDecodeError, ValueError):
            return {}

    def _no_fans(request: Request) -> JSONResponse | None:
        if request.app.state.fans is None:
            return JSONResponse({"error": "Fan profiles aren't available on this server."}, status_code=503)
        return None

    async def api_fan(request: Request) -> JSONResponse:
        from agents.fans import FAN_ID, public_profile
        if (r := _no_fans(request)) is not None:
            return r
        fans, analyst = request.app.state.fans, request.app.state.analyst
        if request.method == "GET":
            fid = request.query_params.get("id", "")
            if not FAN_ID.match(fid):
                return JSONResponse({"error": "bad fan id"}, status_code=400)
            return JSONResponse({"profile": public_profile(fans.load(fid), analyst)})
        body = await _body(request)
        fid = str(body.pop("fan_id", ""))
        if not FAN_ID.match(fid):
            return JSONResponse({"error": "bad fan id"}, status_code=400)
        prof = fans.update(fid, body)
        return JSONResponse({"profile": public_profile(prof, analyst)})

    async def api_forget(request: Request) -> JSONResponse:
        from agents.fans import FAN_ID, public_profile
        if (r := _no_fans(request)) is not None:
            return r
        body = await _body(request)
        fid = str(body.get("fan_id", ""))
        if not FAN_ID.match(fid):
            return JSONResponse({"error": "bad fan id"}, status_code=400)
        prof = request.app.state.fans.forget(fid, body.get("fact_id"), everything=bool(body.get("everything")))
        return JSONResponse({"profile": public_profile(prof, request.app.state.analyst)})

    async def api_alerts(request: Request) -> JSONResponse:
        from agents.fans import FAN_ID
        if (r := _no_fans(request)) is not None:
            return r
        body = await _body(request)
        fid = str(body.get("fan_id", ""))
        if not FAN_ID.match(fid):
            return JSONResponse({"error": "bad fan id"}, status_code=400)
        try:
            clock = max(0.0, float(body.get("clock_s") or 0))
        except (TypeError, ValueError):
            clock = 0.0
        return JSONResponse(request.app.state.alerts.due(fid, clock))

    return Starlette(routes=[Route("/api/ask", api_ask, methods=["POST"]),
                             Route("/api/fan", api_fan, methods=["GET", "POST"]),
                             Route("/api/fan/forget", api_forget, methods=["POST"]),
                             Route("/api/alerts", api_alerts, methods=["POST"]),
                             Mount("/", StaticFiles(directory=str(WEB), html=True), name="web")],
                     lifespan=lifespan)


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--data", default="data")
    ap.add_argument("--offline", action="store_true", help="serve the app without the Ask desk")
    ap.add_argument("--trace", action="store_true", help="send Ask traces to the Foundry project")
    ap.add_argument("--trace-content", action="store_true",
                    help="like --trace, and record questions, tool results and answers too")
    a = ap.parse_args()
    if not (WEB / "data" / "match.json").exists():
        print("web/data/match.json is missing. Run: uv run scripts/export_web.py (or --offline) first.")
        sys.exit(1)
    log_dir = Path(a.data) / "runtime"
    log_dir.mkdir(parents=True, exist_ok=True)
    app = create_app(a.data, "offline" if a.offline else "foundry", log_path=log_dir / "ask_log.jsonl",
                     reasoning_effort=os.environ.get("AGENT_REASONING_EFFORT", "low") or None,
                     trace=a.trace or a.trace_content or os.environ.get("HALFSPACE_TRACE", "") == "1",
                     trace_content=a.trace_content or os.environ.get("HALFSPACE_TRACE_CONTENT", "") == "1")
    import uvicorn
    print(f"Halfspace: http://localhost:{a.port}   (Ctrl+C to stop)", flush=True)
    server = uvicorn.Server(uvicorn.Config(app, host=a.host, port=a.port, log_level="warning"))
    asyncio.run(server.serve())    # default event loop: subprocesses (the MCP server) work on Windows too


if __name__ == "__main__":
    main()
