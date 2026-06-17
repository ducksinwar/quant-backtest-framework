from abc import ABC, abstractmethod

import pandas as pd


class BaseCostCalculator(ABC):
    @abstractmethod
    def compute_cost(
        self,
        leg_id: str,
        event: dict,
        data_feed=None,
    ) -> float:
        ...


class CostModel:
    def __init__(
        self,
        calculators: dict[str, BaseCostCalculator],
        data_feed=None,
    ):
        self._calculators = calculators
        self._data_feed = data_feed

    def compute_costs(self, trades: list) -> dict[str, pd.Series]:
        leg_costs: dict[str, dict[str, float]] = {}

        for trade in trades:
            for structure in trade.structure_history:
                for event in structure.event_log:
                    if event.get("cost_free", False):
                        continue

                    cost_exposures = event.get("cost_exposures", {})
                    if not cost_exposures:
                        continue

                    for leg_id in cost_exposures:
                        leg = self._find_leg(structure, leg_id)
                        if leg is None:
                            continue

                        asset_class = leg.asset_class
                        calculator = self._calculators.get(asset_class)
                        if calculator is None:
                            continue

                        cost = calculator.compute_cost(
                            leg_id, event, self._data_feed,
                        )
                        date = event["date"]

                        if leg_id not in leg_costs:
                            leg_costs[leg_id] = {}
                        leg_costs[leg_id][date] = (
                            leg_costs[leg_id].get(date, 0.0) + cost
                        )

        result: dict[str, pd.Series] = {}
        for leg_id, date_costs in leg_costs.items():
            series = pd.Series(date_costs)
            series.index.name = "date"
            series.name = "cost"
            result[leg_id] = series.sort_index()

        return result

    @staticmethod
    def _find_leg(structure, leg_id: str):
        for leg in structure.legs:
            if leg.leg_id == leg_id:
                return leg
        return None


class EquityCostCalculator(BaseCostCalculator):
    def __init__(self, bps: float):
        self._bps = bps

    def compute_cost(
        self,
        leg_id: str,
        event: dict,
        data_feed=None,
    ) -> float:
        per_unit = event["cost_exposures"][leg_id]
        notional_per_unit = per_unit["notional_per_unit"]
        transacted_notional = notional_per_unit * event["unit_size_change"]
        return transacted_notional * self._bps / 10000.0
