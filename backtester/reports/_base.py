from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from backtester.summary import Summary


class BaseReport(ABC):
    @abstractmethod
    def build(
        self,
        summary: Summary,
        trades: list,
        leg_data: list[dict],
        report_config: dict,
        fx_rates: dict | None,
        output_name: str,
    ) -> dict[str, pd.DataFrame]:
        ...
