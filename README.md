# opencode-bridge

An [OpenClaw](https://github.com/openclaw/openclaw) plugin that delegates **ALL code work** to [OpenCode](https://opencode.ai).

OpenClaw acts as the planner/reviewer; OpenCode acts as the coder. This plugin automates the handoff — server lifecycle, task dispatch, rule injection, and completion callback — so you never have to manually orchestrate the two agents.

## How It Works

```
You: "Implement login API"
      │
      ▼
┌─────────────────────────────┐
│ OpenClaw (Planner/Reviewer)  │
│ - Writes design docs         │
│ - Breaks work into chunks    │
│ - Calls opencode_dispatch    │
└──────────┬──────────────────┘
           │  rules + task
           ▼
┌──────────────────────────────────────────────────────┐
│ OpenCode (Coder)                                      │
│ - Implements, tests, commits                          │
│ - Runs in serve mode (HTTP API)                       │
└──────────────────────────────────────────────────────┘

You monitor progress at http://localhost:4096
```

**Fire and forget** — OpenClaw dispatches the task and reports the session name + URL. You watch progress directly in the OpenCode web UI. OpenClaw does not poll or wait. When OpenCode finishes, it calls back to the plugin, which notifies the OpenClaw session.

## Architecture

| Layer | Audience | Mechanism | When |
|-------|----------|-----------|------|
| **[A]** Behavior rules | OpenClaw (LLM) | `before_prompt_build` hook injects directive | When code keywords are detected (English + Korean) |
| **[B]** OpenCode work rules | OpenCode (LLM) | Rules prepended to the message body on dispatch | Every `opencode_dispatch` call |
| **[C]** Server management | System | `gateway_start` hook starts OpenCode server | Gateway startup |
| **[D]** Completion callback | OpenClaw (session) | HTTP route receives callback, injects next-turn notification | When OpenCode finishes a task |

## Installation

### Prerequisites

1. **OpenClaw** — [install](https://docs.openclaw.ai)
2. **OpenCode** — see [opencode.ai](https://opencode.ai)

### Install the plugin

```bash
# From local path
openclaw plugins install ./opencode-bridge

# From git
openclaw plugins install git:github.com/dev-hann/opencode-bridge
```

### Configuration

Add the plugin path and entry in your `openclaw.json`:

```json5
{
  plugins: {
    load: {
      paths: ["/path/to/opencode-bridge"],
    },
    entries: {
      "opencode-bridge": {
        enabled: true,
      },
    },
  },
}
```

Optional plugin config (defaults shown):

```json5
{
  plugins: {
    entries: {
      "opencode-bridge": {
        enabled: true,
        config: {
          port: 4096,           // OpenCode server port
          hostname: "0.0.0.0",  // OpenCode server hostname
          // rulesFile: "~/.openclaw/opencode-bridge-rules.md"  // optional override
        },
      },
    },
  },
}
```

## Tool Policy

The `opencode_dispatch` tool is registered by the plugin, but **it is filtered out by the `coding` tool profile** (the default for local setups). To make the tool visible to the model, add it to `tools.alsoAllow` in your Gateway config:

```json5
{
  tools: {
    profile: "coding",
    alsoAllow: ["opencode_dispatch"],
  },
}
```

Without this, the plugin loads successfully (hooks fire, directive is injected), but the model never receives the `opencode_dispatch` tool schema, so it cannot actually call it.

If you use `tools.profile: "full"` or have no profile set, no extra config is needed.

## Customizing Rules

The plugin ships with bundled rules in `rules/opencode-bridge.md`. To customize:

1. Copy `rules/opencode-bridge.md` to your preferred location
2. Set `rulesFile` in plugin config to point to it

## Tool

### `opencode_dispatch`

```typescript
opencode_dispatch({
  directory: "/path/to/project",
  task: "Fix login validation in LoginForm component",
  title: "fix-login-validation"  // optional
})
```

Returns:

```json
{
  "status": "dispatched",
  "session_id": "ses_abc123",
  "session_name": "fix-login-validation",
  "web_ui": "http://localhost:4096/session/ses_abc123",
  "directory": "/path/to/project",
  "message": "OpenCode session 'fix-login-validation' started.\nMonitor: http://localhost:4096/session/ses_abc123\nAttach: opencode attach http://localhost:4096 --dir /path/to/project --session ses_abc123"
}
```

## License

MIT
