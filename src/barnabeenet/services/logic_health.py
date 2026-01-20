"""Logic Health Monitor - Tracks classification consistency and detects issues.

This service monitors the health of the pattern matching and classification system:
1. Classification consistency - Same input should produce same output
2. Near-miss tracking - Patterns that frequently almost match
3. Failure patterns - Common failure reasons to address
4. Auto-suggestions - When to update patterns based on observed behavior
"""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class HealthIssueType(Enum):
    """Types of health issues detected."""

    INCONSISTENT_CLASSIFICATION = "inconsistent_classification"
    FREQUENT_NEAR_MISS = "frequent_near_miss"
    HIGH_FAILURE_RATE = "high_failure_rate"
    CONFIDENCE_DRIFT = "confidence_drift"
    PATTERN_CONFLICT = "pattern_conflict"


class IssueSeverity(Enum):
    """Severity levels for health issues."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ClassificationRecord:
    """Record of a single classification for tracking consistency."""

    input_hash: str  # Hash of normalized input
    raw_input: str
    normalized_input: str
    intent: str
    sub_category: str | None
    confidence: float
    classification_method: str  # pattern, heuristic, llm
    matched_pattern: str | None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "input_hash": self.input_hash,
            "raw_input": self.raw_input[:100],
            "normalized_input": self.normalized_input[:100],
            "intent": self.intent,
            "sub_category": self.sub_category,
            "confidence": self.confidence,
            "classification_method": self.classification_method,
            "matched_pattern": self.matched_pattern,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class HealthIssue:
    """A detected health issue in the logic system."""

    issue_type: HealthIssueType
    severity: IssueSeverity
    title: str
    description: str
    affected_inputs: list[str] = field(default_factory=list)
    suggested_action: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    auto_fixable: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "issue_type": self.issue_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "affected_inputs": self.affected_inputs[:10],
            "suggested_action": self.suggested_action,
            "evidence": self.evidence,
            "detected_at": self.detected_at.isoformat(),
            "auto_fixable": self.auto_fixable,
        }


@dataclass
class HealthReport:
    """Overall health report for the logic system."""

    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    total_classifications: int = 0
    unique_inputs: int = 0
    consistency_score: float = 1.0  # 0-1, 1 = perfectly consistent
    avg_confidence: float = 0.0
    pattern_match_rate: float = 0.0
    heuristic_rate: float = 0.0
    llm_fallback_rate: float = 0.0
    issues: list[HealthIssue] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "generated_at": self.generated_at.isoformat(),
            "total_classifications": self.total_classifications,
            "unique_inputs": self.unique_inputs,
            "consistency_score": round(self.consistency_score, 3),
            "avg_confidence": round(self.avg_confidence, 3),
            "pattern_match_rate": round(self.pattern_match_rate, 3),
            "heuristic_rate": round(self.heuristic_rate, 3),
            "llm_fallback_rate": round(self.llm_fallback_rate, 3),
            "issues": [i.to_dict() for i in self.issues],
            "issues_by_severity": {
                "critical": len([i for i in self.issues if i.severity == IssueSeverity.CRITICAL]),
                "error": len([i for i in self.issues if i.severity == IssueSeverity.ERROR]),
                "warning": len([i for i in self.issues if i.severity == IssueSeverity.WARNING]),
                "info": len([i for i in self.issues if i.severity == IssueSeverity.INFO]),
            },
            "recommendations": self.recommendations[:10],
        }


class LogicHealthMonitor:
    """Monitors the health of the classification/logic system.

    Tracks:
    - Classification consistency (same input → same output)
    - Near-miss frequency (patterns that almost match)
    - Failure reasons (why patterns don't match)
    - Confidence trends (are we getting less confident?)
    """

    def __init__(
        self,
        max_records: int = 10000,
        consistency_window: timedelta = timedelta(hours=24),
    ) -> None:
        """Initialize the health monitor.

        Args:
            max_records: Maximum classification records to keep
            consistency_window: Time window for consistency analysis
        """
        self._max_records = max_records
        self._consistency_window = consistency_window

        # Classification history by input hash
        self._classifications: dict[str, list[ClassificationRecord]] = defaultdict(list)

        # Near-miss tracking: (pattern_str, input_hash) -> count
        self._near_miss_counts: dict[tuple[str, str], int] = defaultdict(int)

        # Failure reason tracking: failure_reason -> count
        self._failure_counts: dict[str, int] = defaultdict(int)

        # Method tracking for rate calculation
        self._method_counts: dict[str, int] = defaultdict(int)

        # Total records
        self._total_records = 0

    def _normalize_text(self, text: str) -> str:
        """Normalize text for consistent hashing."""
        return " ".join(text.lower().strip().split())

    def _hash_input(self, text: str) -> str:
        """Create a hash of normalized input text."""
        normalized = self._normalize_text(text)
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def record_classification(
        self,
        raw_input: str,
        intent: str,
        sub_category: str | None,
        confidence: float,
        classification_method: str,
        matched_pattern: str | None = None,
        near_misses: list[dict[str, Any]] | None = None,
        failure_reason: str | None = None,
    ) -> None:
        """Record a classification result for health tracking.

        Args:
            raw_input: The original input text
            intent: Classified intent
            sub_category: Sub-category if any
            confidence: Classification confidence
            classification_method: "pattern", "heuristic", or "llm"
            matched_pattern: Pattern that matched (if any)
            near_misses: List of near-miss patterns
            failure_reason: Why pattern matching failed (if it did)
        """
        normalized = self._normalize_text(raw_input)
        input_hash = self._hash_input(raw_input)

        record = ClassificationRecord(
            input_hash=input_hash,
            raw_input=raw_input,
            normalized_input=normalized,
            intent=intent,
            sub_category=sub_category,
            confidence=confidence,
            classification_method=classification_method,
            matched_pattern=matched_pattern,
        )

        # Store classification
        self._classifications[input_hash].append(record)
        self._total_records += 1

        # Track method usage
        self._method_counts[classification_method] += 1

        # Track near misses
        if near_misses:
            for nm in near_misses:
                pattern_str = nm.get("pattern_str", "unknown")
                self._near_miss_counts[(pattern_str, input_hash)] += 1

        # Track failure reasons
        if failure_reason:
            self._failure_counts[failure_reason] += 1

        # Prune old records if needed
        self._prune_old_records()

    def _prune_old_records(self) -> None:
        """Remove old records to stay under max_records limit."""
        if self._total_records <= self._max_records:
            return

        # Find oldest records and remove them
        cutoff = datetime.now(UTC) - self._consistency_window

        for input_hash in list(self._classifications.keys()):
            records = self._classifications[input_hash]
            # Keep only records within window
            self._classifications[input_hash] = [r for r in records if r.timestamp > cutoff]
            if not self._classifications[input_hash]:
                del self._classifications[input_hash]

        # Recalculate total
        self._total_records = sum(len(r) for r in self._classifications.values())

    def check_consistency(self, input_hash: str) -> tuple[bool, list[ClassificationRecord]]:
        """Check if classifications for an input are consistent.

        Returns:
            Tuple of (is_consistent, list of conflicting records)
        """
        records = self._classifications.get(input_hash, [])
        if len(records) < 2:
            return True, []

        # Check if all records have same intent + sub_category
        first = records[0]
        conflicts = [
            r
            for r in records[1:]
            if r.intent != first.intent or r.sub_category != first.sub_category
        ]

        return len(conflicts) == 0, conflicts

    def generate_health_report(self) -> HealthReport:
        """Generate a comprehensive health report.

        Analyzes:
        - Classification consistency across all inputs
        - Near-miss frequency (potential pattern gaps)
        - Failure patterns
        - Confidence distribution
        - Method usage rates
        """
        report = HealthReport()
        report.total_classifications = self._total_records
        report.unique_inputs = len(self._classifications)

        if self._total_records == 0:
            return report

        # Calculate method rates
        total_methods = sum(self._method_counts.values())
        if total_methods > 0:
            report.pattern_match_rate = self._method_counts.get("pattern", 0) / total_methods
            report.heuristic_rate = self._method_counts.get("heuristic", 0) / total_methods
            report.llm_fallback_rate = self._method_counts.get("llm", 0) / total_methods

        # Calculate average confidence and consistency
        all_records = [r for records in self._classifications.values() for r in records]
        if all_records:
            report.avg_confidence = sum(r.confidence for r in all_records) / len(all_records)

        # Check consistency for each input
        inconsistent_inputs = []
        for input_hash, records in self._classifications.items():
            is_consistent, conflicts = self.check_consistency(input_hash)
            if not is_consistent:
                inconsistent_inputs.append((input_hash, records, conflicts))

        # Calculate consistency score
        if self._classifications:
            consistent_count = len(self._classifications) - len(inconsistent_inputs)
            report.consistency_score = consistent_count / len(self._classifications)

        # Generate issues
        self._detect_issues(report, inconsistent_inputs)

        # Generate recommendations
        self._generate_recommendations(report)

        return report

    def _detect_issues(
        self,
        report: HealthReport,
        inconsistent_inputs: list[tuple[str, list[ClassificationRecord], list]],
    ) -> None:
        """Detect health issues from the data."""
        # Issue 1: Inconsistent classifications
        for _input_hash, records, _conflicts in inconsistent_inputs:
            first = records[0]
            intents_seen = list({r.intent for r in records})

            issue = HealthIssue(
                issue_type=HealthIssueType.INCONSISTENT_CLASSIFICATION,
                severity=IssueSeverity.WARNING,
                title=f"Inconsistent classification for '{first.normalized_input[:50]}...'",
                description=(
                    f"This input has been classified as {len(intents_seen)} different intents: "
                    f"{', '.join(intents_seen)}"
                ),
                affected_inputs=[first.raw_input[:100]],
                suggested_action="Review and add a specific pattern for this input",
                evidence={
                    "intents_seen": intents_seen,
                    "classifications_count": len(records),
                },
            )
            report.issues.append(issue)

        # Issue 2: Frequent near misses (patterns that almost work)
        frequent_near_misses = [
            (pattern_input, count)
            for pattern_input, count in self._near_miss_counts.items()
            if count >= 3  # Pattern almost matched same input 3+ times
        ]

        for (pattern_str, input_hash), count in frequent_near_misses:
            records = self._classifications.get(input_hash, [])
            sample_input = records[0].raw_input if records else "unknown"

            issue = HealthIssue(
                issue_type=HealthIssueType.FREQUENT_NEAR_MISS,
                severity=IssueSeverity.INFO,
                title=f"Pattern '{pattern_str[:50]}...' frequently almost matches",
                description=(
                    f"This pattern came close to matching {count} times. Consider expanding it."
                ),
                affected_inputs=[sample_input[:100]],
                suggested_action="Review pattern and consider making it more flexible",
                evidence={
                    "pattern": pattern_str,
                    "near_miss_count": count,
                },
                auto_fixable=True,
            )
            report.issues.append(issue)

        # Issue 3: High failure rate
        total_failures = sum(self._failure_counts.values())
        if self._total_records > 10 and total_failures / self._total_records > 0.3:
            issue = HealthIssue(
                issue_type=HealthIssueType.HIGH_FAILURE_RATE,
                severity=IssueSeverity.WARNING,
                title="High pattern failure rate detected",
                description=(
                    f"{total_failures}/{self._total_records} classifications "
                    f"({100 * total_failures / self._total_records:.1f}%) fell through to "
                    "heuristic or LLM fallback. Consider adding more patterns."
                ),
                evidence={
                    "total_failures": total_failures,
                    "total_classifications": self._total_records,
                    "failure_rate": total_failures / self._total_records,
                    "top_failure_reasons": dict(
                        sorted(self._failure_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                    ),
                },
                suggested_action="Add patterns for common inputs that fall through",
            )
            report.issues.append(issue)

        # Issue 4: Confidence drift (low average confidence)
        if report.avg_confidence < 0.7 and self._total_records > 20:
            issue = HealthIssue(
                issue_type=HealthIssueType.CONFIDENCE_DRIFT,
                severity=IssueSeverity.INFO,
                title="Low average classification confidence",
                description=(
                    f"Average confidence is {report.avg_confidence:.2f}. "
                    f"This may indicate unclear inputs or insufficient patterns."
                ),
                evidence={
                    "avg_confidence": report.avg_confidence,
                },
                suggested_action="Review low-confidence classifications for patterns",
            )
            report.issues.append(issue)

    def _generate_recommendations(self, report: HealthReport) -> None:
        """Generate actionable recommendations based on health data."""
        # Recommendation based on LLM fallback rate
        if report.llm_fallback_rate > 0.2:
            report.recommendations.append(
                f"High LLM fallback rate ({100 * report.llm_fallback_rate:.1f}%). "
                f"Add patterns for common inputs to reduce latency and cost."
            )

        # Recommendation based on consistency
        if report.consistency_score < 0.95:
            report.recommendations.append(
                f"Classification consistency is {100 * report.consistency_score:.1f}%. "
                f"Review inconsistent inputs and add specific patterns."
            )

        # Recommendation based on failure reasons
        if self._failure_counts:
            top_reason = max(self._failure_counts.items(), key=lambda x: x[1])
            report.recommendations.append(
                f"Most common failure reason: '{top_reason[0]}' ({top_reason[1]} times). "
                f"Consider addressing this pattern gap."
            )

        # General recommendation if things look good
        if not report.recommendations and report.consistency_score >= 0.95:
            report.recommendations.append(
                "Logic system appears healthy. Continue monitoring for regressions."
            )

    def get_inconsistent_inputs(self) -> list[dict[str, Any]]:
        """Get all inputs with inconsistent classifications."""
        inconsistent = []
        for input_hash, records in self._classifications.items():
            is_consistent, conflicts = self.check_consistency(input_hash)
            if not is_consistent:
                first = records[0]
                inconsistent.append(
                    {
                        "input": first.normalized_input,
                        "input_hash": input_hash,
                        "classification_count": len(records),
                        "intents_seen": list({r.intent for r in records}),
                        "records": [r.to_dict() for r in records[:5]],  # Limit to 5
                    }
                )
        return inconsistent

    def get_frequent_near_misses(self, min_count: int = 3) -> list[dict[str, Any]]:
        """Get patterns that frequently almost match."""
        result = []
        for (pattern_str, input_hash), count in self._near_miss_counts.items():
            if count >= min_count:
                records = self._classifications.get(input_hash, [])
                sample_input = records[0].normalized_input if records else "unknown"
                result.append(
                    {
                        "pattern": pattern_str,
                        "input_hash": input_hash,
                        "sample_input": sample_input,
                        "near_miss_count": count,
                    }
                )
        return sorted(result, key=lambda x: x["near_miss_count"], reverse=True)

    def get_stats(self) -> dict[str, Any]:
        """Get summary statistics."""
        return {
            "total_classifications": self._total_records,
            "unique_inputs": len(self._classifications),
            "method_counts": dict(self._method_counts),
            "failure_counts": dict(self._failure_counts),
            "near_miss_patterns": len(self._near_miss_counts),
        }

    def clear(self) -> None:
        """Clear all tracked data."""
        self._classifications.clear()
        self._near_miss_counts.clear()
        self._failure_counts.clear()
        self._method_counts.clear()
        self._total_records = 0


# Singleton instance
_health_monitor: LogicHealthMonitor | None = None


def get_health_monitor() -> LogicHealthMonitor:
    """Get the singleton LogicHealthMonitor instance."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = LogicHealthMonitor()
    return _health_monitor


def reset_health_monitor() -> None:
    """Reset the health monitor (for testing)."""
    global _health_monitor
    if _health_monitor:
        _health_monitor.clear()
    _health_monitor = None
