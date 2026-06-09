from __future__ import annotations

from abc import ABC, abstractmethod

from .models import StrategyAgentSpec, StrategyEvaluationInput, StrategyEvaluationResult


class StrategyAgent(ABC):
    def __init__(self, spec: StrategyAgentSpec):
        self.spec = spec

    @abstractmethod
    def evaluate(self, evaluation_input: StrategyEvaluationInput) -> StrategyEvaluationResult:
        raise NotImplementedError
