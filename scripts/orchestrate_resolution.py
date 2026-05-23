#!/usr/bin/env python3
"""Orchestrate PM -> Worker -> Reviewer resolution loops for Context Sphere tasks."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from context_sphere_v3.assembler import DEFAULT_MAX_FILE_CHARS
from context_sphere_v3.assembler import assemble_context_sphere
from context_sphere_v3.assembler import load_selector_output
from context_sphere_v3.projection import assemble_projected_context_spheres


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
MINIMAX_BASE_URL = "https://api.minimaxi.com/v1"
MINIMAX_MODEL = "MiniMax-M2.7"
DEFAULT_MAX_ATTEMPTS = 3
MODEL_STRATEGIES = ("monolithic", "heterogeneous", "fallback")
PRICING_BASIS = "scenario_profile_user_supplied_not_vendor_quote_2026_05_23"
DEEPSEEK_PRICING_SOURCE = "https://api-docs.deepseek.com/quick_start/pricing-details-usd"
STATE_INIT = "State_INIT"
STATE_PM = "State_PM"
STATE_WORKER = "State_WORKER"
STATE_TARGET_PREFLIGHT = "State_TARGET_PREFLIGHT"
STATE_REVIEWER = "State_REVIEWER"
STATE_VERIFY = "State_VERIFY"
STATE_DONE = "State_DONE"
STATE_MANUAL = "State_MANUAL_INTERVENTION"


def load_dotenv(path: str | Path) -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a float-compatible USD-per-1M-token value") from exc


def route_profile(
    *,
    provider_class: str,
    provider: str,
    client: str,
    model: str,
    role: str,
    base_url: str | None,
    api_key_env: str | None,
    input_usd_per_1m_tokens: float,
    output_usd_per_1m_tokens: float,
    active_completion_call: bool,
) -> dict[str, Any]:
    return {
        "role": role,
        "provider_class": provider_class,
        "provider": provider,
        "client": client,
        "model": model,
        "base_url": base_url,
        "api_key_env": api_key_env,
        "active_completion_call": active_completion_call,
        "pricing": {
            "basis": PRICING_BASIS,
            "input_usd_per_1m_tokens": input_usd_per_1m_tokens,
            "output_usd_per_1m_tokens": output_usd_per_1m_tokens,
        },
    }


def build_routing_profile(*, strategy: str, base_url: str, model: str) -> dict[str, dict[str, Any]]:
    if strategy not in MODEL_STRATEGIES:
        raise ValueError(f"unknown model strategy: {strategy}")
    if strategy in {"monolithic", "fallback"}:
        profile = route_profile(
            provider_class="fast_cost_efficient",
            provider="deepseek",
            client="openai_chat_completions",
            model=model,
            role="shared",
            base_url=base_url,
            api_key_env="DEEPSEEK_API_KEY",
            input_usd_per_1m_tokens=env_float("CONTEXT_SPHERE_MONOLITHIC_INPUT_USD_PER_1M", 0.27),
            output_usd_per_1m_tokens=env_float("CONTEXT_SPHERE_MONOLITHIC_OUTPUT_USD_PER_1M", 1.10),
            active_completion_call=True,
        )
        profile["pricing"]["source"] = DEEPSEEK_PRICING_SOURCE
        profile["pricing"]["input_price_policy"] = "cache_miss"
        secondary = route_profile(
            provider_class="fallback_cost_efficient",
            provider="minimax",
            client="openai_chat_completions",
            model=os.environ.get("CONTEXT_SPHERE_FALLBACK_MODEL", MINIMAX_MODEL),
            role="secondary",
            base_url=os.environ.get("CONTEXT_SPHERE_FALLBACK_BASE_URL", MINIMAX_BASE_URL),
            api_key_env=os.environ.get("CONTEXT_SPHERE_FALLBACK_API_KEY_ENV", "MINIMAX_API_KEY"),
            input_usd_per_1m_tokens=env_float("CONTEXT_SPHERE_FALLBACK_INPUT_USD_PER_1M", 0.30),
            output_usd_per_1m_tokens=env_float("CONTEXT_SPHERE_FALLBACK_OUTPUT_USD_PER_1M", 1.20),
            active_completion_call=True,
        )
        routes = {}
        for role in ("locator", "assembler", "pm", "worker", "reviewer"):
            role_profile = dict(profile)
            role_profile["role"] = role
            role_profile["active_completion_call"] = role in {"pm", "worker", "reviewer"}
            if strategy == "fallback":
                secondary_profile = dict(secondary)
                secondary_profile["role"] = role
                secondary_profile["active_completion_call"] = role in {"pm", "worker", "reviewer"}
                role_profile["secondary"] = secondary_profile
            routes[role] = role_profile
        return routes

    long_context = route_profile(
        provider_class="long_context",
        provider=os.environ.get("CONTEXT_SPHERE_LONG_CONTEXT_PROVIDER", "frontier-long-context"),
        client=os.environ.get("CONTEXT_SPHERE_LONG_CONTEXT_CLIENT", "semantic_profile_metadata"),
        model=os.environ.get("CONTEXT_SPHERE_LONG_CONTEXT_MODEL", "gemini-3.1-pro-or-equivalent"),
        role="locator_assembler",
        base_url=os.environ.get("CONTEXT_SPHERE_LONG_CONTEXT_BASE_URL"),
        api_key_env=os.environ.get("CONTEXT_SPHERE_LONG_CONTEXT_API_KEY_ENV"),
        input_usd_per_1m_tokens=env_float("CONTEXT_SPHERE_LONG_CONTEXT_INPUT_USD_PER_1M", 1.25),
        output_usd_per_1m_tokens=env_float("CONTEXT_SPHERE_LONG_CONTEXT_OUTPUT_USD_PER_1M", 5.00),
        active_completion_call=False,
    )
    reasoning = route_profile(
        provider_class="elite_reasoning",
        provider=os.environ.get("CONTEXT_SPHERE_REASONING_PROVIDER", "frontier-reasoning"),
        client=os.environ.get("CONTEXT_SPHERE_REASONING_CLIENT", "openai_chat_completions"),
        model=os.environ.get("CONTEXT_SPHERE_REASONING_MODEL", "claude-4.6-sonnet-or-equivalent"),
        role="pm_reviewer",
        base_url=os.environ.get("CONTEXT_SPHERE_REASONING_BASE_URL"),
        api_key_env=os.environ.get("CONTEXT_SPHERE_REASONING_API_KEY_ENV", "CONTEXT_SPHERE_REASONING_API_KEY"),
        input_usd_per_1m_tokens=env_float("CONTEXT_SPHERE_REASONING_INPUT_USD_PER_1M", 3.00),
        output_usd_per_1m_tokens=env_float("CONTEXT_SPHERE_REASONING_OUTPUT_USD_PER_1M", 15.00),
        active_completion_call=True,
    )
    implementation = route_profile(
        provider_class="implementation",
        provider=os.environ.get("CONTEXT_SPHERE_WORKER_PROVIDER", "frontier-implementation"),
        client=os.environ.get("CONTEXT_SPHERE_WORKER_CLIENT", "openai_chat_completions"),
        model=os.environ.get("CONTEXT_SPHERE_WORKER_MODEL", "gpt-5.4-pro-or-equivalent"),
        role="worker",
        base_url=os.environ.get("CONTEXT_SPHERE_WORKER_BASE_URL"),
        api_key_env=os.environ.get("CONTEXT_SPHERE_WORKER_API_KEY_ENV", "CONTEXT_SPHERE_WORKER_API_KEY"),
        input_usd_per_1m_tokens=env_float("CONTEXT_SPHERE_WORKER_INPUT_USD_PER_1M", 5.00),
        output_usd_per_1m_tokens=env_float("CONTEXT_SPHERE_WORKER_OUTPUT_USD_PER_1M", 25.00),
        active_completion_call=True,
    )
    return {
        "locator": dict(long_context, role="locator"),
        "assembler": dict(long_context, role="assembler"),
        "pm": dict(reasoning, role="pm"),
        "worker": dict(implementation, role="worker"),
        "reviewer": dict(reasoning, role="reviewer"),
    }


def issue_slug(issue_url: str) -> str:
    value = issue_url.strip().rstrip("/")
    if value.startswith("https://github.com/"):
        parts = value.removeprefix("https://github.com/").split("/")
        if len(parts) >= 4 and parts[2] == "issues":
            return f"{parts[0]}__{parts[1]}__{parts[3]}"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_") or "issue"


def issue_arg_for_inference(issue_url: str) -> tuple[str, str]:
    if issue_url.startswith("https://github.com/"):
        return "--issue-url", issue_url
    return "--issue", issue_url


def default_python_bin() -> str:
    candidate = ROOT / ".venv" / "bin" / "python"
    return str(candidate) if candidate.exists() else sys.executable


def run_command(command: list[str], *, cwd: Path) -> dict[str, Any]:
    started = time.time()
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "elapsed_seconds": round(time.time() - started, 3),
    }


def require_command_success(result: dict[str, Any]) -> None:
    if int(result["returncode"]) != 0:
        raise RuntimeError(
            "command failed: "
            + " ".join(result["command"])
            + f"\nstdout:\n{result['stdout']}\nstderr:\n{result['stderr']}"
        )


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")


def chat_completion(
    *,
    api_key: str,
    base_url: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
    timeout: int,
) -> dict[str, Any]:
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
            status = response.status
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"chat completion request failed with HTTP {exc.code}: {error_body[:2000]}") from exc
    parsed = json.loads(body)
    parsed["_request_meta"] = {
        "endpoint": endpoint,
        "model": model,
        "elapsed_seconds": round(time.time() - started, 3),
        "http_status": status,
    }
    return parsed


def extract_content(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                return message["content"]
            if isinstance(first.get("text"), str):
                return first["text"]
    if isinstance(response.get("reply"), str):
        return response["reply"]
    raise ValueError("Could not find assistant content in MiniMax response")


def response_usage(response: dict[str, Any]) -> dict[str, int]:
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    input_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    total_tokens = int(usage.get("total_tokens") or usage.get("total") or input_tokens + output_tokens)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def estimate_event_cost(profile: dict[str, Any], *, input_tokens: int, output_tokens: int) -> float:
    pricing = profile.get("pricing") if isinstance(profile.get("pricing"), dict) else {}
    input_rate = float(pricing.get("input_usd_per_1m_tokens") or 0.0)
    output_rate = float(pricing.get("output_usd_per_1m_tokens") or 0.0)
    return round((input_tokens * input_rate + output_tokens * output_rate) / 1_000_000, 8)


def summarize_model_usage(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_role: dict[str, Any] = {}
    for event in events:
        role = str(event["role"])
        row = by_role.setdefault(
            role,
            {
                "calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "estimated_inference_cost_usd": 0.0,
            },
        )
        row["calls"] += 1
        row["input_tokens"] += int(event["input_tokens"])
        row["output_tokens"] += int(event["output_tokens"])
        row["total_tokens"] += int(event["total_tokens"])
        row["estimated_inference_cost_usd"] = round(
            float(row["estimated_inference_cost_usd"]) + float(event["estimated_cost_usd"]),
            8,
        )
    return {
        "pricing_basis": PRICING_BASIS,
        "calls": len(events),
        "input_tokens": sum(int(event["input_tokens"]) for event in events),
        "output_tokens": sum(int(event["output_tokens"]) for event in events),
        "total_tokens": sum(int(event["total_tokens"]) for event in events),
        "estimated_inference_cost_usd": round(sum(float(event["estimated_cost_usd"]) for event in events), 8),
        "by_role": by_role,
        "events": events,
    }


def per_dollar(numerator: int | float, cost_usd: float) -> float | None:
    if cost_usd <= 0:
        return None
    return round(float(numerator) / cost_usd, 8)


def provider_error_is_fallbackable(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return bool(
        re.search(r"http\s+(402|429|5\d\d)", text)
        or "rate limit" in text
        or "ratelimit" in text
        or "quota" in text
        or "quotaexceeded" in text
        or "insufficient balance" in text
        or "payment required" in text
        or "timeout" in text
        or "timed out" in text
        or "temporarily unavailable" in text
        or "server error" in text
    )


def sanitized_provider_error(exc: Exception) -> dict[str, str]:
    message = str(exc)
    message = re.sub(r"(bearer\s+)[A-Za-z0-9_.-]+", r"\1[REDACTED]", message, flags=re.IGNORECASE)
    message = re.sub(r"(api[_-]?key[=:]\s*)[A-Za-z0-9_.-]+", r"\1[REDACTED]", message, flags=re.IGNORECASE)
    return {
        "type": type(exc).__name__,
        "message": message[:2000],
    }


def execute_profile_completion(
    *,
    role: str,
    profile: dict[str, Any],
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
    timeout: int,
    raw_out: Path,
    usage_events: list[dict[str, Any]],
) -> str:
    if profile.get("client") != "openai_chat_completions":
        raise RuntimeError(f"Role {role} uses unsupported live client: {profile.get('client')}")
    base_url = str(profile.get("base_url") or "")
    api_key_env = str(profile.get("api_key_env") or "")
    if not base_url:
        raise RuntimeError(f"Role {role} has no base_url configured for strategy profile")
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise RuntimeError(f"{api_key_env} is not visible in shell env or .env.local for role {role}")
    response = chat_completion(
        api_key=api_key,
        base_url=base_url,
        model=str(profile["model"]),
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        timeout=timeout,
    )
    write_json(raw_out, response)
    usage = response_usage(response)
    usage_events.append(
        {
            "role": role,
            "provider_class": profile.get("provider_class"),
            "provider": profile.get("provider"),
            "client": profile.get("client"),
            "model": profile.get("model"),
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "total_tokens": usage["total_tokens"],
            "estimated_cost_usd": estimate_event_cost(
                profile,
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
            ),
        }
    )
    return strip_hidden_thinking(extract_content(response))


def routed_text(
    *,
    role: str,
    profile: dict[str, Any],
    attempt_index: int,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int,
    temperature: float,
    timeout: int,
    raw_out: Path,
    usage_events: list[dict[str, Any]],
    provider_swaps: list[dict[str, Any]],
) -> str:
    try:
        return execute_profile_completion(
            role=role,
            profile=profile,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            raw_out=raw_out,
            usage_events=usage_events,
        )
    except Exception as exc:
        secondary = profile.get("secondary")
        if not isinstance(secondary, dict) or not provider_error_is_fallbackable(exc):
            raise
        provider_swaps.append(
            {
                "state": role,
                "attempt_index": attempt_index,
                "from_provider": profile.get("provider"),
                "from_model": profile.get("model"),
                "to_provider": secondary.get("provider"),
                "to_model": secondary.get("model"),
                "error": sanitized_provider_error(exc),
                "at": time.time(),
            }
        )
        fallback_raw_out = raw_out.with_name(raw_out.stem + ".fallback" + raw_out.suffix)
        return execute_profile_completion(
            role=role,
            profile=secondary,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            raw_out=fallback_raw_out,
            usage_events=usage_events,
        )


def strip_hidden_thinking(text: str) -> str:
    return re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()


def extract_json_object(text: str) -> dict[str, Any]:
    cleaned = strip_hidden_thinking(text)
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    candidate = fenced.group(1) if fenced else cleaned
    if not candidate.strip().startswith("{"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start : end + 1]
    return json.loads(candidate)


SEARCH_REPLACE_BLOCK_PATTERN = re.compile(
    r"<<<<<<< SEARCH\n(?P<search>.*?)\n=======\n(?P<replace>.*?)\n>>>>>>> REPLACE",
    flags=re.DOTALL,
)
FILE_MARKER_PATTERN = re.compile(
    r"(?im)^\s*(?:FILE|File|Target file|Path)\s*:\s*`?(?P<path>[^`\n]+?)`?\s*$"
)


def repo_text_files(repo_path: Path) -> list[Path]:
    try:
        result = run_command(["git", "ls-files"], cwd=repo_path)
        if result["returncode"] == 0:
            files = []
            for raw in result["stdout"].splitlines():
                candidate = (repo_path / raw).resolve()
                try:
                    candidate.relative_to(repo_path.resolve())
                except ValueError:
                    continue
                if candidate.is_file():
                    files.append(candidate)
            return files
    except Exception:
        pass
    ignored = {".git", "__pycache__", ".mypy_cache", ".pytest_cache", ".tox", ".venv", "venv", "node_modules"}
    return [
        path
        for path in repo_path.rglob("*")
        if path.is_file() and not any(part in ignored for part in path.relative_to(repo_path).parts)
    ]


def infer_file_for_search(repo_path: Path, search: str) -> str | None:
    matches: list[str] = []
    for candidate in repo_text_files(repo_path):
        try:
            text = candidate.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        except OSError:
            continue
        if search in text:
            matches.append(candidate.relative_to(repo_path).as_posix())
            if len(matches) > 1:
                return None
    return matches[0] if len(matches) == 1 else None


def normalize_repo_relative_path(repo_path: Path, raw_path: str) -> str | None:
    path_text = raw_path.strip().strip("'\"")
    if path_text.startswith("a/") or path_text.startswith("b/"):
        path_text = path_text[2:]
    candidate = Path(path_text)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (repo_path / candidate).resolve()
    try:
        relative = resolved.relative_to(repo_path.resolve())
    except ValueError:
        return None
    return relative.as_posix()


def parse_search_replace_blocks(text: str, *, repo_path: Path | None = None) -> list[dict[str, str]]:
    cleaned = strip_hidden_thinking(text)
    changes: list[dict[str, str]] = []
    previous_end = 0
    current_file = ""
    for match in SEARCH_REPLACE_BLOCK_PATTERN.finditer(cleaned):
        header = cleaned[previous_end : match.start()]
        file_matches = list(FILE_MARKER_PATTERN.finditer(header))
        raw_path = file_matches[-1].group("path").strip() if file_matches else current_file
        search = match.group("search")
        replace = match.group("replace")
        if not raw_path and repo_path is not None:
            inferred = infer_file_for_search(repo_path, search)
            raw_path = inferred or ""
        if not raw_path:
            raise ValueError("Search/Replace block is missing a FILE: path marker and file inference was ambiguous")
        file_path = normalize_repo_relative_path(repo_path, raw_path) if repo_path is not None else raw_path
        if not file_path:
            raise ValueError(f"Search/Replace block points outside the repository: {raw_path}")
        changes.append(
            {
                "file_path": file_path,
                "search": search,
                "replace": replace,
            }
        )
        current_file = raw_path
        previous_end = match.end()
    if not changes:
        raise ValueError("No Search/Replace blocks found; Worker must not emit raw unified diffs")
    return changes


PREFLIGHT_MALFORMED_BLOCK = (
    "[PREFLIGHT ERROR]: Malformed block structure. You declared a target file but failed to open a valid "
    "<<<<<<< SEARCH block followed by an ======= divider."
)
PREFLIGHT_TRUNCATED_PAYLOAD = (
    "[PREFLIGHT ERROR]: Truncated payload. Your block lacks the closing >>>>>>> REPLACE terminator."
)


def syntactic_preflight_feedback(patch_text: str) -> tuple[str, str] | None:
    cleaned = strip_hidden_thinking(patch_text)
    has_file = FILE_MARKER_PATTERN.search(cleaned) is not None
    has_search = "<<<<<<< SEARCH" in cleaned
    has_divider = "=======" in cleaned
    has_replace = ">>>>>>> REPLACE" in cleaned
    if has_search and has_divider and not has_replace:
        return "truncated_payload", PREFLIGHT_TRUNCATED_PAYLOAD
    if has_file and (not has_search or not has_divider):
        return "malformed_block_structure", PREFLIGHT_MALFORMED_BLOCK
    return None


def validate_patch_target_files(repo_path: Path, patch_text: str, *, attempt: int) -> dict[str, Any]:
    started = time.time()
    try:
        changes = parse_search_replace_blocks(patch_text, repo_path=repo_path)
    except Exception as exc:
        diagnostic = syntactic_preflight_feedback(patch_text)
        kind = diagnostic[0] if diagnostic else "invalid_search_replace_blocks"
        worker_message = (
            diagnostic[1]
            if diagnostic
            else (
                "ERROR: Your response did not contain valid Search/Replace blocks. You must emit only FILE: "
                "path plus <<<<<<< SEARCH / ======= / >>>>>>> REPLACE blocks targeting existing repository files."
            )
        )
        return {
            "attempt": attempt,
            "valid": False,
            "kind": kind,
            "error": f"{type(exc).__name__}: {exc}",
            "target_files": [],
            "invalid_target_files": [],
            "elapsed_seconds": round(time.time() - started, 3),
            "worker_message": worker_message,
        }

    repo = repo_path.resolve()
    target_files: list[str] = []
    invalid_files: list[str] = []
    for change in changes:
        file_path = str(change["file_path"])
        target_files.append(file_path)
        resolved = (repo / file_path).resolve()
        try:
            resolved.relative_to(repo)
        except ValueError:
            invalid_files.append(file_path)
            continue
        if not os.path.exists(str(resolved)):
            invalid_files.append(file_path)
    if invalid_files:
        path_list = ", ".join(invalid_files)
        return {
            "attempt": attempt,
            "valid": False,
            "kind": "invalid_target_file",
            "error": f"Target file path does not exist in repository workspace: {path_list}",
            "target_files": target_files,
            "invalid_target_files": invalid_files,
            "elapsed_seconds": round(time.time() - started, 3),
            "worker_message": (
                f"ERROR: The file path you targeted [{path_list}] does not exist in this repository workspace. "
                "You are strictly restricted to modifying existing files discovered within your active Context "
                "Sphere or selector output."
            ),
        }
    return {
        "attempt": attempt,
        "valid": True,
        "kind": "valid_target_files",
        "error": None,
        "target_files": target_files,
        "invalid_target_files": [],
        "elapsed_seconds": round(time.time() - started, 3),
        "worker_message": None,
    }


def parse_review_status(text: str) -> str:
    upper = strip_hidden_thinking(text).upper()
    approved_index = upper.find("APPROVED")
    rejected_index = upper.find("REJECTED")
    if approved_index >= 0 and (rejected_index < 0 or approved_index < rejected_index):
        return "APPROVED"
    if rejected_index >= 0:
        return "REJECTED"
    return "REJECTED"


def pm_prompt(issue_url: str, pm_sphere: str) -> tuple[str, str]:
    system = (
        "You are the PM lens in a code-resolution loop. Do not call tools. "
        "Return only valid JSON with keys: issue_url, constraints, acceptance_criteria, risks, reviewer_feedback."
    )
    user = "\n".join(
        [
            f"Issue: {issue_url}",
            "Read this PM Context Sphere and produce constraints.json for the Worker.",
            "Keep constraints specific and implementation-relevant.",
            "",
            pm_sphere,
        ]
    )
    return system, user


def worker_prompt(issue_url: str, worker_sphere: str, constraints: dict[str, Any]) -> tuple[str, str]:
    system = (
        "You are the Worker lens in a code-resolution loop. Do not call tools. "
        "Do not emit git diffs, unified diffs, @@ hunk headers, or line-count headers. "
        "Return only precise Search/Replace edit blocks. Each block must include a FILE line "
        "followed by this exact structure:\n"
        "FILE: path/to/file.py\n"
        "<<<<<<< SEARCH\n"
        "[exact original code block from the repository]\n"
        "=======\n"
        "[the updated code block to replace it with]\n"
        ">>>>>>> REPLACE"
        "\n\n"
        "You must strictly adhere to the following output syntax. Do not include conversational preambles, "
        "introductory summaries, or loose explanations. Output your modifications using exactly this structure:\n\n"
        "FILE: path/to/target_file.py\n"
        "<<<<<<< SEARCH\n"
        "def existing_function_name(x):\n"
        "    return x + 1\n"
        "=======\n"
        "def existing_function_name(x):\n"
        "    \"\"\"Fixed docstring regression.\"\"\"\n"
        "    return x + 2\n"
        ">>>>>>> REPLACE\n\n"
        "CRITICAL: The SEARCH block must copy the target lines from your context repository EXACTLY, "
        "character-for-character, space-for-space. Keep the SEARCH window as minimal as possible (1 to 3 lines "
        "max). If you need to make edits in separate regions of the same file, output multiple distinct "
        "FILE/SEARCH/REPLACE sequences sequentially."
    )
    user = "\n".join(
        [
            f"Issue: {issue_url}",
            "Use the Context Sphere and constraints to generate minimal Search/Replace edits.",
            "The SEARCH section must match the current repository text exactly.",
            "CRITICAL CONSTRAINT: You are strictly forbidden from fabricating paths or attempting to create new "
            "modules. Every SEARCH block must target a verified, existing repository file.",
            "CRITICAL: Keep your SEARCH blocks as compact as possible. Do not include excessive surrounding "
            "padding lines. Provide only the absolute minimum number of lines, ideally 1 to 3 lines, required "
            "to uniquely identify the edit location in the file. This drastically minimizes the risk of line "
            "formatting mismatches.",
            "Do not include commentary outside FILE + SEARCH/REPLACE blocks.",
            "",
            "constraints.json:",
            json.dumps(constraints, indent=2, ensure_ascii=False),
            "",
            "Worker Context Sphere:",
            worker_sphere,
        ]
    )
    return system, user


def reviewer_prompt(issue_url: str, reviewer_sphere: str, patch_blocks: str) -> tuple[str, str]:
    system = (
        "You are the Reviewer lens in a code-resolution loop. Do not call tools. "
        "Start your response with APPROVED or REJECTED on the first line, then explain. "
        "Review Search/Replace edit blocks, not unified diffs. "
        "Never reject for minor formatting style, missing type hints, naming taste, or cosmetic conventions. "
        "Reject only for an explicit syntax error, a breaking logical regression, or a clear violation of "
        "constraints.json."
    )
    user = "\n".join(
        [
            f"Issue: {issue_url}",
            "Review these candidate Search/Replace edits against the Context Sphere.",
            "",
            "patch_blocks:",
            patch_blocks,
            "",
            "Reviewer Context Sphere:",
            reviewer_sphere,
        ]
    )
    return system, user


def dry_constraints(issue_url: str) -> dict[str, Any]:
    return {
        "issue_url": issue_url,
        "constraints": [
            "Keep the patch minimal.",
            "Preserve existing public behavior unless the issue requires a compatibility fix.",
            "Add or describe a regression test for the reported URL handling behavior.",
        ],
        "acceptance_criteria": [
            "Patch is expressed as exact Search/Replace blocks.",
            "Patch targets files present in the Context Sphere.",
            "Reviewer can approve or reject with concrete feedback.",
        ],
        "risks": ["Dry-run constraints are placeholders, not model evidence."],
        "reviewer_feedback": [],
    }


def dry_patch(attempt: int) -> str:
    return "\n".join(
        [
            "FILE: src/demo/core.py",
            "<<<<<<< SEARCH",
            "import os",
            "from .helper import normalize",
            "from demo.config import SETTINGS",
            "=======",
            "import os",
            "from .helper import normalize",
            "from demo.config import SETTINGS",
            f"# dry-run patch attempt {attempt}",
            ">>>>>>> REPLACE",
            "",
        ]
    )


def dry_review(attempt: int) -> str:
    if attempt == 1:
        return "REJECTED\nThe patch is only a placeholder and needs a real implementation plus regression test.\n"
    return "APPROVED\nDry-run approval after feedback loop exercised.\n"


def append_feedback(constraints: dict[str, Any], *, attempt: int, review: str) -> dict[str, Any]:
    updated = json.loads(json.dumps(constraints))
    feedback = updated.setdefault("reviewer_feedback", [])
    if not isinstance(feedback, list):
        feedback = []
        updated["reviewer_feedback"] = feedback
    feedback.append({"attempt": attempt, "review": review})
    return updated


def append_worker_preflight_feedback(
    constraints: dict[str, Any],
    *,
    attempt: int,
    preflight: dict[str, Any],
) -> dict[str, Any]:
    updated = json.loads(json.dumps(constraints))
    feedback = updated.setdefault("reviewer_feedback", [])
    if not isinstance(feedback, list):
        feedback = []
        updated["reviewer_feedback"] = feedback
    message = str(preflight.get("worker_message") or preflight.get("error") or "Worker patch preflight failed.")
    feedback.append(
        {
            "attempt": attempt,
            "source": "target_file_preflight",
            "review": message,
            "preflight": preflight,
        }
    )
    return updated


def append_test_failure_feedback(
    constraints: dict[str, Any],
    *,
    attempt: int,
    patch_apply: dict[str, Any],
    test_result: dict[str, Any] | None,
    build_result: dict[str, Any] | None = None,
    context_expansion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    updated = json.loads(json.dumps(constraints))
    feedback = updated.setdefault("reviewer_feedback", [])
    if not isinstance(feedback, list):
        feedback = []
        updated["reviewer_feedback"] = feedback
    feedback.append(
        {
            "attempt": attempt,
            "source": STATE_VERIFY,
            "review": (
                "Patch was reviewer-approved but failed the required inplace build before tests."
                if build_result is not None and int(build_result.get("returncode", 0)) != 0
                else "Patch was reviewer-approved but failed execution verification."
            ),
            "patch_apply": patch_apply,
            "build_result": build_result,
            "test_result": test_result,
            "context_expansion": context_expansion,
        }
    )
    if context_expansion is not None:
        expansions = updated.setdefault("verification_context_expansions", [])
        if not isinstance(expansions, list):
            expansions = []
            updated["verification_context_expansions"] = expansions
        expansions.append(context_expansion)
    return updated


REPO_PATH_PATTERN = re.compile(
    r"(?P<path>(?:[A-Za-z0-9_. -]+/)+[A-Za-z0-9_. -]+\.(?:py|pyi|js|jsx|ts|tsx|go|rs|java|rb|sh|toml|yaml|yml|json|md|rst|txt))"
)
ABSOLUTE_FILE_PATTERN = re.compile(r'File\s+"(?P<path>[^"]+)"')
MODULE_PATTERN = re.compile(
    r"(?:ModuleNotFoundError|ImportError)[^\n]*(?:No module named|from|module named)\s+[\"'](?P<module>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)[\"']"
)


def repo_relative_existing_file(repo_path: Path, raw_path: str) -> str | None:
    repo = repo_path.resolve()
    candidate = Path(raw_path)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (repo / raw_path).resolve()
    try:
        relative = resolved.relative_to(repo)
    except ValueError:
        return None
    if not resolved.is_file():
        return None
    return relative.as_posix()


def module_to_repo_file(repo_path: Path, module_name: str) -> str | None:
    parts = [part for part in module_name.split(".") if part]
    if not parts:
        return None
    repo = repo_path.resolve()
    module_path = Path(*parts)
    for root in (repo, repo / "src", repo / "lib"):
        for candidate in (root / module_path.with_suffix(".py"), root / module_path / "__init__.py"):
            try:
                relative = candidate.resolve().relative_to(repo)
            except ValueError:
                continue
            if candidate.is_file():
                return relative.as_posix()
    return None


def extract_repo_files_from_trace(repo_path: Path, trace_text: str) -> list[str]:
    files: list[str] = []
    seen: set[str] = set()
    for pattern in (ABSOLUTE_FILE_PATTERN, REPO_PATH_PATTERN):
        for match in pattern.finditer(trace_text):
            relative = repo_relative_existing_file(repo_path, match.group("path"))
            if relative and relative not in seen:
                seen.add(relative)
                files.append(relative)
    for match in MODULE_PATTERN.finditer(trace_text):
        relative = module_to_repo_file(repo_path, match.group("module"))
        if relative and relative not in seen:
            seen.add(relative)
            files.append(relative)
    return files


def selector_known_files(selector_output: dict[str, Any]) -> set[str]:
    known: set[str] = set()
    for row in selector_output.get("top_files", []) or []:
        path = str(row.get("path", "")).strip()
        if path:
            known.add(path)
    for row in selector_output.get("active_sub_centroids", []) or []:
        path = str(row.get("path", "")).strip()
        if path:
            known.add(path)
    return known


def register_sub_centroids(
    *,
    selector_path: Path,
    repo_path: Path,
    trace_text: str,
    attempt: int,
) -> tuple[dict[str, Any], list[str]]:
    selector = load_selector_output(selector_path)
    discovered = extract_repo_files_from_trace(repo_path, trace_text)
    known = selector_known_files(selector)
    new_files = [path for path in discovered if path not in known]
    if not new_files:
        return selector, []
    top_files = selector.setdefault("top_files", [])
    sub_centroids = selector.setdefault("active_sub_centroids", [])
    for path in new_files:
        row = {
            "path": path,
            "score": 0.0,
            "source": "verification_failure_trace",
            "attempt": attempt,
        }
        top_files.append(row)
        sub_centroids.append(row)
    write_json(selector_path, selector)
    return selector, new_files


def append_recursive_context(
    *,
    run_dir: Path,
    repo_path: Path,
    selector_output: dict[str, Any],
    sub_centroid_files: list[str],
    attempt: int,
    max_file_chars: int,
    max_neighborhood_files: int,
) -> dict[str, Any] | None:
    if not sub_centroid_files:
        return None
    sub_selector = json.loads(json.dumps(selector_output))
    sub_selector["top_files"] = [
        {
            "path": path,
            "score": 0.0,
            "source": "verification_failure_trace",
            "attempt": attempt,
        }
        for path in sub_centroid_files
    ]
    sub_selector["top_chunks"] = [
        {
            "chunk_id": f"verification_failure_attempt_{attempt}",
            "score": 0.0,
            "text": "Files discovered from execution verification failure trace.",
        }
    ]
    appended: dict[str, Any] = {}
    for persona in ("WORKER", "REVIEWER"):
        sphere_path = run_dir / f"{persona.lower()}_sphere.md"
        before = sphere_path.stat().st_size if sphere_path.exists() else 0
        assembled = assemble_context_sphere(
            selector_output=sub_selector,
            repo_path=repo_path,
            target_persona=persona,
            max_file_chars=max_file_chars,
            max_neighborhood_files=max_neighborhood_files,
        )
        append_text = "\n\n".join(
            [
                "",
                "## Recursive Verification Context Expansion",
                "",
                f"- Attempt: `{attempt}`",
                "- Trigger: execution verification failure trace",
                "- Use this expanded context before retrying the patch.",
                "",
                str(assembled["markdown"]).strip(),
                "",
            ]
        )
        with sphere_path.open("a", encoding="utf-8") as handle:
            handle.write(append_text)
        json_path = run_dir / f"{persona.lower()}_sphere_recursive_v{attempt}.json"
        write_json(json_path, {key: value for key, value in assembled.items() if key != "markdown"})
        after = sphere_path.stat().st_size
        appended[persona.lower()] = {
            "sphere_path": str(sphere_path),
            "recursive_json_path": str(json_path),
            "chars_before": before,
            "chars_after": after,
            "core_files": assembled["core_files"],
            "neighborhood_files": assembled["neighborhood_files"],
        }
    return {
        "attempt": attempt,
        "source": STATE_VERIFY,
        "sub_centroid_files": sub_centroid_files,
        "token_bounds": {
            "worker_sphere_chars_before": appended["worker"]["chars_before"],
            "worker_sphere_chars_after": appended["worker"]["chars_after"],
            "reviewer_sphere_chars_before": appended["reviewer"]["chars_before"],
            "reviewer_sphere_chars_after": appended["reviewer"]["chars_after"],
            "max_file_chars": max_file_chars,
            "max_neighborhood_files": max_neighborhood_files,
        },
        "worker_neighborhood_files": appended["worker"]["neighborhood_files"],
        "reviewer_neighborhood_files": appended["reviewer"]["neighborhood_files"],
        "artifacts": appended,
    }


def expand_context_from_verification_failure(
    *,
    run_dir: Path,
    repo_path: Path,
    selector_path: Path,
    verify_result: dict[str, Any],
    attempt: int,
    max_file_chars: int,
    max_neighborhood_files: int,
) -> dict[str, Any] | None:
    test_result = verify_result.get("test_result")
    if not isinstance(test_result, dict) or int(test_result.get("returncode", 0)) == 0:
        return None
    trace_text = "\n".join([str(test_result.get("stdout", "")), str(test_result.get("stderr", ""))])
    selector, sub_centroid_files = register_sub_centroids(
        selector_path=selector_path,
        repo_path=repo_path,
        trace_text=trace_text,
        attempt=attempt,
    )
    return append_recursive_context(
        run_dir=run_dir,
        repo_path=repo_path,
        selector_output=selector,
        sub_centroid_files=sub_centroid_files,
        attempt=attempt,
        max_file_chars=max_file_chars,
        max_neighborhood_files=max_neighborhood_files,
    )


def reset_repo(repo_path: Path) -> dict[str, Any]:
    return run_command(["git", "reset", "--hard", "HEAD"], cwd=repo_path)


def git_head(repo_path: Path) -> str | None:
    result = run_command(["git", "rev-parse", "HEAD"], cwd=repo_path)
    if result["returncode"] != 0:
        return None
    return result["stdout"].strip()


def reset_repo_to(repo_path: Path, revision: str | None) -> dict[str, Any]:
    target = revision or "HEAD"
    return run_command(["git", "reset", "--hard", target], cwd=repo_path)


def normalize_search_line(line: str) -> str:
    return line.rstrip()


def nonempty_normalized_lines(text: str) -> list[tuple[int, str]]:
    rows: list[tuple[int, str]] = []
    for index, line in enumerate(text.splitlines()):
        normalized = normalize_search_line(line)
        if normalized.strip():
            rows.append((index, normalized))
    return rows


def find_unique_subsequence(haystack: list[str], needle: list[str]) -> tuple[int, int] | None:
    if not needle or len(needle) > len(haystack):
        return None
    starts: list[int] = []
    max_start = len(haystack) - len(needle)
    for start in range(max_start + 1):
        if haystack[start : start + len(needle)] == needle:
            starts.append(start)
            if len(starts) > 1:
                return None
    if len(starts) != 1:
        return None
    return starts[0], starts[0] + len(needle)


def find_replacement_span(file_content: str, search_block: str) -> tuple[int, int, str]:
    strict_count = file_content.count(search_block)
    if strict_count == 1:
        start = file_content.find(search_block)
        return start, start + len(search_block), "exact"
    if strict_count > 1:
        raise ValueError(f"SEARCH block matched {strict_count} times exactly; expected one unique match")

    file_rows = nonempty_normalized_lines(file_content)
    search_rows = nonempty_normalized_lines(search_block)
    file_norm = [row[1] for row in file_rows]
    search_norm = [row[1] for row in search_rows]
    normalized_match = find_unique_subsequence(file_norm, search_norm)
    if normalized_match is not None:
        start_norm, end_norm = normalized_match
        start_line = file_rows[start_norm][0]
        end_line = file_rows[end_norm - 1][0] + 1
        return line_span_to_char_span(file_content, start_line, end_line) + ("normalized_whitespace",)

    signature_lines = search_norm[:2] if len(search_norm) >= 2 else search_norm[:1]
    signature_match = find_unique_subsequence(file_norm, signature_lines)
    if signature_match is not None:
        start_norm, end_norm = signature_match
        start_line = file_rows[start_norm][0]
        end_line = file_rows[end_norm - 1][0] + 1
        return line_span_to_char_span(file_content, start_line, end_line) + ("signature_anchor",)

    raise ValueError("SEARCH block matched 0 times, including whitespace-normalized and signature-anchor fallbacks")


def line_span_to_char_span(text: str, start_line: int, end_line: int) -> tuple[int, int]:
    lines = text.splitlines(keepends=True)
    start = sum(len(line) for line in lines[:start_line])
    end = sum(len(line) for line in lines[:end_line])
    return start, end


REBUILD_TRIGGER_SUFFIXES = {".c", ".cpp", ".cxx", ".cc", ".h", ".hpp", ".pyx", ".pyi"}
REBUILD_TRIGGER_FILES = {"setup.py", "setup.cfg", "pyproject.toml"}


def changed_files_require_rebuild(changed_files: list[str]) -> bool:
    for file_path in changed_files:
        path = Path(file_path)
        if path.name in REBUILD_TRIGGER_FILES or path.suffix.lower() in REBUILD_TRIGGER_SUFFIXES:
            return True
    return False


def purge_egg_cache(repo_path: Path) -> dict[str, Any]:
    egg_cache_path = repo_path / ".eggs"
    existed = os.path.exists(str(egg_cache_path))
    if existed:
        shutil.rmtree(egg_cache_path, ignore_errors=True)
    return {
        "path": str(egg_cache_path),
        "existed": existed,
        "removed": existed and not os.path.exists(str(egg_cache_path)),
    }


def apply_search_replace_blocks_to_repo(repo_path: Path, block_path: Path, *, attempt: int) -> dict[str, Any]:
    started = time.time()
    stdout_lines: list[str] = []
    try:
        raw = block_path.read_text(encoding="utf-8")
        changes = parse_search_replace_blocks(raw, repo_path=repo_path)
        touched_files: list[str] = []
        applied_changes: list[dict[str, Any]] = []
        for change in changes:
            file_path = change["file_path"]
            target = (repo_path / file_path).resolve()
            try:
                target.relative_to(repo_path.resolve())
            except ValueError:
                raise ValueError(f"Refusing to edit path outside repository: {file_path}")
            if not target.is_file():
                raise FileNotFoundError(f"Search/Replace target file does not exist: {file_path}")
            current = target.read_text(encoding="utf-8")
            start, end, match_mode = find_replacement_span(current, change["search"])
            target.write_text(current[:start] + change["replace"] + current[end:], encoding="utf-8")
            touched_files.append(file_path)
            applied_changes.append(
                {
                    "file_path": file_path,
                    "match_mode": match_mode,
                    "start_char": start,
                    "end_char": end,
                }
            )
            stdout_lines.append(f"applied search/replace to {file_path} via {match_mode}")

        diff_check = run_command(["git", "diff", "--check"], cwd=repo_path)
        if diff_check["returncode"] != 0:
            raise RuntimeError(f"git diff --check failed:\n{diff_check['stdout']}\n{diff_check['stderr']}")
        add_result = run_command(["git", "add", "--", *touched_files], cwd=repo_path)
        if add_result["returncode"] != 0:
            raise RuntimeError(f"git add failed:\n{add_result['stdout']}\n{add_result['stderr']}")
        diff_cached = run_command(["git", "diff", "--cached", "--quiet"], cwd=repo_path)
        if diff_cached["returncode"] == 0:
            raise RuntimeError("Search/Replace blocks produced no staged changes")
        commit_result = run_command(
            [
                "git",
                "-c",
                "user.name=Context Sphere",
                "-c",
                "user.email=context-sphere@example.invalid",
                "commit",
                "-m",
                f"context sphere structural patch attempt {attempt}",
            ],
            cwd=repo_path,
        )
        if commit_result["returncode"] != 0:
            raise RuntimeError(f"git commit failed:\n{commit_result['stdout']}\n{commit_result['stderr']}")
        return {
            "command": ["python", "apply_search_replace_blocks", str(block_path.resolve())],
            "format": "search_replace_blocks",
            "returncode": 0,
            "stdout": "\n".join(stdout_lines + [commit_result["stdout"].strip()]).strip() + "\n",
            "stderr": "",
            "elapsed_seconds": round(time.time() - started, 3),
            "changed_files": touched_files,
            "applied_changes": applied_changes,
            "commit": git_head(repo_path),
        }
    except Exception as exc:
        return {
            "command": ["python", "apply_search_replace_blocks", str(block_path.resolve())],
            "format": "search_replace_blocks",
            "returncode": 1,
            "stdout": "\n".join(stdout_lines),
            "stderr": f"{type(exc).__name__}: {exc}",
            "elapsed_seconds": round(time.time() - started, 3),
            "changed_files": [],
            "applied_changes": [],
            "commit": None,
        }


def split_test_command(test_cmd: str, *, python_bin: str | None = None) -> list[str]:
    parts = shlex.split(test_cmd)
    if parts and parts[0] in {"python", "python3"}:
        parts[0] = python_bin or default_python_bin()
    return parts



def run_verification(
    *,
    repo_path: Path,
    patch_blocks_path: Path,
    test_cmd: str | None,
    run_dir: Path,
    attempt: int,
    python_bin: str,
) -> dict[str, Any]:
    if not test_cmd:
        result = {
            "attempt": attempt,
            "patch_path": str(patch_blocks_path),
            "patch_format": "search_replace_blocks",
            "test_cmd": None,
            "patch_apply": None,
            "test_result": None,
            "cleanup": None,
            "tests_passed": None,
            "skipped": True,
            "skip_reason": "no test command provided",
        }
        write_json(run_dir / f"verify_v{attempt}.json", result)
        return result
    reset_result = reset_repo(repo_path)
    base_head = git_head(repo_path)
    patch_result = apply_search_replace_blocks_to_repo(repo_path, patch_blocks_path, attempt=attempt)
    test_result = None
    build_result = None
    build_cache_purge = None
    tests_passed: bool | None = None
    requires_rebuild = False
    if patch_result["returncode"] == 0:
        changed_files = [str(path) for path in patch_result.get("changed_files", [])]
        requires_rebuild = changed_files_require_rebuild(changed_files)
        if requires_rebuild:
            build_cache_purge = purge_egg_cache(repo_path)
            build_result = run_command([python_bin, "setup.py", "build_ext", "--inplace"], cwd=repo_path)
        if build_result is not None and build_result["returncode"] != 0:
            tests_passed = False
        else:
            test_result = run_command(split_test_command(test_cmd, python_bin=python_bin), cwd=repo_path)
            tests_passed = test_result["returncode"] == 0
    else:
        tests_passed = False
    # Leave repo clean for next attempt or future cases.
    cleanup_result = reset_repo_to(repo_path, base_head)
    result = {
        "attempt": attempt,
        "patch_path": str(patch_blocks_path),
        "patch_format": "search_replace_blocks",
        "test_cmd": test_cmd,
        "resolved_test_command": split_test_command(test_cmd, python_bin=python_bin),
        "base_head": base_head,
        "patch_apply": patch_result,
        "requires_rebuild": requires_rebuild,
        "build_cache_purge": build_cache_purge,
        "build_result": build_result,
        "test_result": test_result,
        "cleanup": cleanup_result,
        "tests_passed": tests_passed,
    }
    write_json(run_dir / f"verify_v{attempt}.json", result)
    if build_result is not None:
        write_text(run_dir / f"verify_v{attempt}.build.stdout", build_result.get("stdout", ""))
        write_text(run_dir / f"verify_v{attempt}.build.stderr", build_result.get("stderr", ""))
    if test_result is not None:
        write_text(run_dir / f"verify_v{attempt}.stdout", test_result.get("stdout", ""))
        write_text(run_dir / f"verify_v{attempt}.stderr", test_result.get("stderr", ""))
    return result


def state_init(
    *,
    issue_url: str,
    repo_path: Path,
    run_dir: Path,
    python_bin: str,
    selector_output: Path | None,
    max_file_chars: int,
    max_neighborhood_files: int,
    retrieval_mode: str,
    projection_model_dir: Path,
    projection_thresholds: Path,
    projection_device: str,
    projection_batch_size: int,
    projection_min_k: int,
) -> dict[str, Any]:
    selector_path = run_dir / "selector_output.json"
    command_results = []
    if selector_output is not None:
        selector_path.write_text(selector_output.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        issue_flag, issue_value = issue_arg_for_inference(issue_url)
        result = run_command(
            [
                python_bin,
                "scripts/inference.py",
                issue_flag,
                issue_value,
                "--out",
                str(selector_path),
            ],
            cwd=ROOT,
        )
        command_results.append(result)
        require_command_success(result)

    sphere_paths: dict[str, str] = {}
    sphere_json_paths: dict[str, str] = {}
    projection_summary: dict[str, Any] | None = None
    if retrieval_mode == "projection":
        selector = load_selector_output(selector_path)
        projected = assemble_projected_context_spheres(
            selector_output=selector,
            repo_path=repo_path,
            model_dir=projection_model_dir,
            thresholds_path=projection_thresholds,
            device=projection_device,
            batch_size=projection_batch_size,
            min_k=projection_min_k,
            max_file_chars=max_file_chars,
            max_neighborhood_files=max_neighborhood_files,
        )
        write_json(run_dir / "projection_master_context.json", {key: value for key, value in projected.items() if key != "personas"})
        projection_summary = {
            "model_dir": str(projection_model_dir),
            "thresholds_path": str(projection_thresholds),
            "min_k": projection_min_k,
            "master_node_count": projected["master_node_count"],
            "master_core_file_count": projected["master_core_file_count"],
            "master_neighborhood_file_count": projected["master_neighborhood_file_count"],
            "selected_node_counts": {
                persona: payload["selected_node_count"]
                for persona, payload in projected["personas"].items()
            },
        }
        for persona, payload in projected["personas"].items():
            out = run_dir / f"{persona}_sphere.md"
            json_out = run_dir / f"{persona}_sphere.json"
            write_text(out, str(payload["markdown"]))
            write_json(json_out, {key: value for key, value in payload.items() if key != "markdown"})
            sphere_paths[persona] = str(out)
            sphere_json_paths[persona] = str(json_out)
    else:
        for persona in ("PM", "WORKER", "REVIEWER"):
            out = run_dir / f"{persona.lower()}_sphere.md"
            json_out = run_dir / f"{persona.lower()}_sphere.json"
            result = run_command(
                [
                    sys.executable,
                    "scripts/assembler.py",
                    str(selector_path),
                    str(repo_path),
                    persona,
                    "--out",
                    str(out),
                    "--json-out",
                    str(json_out),
                    "--max-file-chars",
                    str(max_file_chars),
                    "--max-neighborhood-files",
                    str(max_neighborhood_files),
                ],
                cwd=ROOT,
            )
            command_results.append(result)
            require_command_success(result)
            sphere_paths[persona.lower()] = str(out)
            sphere_json_paths[persona.lower()] = str(json_out)

    return {
        "selector_output": str(selector_path),
        "sphere_paths": sphere_paths,
        "sphere_json_paths": sphere_json_paths,
        "retrieval_mode": retrieval_mode,
        "projection_summary": projection_summary,
        "commands": command_results,
        "selector_summary": {
            "top_files": [row.get("path") for row in load_selector_output(selector_path).get("top_files", [])],
        },
    }


def orchestrate(args: argparse.Namespace) -> dict[str, Any]:
    load_dotenv(args.env_file)
    run_slug = issue_slug(args.issue_url)
    run_dir = Path(args.run_dir) if args.run_dir else Path(args.out_dir) / run_slug
    run_dir.mkdir(parents=True, exist_ok=True)
    repo_path = Path(args.repo_path).resolve()
    routing_profile = build_routing_profile(strategy=args.model_strategy, base_url=args.base_url, model=args.model)
    write_json(run_dir / "routing_profile.json", {"model_strategy": args.model_strategy, "routes": routing_profile})
    transitions: list[dict[str, Any]] = []
    usage_events: list[dict[str, Any]] = []
    provider_swaps: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "schema_version": 1,
        "issue_url": args.issue_url,
        "repo_path": str(repo_path),
        "run_dir": str(run_dir),
        "dry_run": args.dry_run,
        "model": args.model,
        "model_strategy": args.model_strategy,
        "retrieval_mode": args.retrieval_mode,
        "routing_profile": routing_profile,
        "max_attempts": args.max_attempts,
        "status": "running",
    }

    transitions.append({"state": STATE_INIT, "at": time.time()})
    init = state_init(
        issue_url=args.issue_url,
        repo_path=repo_path,
        run_dir=run_dir,
        python_bin=args.python_bin,
        selector_output=Path(args.selector_output).resolve() if args.selector_output else None,
        max_file_chars=args.max_file_chars,
        max_neighborhood_files=args.max_neighborhood_files,
        retrieval_mode=args.retrieval_mode,
        projection_model_dir=Path(args.projection_model_dir).resolve(),
        projection_thresholds=Path(args.projection_thresholds).resolve(),
        projection_device=args.projection_device,
        projection_batch_size=args.projection_batch_size,
        projection_min_k=args.projection_min_k,
    )
    summary.update(init)

    pm_sphere = Path(init["sphere_paths"]["pm"]).read_text(encoding="utf-8")
    worker_sphere = Path(init["sphere_paths"]["worker"]).read_text(encoding="utf-8")
    reviewer_sphere = Path(init["sphere_paths"]["reviewer"]).read_text(encoding="utf-8")

    transitions.append({"state": STATE_PM, "at": time.time()})
    if args.dry_run:
        constraints = dry_constraints(args.issue_url)
        pm_raw = json.dumps(constraints, indent=2, ensure_ascii=False)
    else:
        system, user = pm_prompt(args.issue_url, pm_sphere)
        pm_raw = routed_text(
            role="pm",
            profile=routing_profile["pm"],
            attempt_index=0,
            system_prompt=system,
            user_prompt=user,
            max_tokens=args.pm_max_tokens,
            temperature=args.temperature,
            timeout=args.timeout,
            raw_out=run_dir / "pm_constraints.raw.json",
            usage_events=usage_events,
            provider_swaps=provider_swaps,
        )
        try:
            constraints = extract_json_object(pm_raw)
        except Exception as exc:
            constraints = {
                "issue_url": args.issue_url,
                "constraints": [],
                "acceptance_criteria": [],
                "risks": [f"PM constraints JSON parse failed: {exc}"],
                "reviewer_feedback": [],
                "raw_pm_response": pm_raw,
            }
    write_text(run_dir / "constraints.md", pm_raw)
    write_json(run_dir / "constraints.json", constraints)

    final_patch = ""
    final_review = ""
    final_status = STATE_MANUAL
    tests_passed: bool | None = None
    verification_results: list[dict[str, Any]] = []
    patch_preflight_results: list[dict[str, Any]] = []
    invalid_target_file_traces: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    consecutive_reviewer_rejections = 0
    for attempt in range(1, args.max_attempts + 1):
        transitions.append({"state": STATE_WORKER, "attempt": attempt, "at": time.time()})
        if args.dry_run:
            patch = dry_patch(attempt)
        else:
            system, user = worker_prompt(args.issue_url, worker_sphere, constraints)
            worker_raw = routed_text(
                role="worker",
                profile=routing_profile["worker"],
                attempt_index=attempt,
                system_prompt=system,
                user_prompt=user,
                max_tokens=args.worker_max_tokens,
                temperature=args.temperature,
                timeout=args.timeout,
                raw_out=run_dir / f"patch_v{attempt}.raw.json",
                usage_events=usage_events,
                provider_swaps=provider_swaps,
            )
            write_text(run_dir / f"patch_v{attempt}.raw.md", worker_raw)
            patch = strip_hidden_thinking(worker_raw).strip() + "\n"
        patch_path = run_dir / f"patch_v{attempt}.blocks.md"
        write_text(patch_path, patch)

        transitions.append({"state": STATE_TARGET_PREFLIGHT, "attempt": attempt, "at": time.time()})
        preflight = validate_patch_target_files(repo_path, patch, attempt=attempt)
        preflight_path = run_dir / f"patch_target_preflight_v{attempt}.json"
        write_json(preflight_path, preflight)
        patch_preflight_results.append(preflight)
        if not preflight["valid"]:
            if preflight["kind"] == "invalid_target_file":
                invalid_target_file_traces.append(preflight)
            constraints = append_worker_preflight_feedback(constraints, attempt=attempt, preflight=preflight)
            write_json(run_dir / "constraints.json", constraints)
            write_json(run_dir / f"constraints_after_target_preflight_v{attempt}.json", constraints)
            attempts.append(
                {
                    "attempt": attempt,
                    "patch_path": str(patch_path),
                    "patch_format": "search_replace_blocks",
                    "target_preflight_path": str(preflight_path),
                    "target_preflight_status": preflight["kind"],
                    "review_status": "TARGET_PREFLIGHT_FAILED",
                    "reviewer_bypassed": False,
                }
            )
            final_patch = patch
            final_review = str(preflight.get("worker_message") or preflight.get("error") or "Patch target preflight failed.")
            continue

        reviewer_bypassed = bool(args.test_cmd and consecutive_reviewer_rejections >= 2)
        if reviewer_bypassed:
            transitions.append(
                {
                    "state": STATE_REVIEWER,
                    "attempt": attempt,
                    "at": time.time(),
                    "bypassed": True,
                    "reason": "two consecutive reviewer rejections; execution tests act as final judge",
                }
            )
            review = (
                "APPROVED\n"
                "Reviewer bypassed after two consecutive rejections; routing directly to State_VERIFY "
                "so execution tests can judge the patch.\n"
            )
        else:
            transitions.append({"state": STATE_REVIEWER, "attempt": attempt, "at": time.time()})
            if args.dry_run:
                review = dry_review(attempt)
            else:
                system, user = reviewer_prompt(args.issue_url, reviewer_sphere, patch)
                review = routed_text(
                    role="reviewer",
                    profile=routing_profile["reviewer"],
                    attempt_index=attempt,
                    system_prompt=system,
                    user_prompt=user,
                    max_tokens=args.reviewer_max_tokens,
                    temperature=args.temperature,
                    timeout=args.timeout,
                    raw_out=run_dir / f"review_v{attempt}.raw.json",
                    usage_events=usage_events,
                    provider_swaps=provider_swaps,
                )
        review_path = run_dir / f"review_v{attempt}.md"
        write_text(review_path, review)
        review_status = parse_review_status(review)
        if reviewer_bypassed:
            review_status = "BYPASSED_TO_VERIFY"
        attempts.append(
            {
                "attempt": attempt,
                "patch_path": str(patch_path),
                "patch_format": "search_replace_blocks",
                "target_preflight_path": str(preflight_path),
                "target_preflight_status": preflight["kind"],
                "review_path": str(review_path),
                "review_status": review_status,
                "reviewer_bypassed": reviewer_bypassed,
            }
        )
        if review_status in {"APPROVED", "BYPASSED_TO_VERIFY"}:
            consecutive_reviewer_rejections = 0
            transitions.append({"state": STATE_VERIFY, "attempt": attempt, "at": time.time()})
            verify_result = run_verification(
                repo_path=repo_path,
                patch_blocks_path=patch_path,
                test_cmd=args.test_cmd,
                run_dir=run_dir,
                attempt=attempt,
                python_bin=args.python_bin,
            )
            verification_results.append(verify_result)
            tests_passed = verify_result["tests_passed"]
            attempts[-1]["verify_path"] = str(run_dir / f"verify_v{attempt}.json")
            attempts[-1]["tests_passed"] = tests_passed
            if tests_passed is True or (tests_passed is None and args.allow_unverified_done):
                final_patch = patch
                final_review = review
                final_status = STATE_DONE
                write_text(run_dir / "final_patch.blocks.md", patch)
                write_text(run_dir / "final_patch.diff", patch)
                write_text(run_dir / "final_review.md", review)
                break
            context_expansion = expand_context_from_verification_failure(
                run_dir=run_dir,
                repo_path=repo_path,
                selector_path=Path(init["selector_output"]),
                verify_result=verify_result,
                attempt=attempt,
                max_file_chars=args.max_file_chars,
                max_neighborhood_files=args.max_neighborhood_files,
            )
            if context_expansion is not None:
                attempts[-1]["context_expansion"] = context_expansion
                worker_sphere = Path(init["sphere_paths"]["worker"]).read_text(encoding="utf-8")
                reviewer_sphere = Path(init["sphere_paths"]["reviewer"]).read_text(encoding="utf-8")
            constraints = append_test_failure_feedback(
                constraints,
                attempt=attempt,
                patch_apply=verify_result["patch_apply"],
                test_result=verify_result["test_result"],
                build_result=verify_result.get("build_result"),
                context_expansion=context_expansion,
            )
            write_json(run_dir / "constraints.json", constraints)
            write_json(run_dir / f"constraints_after_verify_v{attempt}.json", constraints)
            final_patch = patch
            final_review = "Reviewer approved, but execution verification failed."
            continue
        consecutive_reviewer_rejections += 1
        constraints = append_feedback(constraints, attempt=attempt, review=review)
        write_json(run_dir / "constraints.json", constraints)
        write_json(run_dir / f"constraints_after_review_v{attempt}.json", constraints)
        final_patch = patch
        final_review = review

    if final_status != STATE_DONE:
        write_text(run_dir / "manual_intervention.md", final_review or "No reviewer approval within attempt budget.")

    transitions.append({"state": final_status, "at": time.time()})
    model_usage = summarize_model_usage(usage_events)
    estimated_cost_usd = float(model_usage["estimated_inference_cost_usd"])
    internal_approval_indicator = int(final_status == STATE_DONE)
    verification_success_indicator = None if tests_passed is None else int(tests_passed is True)
    summary.update(
        {
            "status": "approved" if final_status == STATE_DONE else "manual_intervention",
            "final_state": final_status,
            "attempts": attempts,
            "approved": final_status == STATE_DONE,
            "tests_passed": tests_passed,
            "patch_preflight_results": patch_preflight_results,
            "invalid_target_file_traces": invalid_target_file_traces,
            "verification_results": verification_results,
            "provider_swaps": provider_swaps,
            "model_usage": model_usage,
            "estimated_inference_cost_usd": estimated_cost_usd,
            "internal_approval_indicator": internal_approval_indicator,
            "verification_success_indicator": verification_success_indicator,
            "internal_approval_per_dollar": per_dollar(internal_approval_indicator, estimated_cost_usd),
            "efficacy_per_dollar": (
                per_dollar(verification_success_indicator, estimated_cost_usd)
                if verification_success_indicator is not None
                else None
            ),
            "final_patch_path": str(run_dir / "final_patch.diff") if final_status == STATE_DONE else None,
            "final_patch_blocks_path": str(run_dir / "final_patch.blocks.md") if final_status == STATE_DONE else None,
            "manual_intervention_path": str(run_dir / "manual_intervention.md") if final_status != STATE_DONE else None,
            "transitions": transitions,
        }
    )
    write_json(run_dir / "resolution_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("issue_url", help="GitHub issue URL or owner/repo#number")
    parser.add_argument("repo_path", help="Local repository root")
    parser.add_argument("--out-dir", default="outputs/resolution_history")
    parser.add_argument("--run-dir", help="Exact output directory for this run; overrides --out-dir/<issue_slug>")
    parser.add_argument("--selector-output", help="Existing selector output JSON; skips inference but still assembles spheres")
    parser.add_argument("--python-bin", default=default_python_bin())
    parser.add_argument("--dry-run", action="store_true", help="Do not call MiniMax; exercise artifact/state loop with placeholders")
    parser.add_argument("--env-file", default=".env.local")
    parser.add_argument("--base-url", default=os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--model", default=os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL))
    parser.add_argument(
        "--model-strategy",
        choices=MODEL_STRATEGIES,
        default="monolithic",
        help="Model routing strategy: monolithic, heterogeneous, or DeepSeek-primary/MiniMax-secondary fallback.",
    )
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS)
    parser.add_argument("--max-file-chars", type=int, default=DEFAULT_MAX_FILE_CHARS)
    parser.add_argument("--max-neighborhood-files", type=int, default=24)
    parser.add_argument(
        "--retrieval-mode",
        choices=("standard", "projection"),
        default="standard",
        help="Context assembly mode. projection filters the master sphere through context_projector_v3.",
    )
    parser.add_argument("--projection-model-dir", default="models/context_projector_v3")
    parser.add_argument("--projection-thresholds", default="artifacts/model_reports/context_projector_v3_persona_thresholds.json")
    parser.add_argument("--projection-device", default="auto")
    parser.add_argument("--projection-batch-size", type=int, default=32)
    parser.add_argument("--projection-min-k", type=int, default=2)
    parser.add_argument("--test-cmd", help="Command to run after applying a reviewer-approved patch")
    parser.add_argument(
        "--allow-unverified-done",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Allow State_DONE when reviewer approves but no --test-cmd is provided.",
    )
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--pm-max-tokens", type=int, default=2500)
    parser.add_argument("--worker-max-tokens", type=int, default=7000)
    parser.add_argument("--reviewer-max-tokens", type=int, default=3500)
    args = parser.parse_args()
    summary = orchestrate(args)
    print(json.dumps({key: summary[key] for key in ("status", "final_state", "approved", "run_dir", "attempts")}, indent=2))
    return 0 if summary["status"] == "approved" else 2


if __name__ == "__main__":
    raise SystemExit(main())
