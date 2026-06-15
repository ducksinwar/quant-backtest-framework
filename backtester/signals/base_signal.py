from __future__ import annotations

from abc import ABC, abstractmethod


class BaseSignal(ABC):
    requires_portfolio_state: bool = False
    requires_trade_history: bool = False

    @abstractmethod
    def generate_signals(
        self,
        current_date: str,
        portfolio_state: object | None = None,
        trade_history_snapshot: tuple | None = None,
    ) -> list[dict]:
        ...
