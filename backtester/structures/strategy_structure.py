class StrategyStructure:
    def __init__(self, structure_id: str, legs: list, tags: list[str] | None = None):
        self.structure_id = structure_id
        self.legs = list(legs)
        self.tags = tags
        self.event_log: list[dict] = []
        self.original_entry_date: str | None = None

    def get_cost_exposure(self) -> dict:
        return {
            "total_notional": sum(leg.current_size for leg in self.legs)
        }

    def open(self, date: str):
        if self.original_entry_date is None:
            self.original_entry_date = date

        cost_exposure = self.get_cost_exposure()
        total_size = sum(leg.current_size for leg in self.legs)
        cost_leg_id = self.legs[0].leg_id if self.legs else None

        event = {
            "event_type": "open",
            "date": date,
            "unit_size_change": total_size,
            "cost_exposure": cost_exposure,
            "cost_leg_id": cost_leg_id,
            "cost_free": False,
        }
        self.event_log.append(event)

    def add_size(self, date: str, amount: float):
        total_size = sum(leg.current_size for leg in self.legs)
        cost_exposure = self.get_cost_exposure()
        cost_leg_id = self.legs[0].leg_id if self.legs else None

        for leg in self.legs:
            scale = leg.current_size / total_size if total_size > 0 else 1.0 / len(self.legs)
            leg.current_size += scale * amount

        event = {
            "event_type": "partial add",
            "date": date,
            "unit_size_change": amount,
            "cost_exposure": cost_exposure,
            "cost_leg_id": cost_leg_id,
            "cost_free": False,
        }
        self.event_log.append(event)

    def unwind(self, date: str, fraction: float = 1.0):
        total_size = sum(leg.current_size for leg in self.legs)
        amount_unwound = total_size * fraction
        cost_exposure = self.get_cost_exposure()
        cost_leg_id = self.legs[0].leg_id if self.legs else None

        for leg in self.legs:
            leg.current_size *= (1.0 - fraction)

        event_type = "full close" if fraction == 1.0 else "partial unwind"
        event = {
            "event_type": event_type,
            "date": date,
            "unit_size_change": amount_unwound,
            "cost_exposure": cost_exposure,
            "cost_leg_id": cost_leg_id,
            "cost_free": False,
        }
        self.event_log.append(event)

    def roll(self, new_structure: "StrategyStructure", date: str):
        raise NotImplementedError("Roll not implemented in Phase 1")
