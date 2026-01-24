"""Logic Diagnostics Service - Comprehensive debugging for pattern matching and routing.

This service provides deep analysis of why logic decisions succeeded or failed.
It captures:
1. All patterns that were checked and their results
2. Why specific patterns did or didn't match
3. Alternative patterns that came close to matching
4. Suggestions for improving pattern coverage
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from difflib import SequenceMatcher
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MatchFailureReason(Enum):
    """Reasons why a pattern didn't match."""

    NO_MATCH = "no_match"  # Pattern simply didn't match
    CASE_MISMATCH = "case_mismatch"  # Would match with different case
    PARTIAL_MATCH = "partial_match"  # Matched part of text
    ANCHOR_FAIL = "anchor_fail"  # ^ or $ prevented match
    WORD_ORDER = "word_order"  # Words present but wrong order
    MISSING_KEYWORD = "missing_keyword"  # Key word from pattern not in text
    EXTRA_WORDS = "extra_words"  # Text has extra words not in pattern
    TYPO = "typo"  # Likely typo in key word
    DISABLED = "disabled"  # Pattern is disabled


@dataclass
class PatternCheckResult:
    """Result of checking a single pattern against text."""

    pattern_str: str
    pattern_group: str
    sub_category: str | None
    matched: bool
    failure_reason: MatchFailureReason | None = None
    similarity_score: float = 0.0  # 0-1, how close was the match
    partial_matches: list[str] = field(default_factory=list)  # What parts matched
    suggestions: list[str] = field(default_factory=list)  # How to fix
    match_position: tuple[int, int] | None = None  # Start, end of match in text


@dataclass
class PatternDiagnostics:
    """Full diagnostic report for pattern matching on a text input."""

    input_text: str
    normalized_text: str  # After normalization (lowercase, etc.)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Results
    winner: PatternCheckResult | None = None  # The pattern that matched (if any)
    all_checks: list[PatternCheckResult] = field(default_factory=list)
    near_misses: list[PatternCheckResult] = field(default_factory=list)

    # Analysis
    total_patterns_checked: int = 0
    classification_method: str = ""  # "pattern", "heuristic", "llm"
    processing_time_ms: float = 0

    # Suggestions for improvement
    suggested_patterns: list[str] = field(default_factory=list)
    suggested_modifications: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for API responses."""
        return {
            "input_text": self.input_text,
            "normalized_text": self.normalized_text,
            "timestamp": self.timestamp.isoformat(),
            "winner": self._check_to_dict(self.winner) if self.winner else None,
            "near_misses": [self._check_to_dict(c) for c in self.near_misses[:10]],
            "total_patterns_checked": self.total_patterns_checked,
            "classification_method": self.classification_method,
            "processing_time_ms": self.processing_time_ms,
            "suggested_patterns": self.suggested_patterns[:5],
            "suggested_modifications": self.suggested_modifications[:5],
        }

    @staticmethod
    def _check_to_dict(check: PatternCheckResult) -> dict[str, Any]:
        return {
            "pattern": check.pattern_str,
            "group": check.pattern_group,
            "sub_category": check.sub_category,
            "matched": check.matched,
            "failure_reason": check.failure_reason.value if check.failure_reason else None,
            "similarity_score": check.similarity_score,
            "partial_matches": check.partial_matches,
            "suggestions": check.suggestions,
        }


class LogicDiagnosticsService:
    """Service for diagnosing pattern matching and routing logic."""

    # Common typo mappings
    TYPO_CORRECTIONS: dict[str, list[str]] = {
        "turn": ["trun", "tunr", "turrn", "tern"],
        "switch": ["swtich", "swich", "swithc", "siwtch"],
        "light": ["lihgt", "ligth", "ligt", "ligh"],
        "lights": ["lihgts", "ligths", "ligts", "lighs"],
        "off": ["of", "offfff", "offf", "fo"],
        "on": ["no", "onnn", "onn"],
        "room": ["roon", "rom", "rooom"],
        "living": ["livign", "livin", "livng"],
        "bedroom": ["bedroon", "bedrom", "bedrooom"],
        "kitchen": ["kithcen", "kithen", "kicthen"],
        "what": ["waht", "wht", "whta"],
        "time": ["tiem", "tim", "tmie"],
        "temperature": ["temperture", "tempreature", "tempurature", "temp"],
        "remember": ["remeber", "remmeber", "remembr"],
    }

    def __init__(self) -> None:
        self._diagnostics_history: list[PatternDiagnostics] = []
        self._max_history = 1000

    def diagnose_pattern_match(
        self,
        text: str,
        compiled_patterns: dict[str, list[tuple[re.Pattern[str], str]]],
        pattern_priority: list[tuple[str, Any, float]],
    ) -> PatternDiagnostics:
        """Perform detailed diagnosis of pattern matching.

        Args:
            text: The input text to classify
            compiled_patterns: Dict of pattern_group -> [(compiled_pattern, sub_category)]
            pattern_priority: List of (group_name, intent_category, confidence) in order

        Returns:
            PatternDiagnostics with full analysis
        """
        import time

        start = time.perf_counter()

        normalized = text.lower().strip()
        diag = PatternDiagnostics(
            input_text=text,
            normalized_text=normalized,
        )

        # Check all patterns in priority order
        found_winner = False
        for group_name, _intent, _confidence in pattern_priority:
            patterns = compiled_patterns.get(group_name, [])
            for pattern, sub_category in patterns:
                check_result = self._check_pattern(
                    text=normalized,
                    pattern=pattern,
                    group=group_name,
                    sub_category=sub_category,
                )
                diag.all_checks.append(check_result)
                diag.total_patterns_checked += 1

                if check_result.matched and not found_winner:
                    diag.winner = check_result
                    found_winner = True
                elif not check_result.matched and check_result.similarity_score > 0.6:
                    # Near miss - worth noting
                    diag.near_misses.append(check_result)

        # Sort near misses by similarity
        diag.near_misses.sort(key=lambda x: x.similarity_score, reverse=True)

        # Generate suggestions if no winner
        if not diag.winner:
            diag.classification_method = "fallback"
            diag.suggested_patterns = self._generate_pattern_suggestions(normalized)
            diag.suggested_modifications = self._suggest_modifications(normalized, diag.near_misses)
        else:
            diag.classification_method = "pattern"

        diag.processing_time_ms = (time.perf_counter() - start) * 1000

        # Store in history
        self._store_diagnostics(diag)

        return diag

    def _check_pattern(
        self,
        text: str,
        pattern: re.Pattern[str],
        group: str,
        sub_category: str | None,
    ) -> PatternCheckResult:
        """Check if a pattern matches and diagnose why/why not."""
        result = PatternCheckResult(
            pattern_str=pattern.pattern,
            pattern_group=group,
            sub_category=sub_category,
            matched=False,
        )

        # Try the match
        match = pattern.match(text)
        if match:
            result.matched = True
            result.similarity_score = 1.0
            result.match_position = match.span()
            return result

        # Pattern didn't match - figure out why
        result.failure_reason = self._diagnose_failure(text, pattern)
        result.similarity_score = self._calculate_similarity(text, pattern)
        result.partial_matches = self._find_partial_matches(text, pattern)
        result.suggestions = self._generate_fix_suggestions(text, pattern, result.failure_reason)

        return result

    def _diagnose_failure(self, text: str, pattern: re.Pattern[str]) -> MatchFailureReason:
        """Diagnose why a pattern didn't match."""
        pattern_str = pattern.pattern

        # Check if it's an anchor issue
        if pattern_str.startswith("^"):
            # Would it match without the anchor?
            test_pattern = re.compile(pattern_str[1:], re.IGNORECASE)
            if test_pattern.search(text):
                return MatchFailureReason.ANCHOR_FAIL

        if pattern_str.endswith("$"):
            test_pattern = re.compile(pattern_str[:-1], re.IGNORECASE)
            if test_pattern.search(text):
                return MatchFailureReason.ANCHOR_FAIL

        # Check for partial match
        if pattern.search(text):
            return MatchFailureReason.PARTIAL_MATCH

        # Extract keywords from pattern and check presence
        keywords = self._extract_keywords(pattern_str)
        text_words = set(text.lower().split())
        missing = [kw for kw in keywords if kw not in text_words]

        if missing:
            # Check if missing words are typos
            for word in missing:
                if self._is_likely_typo(word, text_words):
                    return MatchFailureReason.TYPO
            return MatchFailureReason.MISSING_KEYWORD

        # All keywords present but still no match - likely word order
        if all(kw in text_words for kw in keywords):
            return MatchFailureReason.WORD_ORDER

        return MatchFailureReason.NO_MATCH

    def _extract_keywords(self, pattern_str: str) -> list[str]:
        """Extract meaningful keywords from a regex pattern."""
        # Remove regex special chars and extract words
        cleaned = re.sub(r"[\^\$\.\*\+\?\(\)\[\]\{\}\|\\]", " ", pattern_str)
        words = cleaned.split()
        # Filter out single chars and regex tokens
        keywords = [
            w.lower()
            for w in words
            if len(w) > 2 and w not in {"the", "and", "for", "can", "you", "please"}
        ]
        return keywords

    def _is_likely_typo(self, target: str, text_words: set[str]) -> bool:
        """Check if any word in text is a typo of target."""
        # Check known typo mappings
        if target in self.TYPO_CORRECTIONS:
            if any(typo in text_words for typo in self.TYPO_CORRECTIONS[target]):
                return True

        # Check edit distance
        for word in text_words:
            if self._edit_distance(word, target) <= 2 and len(word) > 3:
                return True

        return False

    @staticmethod
    def _edit_distance(s1: str, s2: str) -> int:
        """Calculate Levenshtein edit distance."""
        if len(s1) < len(s2):
            return LogicDiagnosticsService._edit_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]

    def _calculate_similarity(self, text: str, pattern: re.Pattern[str]) -> float:
        """Calculate how similar the text is to the pattern."""
        # Extract the most representative string from the pattern
        clean_pattern = re.sub(r"[\^\$\.\*\+\?\(\)\[\]\{\}\|\\]", "", pattern.pattern)
        clean_pattern = re.sub(r"\s+", " ", clean_pattern).strip()

        if not clean_pattern:
            return 0.0

        return SequenceMatcher(None, text.lower(), clean_pattern.lower()).ratio()

    def _find_partial_matches(self, text: str, pattern: re.Pattern[str]) -> list[str]:
        """Find parts of the text that partially match the pattern."""
        partial = []

        # Extract groups from pattern if any
        # Also try to find literal strings that do match
        keywords = self._extract_keywords(pattern.pattern)
        for kw in keywords:
            if kw in text.lower():
                partial.append(f"'{kw}' found")

        return partial[:5]

    def _generate_fix_suggestions(
        self,
        text: str,
        pattern: re.Pattern[str],
        failure_reason: MatchFailureReason,
    ) -> list[str]:
        """Generate suggestions for how to fix the mismatch."""
        suggestions = []

        if failure_reason == MatchFailureReason.ANCHOR_FAIL:
            suggestions.append("Consider using .* at the start/end of pattern")
            suggestions.append("Pattern requires exact start/end but input has extra words")

        elif failure_reason == MatchFailureReason.TYPO:
            suggestions.append("Input appears to have typos - add typo variations to pattern")
            # Find the likely typo
            keywords = self._extract_keywords(pattern.pattern)
            text_words = text.lower().split()
            for kw in keywords:
                for word in text_words:
                    if self._edit_distance(kw, word) <= 2:
                        suggestions.append(f"Add typo variant: {word} → {kw}")

        elif failure_reason == MatchFailureReason.MISSING_KEYWORD:
            keywords = self._extract_keywords(pattern.pattern)
            text_words = set(text.lower().split())
            missing = [kw for kw in keywords if kw not in text_words]
            suggestions.append(f"Input missing keywords: {', '.join(missing)}")

        elif failure_reason == MatchFailureReason.WORD_ORDER:
            suggestions.append("Keywords present but in different order")
            suggestions.append("Consider making pattern order-independent")

        return suggestions[:3]

    def _generate_pattern_suggestions(self, text: str) -> list[str]:
        """Generate new pattern suggestions based on input text."""
        suggestions = []
        words = text.split()

        # Common command patterns
        if words and words[0] in {"turn", "switch", "set", "make", "adjust", "open", "close"}:
            verb = words[0]
            rest = " ".join(words[1:])
            suggestions.append(f"^{verb}\\s+.*{re.escape(rest[:20])}.*$")
            suggestions.append(f"^{verb}\\s+(on|off|up|down).*$")

        # Question patterns
        if text.endswith("?") or words and words[0] in {"what", "where", "when", "how", "why"}:
            first_word = words[0] if words else "what"
            suggestions.append(f"^{first_word}\\s+.*$")

        # Memory patterns
        if any(w in text for w in ["remember", "recall", "forget", "note"]):
            for trigger in ["remember", "recall", "forget", "note"]:
                if trigger in text:
                    suggestions.append(f".*{trigger}.*")

        return suggestions

    def _suggest_modifications(
        self,
        text: str,
        near_misses: list[PatternCheckResult],
    ) -> list[dict[str, Any]]:
        """Suggest modifications to existing patterns that almost matched."""
        mods = []

        for miss in near_misses[:3]:
            if miss.similarity_score < 0.6:
                continue

            mod = {
                "pattern": miss.pattern_str,
                "group": miss.pattern_group,
                "similarity": miss.similarity_score,
                "reason": miss.failure_reason.value if miss.failure_reason else "unknown",
                "suggestion": self._suggest_pattern_modification(
                    text, miss.pattern_str, miss.failure_reason
                ),
            }
            mods.append(mod)

        return mods

    def _suggest_pattern_modification(
        self,
        text: str,
        pattern_str: str,
        failure_reason: MatchFailureReason | None,
    ) -> str:
        """Suggest how to modify a pattern to match this text."""
        if failure_reason == MatchFailureReason.ANCHOR_FAIL:
            # Remove anchors
            new_pattern = pattern_str
            if new_pattern.startswith("^"):
                new_pattern = ".*" + new_pattern[1:]
            if new_pattern.endswith("$"):
                new_pattern = new_pattern[:-1] + ".*"
            return f"Try: {new_pattern}"

        if failure_reason == MatchFailureReason.TYPO:
            # Add typo alternation
            words = text.split()
            for word in words:
                if len(word) > 3:
                    return f"Add typo: ({word}|{word.replace(word[1], word[2], 1)})"

        return f"Consider pattern that matches: {text[:30]}..."

    def _store_diagnostics(self, diag: PatternDiagnostics) -> None:
        """Store diagnostics in history."""
        self._diagnostics_history.append(diag)
        if len(self._diagnostics_history) > self._max_history:
            self._diagnostics_history = self._diagnostics_history[-self._max_history :]

    def get_recent_failures(self, limit: int = 50) -> list[PatternDiagnostics]:
        """Get recent classification failures (no winner found)."""
        failures = [d for d in self._diagnostics_history if d.winner is None]
        return failures[-limit:]

    def get_common_near_misses(self) -> dict[str, int]:
        """Get patterns that frequently almost match."""
        near_miss_counts: dict[str, int] = {}
        for diag in self._diagnostics_history:
            for miss in diag.near_misses:
                key = f"{miss.pattern_group}:{miss.pattern_str[:50]}"
                near_miss_counts[key] = near_miss_counts.get(key, 0) + 1
        return dict(sorted(near_miss_counts.items(), key=lambda x: -x[1])[:20])

    def get_stats(self) -> dict[str, Any]:
        """Get diagnostic statistics."""
        total = len(self._diagnostics_history)
        if total == 0:
            return {"total_diagnoses": 0}

        failures = sum(1 for d in self._diagnostics_history if d.winner is None)
        pattern_matches = sum(
            1 for d in self._diagnostics_history if d.classification_method == "pattern"
        )

        failure_reasons: dict[str, int] = {}
        for diag in self._diagnostics_history:
            if diag.winner is None and diag.near_misses:
                reason = diag.near_misses[0].failure_reason
                if reason:
                    failure_reasons[reason.value] = failure_reasons.get(reason.value, 0) + 1

        return {
            "total_diagnoses": total,
            "pattern_match_rate": pattern_matches / total if total else 0,
            "failure_rate": failures / total if total else 0,
            "failure_reasons": failure_reasons,
            "common_near_misses": self.get_common_near_misses(),
        }


# Singleton instance
_diagnostics_service: LogicDiagnosticsService | None = None


def get_diagnostics_service() -> LogicDiagnosticsService:
    """Get the singleton diagnostics service."""
    global _diagnostics_service
    if _diagnostics_service is None:
        _diagnostics_service = LogicDiagnosticsService()
    return _diagnostics_service
