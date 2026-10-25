"""Position books: the T-1 positions a strategy and the converter may read.

:class:`PositionBook` wraps the snapshot data (``PortfolioState`` /
``TradeRecord``) without changing it.  It is read-only and holds no live
``Trade`` / ``LegState`` references: a signal can inspect its positions but
cannot corrupt engine state through them.

The structure -> trade registry the converter validates structure-scoped
actions against is derived from the same snapshot, so the signal and the
validator provably look at one identical view of the book.

The converter reads the signed ``LegSnapshot.size`` of a structure's anchor leg
(``legs[0]``) for its partial-modification bounds.
"""

from __future__ import annotations

from dataclasses import dataclass

from backtester.snapshots import LegSnapshot, PortfolioState, TradeRecord


@dataclass(frozen=True)
class Holding:
    """One leg the book holds, with its structural address."""

    trade_id: str
    structure_id: str
    leg: LegSnapshot


@dataclass(frozen=True)
class PositionBook:
    """The T-1 snapshot (active positions) plus the trade history."""

    portfolio_state: PortfolioState | None = None
    trade_history: tuple[TradeRecord, ...] = ()

    @property
    def trades(self) -> tuple:
        """The active positions as of T-1 (``()`` before the first day)."""
        if self.portfolio_state is None:
            return ()
        return self.portfolio_state.trades

    def find_holding(self, ticker: str) -> Holding | None:
        """First leg holding *ticker*, or ``None``.

        The enumeration is trades -> structures -> legs, i.e. exactly the order
        ``PortfolioState`` was built in (``active_trades`` insertion order), so
        "first match" means the same trade the ticker lookup found.

        The book is global -- one signal per run -- so a first match is
        unambiguous.  Under multi-strategy runs this same call would return
        *any* strategy's holding; per-strategy books are a future design item,
        recorded in the worklog ledger rather than guessed at here.
        """
        for trade in self.trades:
            for structure in trade.structures:
                for leg in structure.legs:
                    if leg.ticker == ticker:
                        return Holding(
                            trade_id=trade.trade_id,
                            structure_id=structure.structure_id,
                            leg=leg,
                        )
        return None

    def is_in_position(self, ticker: str) -> bool:
        return self.find_holding(ticker) is not None

    def structure_to_trade(self) -> dict[str, str]:
        """Active ``structure_id -> trade_id`` registry.

        Raises when any structure does not map to exactly one active trade:
        an ambiguous or dangling address must fail loudly, never be guessed.
        """
        owners: dict[str, set[str]] = {}
        for trade in self.trades:
            for structure in trade.structures:
                owners.setdefault(structure.structure_id, set()).add(
                    trade.trade_id
                )

        ambiguous = {
            structure_id: sorted(trade_ids)
            for structure_id, trade_ids in owners.items()
            if len(trade_ids) != 1
        }
        if ambiguous:
            raise ValueError(
                f"structure id(s) {sorted(ambiguous)} do not map to exactly "
                f"one active trade: {ambiguous}"
            )
        return {
            structure_id: next(iter(trade_ids))
            for structure_id, trade_ids in owners.items()
        }

    def trade_id_for_structure(self, structure_id: str) -> str:
        """The single active trade holding *structure_id* (fail-loud)."""
        registry = self.structure_to_trade()
        try:
            return registry[structure_id]
        except KeyError:
            raise ValueError(
                f"no active trade holds structure {structure_id!r} in the "
                f"T-1 position book; refusing to guess a trade_id"
            ) from None


class PositionBooks:
    """Per-day access to position books.

    A run holds a single, global book: a run has one signal and positions are
    not partitioned per strategy, so :meth:`full` returns that one book -- the
    *same object* every time.  It is named for the risk plugins that need the
    whole book; the signal receives the same book object directly.
    Per-strategy partitioning is deferred with multi-strategy runs, and any
    strategy tagging happens at the §10 ingestion boundary (``StrategyRun``).
    """

    def __init__(
        self,
        portfolio_state: PortfolioState | None = None,
        trade_history: tuple[TradeRecord, ...] = (),
    ):
        self._book = PositionBook(
            portfolio_state=portfolio_state,
            trade_history=tuple(trade_history),
        )

    def full(self) -> PositionBook:
        return self._book
