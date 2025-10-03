"""
Escalation trigger detection utilities for Story 2.2

Implements pattern matching and keyword analysis to detect escalation triggers
in customer responses according to AC1 and AC2 requirements.
"""

import re
from typing import List, Dict, Any, Optional
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class EscalationReason(Enum):
    """Enumeration of escalation reasons per requirements."""
    ANGER = "customer_anger"
    LEGAL_REQUEST = "legal_request"
    COMPLAINT = "formal_complaint"
    CONFUSION = "customer_confusion"
    DISSATISFACTION = "general_dissatisfaction"


class EscalationTrigger:
    """Represents a detected escalation trigger with confidence score."""

    def __init__(
        self,
        reason: EscalationReason,
        confidence: float,
        matched_text: str,
        pattern_type: str
    ):
        self.reason = reason
        self.confidence = confidence
        self.matched_text = matched_text
        self.pattern_type = pattern_type

    def to_dict(self) -> Dict[str, Any]:
        """Convert trigger to dictionary format."""
        return {
            "reason": self.reason.value,
            "confidence": self.confidence,
            "matched_text": self.matched_text,
            "pattern_type": self.pattern_type
        }


class EscalationDetector:
    """
    Detects escalation triggers in customer responses using pattern matching
    and keyword analysis as specified in requirements AC1 and AC2.
    """

    def __init__(self):
        """Initialize the escalation detector with patterns and keywords."""
        self._initialize_patterns()
        self._initialize_keywords()

    def _initialize_patterns(self) -> None:
        """Initialize regex patterns for different escalation types."""
        self.patterns = {
            EscalationReason.ANGER: [
                # Direct expressions of anger
                r'\b(?i:furious|enraged|pissed off|livid|irate)\b',
                # Threats to take business elsewhere
                r'\b(?i:taking my business elsewhere|going to your competitor|switching companies)\b',
                # Demands to speak to supervisors
                r'\b(?i:speak to your supervisor|talk to your manager|let me speak to someone higher)\b',
            ],
            EscalationReason.LEGAL_REQUEST: [
                # Legal terminology
                r'\b(?i:lawyer|attorney|legal action|lawsuit|suing|legal counsel)\b',
                # Regulatory references
                r'\b(?i:CFPB|consumer financial protection bureau|better business bureau|BBB|regulatory complaint)\b',
                # Formal legal threats
                r'\b(?i:taking legal action|pursuing legal options|consulting my attorney)\b',
            ],
            EscalationReason.COMPLAINT: [
                # Explicit complaint requests
                r'\b(?i:file a complaint|formal complaint|submit a complaint|register a complaint)\b',
                # Documentation requests
                r'\b(?i:written confirmation|documentation|evidence|proof|record of this)\b',
                # Official process mentions
                r'\b(?i:escalate this matter|formal escalation|official complaint|report this issue)\b',
            ],
            EscalationReason.CONFUSION: [
                # Expressions of confusion
                r'\b(?i:i don\'t understand|confused|unclear|doesn\'t make sense|this is confusing)\b',
                # Requests for simpler explanations
                r'\b(?i:explain this simply|break this down|put this in plain english|can you explain this better)\b',
                # Multiple questions indicating confusion
                r'\b(?i:i have so many questions|this is overwhelming|too much information)\b',
            ],
            EscalationReason.DISSATISFACTION: [
                # General negative sentiment
                r'\b(?i:unacceptable|terrible|awful|horrible|disgusted with this service)\b',
                # Strong dissatisfaction
                r'\b(?i:this is ridiculous|outrageous|completely unreasonable|totally unacceptable)\b',
                # Threats to leave (non-anger based)
                r'\b(?i:done with this service|finished with your company|leaving for good)\b',
            ]
        }

    def _initialize_keywords(self) -> None:
        """Initialize keyword lists for different escalation types."""
        self.keywords = {
            EscalationReason.ANGER: [
                'angry', 'mad', 'furious', 'enraged', 'livid', 'irate',
                'supervisor', 'manager', 'someone higher up', 'escalate',
                'taking business elsewhere', 'competitor', 'switching'
            ],
            EscalationReason.LEGAL_REQUEST: [
                'lawyer', 'attorney', 'legal', 'lawsuit', 'suing',
                'CFPB', 'consumer protection', 'better business bureau', 'BBB',
                'regulatory', 'formal complaint', 'legal action'
            ],
            EscalationReason.COMPLAINT: [
                'complaint', 'formal', 'written', 'documentation', 'evidence',
                'proof', 'record', 'escalate', 'official', 'report', 'submit'
            ],
            EscalationReason.CONFUSION: [
                'confused', 'unclear', 'don\'t understand', 'explain',
                'simple terms', 'break it down', 'plain english', 'overwhelmed'
            ],
            EscalationReason.DISSATISFACTION: [
                'unacceptable', 'terrible', 'awful', 'horrible', 'ridiculous',
                'outrageous', 'unreasonable', 'disgusted', 'done', 'leaving'
            ]
        }

    def detect_triggers(self, message_text: str) -> List[EscalationTrigger]:
        """
        Detect escalation triggers in a message.

        Args:
            message_text: The customer message to analyze

        Returns:
            List of detected triggers with confidence scores
        """
        triggers = []
        normalized_text = message_text.lower().strip()

        logger.debug(
            "Analyzing message for escalation triggers",
            message_length=len(normalized_text),
            message_preview=normalized_text[:100] + "..." if len(normalized_text) > 100 else normalized_text
        )

        # Check each escalation reason
        for reason, patterns in self.patterns.items():
            # Pattern matching with confidence scoring
            for pattern in patterns:
                matches = re.finditer(pattern, message_text, re.IGNORECASE)
                for match in matches:
                    confidence = self._calculate_pattern_confidence(match, pattern, reason)
                    triggers.append(EscalationTrigger(
                        reason=reason,
                        confidence=confidence,
                        matched_text=match.group(),
                        pattern_type="regex"
                    ))

            # Keyword matching with confidence scoring
            keyword_matches = self._match_keywords(normalized_text, reason)
            triggers.extend(keyword_matches)

        # Remove duplicates and sort by confidence
        unique_triggers = self._deduplicate_triggers(triggers)
        sorted_triggers = sorted(unique_triggers, key=lambda t: t.confidence, reverse=True)

        logger.info(
            "Escalation trigger detection complete",
            total_triggers=len(sorted_triggers),
            high_confidence_triggers=len([t for t in sorted_triggers if t.confidence >= 0.8])
        )

        return sorted_triggers

    def _calculate_pattern_confidence(
        self,
        match: re.Match,
        pattern: str,
        reason: EscalationReason
    ) -> float:
        """
        Calculate confidence score for a pattern match.

        Higher confidence for:
        - Exact phrase matches
        - Legal-related patterns (higher risk)
        - Multiple occurrences in same message
        """
        base_confidence = 0.7

        # Boost confidence for legal-related patterns
        if reason == EscalationReason.LEGAL_REQUEST:
            base_confidence = 0.85

        # Boost for longer matches (more specific phrases)
        match_length = len(match.group())
        if match_length > 10:
            base_confidence += 0.1

        # Boost for exact phrase matches (no wildcards)
        if '?' not in pattern and '*' not in pattern:
            base_confidence += 0.05

        # Boost for supervisor/manager demands
        if reason == EscalationReason.ANGER and any(
            word in match.group().lower()
            for word in ['supervisor', 'manager', 'someone higher']
        ):
            base_confidence += 0.1

        return min(base_confidence, 1.0)

    def _match_keywords(self, text: str, reason: EscalationReason) -> List[EscalationTrigger]:
        """
        Match keywords for a specific escalation reason.

        Returns list of triggers with confidence scores based on keyword strength.
        """
        triggers = []
        keywords = self.keywords.get(reason, [])

        for keyword in keywords:
            if keyword.lower() in text:
                # Calculate confidence based on keyword importance
                base_confidence = 0.5

                # Higher confidence for stronger keywords
                strong_keywords = {
                    EscalationReason.LEGAL_REQUEST: ['lawyer', 'attorney', 'lawsuit', 'suing'],
                    EscalationReason.ANGER: ['furious', 'enraged', 'supervisor', 'manager'],
                    EscalationReason.COMPLAINT: ['formal complaint', 'written', 'documentation'],
                }

                if reason in strong_keywords and keyword in strong_keywords[reason]:
                    base_confidence = 0.75

                # Check for multiple occurrences
                occurrences = text.lower().count(keyword.lower())
                if occurrences > 1:
                    base_confidence += 0.1

                triggers.append(EscalationTrigger(
                    reason=reason,
                    confidence=min(base_confidence, 1.0),
                    matched_text=keyword,
                    pattern_type="keyword"
                ))

        return triggers

    def _deduplicate_triggers(self, triggers: List[EscalationTrigger]) -> List[EscalationTrigger]:
        """
        Remove duplicate triggers and keep the highest confidence version.
        """
        unique_triggers = {}

        for trigger in triggers:
            key = (trigger.reason, trigger.matched_text.lower())
            if key not in unique_triggers or trigger.confidence > unique_triggers[key].confidence:
                unique_triggers[key] = trigger

        return list(unique_triggers.values())

    def should_escalate(self, triggers: List[EscalationTrigger], threshold: float = 0.7) -> bool:
        """
        Determine if escalation should be triggered based on detected triggers.

        Args:
            triggers: List of detected triggers
            threshold: Minimum confidence threshold for escalation

        Returns:
            True if escalation should be triggered
        """
        if not triggers:
            return False

        # Escalate if any trigger meets the threshold
        high_confidence_triggers = [t for t in triggers if t.confidence >= threshold]

        # Always escalate for legal requests, even with lower confidence
        legal_triggers = [t for t in triggers if t.reason == EscalationReason.LEGAL_REQUEST]

        should_escalate = bool(high_confidence_triggers) or bool(legal_triggers)

        logger.info(
            "Escalation decision",
            should_escalate=should_escalate,
            high_confidence_count=len(high_confidence_triggers),
            legal_triggers_count=len(legal_triggers),
            threshold=threshold
        )

        return should_escalate

    def get_primary_trigger(self, triggers: List[EscalationTrigger]) -> Optional[EscalationTrigger]:
        """
        Get the primary (highest confidence) trigger from a list.
        """
        if not triggers:
            return None

        return max(triggers, key=lambda t: t.confidence)