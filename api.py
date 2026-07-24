"""OpenCode HTTP API client — dispatch only. Throw task, return session info."""

from __future__ import annotations

import json
import pathlib
import urllib.request

from server import BASE_URL, is_running

_RULES_PATH = pathlib.Path.home() / ".hermes" / "opencode-bridge-rule.md"
_TEMPLATE_PATH = pathlib.Path(__file__).parent / "template" / "opencode-bridge.md"


def _http(method: str, path: str, body: dict | None = None, timeout: int = 30) -> dict:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        if not raw:
            return {}
        return json.loads(raw)


def _b64url(text: str) -> str:
    """Base64url encode (matches OpenCode web frontend xn() function)."""
    import base64
    raw = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return raw.replace("+", "-").replace("/", "_").replace("=", "")


def _load_rules() -> str:
    """Load user rules, seeding from the bundled template on first use.

    If ~/.hermes/opencode-bridge-rule.md does not exist, copy it from the plugin's
    template/opencode-bridge.md so the user gets a sensible default
    they can then freely edit. The rules file lives OUTSIDE the plugin
    directory, so plugin updates/reinstalls never overwrite it.
    """
    if not _RULES_PATH.exists() and _TEMPLATE_PATH.exists():
        _RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
        _RULES_PATH.write_text(
            _TEMPLATE_PATH.read_text(encoding="utf-8"), encoding="utf-8"
        )
    if _RULES_PATH.exists():
        return _RULES_PATH.read_text(encoding="utf-8").strip()
    return ""


def dispatch(directory: str, task: str, title: str = "") -> str:
    """Dispatch a coding task to OpenCode. Returns immediately.

    1. Create a session with the working directory.
    2. Send the task via prompt_async.
    3. Return session info.

    Permissions: OpenCode serve mode auto-approves most permissions.
    External directory access may require manual approval in the web UI.

    Returns: JSON string.
    """
    if not is_running():
        return json.dumps({
            "status": "error",
            "message": "OpenCode server is not running.",
        })

    # Create session
    try:
        session_body = {"directory": directory}
        if title:
            session_body["title"] = title
        resp = _http("POST", "/session", session_body)
        session_id = resp.get("id", "")
        session_title = resp.get("title", title or "")
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Failed to create session: {e}",
        })

    if not session_id:
        return json.dumps({
            "status": "error",
            "message": "Server returned no session id.",
        })

    # Send task
    rules = _load_rules()
    message_text = f"<system_rules>\n{rules}\n</system_rules>\n\n<task>\n{task}\n</task>" if rules else task
    try:
        _http("POST", f"/session/{session_id}/prompt_async", {
            "parts": [{"type": "text", "text": message_text}]
        }, timeout=10)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "session_id": session_id,
            "message": f"Session created but failed to send task: {e}",
        })

    # Build URLs — OpenCode web UI uses /server/{b64url(serverUrl)}/session/{sessionId}
    # (matching the _f() function in the web frontend; uses session ID, not slug)
    server_encoded = _b64url(BASE_URL)
    web_ui = f"{BASE_URL}/server/{server_encoded}/session/{session_id}"
    tui_command = f"opencode attach {BASE_URL} -s {session_id}"

    return json.dumps({
        "status": "dispatched",
        "session_id": session_id,
        "session_name": session_title,
        "web_ui": web_ui,
        "tui_command": tui_command,
        "directory": directory,
        "message": (
            f"OpenCode 디스패치 완료.\n"
            f"세션: {session_title}\n"
            f"WEB: {web_ui}\n"
            f"TUI: {tui_command}"
        ),
    }, ensure_ascii=False)
