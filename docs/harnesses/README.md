# Harness Adapters

The adapters connect the benchmark to versioned agent runtimes.

| Harness | Supported runtime |
| --- | --- |
| OpenClaw | 2026.4.15 |
| Claude Code | CLI 2.1.153 and Agent SDK 0.2.128 |
| Hermes | v0.20.0 |

Version preflight runs once per trajectory. Later upstream versions may require
adapter updates. 

## Setup

Install OpenClaw at the pinned version and make its command available on PATH.
`openclaw.command` in `configs/benchmark.yaml` also accepts an explicit command
list. The benchmark launcher prepares an isolated home, registers its MCP
server, starts a fresh loopback Gateway, and owns that process through shutdown.

For Claude Code, install `pip install -e ".[claude-code]"`, the pinned CLI, and
set `CLAUDE_CODE_BASE_URL`. `CLAUDE_CODE_CLI` can select the CLI executable.
The endpoint exposes the Anthropic-compatible API.

For Hermes, install the pinned upstream runtime and this package in its Python
environment. Set `HERMES_PYTHON` to that interpreter. The adapter starts the
Python bridge in that environment and supplies the Task model credentials.

## Memory and File Boundaries

Controlled OpenClaw disables native memory search, the memory plugin and
compaction memory flush. The task prompt identifies the injected block as the
long-term memory source, and the configured memory method stores its state
separately. The upstream general-purpose tool set is retained.

Native OpenClaw retains its memory tools. Claude Code retains native
auto-memory with a trajectory-local directory. Hermes retains MEMORY.md,
USER.md, session search, skills, native file tools and background review in
its isolated profile. Native baselines use the Task model for memory management.
Claude's primary and auxiliary model slots are all bound to that Task model.

Claude and Hermes file hooks restrict generic file access to the trajectory's
workspace and native-memory roots. Their exposed tool sets follow the native
adapters. These application-level boundaries complement process or container
isolation; the OpenClaw tool set includes its upstream shell tools.
