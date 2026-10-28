"""
Confidence threshold evaluation for classification results.

Thresholds are loaded from AppConfig and are intentionally documented as
empirically-tuned starting points, NOT calibrated probabilities.
"""
from __future__ import annotations

from app.database.models import ClassificationResult
from app.utils.config import AppConfig


class ConfidenceEvaluator:
    """
    Annotates a ClassificationResult with should_review based on the
    configured auto_confirm and suggest thresholds.
    """

    def evaluate(self, result: ClassificationResult) -> ClassificationResult:
        cfg = AppConfig.instance()
        auto_threshold: float = cfg.get("auto_confirm_threshold", 0.72)
        suggest_threshold: float = cfg.get("suggest_threshold", 0.45)

        if result.confidence >= auto_threshold:
            result.should_review = False

        elif result.confidence >= suggest_threshold:
            # Enough signal to suggest, but not enough to act automatically
            result.should_review = True

        else:
            # Below all thresholds — clear category so it goes to Review Queue
            result.should_review = True
            result.category_id = None
            result.category_path = None
            result.explanation = (
                f"Confidence ({result.confidence:.2f}) is below the suggestion "
                f"threshold ({suggest_threshold:.2f}). Manual review required."
            )

        return result
