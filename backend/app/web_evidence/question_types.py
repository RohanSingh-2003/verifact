"""Question-type taxonomy for Web Evidence routing."""

from __future__ import annotations

from enum import Enum


class QuestionType(str, Enum):
    GENERAL_FACT = "GENERAL_FACT"
    SCIENCE = "SCIENCE"
    GOVERNMENT_POLICY = "GOVERNMENT_POLICY"
    POLITICS = "POLITICS"
    CURRENT_EVENT = "CURRENT_EVENT"
    STATISTICS = "STATISTICS"
    TECHNOLOGY = "TECHNOLOGY"
    HISTORY = "HISTORY"
    MEDICINE_HEALTH = "MEDICINE_HEALTH"
    SPORTS = "SPORTS"
    BUSINESS_FINANCE = "BUSINESS_FINANCE"
    ACADEMIC_RESEARCH = "ACADEMIC_RESEARCH"
    FACT_CHECK = "FACT_CHECK"
    OTHER = "OTHER"


QUESTION_TYPE_LABELS: dict[QuestionType, str] = {
    QuestionType.GENERAL_FACT: "General fact",
    QuestionType.SCIENCE: "Science",
    QuestionType.GOVERNMENT_POLICY: "Government / policy",
    QuestionType.POLITICS: "Politics",
    QuestionType.CURRENT_EVENT: "Current event",
    QuestionType.STATISTICS: "Statistics",
    QuestionType.TECHNOLOGY: "Technology",
    QuestionType.HISTORY: "History",
    QuestionType.MEDICINE_HEALTH: "Medicine / health",
    QuestionType.SPORTS: "Sports",
    QuestionType.BUSINESS_FINANCE: "Business / finance",
    QuestionType.ACADEMIC_RESEARCH: "Academic research",
    QuestionType.FACT_CHECK: "Fact check",
    QuestionType.OTHER: "Other",
}
