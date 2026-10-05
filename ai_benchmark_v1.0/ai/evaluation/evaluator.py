# app/ai/evaluation/evaluator.py
# Re-export NLPEvaluator from evaluation.evaluator to eliminate code duplication.

from evaluation.evaluator import NLPEvaluator

__all__ = ["NLPEvaluator"]
