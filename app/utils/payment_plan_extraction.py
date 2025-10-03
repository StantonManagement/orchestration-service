"""
Payment plan extraction utility for detecting payment arrangements in tenant messages.

This module provides pattern matching and extraction logic for identifying
structured payment plans in both tenant messages and AI responses.
"""

import re
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ConfidenceLevel(Enum):
    """Confidence levels for extracted payment plans."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ExtractedPaymentPlan:
    """Structured representation of an extracted payment plan."""

    weekly_amount: Optional[Decimal] = None
    duration_weeks: Optional[int] = None
    start_date: Optional[datetime] = None
    confidence: ConfidenceLevel = ConfidenceLevel.LOW
    confidence_score: float = 0.0
    extraction_patterns: List[str] = None
    raw_text: str = ""

    def __post_init__(self):
        if self.extraction_patterns is None:
            self.extraction_patterns = []
            # Set confidence_score based on confidence level
            if self.confidence == ConfidenceLevel.HIGH:
                self.confidence_score = 0.9
            elif self.confidence == ConfidenceLevel.MEDIUM:
                self.confidence_score = 0.6
            else:
                self.confidence_score = 0.3

    def is_complete(self) -> bool:
        """Check if all required fields are present."""
        return self.weekly_amount is not None and self.duration_weeks is not None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "weekly_amount": float(self.weekly_amount) if self.weekly_amount else None,
            "duration_weeks": self.duration_weeks,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "confidence": self.confidence.value,
            "extraction_patterns": self.extraction_patterns,
            "raw_text": self.raw_text,
            "is_complete": self.is_complete(),
        }


class PaymentPlanExtractor:
    """Extracts payment plans from text using pattern matching."""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.PaymentPlanExtractor")

        # Payment amount patterns
        self.amount_patterns = [
            r"\$(\d+(?:\.\d{2})?)\s*(?:per|\/|a)\s*week",  # $200 per week
            r"\$(\d+(?:\.\d{2})?)\s*(?:weekly|week)",  # $200 weekly
            r"(\d+(?:\.\d{2})?)\s*dollars?\s*(?:per|\/|a)\s*week",  # 200 dollars per week
            r"pay\s*\$(\d+(?:\.\d{2})?)\s*(?:per|\/|a)\s*week",  # pay $200 per week
            r"\$(\d+(?:\.\d{2})?)\s*every\s*week",  # $200 every week
            r"(\d+(?:\.\d{2})?)\s*bucks\s*(?:per|\/|a)\s*week",  # 50 bucks per week
            r"\$(\d+(?:\.\d{2})?)\s*\/\s*week",  # $200/week
            r"\$(\d+(?:\.\d{2})?)\s*each\s*week",  # $200 each week
            r"monthly\s+payments?\s+of\s+\$(\d+(?:\.\d{2})?)",  # monthly payments of $200
            r"\$(\d+(?:\.\d{2})?)\s*monthly",  # $200 monthly
        ]

        # Duration patterns
        self.duration_patterns = [
            r"(\d+)\s*(?:weeks?|w)",  # 8 weeks, 8 w
            r"for\s+(\d+)\s*(?:weeks?|w)",  # for 8 weeks
            r"(\d+)\s*(?:weeks?|w)\s*(?:duration|period)",  # 8 weeks duration
            r"next\s+(\d+)\s*(?:weeks?|w)",  # next 8 weeks
            r"(\d+)\s*months?",  # 2 months (convert to weeks)
        ]

        # Start date patterns
        self.start_date_patterns = [
            r"starting\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
            r"next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
            r"beginning\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
            r"start\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
            r"this\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
            r"on\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
            r"tomorrow",  # Special case for tomorrow
        ]

        # Combined patterns for high confidence
        self.combined_patterns = [
            r"\$(\d+(?:\.\d{2})?)\s*(?:per|\/|a)\s*week\s*(?:for|over)\s+(\d+)\s*(?:weeks?|w)",
            r"pay\s*\$(\d+(?:\.\d{2})?)\s*(?:per|\/|a)\s*week\s*for\s+(\d+)\s*(?:weeks?|w)",
            r"\$(\d+(?:\.\d{2})?)\s*weekly\s*for\s+(\d+)\s*(?:weeks?|w)",
            r"(\d+)\s*(?:weeks?|w)\s*(?:at|@)\s*\$(\d+(?:\.\d{2})?)\s*(?:per|\/|a)\s*week",
            r"(\d+(?:\.\d{2})?)\s*dollars?\s*weekly\s*for\s+(\d+)\s*(?:weeks?|w)",  # 75 dollars weekly for 5 weeks
            r"(\d+(?:\.\d{2})?)\s*dollars?\s*(?:per|\/|a)\s*week\s*for\s+(\d+)\s*(?:weeks?|w)",  # 75 dollars per week for 5 weeks
        ]

    def extract_payment_plan(self, text: str) -> Optional[ExtractedPaymentPlan]:
        """
        Extract payment plan from text.

        Args:
            text: The message text to analyze

        Returns:
            ExtractedPaymentPlan object with extracted information, or None if no plan found
        """
        if text is None:
            raise AttributeError("text cannot be None")

        self.logger.debug(f"Extracting payment plan from text: {text[:100]}...")

        plan = ExtractedPaymentPlan(raw_text=text)

        # Try combined patterns first (highest confidence)
        for i, pattern in enumerate(self.combined_patterns):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                self.logger.debug(f"Combined pattern matched: {pattern}")

                # Different confidence scores based on pattern type
                # $ sign patterns (more structured) get higher confidence
                if r'\$' in pattern:
                    plan.confidence_score = 0.8
                else:
                    plan.confidence_score = 0.6  # Lower confidence for "dollars" patterns

                plan.confidence = ConfidenceLevel.MEDIUM if plan.confidence_score < 0.8 else ConfidenceLevel.HIGH
                plan.extraction_patterns.append("combined:amount_and_duration")
                plan.extraction_patterns.append("amount:combined")
                plan.extraction_patterns.append("duration:combined")

                # Extract amount and duration from combined pattern
                groups = match.groups()
                if len(groups) == 2:
                    # Determine which group is amount vs duration
                    if self._looks_like_amount(groups[0]):
                        plan.weekly_amount = Decimal(groups[0])
                        plan.duration_weeks = self._parse_duration(groups[1])
                    else:
                        plan.weekly_amount = Decimal(groups[1])
                        plan.duration_weeks = self._parse_duration(groups[0])
                break

        # If no combined pattern match, try individual patterns
        if plan.weekly_amount is None:
            plan.weekly_amount = self._extract_amount(text)
            if plan.weekly_amount:
                plan.extraction_patterns.append("amount:individual")

        if plan.duration_weeks is None:
            plan.duration_weeks = self._extract_duration(text)
            if plan.duration_weeks:
                plan.extraction_patterns.append("duration:individual")

        # Extract start date
        plan.start_date = self._extract_start_date(text)
        if plan.start_date:
            plan.extraction_patterns.append("start_date")

        # Adjust confidence based on completeness (only if not already set by combined patterns)
        if plan.weekly_amount and plan.duration_weeks:
            # Only adjust if confidence wasn't already set by combined patterns
            if "combined:" not in "".join(plan.extraction_patterns):
                # Base confidence for having both amount and duration
                plan.confidence = ConfidenceLevel.MEDIUM
                plan.confidence_score = 0.7

            # Extra confidence for having start date
            if plan.start_date:
                plan.confidence = ConfidenceLevel.HIGH
                plan.confidence_score = 0.9
        elif plan.weekly_amount or plan.duration_weeks:
            if plan.confidence == ConfidenceLevel.LOW:
                plan.confidence = ConfidenceLevel.MEDIUM
                plan.confidence_score = 0.6

        # Business rule validation
        if plan.weekly_amount and plan.weekly_amount < 25:
            self.logger.debug(f"Weekly amount ${plan.weekly_amount} below minimum $25")
            return None

        if plan.duration_weeks and plan.duration_weeks > 12:
            self.logger.debug(f"Duration {plan.duration_weeks} weeks exceeds maximum 12 weeks")
            return None

        # Return None if no valid payment plan found
        if not plan.is_complete():
            self.logger.debug("No complete payment plan found in text")
            return None

        self.logger.info(f"Extracted payment plan: {plan.to_dict()}")
        return plan

    def extract_from_ai_response(self, ai_response: str) -> Optional[ExtractedPaymentPlan]:
        """
        Extract payment plan from AI response.

        Args:
            ai_response: The AI response text to analyze

        Returns:
            ExtractedPaymentPlan object if payment plan found, None otherwise
        """
        self.logger.debug(f"Extracting payment plan from AI response: {ai_response[:100]}...")

        # Check for structured AI response format first
        structured_pattern = r"PAYMENT_PLAN:\s*weekly=(\d+(?:\.\d{2})?),\s*weeks=(\d+)"
        match = re.search(structured_pattern, ai_response, re.IGNORECASE)

        if match:
            self.logger.debug("Structured AI payment plan pattern found")
            plan = ExtractedPaymentPlan(
                weekly_amount=Decimal(match.group(1)),
                duration_weeks=int(match.group(2)),
                confidence=ConfidenceLevel.HIGH,
                confidence_score=0.95,  # Very high confidence for structured AI
                raw_text=ai_response
            )
            plan.extraction_patterns.append("ai_structured")

            # Try to extract start date from AI response as well
            start_date = self._extract_start_date(ai_response)
            if start_date:
                plan.start_date = start_date
                plan.extraction_patterns.append("ai_start_date")

            self.logger.info(f"Extracted structured AI payment plan: {plan.to_dict()}")
            return plan

        # If no structured pattern, try regular extraction
        plan = self.extract_payment_plan(ai_response)
        if plan:
            # Boost confidence for AI responses that have payment plans
            plan.confidence_score = min(plan.confidence_score + 0.1, 1.0)
            if plan.confidence_score >= 0.8:
                plan.confidence = ConfidenceLevel.HIGH
            plan.extraction_patterns.append("ai_unstructured")
            self.logger.info(f"Extracted unstructured AI payment plan: {plan.to_dict()}")

        return plan

    def _extract_amount(self, text: str) -> Optional[Decimal]:
        """Extract payment amount from text."""
        for pattern in self.amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1)
                try:
                    amount = Decimal(amount_str)
                    self.logger.debug(f"Extracted amount: ${amount} from pattern: {pattern}")
                    return amount
                except Exception as e:
                    self.logger.warning(f"Failed to parse amount '{amount_str}': {e}")
        return None

    def _extract_duration(self, text: str) -> Optional[int]:
        """Extract duration in weeks from text."""
        for pattern in self.duration_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                duration_str = match.group(0)  # Use the full match, not just group(1)
                weeks = self._parse_duration(duration_str)
                if weeks:
                    self.logger.debug(f"Extracted duration: {weeks} weeks from pattern: {pattern}")
                    return weeks
        return None

    def _extract_start_date(self, text: str) -> Optional[datetime]:
        """Extract start date from text."""
        for pattern in self.start_date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if "tomorrow" in pattern.lower():
                    start_date = datetime.now() + timedelta(days=1)
                    self.logger.debug(f"Extracted start date (tomorrow): {start_date} from pattern: {pattern}")
                    return start_date
                else:
                    day_name = match.group(1).lower()
                    start_date = self._calculate_next_day(day_name)
                    if start_date:
                        self.logger.debug(f"Extracted start date: {start_date} from pattern: {pattern}")
                        return start_date
        return None

    def _parse_duration(self, duration_str: str) -> Optional[int]:
        """Parse duration string and convert to weeks."""
        try:
            # Extract the number from the duration string
            number_match = re.search(r'(\d+)', duration_str)
            if not number_match:
                return None

            duration = int(number_match.group(1))

            # Check if it's specified in months
            if "month" in duration_str.lower():
                return duration * 4  # Approximate months as 4 weeks

            return duration
        except ValueError:
            return None

    def _calculate_next_day(self, day_name: str) -> Optional[datetime]:
        """Calculate the next occurrence of a specific day."""
        today = datetime.now()
        days_of_week = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }

        if day_name not in days_of_week:
            return None

        target_day = days_of_week[day_name]
        current_day = today.weekday()

        # Calculate days to add
        days_ahead = target_day - current_day
        if days_ahead <= 0:  # Target day already passed this week
            days_ahead += 7

        return today + timedelta(days=days_ahead)

    def _looks_like_amount(self, value: str) -> bool:
        """Determine if a string looks like a monetary amount."""
        try:
            amount = float(value)
            return 10 <= amount <= 10000  # Reasonable payment range
        except ValueError:
            return False
