# Jarvis AI - Technical Audit Fix Plan

## Summary of Issues Found

### CRITICAL (3 issues)

1. **mute_toggle crash** - VERIFIED: The method DOES exist in tts_local.py (line 229-232). The audit was INCORRECT on this issue. No fix needed.

2. **Package-level imports broken** - `agent.py` lines 11-32 use absolute imports in try block without proper fallback

3. **API keys in .env** - Security risk, needs proper handling

### HIGH (7 issues)

4. **Build/lint workflow broken** - npm scripts use wrong commands

5. **Test pipeline weak** - npm test just echoes

6. **Python test tooling** - Already in requirements.txt (pytest), but need verification

7. **Data path inconsistency** - Config uses CONFIG_DIR, db.py uses BASE_DIR

8. **Plugin dir wrong in frozen mode** - Points to BASE_DIR instead of CONFIG_DIR

9. **Integrations hard-import** - Need try/except for optional dependencies

### MEDIUM (6 issues)

10. **Channel adapters are stubs** - Telegram/Discord/Slack not implemented

11. **Legacy launcher wrong port** - Shows 8000 but app uses 8080

12. **Docs outdated** - README mismatches code

13. **files.py USERPROFILE crash risk** - Direct access without fallback

14. **Electron backend fallback weak** - Silent failure

15. **Repo hygiene** - build artifacts tracked, no lockfile
