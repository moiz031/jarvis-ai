# Jarvis Super Mode

Super Mode provides one-time onboarding plus centralized control across channels, plugins, and system actions.

## Implemented Components
- `jarvis/supervisor/orchestrator.py`: central brain for routing, authorization, and dispatch.
- `jarvis/supervisor/channel_gateway.py`: channel registry/connect/send/ingest pipeline.
- `jarvis/supervisor/plugin_runtime.py`: local plugin loader (`jarvis/plugins/*.py`) and action execution.
- `jarvis/supervisor/worker_pool.py`: background jobs with retry and low-RAM guard.
- `jarvis/supervisor/policy.py`: profile-based permissions (`basic`, `power`, `admin`) + step-up checks.
- `jarvis/supervisor/onboarding.py`: one-time access flow and persistent state.
- `jarvis/supervisor/auth_vault.py`: encrypted credential vault.
- `jarvis/supervisor/directory.py`: cross-channel contact routing map.

## One-Time Setup Flow
1. Start Jarvis: `python jarvis/main.py`
2. Onboard once:
   - CLI: `python jarvis/super_cli.py onboard --profile power --users local-admin --channels telegram,discord,email`
   - API: `POST /api/super/onboard`
3. Connect channels later without full re-setup:
   - CLI: `python jarvis/super_cli.py connect telegram`
   - API: `POST /api/super/channel/connect`

## Runtime APIs
- `GET /api/super/state`
- `POST /api/super/onboard`
- `POST /api/super/channel/connect`
- `POST /api/super/channel/disconnect`
- `POST /api/super/channel/send`
- `POST /api/super/channel/inbound`
- `POST /api/super/task`
- `POST /api/super/plugin/reload`
- `POST /api/super/status`

## Command Router (chat commands)
- `/super status`
- `/super channels`
- `/super plugins`
- `/super jobs`
- `/channel connect <channel>`
- `/channel disconnect <channel>`
- `/channel send <channel> <target> <message>`
- `/plugin reload`
- `/plugin run <action> <json_payload>`
- `/directory set <alias> <channel> <id>`
- `/directory list`
- `/task async <prompt>`

## Low-RAM Behavior (8GB)
- Profile defaults to `low_ram` when RAM <= 8.5 GB.
- `MAX_AGENT_WORKERS` defaults to `2` in low-RAM mode.
- Worker pool rejects new heavy scheduling if RAM usage is too high.
- Keep local model small in `.env`, e.g. `OLLAMA_MODEL=llama3.2:3b`.

## Data Files
Persisted under `data/`:
- `super_state.json`
- `super_channels.json`
- `super_policy.json`
- `super_directory.json`
- `super_vault.json` and `super_vault.key`
