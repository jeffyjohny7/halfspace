"""Score what the agents published: does every graphic and every Ask answer stick to the facts?

    uv run --with "azure-ai-evaluation>=1.18.9,<2" scripts/eval_agents.py           # Foundry judge; run shows in the portal
    uv run --with "azure-ai-evaluation>=1.18.9,<2" scripts/eval_agents.py --local   # same judge, results only on disk
    uv run scripts/eval_agents.py --offline                                           # code checks only, no model
    ... --limit 20                                                                    # quick try on the first 20 items

(--with: azure-ai-evaluation needs pandas 2, the project uses pandas 3; uv layers it for this script only.)

Scored: every graphic variant the model wrote in the last broadcast (templates are skipped) and every
checked Ask answer in data/runtime/ask_log.jsonl.

  grounded        Foundry GroundednessEvaluator, 1-5: is every claim supported by what the writer was given
                  (the cue's facts and the analyst's angle; for Ask, the tool results)? Text in Spanish, Arabic,
                  Hindi or Malayalam is translated back to English first, so a translation that changes the
                  meaning loses points too.
  numbers_traced  code: share of the numbers in the text that appear in that context (the Verifier's rule, re-run)
  right_language  code: written in the fan's language and script (names and metric names may stay in Latin)

Plus figures from the broadcast itself: drafts the Verifier sent back, graphics that fell back to the template.
Output: data/reports/agent_eval.json, data/reports/agent_eval.md (and the Evaluations page in Foundry).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from statistics import mean
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agents.config import LANGUAGES  # noqa: E402
from agents.verifier import SCRIPTS, _matches, _other_scripts, _script_chars, numbers, pool_from  # noqa: E402

ES_WORDS = re.compile(r"\b(de|la|el|los|las|en|que|y|con|del|por|para|un|una|se|su|al|sin|más|tras)\b", re.I)
THRESHOLD = 3          # GroundednessEvaluator default: 3 or more out of 5 passes


# ---------------------------------------------------------------------------
# What gets scored
# ---------------------------------------------------------------------------

def _jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def broadcast_rows(run_dir: Path) -> list[dict]:
    cues = _jsonl(run_dir / "cues.jsonl")
    recap_path = run_dir / "recap.json"
    recap = json.loads(recap_path.read_text(encoding="utf-8")) if recap_path.exists() else None
    rows = []
    for c in cues:
        given = list(c.get("facts") or [])
        if c.get("kind") == "recap" and recap:
            given = recap.get("facts") or given          # the recap graphic is judged against the match facts
        if c.get("angle"):
            given.append(c["angle"])
        if c.get("phase") == "live" and c.get("minute") is not None:
            given.insert(0, f"Match minute: {c['minute']}.")     # the writer knows when the graphic airs
        for key, v in (c.get("variants") or {}).items():
            if v.get("source") != "llm":
                continue
            viewer, _, lang = key.partition("/")
            rows.append({"source": "broadcast", "item": f"{c['cue_id']} {key}", "kind": c.get("kind", ""),
                         "minute": c.get("minute"), "viewer": viewer, "language": lang,
                         "context": "\n".join(given), "response": f"{v.get('headline', '')}\n{v.get('body', '')}".strip()})
    if recap and recap.get("source") == "llm":
        text = " ".join(str(recap.get(k, "")) for k in ("headline", "summary", "plan_vs_reality", "player_reason"))
        rows.append({"source": "recap", "item": "recap", "kind": "recap", "minute": 90, "viewer": "all",
                     "language": "en", "context": "\n".join(recap.get("facts") or []), "response": text.strip()})
    return rows


def ask_rows(log_path: Path) -> list[dict]:
    rows = []
    for i, r in enumerate(_jsonl(log_path), 1):
        reply, log = r.get("reply") or {}, r.get("log") or []
        evidence = next((e["evidence"] for e in reversed(log) if e.get("evidence")), None)
        if not reply.get("checked") or not evidence:      # unchecked answers never reached a fan
            continue
        rows.append({"source": "ask", "item": f"ask {i}", "kind": "ask", "minute": None, "viewer": "fan",
                     "language": r.get("language") or "en", "query": r.get("question") or "",
                     "context": f"Fan's question: {r.get('question')}\n" + "\n".join(evidence),
                     "response": reply.get("answer", "")})
    return rows


# ---------------------------------------------------------------------------
# Code evaluators (also usable as azure-ai-evaluation custom evaluators)
# ---------------------------------------------------------------------------

class NumbersTraced:
    """Share of the numbers in the response that appear in the context."""

    def __call__(self, *, response: str, context: str) -> dict:
        pool = pool_from([context])
        nums = numbers(response)
        bad = sorted({f"{v:g}" for v, d, _p in nums if not _matches(v, d, pool)})
        share = 1.0 if not nums else round(sum(_matches(v, d, pool) for v, d, _p in nums) / len(nums), 3)
        return {"numbers_traced": share, "untraced": ", ".join(bad)}


class RightLanguage:
    """1 if the response is in the fan's language and script, else 0."""

    def __call__(self, *, response: str, language: str) -> dict:
        why = ""
        if _other_scripts(response, language):
            why = "letters from another writing system"
        elif language in SCRIPTS and _script_chars(response, language) < 4:
            why = f"not written in {LANGUAGES.get(language, language)} script"
        elif language == "es" and not ES_WORDS.search(response):
            why = "does not read as Spanish"
        return {"right_language": 0 if why else 1, "right_language_reason": why}


# ---------------------------------------------------------------------------
# Foundry: back-translation and the groundedness judge
# ---------------------------------------------------------------------------

def _env() -> dict[str, str]:
    env = dict(os.environ)
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            k, sep, v = line.partition("=")
            if sep and not line.lstrip().startswith("#"):
                env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env


def openai_endpoint(env: dict[str, str]) -> str:
    """https://<resource>.openai.azure.com/ for the resource behind FOUNDRY_PROJECT_ENDPOINT."""
    if env.get("AZURE_OPENAI_ENDPOINT"):
        return env["AZURE_OPENAI_ENDPOINT"]
    host = urlparse(env.get("FOUNDRY_PROJECT_ENDPOINT", "")).netloc
    if not host:
        sys.exit("FOUNDRY_PROJECT_ENDPOINT is not set (.env). Or set AZURE_OPENAI_ENDPOINT.")
    return f"https://{host.split('.')[0]}.openai.azure.com/"


QUOTA_HINT = ("The gpt-5-mini deployment hit its rate limit (429). Raise it in Foundry: Models > gpt-5-mini > "
              "Edit > Tokens per minute, or run again with --concurrency 1.")


CACHE = ROOT / "data" / "runtime" / "back_translations.json"


def _key(r: dict) -> str:
    import hashlib
    return hashlib.sha1(f"{r['language']}|{r['response']}".encode("utf-8")).hexdigest()


async def back_translate(rows: list[dict], model: str | None, concurrency: int = 2) -> None:
    """Fill row['response_en']: the text itself for English, a literal English translation otherwise.
    Translations are cached, so running the evaluation again only translates new text."""
    try:
        cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    except (OSError, ValueError):
        cache = {}
    for r in rows:
        if r["language"] == "en":
            r["response_en"] = r["response"]
        elif _key(r) in cache:
            r["response_en"] = cache[_key(r)]
    todo = [r for r in rows if not r.get("response_en")]
    if not todo:
        return
    from agent_framework import Agent
    from pydantic import BaseModel

    from agents.llm import ask, make_client, model_options

    class Translation(BaseModel):
        english: str

    agent = Agent(make_client("foundry", model=model),
                  "You translate football graphics and answers into English, literally and completely: keep every "
                  "claim, number, name and hedge exactly as written. Do not fix, add or soften anything.",
                  name="BackTranslator", default_options=model_options("low"))
    gate = asyncio.Semaphore(concurrency)

    async def one(r: dict) -> None:
        async with gate:
            res = await ask(agent, f"Translate from {LANGUAGES.get(r['language'], r['language'])}:\n\n{r['response']}",
                            Translation, timeout_s=120, retries=4)
            r["response_en"] = res.value.english if res.value else ""
            if res.value is None:
                r["_why"] = res.error or ""
            else:
                r.pop("_why", None)

    await asyncio.gather(*(one(r) for r in todo))
    failed = [r for r in todo if not r["response_en"]]
    if failed:                                  # one more, slower pass for whatever was throttled
        print(f"  {len(failed)} back-translations failed; trying them again one at a time...", flush=True)
        gate = asyncio.Semaphore(1)
        await asyncio.gather(*(one(r) for r in failed))
    failed = [r for r in todo if not r["response_en"]]
    for r in failed:
        print(f"  back-translation failed for {r['item']}: {r.get('_why', '')[:200]}")
    if any("429" in r.get("_why", "") for r in failed):
        print("  " + QUOTA_HINT)
    cache.update({_key(r): r["response_en"] for r in todo if r["response_en"]})
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"Back-translated {len(todo) - len(failed)} of {len(todo)} items to English"
          + (" (the rest are left out of the judging)." if failed else "."), flush=True)


class _OpenAIAudience:
    """The judge calls the Azure OpenAI endpoint directly, so its token is for Azure OpenAI's own audience
    (the SDK otherwise asks for an ai.azure.com token). The Foundry upload keeps the plain credential."""
    SCOPE = "https://cognitiveservices.azure.com/.default"

    def __init__(self, inner):
        self.inner = inner

    def get_token(self, *scopes, **kwargs):
        return self.inner.get_token(self.SCOPE, **kwargs)

    def get_token_info(self, *scopes, options=None):
        return self.inner.get_token_info(self.SCOPE, options=options)


ROLE_HINT = (
    "The judge was refused by Azure (401 PermissionDenied): your account can use the Foundry project, but not the "
    "Azure OpenAI endpoint of the resource behind it. Give yourself the role once, then run this again:\n"
    "  Azure portal > your Foundry resource ({resource}) > Access control (IAM) > Add > Add role assignment >\n"
    "  Cognitive Services OpenAI User > Next > Select members > your account > Review + assign.\n"
    "  The role can take up to 5 minutes to apply.")


def _bearer(cred, scope: str) -> str:
    return cred.get_token(scope).token


def _judge_routes(env: dict[str, str], deployment: str, cred) -> list[tuple[str, dict, object]]:
    """Ways to reach the judge model, most standard first: (label, model config, credential or None).

    1. the resource's Azure OpenAI endpoint (needs the Cognitive Services OpenAI User role on the resource);
    2. the resource's OpenAI v1 endpoint with an Entra token;
    3. the project's OpenAI v1 endpoint, the same door the broadcast agents use (project access is enough)."""
    from azure.ai.evaluation import AzureOpenAIModelConfiguration, OpenAIModelConfiguration

    aoai = openai_endpoint(env)
    host = urlparse(env.get("FOUNDRY_PROJECT_ENDPOINT", "")).netloc
    routes = [("Azure OpenAI endpoint", AzureOpenAIModelConfiguration(
        azure_endpoint=aoai, azure_deployment=deployment,
        api_version=env.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")), _OpenAIAudience(cred))]
    try:
        if host:
            routes.append(("resource OpenAI v1 endpoint", OpenAIModelConfiguration(
                type="openai", base_url=f"https://{host}/openai/v1", model=deployment,
                api_key=_bearer(cred, _OpenAIAudience.SCOPE)), None))
        if env.get("FOUNDRY_PROJECT_ENDPOINT"):
            routes.append(("project OpenAI v1 endpoint", OpenAIModelConfiguration(
                type="openai", base_url=env["FOUNDRY_PROJECT_ENDPOINT"].rstrip("/") + "/openai/v1", model=deployment,
                api_key=_bearer(cred, "https://ai.azure.com/.default")), None))
    except Exception as e:                      # no token: the first route will report the real problem
        print(f"  (couldn't get a token for the other routes: {type(e).__name__})")
    return routes


def _working_judge(env: dict[str, str], deployment: str, cred, reasoning: bool):
    """Try each route with one small call; an auth problem stops here, not after 132 failed rows."""
    from azure.ai.evaluation import GroundednessEvaluator

    problems = []
    for label, config, credential in _judge_routes(env, deployment, cred):
        judge = GroundednessEvaluator(config, threshold=THRESHOLD, credential=credential, is_reasoning_model=reasoning)
        # A judge call normally takes 2-15 s, but now and then the service sits on one for minutes. Give up on a
        # call after 60 s and let the evaluator retry it (the SDK default waits up to 10 minutes).
        judge._LLM_CALL_TIMEOUT = 60
        try:
            judge(response="Lowmarsh Harriers lead 1-0.", context="Score: Lowmarsh Harriers 1-0 Oxmere County.")
            return judge, label
        except Exception as e:
            text = " ".join(str(x) for x in (e, e.__cause__) if x)
            problems.append(f"{label}: {text[:180]}")
    text = " ".join(problems)
    for p in problems:
        print("  " + p)
    if re.search(r"401|403|PermissionDenied|AuthenticationError|does not have access", text):
        sys.exit(ROLE_HINT.format(resource=urlparse(openai_endpoint(env)).netloc.split(".")[0]))
    if re.search(r"DeploymentNotFound|404", text):
        sys.exit(f"The judge deployment '{deployment}' wasn't found. Pass --judge-model with your deployment name.")
    sys.exit("The judge couldn't be reached; see the errors above.")


def run_foundry(rows: list[dict], out_dir: Path, upload: bool, judge_model: str | None,
                concurrency: int = 2) -> tuple[list[dict], str | None]:
    try:
        from azure.ai.evaluation import AzureOpenAIModelConfiguration, GroundednessEvaluator, evaluate
    except ImportError:
        sys.exit('The judge needs azure-ai-evaluation. Run:\n  uv run --with "azure-ai-evaluation>=1.18.9,<2" '
                 "scripts/eval_agents.py\n(or --offline for the code checks only)")
    from azure.identity import DefaultAzureCredential

    env = _env()
    deployment = judge_model or env.get("FOUNDRY_MODEL", "gpt-5-mini")
    cred = DefaultAzureCredential()
    reasoning = bool(re.match(r"(gpt-5|o\d)", deployment))
    judge, route = _working_judge(env, deployment, cred, reasoning)
    print(f"Judge: {deployment} via {route}.", flush=True)

    data = out_dir / "agent_eval_input.jsonl"
    data.write_text("".join(json.dumps({k: v for k, v in r.items() if v is not None}, ensure_ascii=False) + "\n"
                            for r in rows if r.get("response_en")), encoding="utf-8")
    kwargs = dict(
        data=str(data),
        evaluators={"grounded": judge, "numbers": NumbersTraced(), "language": RightLanguage()},
        evaluator_config={
            "grounded": {"column_mapping": {"response": "${data.response_en}", "context": "${data.context}"}},
            "numbers": {"column_mapping": {"response": "${data.response}", "context": "${data.context}"}},
            "language": {"column_mapping": {"response": "${data.response}", "language": "${data.language}"}},
        },
        evaluation_name=f"halfspace-agents-{time.strftime('%Y%m%d-%H%M')}",
        output_path=str(out_dir / "agent_eval_raw.json"),
    )
    print(f"Judging {sum(1 for r in rows if r.get('response_en'))} items with {deployment} "
          f"(GroundednessEvaluator)...", flush=True)
    # The SDK's worker pool runs each evaluator in its own thread *and* caps the rows in flight, so it must be larger
    # than the number of evaluators or it deadlocks. concurrency + 3 keeps the judge gentle on the rate limit.
    os.environ["PF_WORKER_COUNT"] = str(max(concurrency, 1) + len(kwargs["evaluators"]))
    # A judge call normally takes 2-3 s; one that hangs is given up after 150 s instead of the SDK's 10 minutes
    # (that item is reported as not judged).
    os.environ.setdefault("PF_LINE_TIMEOUT_SEC", "150")
    result = None
    if upload and env.get("FOUNDRY_PROJECT_ENDPOINT"):
        try:
            result = evaluate(azure_ai_project=env["FOUNDRY_PROJECT_ENDPOINT"], credential=cred, **kwargs)
        except Exception as e:
            print(f"Couldn't log the run to Foundry ({type(e).__name__}: {str(e)[:200]}). Scoring locally instead.")
    if result is None:
        result = evaluate(**kwargs)
    data.unlink(missing_ok=True)
    by_item = {r["item"]: r for r in rows}
    out = []
    for raw in result["rows"]:
        r = dict(by_item.get(raw.get("inputs.item"), {}))
        if not r:
            continue
        g = raw.get("outputs.grounded.groundedness")
        r["grounded"] = float(g) if isinstance(g, (int, float)) and g == g else None     # g != g: NaN, a failed row
        r["grounded_reason"] = raw.get("outputs.grounded.groundedness_reason", "")
        r["numbers_traced"] = raw.get("outputs.numbers.numbers_traced")
        r["untraced"] = raw.get("outputs.numbers.untraced", "")
        r["right_language"] = raw.get("outputs.language.right_language")
        r["right_language_reason"] = raw.get("outputs.language.right_language_reason", "")
        out.append(r)
    return out, result.get("studio_url")


def run_offline(rows: list[dict]) -> list[dict]:
    num, lang = NumbersTraced(), RightLanguage()
    for r in rows:
        r.update(num(response=r["response"], context=r["context"]))
        r.update(lang(response=r["response"], language=r["language"]))
        r["grounded"] = None
    return rows


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def broadcast_stats(run_dir: Path) -> dict:
    cues = _jsonl(run_dir / "cues.jsonl")
    variants = [v for c in cues for v in (c.get("variants") or {}).values()]
    ver = [c.get("verification") or {} for c in cues]
    return {
        "cues": len(cues),
        "variants": len(variants),
        "variants_by_model": sum(v.get("source") == "llm" for v in variants),
        "variants_by_template": sum(v.get("source") == "template" for v in variants),
        "cues_sent_back_by_verifier": sum(bool(v.get("rejections")) or (v.get("attempts") or 1) > 1 for v in ver),
        "cues_on_safe_template": sum(bool(v.get("degraded")) for v in ver),
    }


def _avg(xs: list) -> float | None:
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(mean(xs), 2) if xs else None


def summarise(rows: list[dict]) -> dict:
    def block(rs: list[dict]) -> dict:
        g = [r["grounded"] for r in rs if isinstance(r.get("grounded"), (int, float))]
        return {"items": len(rs), "grounded_avg": _avg(g),
                "grounded_pass": round(sum(x >= THRESHOLD for x in g) / len(g), 3) if g else None,
                "numbers_traced": _avg([r.get("numbers_traced") for r in rs]),
                "right_language": _avg([r.get("right_language") for r in rs])}

    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        label = {"broadcast": "Graphics", "recap": "Full-time recap", "ask": "Ask answers"}[r["source"]]
        groups[f"{label} · {LANGUAGES.get(r['language'], r['language'])}"].append(r)
    return {"overall": block(rows), "groups": {k: block(v) for k, v in sorted(groups.items())}}


def _fmt(x, pct=False):
    if x is None:
        return "–"
    return f"{x * 100:.0f}%" if pct else f"{x:.2f}"


def write_report(rows: list[dict], stats: dict, studio_url: str | None, judge: str | None, out_dir: Path) -> dict:
    summary = summarise(rows)
    report = {"generated": time.strftime("%Y-%m-%d %H:%M"), "judge": judge, "threshold": THRESHOLD,
              "summary": summary, "broadcast": stats, "foundry_run": studio_url,
              "items": [{k: r.get(k) for k in ("item", "source", "kind", "minute", "viewer", "language", "grounded",
                                               "grounded_reason", "numbers_traced", "untraced", "right_language",
                                               "right_language_reason", "response", "response_en")} for r in rows]}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "agent_eval.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    o = summary["overall"]
    lines = ["# Do the agents stick to the facts?", "",
             f"Generated {report['generated']}. "
             + (f"Judge: Foundry GroundednessEvaluator on `{judge}` (1-5, pass at {THRESHOLD}+). "
                if judge else "Code checks only (run without --offline for the Foundry judge). ")
             + "Text in other languages is translated back to English before it is judged.", ""]
    if studio_url:
        lines += [f"Run in the Foundry portal: {studio_url}", ""]
    lines += ["| | Items | Grounded (avg, 1-5) | Grounded (pass) | Numbers traced | Right language |",
              "|---|---:|---:|---:|---:|---:|",
              f"| **All** | {o['items']} | {_fmt(o['grounded_avg'])} | {_fmt(o['grounded_pass'], True)} | "
              f"{_fmt(o['numbers_traced'], True)} | {_fmt(o['right_language'], True)} |"]
    for k, b in summary["groups"].items():
        lines.append(f"| {k} | {b['items']} | {_fmt(b['grounded_avg'])} | {_fmt(b['grounded_pass'], True)} | "
                     f"{_fmt(b['numbers_traced'], True)} | {_fmt(b['right_language'], True)} |")
    if stats.get("cues"):
        lines += ["", "## The broadcast run", "",
                  f"- {stats['cues']} graphics, {stats['variants']} versions (viewer × language): "
                  f"{stats['variants_by_model']} written by the model, {stats['variants_by_template']} by the safe template.",
                  f"- The Verifier sent {stats['cues_sent_back_by_verifier']} graphics back for a rewrite; "
                  f"{stats['cues_on_safe_template']} ended on the safe template."]
    judged = [r for r in rows if isinstance(r.get("grounded"), (int, float))]
    low = sorted(judged, key=lambda r: r["grounded"])[:5]
    if low and low[0]["grounded"] < 5:
        lines += ["", "## Lowest scores", "", "What the judge flagged, so the prompts can improve:", ""]
        for r in low:
            if r["grounded"] >= 5:
                break
            en = r.get("response_en") if r["language"] != "en" else None
            lines.append(f"- **{r['item']}** ({r['grounded']:.0f}/5): {r['response'].replace(chr(10), ' / ')}"
                         + (f"  \n  _In English:_ {en.replace(chr(10), ' / ')}" if en else "")
                         + f"  \n  _Judge:_ {str(r.get('grounded_reason', '')).strip()[:400]}")
    bad = [r for r in rows if (r.get("numbers_traced") is not None and r["numbers_traced"] < 1)
           or r.get("right_language") == 0]
    if bad:
        lines += ["", "## Code checks that failed", ""]
        lines += [f"- **{r['item']}**: " + "; ".join(x for x in (
            f"numbers not in the context: {r['untraced']}" if r.get("untraced") else "",
            r.get("right_language_reason", "")) if x) for r in bad[:10]]
    (out_dir / "agent_eval.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default="data/runtime/broadcast", help="broadcast output folder")
    ap.add_argument("--ask-log", default="data/runtime/ask_log.jsonl")
    ap.add_argument("--out", default="data/reports")
    ap.add_argument("--offline", action="store_true", help="code checks only, no model calls")
    ap.add_argument("--local", action="store_true", help="don't log the run to the Foundry project")
    ap.add_argument("--judge-model", help="deployment for the judge and back-translation (default FOUNDRY_MODEL)")
    ap.add_argument("--limit", type=int, help="score only the first N items")
    ap.add_argument("--concurrency", type=int, default=2,
                    help="model calls at once (default 2; use 1 if the deployment's rate limit is low)")
    a = ap.parse_args()

    run_dir, out_dir = Path(a.run), Path(a.out)
    rows = broadcast_rows(run_dir) + ask_rows(Path(a.ask_log))
    if a.limit:
        rows = rows[:a.limit]
    if not rows:
        sys.exit(f"Nothing to score: no model-written graphics in {run_dir} and no checked answers in {a.ask_log}. "
                 "Run scripts/run_broadcast.py (not --offline) first.")
    print(f"{len(rows)} items: " + ", ".join(f"{n} {s}" for s, n in
                                              sorted({s: sum(r['source'] == s for r in rows) for s in
                                                      {r['source'] for r in rows}}.items())))
    studio_url, judge = None, None
    if a.offline:
        rows = run_offline(rows)
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
        asyncio.run(back_translate(rows, a.judge_model, a.concurrency))
        judge = a.judge_model or _env().get("FOUNDRY_MODEL", "gpt-5-mini")
        rows, studio_url = run_foundry(rows, out_dir, upload=not a.local, judge_model=a.judge_model,
                                       concurrency=a.concurrency)
    report = write_report(rows, broadcast_stats(run_dir), studio_url, judge, out_dir)
    o = report["summary"]["overall"]
    print(f"Grounded {_fmt(o['grounded_avg'])}/5 (pass {_fmt(o['grounded_pass'], True)}), numbers traced "
          f"{_fmt(o['numbers_traced'], True)}, right language {_fmt(o['right_language'], True)}.")
    print(f"Report: {out_dir / 'agent_eval.md'}" + (f"\nFoundry: {studio_url}" if studio_url else ""))


if __name__ == "__main__":
    main()
