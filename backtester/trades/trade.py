class Trade:
    def __init__(
        self,
        trade_id: str,
        tags: list[str] | None = None,
    ):
        self.trade_id = trade_id
        self.tags = tags
        self.active_structures: list = []
        self.structure_history: list = []
        self.entry_date: str | None = None
        self.exit_date: str | None = None

    def add_structure(self, structure, date: str):
        if self.entry_date is None:
            self.entry_date = date

        self.active_structures.append(structure)
        self.structure_history.append(structure)
        structure.open(date)

    def add_to_structure(self, structure, date: str, additional_size: float):
        total_size = sum(leg.current_size for leg in structure.legs)
        for leg in structure.legs:
            scale = leg.current_size / total_size if total_size > 0 else 1.0 / len(structure.legs)
            new_total = leg.current_size + scale * additional_size
            leg.entry_price = (
                (leg.entry_price * leg.current_size + leg.current_price * scale * additional_size)
                / new_total
            )
        structure.add_size(date, additional_size)

    def unwind_structure(self, structure, date: str, fraction: float = 1.0):
        structure.unwind(date, fraction)
        if fraction == 1.0:
            self._remove_from_active(structure)
            if len(self.active_structures) == 0:
                self.exit_date = date

    def roll_structure(self, old_structure, new_structure, date: str):
        old_structure.roll(new_structure, date)

    def _remove_from_active(self, structure):
        self.active_structures = [s for s in self.active_structures if s is not structure]
