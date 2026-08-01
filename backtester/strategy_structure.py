class StrategyStructure:
    def __init__(
        self,
        structure_id: str,
        legs: list,
        tags: list[str] | None = None,
    ):
        self.structure_id = structure_id
        self.legs = list(legs)
        self.tags = tags
        self.event_log: list[dict] = []
        self.original_entry_date: str | None = None

    def open(
        self,
        date: str,
        cost_exposures: dict[str, dict] | None = None,
    ):
        if self.original_entry_date is None:
            self.original_entry_date = date

        leg_size_changes = {
            leg.leg_id: leg.current_size for leg in self.legs
        }

        event = {
            "event_type": "open",
            "date": date,
            "leg_size_changes": leg_size_changes,
            "cost_exposures": cost_exposures or {},
            "cost_free": False,
        }
        self.event_log.append(event)

    def add_size(
        self,
        date: str,
        amount: float,
        cost_exposures: dict[str, dict] | None = None,
    ):
        total_size = sum(leg.current_size for leg in self.legs)
        leg_size_changes = {}

        for leg in self.legs:
            scale = (
                leg.current_size / total_size
                if total_size > 0
                else 1.0 / len(self.legs)
            )
            old_size = leg.current_size
            new_total = old_size + scale * amount
            leg.current_size = new_total
            leg_size_changes[leg.leg_id] = new_total - old_size
            leg.entry_price = (
                (leg.entry_price * old_size + leg.current_price * scale * amount)
                / new_total
            )

        event = {
            "event_type": "partial add",
            "date": date,
            "leg_size_changes": leg_size_changes,
            "cost_exposures": cost_exposures or {},
            "cost_free": False,
        }
        self.event_log.append(event)

    def unwind(
        self,
        date: str,
        fraction: float = 1.0,
        cost_exposures: dict[str, dict] | None = None,
    ):
        if not (0.0 < fraction <= 1.0):
            raise ValueError(
                f"unwind fraction must be in (0, 1], got {fraction}"
            )

        total_size = sum(leg.current_size for leg in self.legs)
        leg_size_changes = {
            leg.leg_id: leg.current_size * fraction
            for leg in self.legs
        }
        for leg in self.legs:
            leg.current_size *= 1.0 - fraction

        event_type = (
            "full close" if abs(fraction - 1.0) < 1e-12 else "partial unwind"
        )
        event = {
            "event_type": event_type,
            "date": date,
            "leg_size_changes": leg_size_changes,
            "cost_exposures": cost_exposures or {},
            "cost_free": False,
        }
        self.event_log.append(event)

    def roll(
        self, new_structure: "StrategyStructure", date: str,
        cost_exposures: dict[str, dict] | None = None,
    ):
        raise NotImplementedError("Roll not implemented in Phase 1")

    def __repr__(self) -> str:
        return f"StrategyStructure(id={self.structure_id!r}, legs={len(self.legs)})"
