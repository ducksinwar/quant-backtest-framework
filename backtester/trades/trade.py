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

    def add_structure(
        self,
        structure,
        date: str,
        cost_exposures: dict[str, dict] | None = None,
    ):
        if self.entry_date is None:
            self.entry_date = date

        self.active_structures.append(structure)
        self.structure_history.append(structure)
        structure.open(date, cost_exposures)

    def add_to_structure(
        self,
        structure,
        date: str,
        additional_size: float,
        cost_exposures: dict[str, dict] | None = None,
    ):
        structure.add_size(date, additional_size, cost_exposures)

    def unwind_structure(
        self,
        structure,
        date: str,
        fraction: float = 1.0,
        cost_exposures: dict[str, dict] | None = None,
    ):
        structure.unwind(date, fraction, cost_exposures)
        if fraction == 1.0:
            self._remove_from_active(structure)
            if len(self.active_structures) == 0:
                self.exit_date = date

    def roll_structure(
        self,
        old_structure,
        new_structure,
        date: str,
        cost_exposures: dict[str, dict] | None = None,
    ):
        old_structure.roll(new_structure, date, cost_exposures)

    def _remove_from_active(self, structure):
        self.active_structures = [
            s for s in self.active_structures if s is not structure
        ]

    def __repr__(self) -> str:
        return f"Trade(id={self.trade_id!r}, entry={self.entry_date!r})"
