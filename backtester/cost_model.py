from abc import ABC, abstractmethod

import pandas as pd


class CostModel(ABC):
    @abstractmethod
    def compute_costs(self, trades: list) -> dict[str, pd.Series]:
        ...


class FixedCostModel(CostModel):
    def __init__(self, fees: dict[str, float]):
        self._fees = fees

    def compute_costs(self, trades: list) -> dict[str, pd.Series]:
        leg_costs: dict[str, dict[str, float]] = {}

        for trade in trades:
            for structure in trade.structure_history:
                asset_class = (
                    structure.legs[0].asset_class if structure.legs else "equity"
                )
                bps = self._fees.get(asset_class, 0.0)

                for event in structure.event_log:
                    if event.get("cost_free", False):
                        continue

                    leg_id = event.get("cost_leg_id")
                    if not leg_id:
                        continue

                    notional = event.get("cost_exposure", {}).get("total_notional", 0.0)
                    cost = notional * bps / 10000.0
                    date = event["date"]

                    if leg_id not in leg_costs:
                        leg_costs[leg_id] = {}
                    leg_costs[leg_id][date] = leg_costs[leg_id].get(date, 0.0) + cost

        result: dict[str, pd.Series] = {}
        for leg_id, date_costs in leg_costs.items():
            series = pd.Series(date_costs)
            series.index.name = "date"
            series.name = "cost"
            result[leg_id] = series.sort_index()

        return result
