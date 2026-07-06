"""Budget guard for the tool-calling agent loop."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum


class BudgetDecision(str, Enum):
    ALLOW = "allow"
    WARN_REPEAT = "warn_repeat"
    SKIP_REPEAT = "skip_repeat"
    FORCE_FINISH = "force_finish"


@dataclass
class BudgetGuard:
    max_calls: int
    wall_clock_seconds: int
    started_at: float = field(default_factory=time.monotonic)
    call_count: int = 0
    history: list[str] = field(default_factory=list)
    repeat_counts: dict[str, int] = field(default_factory=dict)
    warnings_issued: set[float] = field(default_factory=set)
    warning_thresholds: tuple[float, ...] = (0.5, 0.8)

    def _signature(self, tool_name: str, args: dict) -> str:
        payload = json.dumps({"tool": tool_name, "args": args}, sort_keys=True, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def elapsed_seconds(self) -> float:
        return time.monotonic() - self.started_at

    def _usage_ratio(self) -> float:
        call_ratio = self.call_count / self.max_calls if self.max_calls else 1.0
        time_ratio = self.elapsed_seconds() / self.wall_clock_seconds if self.wall_clock_seconds else 1.0
        return max(call_ratio, time_ratio)

    def pending_warning(self) -> str | None:
        ratio = self._usage_ratio()
        for threshold in self.warning_thresholds:
            if ratio >= threshold and threshold not in self.warnings_issued:
                self.warnings_issued.add(threshold)
                pct = int(threshold * 100)
                return (
                    f"Budget warning ({pct}% used): you have used {self.call_count} of "
                    f"{self.max_calls} tool calls and {self.elapsed_seconds():.0f}s of "
                    f"{self.wall_clock_seconds}s. Prioritize validating and executing SQL now."
                )
        return None

    def check_before_call(self, tool_name: str, args: dict) -> BudgetDecision:
        if self.call_count >= self.max_calls:
            return BudgetDecision.FORCE_FINISH
        if self.elapsed_seconds() >= self.wall_clock_seconds:
            return BudgetDecision.FORCE_FINISH

        sig = self._signature(tool_name, args)
        repeats = self.repeat_counts.get(sig, 0) + 1
        self.repeat_counts[sig] = repeats
        if repeats >= 4:
            return BudgetDecision.FORCE_FINISH
        if repeats == 3:
            return BudgetDecision.SKIP_REPEAT
        if repeats == 2:
            return BudgetDecision.WARN_REPEAT
        return BudgetDecision.ALLOW

    def record_call(self, tool_name: str, args: dict) -> None:
        sig = self._signature(tool_name, args)
        self.history.append(sig)
        self.call_count += 1

    def guard_message(self, decision: BudgetDecision, tool_name: str) -> str | None:
        if decision == BudgetDecision.WARN_REPEAT:
            return (
                f"You already called `{tool_name}` with the same arguments. "
                "The result will not change. Try a different tool or answer now."
            )
        if decision == BudgetDecision.SKIP_REPEAT:
            return (
                f"You called `{tool_name}` with identical arguments again and received the same "
                "information. Your assumption may be wrong — try a different tool or answer now."
            )
        if decision == BudgetDecision.FORCE_FINISH:
            return (
                "Tool budget exhausted or time limit reached. "
                "Respond now with your best validated SQL in the required JSON format, "
                "or explain what you learned and what you would query next."
            )
        return None


__all__ = ["BudgetDecision", "BudgetGuard"]
