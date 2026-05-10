"""Capability Evolver plugin adapted for Jarvis Super Mode.

Imported from capability-evolver-pro-1.0.2 and exposed through the local
Python plugin runtime so Jarvis can run deterministic log analysis locally.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections import Counter
from typing import Any, Dict, List

VALID_ACTIONS = ("analyze", "evolve", "status")
VALID_STRATEGIES = ("balanced", "innovate", "harden", "repair-only", "auto")
MAX_LOGS_PER_REQUEST = 10_000
MAX_PATTERNS_RETURNED = 50
MAX_RECOMMENDATIONS = 20
SLOW_OP_RE = re.compile(r"(\d{4,})ms|slow|timeout", re.IGNORECASE)


def _round_js(value: float) -> int:
    return int(math.floor(value + 0.5))


def _ordered_unique(values: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _merge_input(payload: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(payload or {})
    nested = merged.get("input")
    if isinstance(nested, dict):
        merged.update(nested)
    return merged


def _validate_request(payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    action = payload.get("action")
    strategy = payload.get("strategy")
    logs = payload.get("logs")

    if action not in VALID_ACTIONS:
        errors.append(f'"action" must be one of: {", ".join(VALID_ACTIONS)}')

    if strategy is not None and strategy not in VALID_STRATEGIES:
        errors.append(f'"strategy" must be one of: {", ".join(VALID_STRATEGIES)}')

    if action in {"analyze", "evolve"}:
        if not isinstance(logs, list) or not logs:
            errors.append('"logs" array is required for analyze/evolve actions')
        elif len(logs) > MAX_LOGS_PER_REQUEST:
            errors.append(f'"logs" supports at most {MAX_LOGS_PER_REQUEST} entries per request')

    return errors


def _normalize_log(log: Dict[str, Any]) -> Dict[str, str]:
    context = log.get("context")
    return {
        "timestamp": str(log.get("timestamp") or ""),
        "level": str(log.get("level") or "").lower(),
        "message": str(log.get("message") or ""),
        "context": str(context) if context is not None else "",
    }


def _analyze(logs: List[Dict[str, Any]]) -> Dict[str, Any]:
    patterns: List[Dict[str, Any]] = []
    error_map: Dict[str, Dict[str, Any]] = {}

    normalized_logs = [_normalize_log(log) for log in logs]

    for log in normalized_logs:
        if log["level"] in {"error", "warn"}:
            key = log["message"][:100]
            existing = error_map.get(key)
            if existing:
                existing["count"] += 1
                existing["last"] = log["timestamp"]
                if log["context"]:
                    existing["files"].append(log["context"])
            else:
                error_map[key] = {
                    "count": 1,
                    "first": log["timestamp"],
                    "last": log["timestamp"],
                    "files": [log["context"]] if log["context"] else [],
                }

    for message, data in error_map.items():
        count = data["count"]
        if count >= 10:
            severity = "critical"
        elif count >= 5:
            severity = "high"
        elif count >= 2:
            severity = "medium"
        else:
            severity = "low"
        patterns.append(
            {
                "type": "regression" if count >= 3 else "error",
                "severity": severity,
                "description": message,
                "occurrences": count,
                "first_seen": data["first"],
                "last_seen": data["last"],
                "affected_files": _ordered_unique(data["files"]),
            }
        )

    slow_ops = [
        log
        for log in normalized_logs
        if log["level"] == "info" and SLOW_OP_RE.search(log["message"])
    ]
    if len(slow_ops) >= 2:
        patterns.append(
            {
                "type": "inefficiency",
                "severity": "high" if len(slow_ops) >= 5 else "medium",
                "description": f"{len(slow_ops)} slow operations detected in logs",
                "occurrences": len(slow_ops),
                "first_seen": slow_ops[0]["timestamp"],
                "last_seen": slow_ops[-1]["timestamp"],
                "affected_files": _ordered_unique([log["context"] for log in slow_ops]),
            }
        )

    total_logs = len(normalized_logs)
    error_count = sum(1 for log in normalized_logs if log["level"] == "error")
    warn_count = sum(1 for log in normalized_logs if log["level"] == "warn")
    health_score = max(
        0,
        _round_js(
            100
            - (error_count / max(total_logs, 1)) * 100
            - (warn_count / max(total_logs, 1)) * 30
        ),
    )
    critical_count = sum(1 for pattern in patterns if pattern["severity"] == "critical")

    recommendations: List[str] = []
    if critical_count > 0:
        recommendations.append(
            "Critical patterns detected - prioritize immediate fixes before any new development"
        )
    if sum(1 for pattern in patterns if pattern["type"] == "regression") >= 2:
        recommendations.append(
            'Multiple regressions found - add regression tests and consider "harden" strategy'
        )
    if health_score > 80 and len(patterns) < 3:
        recommendations.append(
            'System is healthy - safe to pursue "innovate" strategy for capability expansion'
        )
    if health_score < 50:
        recommendations.append(
            "Low health score - enable review_mode and focus on stability before adding features"
        )
    if any(pattern["type"] == "inefficiency" for pattern in patterns):
        recommendations.append(
            "Performance bottlenecks detected - profile slow operations and add caching where applicable"
        )

    hot_files = Counter()
    for pattern in patterns:
        hot_files.update(pattern["affected_files"])
    top_hot_files = hot_files.most_common(3)
    if top_hot_files:
        joined = ", ".join(f"{name} ({count})" for name, count in top_hot_files)
        recommendations.append(f"Hot files (most issues): {joined}")

    patterns_sorted = sorted(patterns, key=lambda item: item["occurrences"], reverse=True)[
        :MAX_PATTERNS_RETURNED
    ]
    return {
        "patterns": patterns_sorted,
        "health_score": health_score,
        "recommendations": recommendations,
        "summary": {
            "total_logs": total_logs,
            "error_count": error_count,
            "warn_count": warn_count,
            "unique_patterns": len(patterns),
            "critical_count": critical_count,
        },
    }


def _build_evolution_id(
    analysis: Dict[str, Any], strategy: str, target_file: str
) -> str:
    basis = json.dumps(
        {
            "analysis": analysis,
            "strategy": strategy,
            "target_file": target_file,
        },
        sort_keys=True,
    )
    return f"evo_{hashlib.sha1(basis.encode('utf-8')).hexdigest()[:12]}"


def _evolve(logs: List[Dict[str, Any]], strategy: str, target_file: str = "") -> Dict[str, Any]:
    analysis = _analyze(logs)
    effective_strategy = strategy
    if strategy == "auto":
        if analysis["health_score"] < 40:
            effective_strategy = "repair-only"
        elif analysis["health_score"] < 70:
            effective_strategy = "harden"
        else:
            effective_strategy = "balanced"

    recommendations: List[Dict[str, Any]] = []

    for pattern in analysis["patterns"]:
        affected_files = pattern["affected_files"]
        if target_file and affected_files and target_file not in affected_files:
            continue

        if pattern["severity"] == "critical" or effective_strategy == "repair-only":
            recommendations.append(
                {
                    "priority": "immediate",
                    "category": "error-handling",
                    "description": f"Fix: {pattern['description']}",
                    "affected_files": affected_files,
                    "suggested_approach": (
                        "Add regression test, then fix the root cause. Check recent changes to affected files."
                        if pattern["type"] == "regression"
                        else "Add try-catch or input validation. Review error boundary coverage."
                    ),
                }
            )

        if pattern["type"] == "inefficiency" and effective_strategy != "repair-only":
            recommendations.append(
                {
                    "priority": "medium",
                    "category": "performance",
                    "description": f"Optimize: {pattern['description']}",
                    "affected_files": affected_files,
                    "suggested_approach": "Profile the slow path, add caching, or batch operations where possible.",
                }
            )

        if pattern["type"] == "regression" and effective_strategy in {"harden", "balanced"}:
            recommendations.append(
                {
                    "priority": "high",
                    "category": "stability",
                    "description": f"Stabilize: {pattern['description']} ({pattern['occurrences']} occurrences)",
                    "affected_files": affected_files,
                    "suggested_approach": "Write targeted tests for this scenario. Add monitoring/alerting for early detection.",
                }
            )

    if effective_strategy == "innovate" and analysis["health_score"] > 70:
        recommendations.append(
            {
                "priority": "low",
                "category": "architecture",
                "description": "System is stable - consider adding new capabilities or refactoring for extensibility",
                "affected_files": [],
                "suggested_approach": "Identify the most-called code paths and optimize or extend them.",
            }
        )

    if effective_strategy == "harden":
        unique_files = _ordered_unique(
            [file_name for pattern in analysis["patterns"] for file_name in pattern["affected_files"]]
        )[:5]
        recommendations.append(
            {
                "priority": "high",
                "category": "monitoring",
                "description": "Add structured logging and health checks to detect issues earlier",
                "affected_files": unique_files,
                "suggested_approach": "Add error rate metrics, latency tracking, and automated alerting thresholds.",
            }
        )

    critical_patterns = [pattern for pattern in analysis["patterns"] if pattern["severity"] == "critical"]
    if len(critical_patterns) >= 3:
        risk_level = "high"
    elif critical_patterns:
        risk_level = "medium"
    else:
        risk_level = "low"

    estimated_score = min(100, analysis["health_score"] + (len(recommendations) * 5))
    return {
        "evolution_id": _build_evolution_id(analysis, effective_strategy, target_file),
        "strategy": effective_strategy,
        "recommendations": recommendations[:MAX_RECOMMENDATIONS],
        "risk_assessment": {
            "level": risk_level,
            "factors": [pattern["description"] for pattern in critical_patterns[:5]],
        },
        "estimated_improvement": (
            f"Health score: {analysis['health_score']} -> ~{estimated_score} "
            "(if all recommendations applied)"
        ),
    }


def _status() -> Dict[str, Any]:
    return {
        "skill": "capability-evolver",
        "package": "capability-evolver-pro",
        "version": "1.0.2",
        "mode": "jarvis-super-plugin",
        "engine": "pure-logic",
        "supported_actions": list(VALID_ACTIONS),
        "supported_strategies": list(VALID_STRATEGIES),
        "upstream_dependency": "none",
        "limits": {
            "max_logs_per_request": MAX_LOGS_PER_REQUEST,
            "max_patterns_returned": MAX_PATTERNS_RETURNED,
            "max_recommendations": MAX_RECOMMENDATIONS,
        },
    }


def _run(payload: Dict[str, Any]) -> Dict[str, Any]:
    merged = _merge_input(payload)
    errors = _validate_request(merged)
    if errors:
        raise ValueError(f"Invalid request: {', '.join(errors)}")

    action = merged["action"]
    start_time = time.perf_counter()

    if action == "analyze":
        result = _analyze(merged["logs"])
    elif action == "evolve":
        result = _evolve(
            merged["logs"],
            merged.get("strategy", "auto"),
            str(merged.get("target_file") or ""),
        )
    else:
        result = _status()

    latency_ms = _round_js((time.perf_counter() - start_time) * 1000)
    return {
        "action": action,
        **result,
        "_meta": {
            "skill": "capability-evolver",
            "package": "capability-evolver-pro",
            "version": "1.0.2",
            "mode": "local",
            "latency_ms": latency_ms,
            "strategy": merged.get("strategy", "auto"),
        },
    }


def _run_with_action(default_action: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(payload or {})
    merged.setdefault("action", default_action)
    return _run(merged)


def register(runtime):
    runtime.register_plugin(
        "capability_evolver",
        description="Local deterministic log analysis and self-improvement planning for Jarvis.",
    )
    runtime.register_action(
        "capability_evolver",
        "capability_evolver.run",
        _run,
        description="Run analyze, evolve, or status actions through the Capability Evolver bridge.",
    )
    runtime.register_action(
        "capability_evolver",
        "capability_evolver.analyze",
        lambda payload: _run_with_action("analyze", payload),
        description="Analyze logs and return patterns, health score, and recommendations.",
    )
    runtime.register_action(
        "capability_evolver",
        "capability_evolver.evolve",
        lambda payload: _run_with_action("evolve", payload),
        description="Generate an evolution plan from runtime logs.",
    )
    runtime.register_action(
        "capability_evolver",
        "capability_evolver.status",
        lambda payload: _run_with_action("status", payload),
        description="Return plugin status, limits, and supported actions.",
    )
