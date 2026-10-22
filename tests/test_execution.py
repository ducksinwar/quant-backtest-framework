import warnings

import pytest

from backtester.backtest_engine import AssetClassConfig
from backtester.execution import (
    ExecutionBackend,
    ExecutionContext,
    ExecutionOutcome,
    LegFill,
    SimulatedExecution,
    leg_dict_from_order_leg,
    write_cost_exposures,
)
from backtester.execution_log import ExecutionLog
from backtester.instruments import Contract, LegState
from backtester.orders import Order, OrderGroup, OrderOutcome, OrderLeg, OrderSide
from backtester.strategy_structure import StrategyStructure
from backtester.trade import Trade


class _StubPricer:
    def __init__(self, prices, exposures=None):
        self.prices = prices
        self.exposures = exposures
        self.cost_calls = []

    def resolve_instrument(self, leg_dict, date):
        return Contract(
            ticker=leg_dict.get("ticker", ""),
            asset_class=leg_dict.get("asset_class", "equity"),
        )

    def price(self, contract, date):
        return self.prices.get(contract.ticker)

    def compute_cost_exposure(self, contract, date):
        self.cost_calls.append((contract.ticker, date))
        if self.exposures is not None:
            return self.exposures.get(contract.ticker)
        price = self.prices.get(contract.ticker)
        return None if price is None else {"notional_per_unit": price}


def _ctx(pricer, active_trades=(), date="2024-01-02"):
    return ExecutionContext(
        active_trades=tuple(active_trades),
        asset_class_configs={"equity": AssetClassConfig(pricer=pricer)},
        date=date,
        action_group_id="i1",
        strategy_id="s",
    )


def _leg(ticker, size, asset_class="equity"):
    return OrderLeg(
        ticker=ticker,
        side=OrderSide.BUY if size >= 0 else OrderSide.SELL,
        quantity=abs(size),
        asset_class=asset_class,
    )


def _new_group(legs, *, order_id="o1", action_id="a1", structure_id=None,
               trade_id=None):
    return OrderGroup(
        orders=(
            Order(
                action_id=action_id,
                order_id=order_id,
                legs=tuple(legs),
                structure_id=structure_id,
                trade_id=trade_id,
            ),
        )
    )


def _trade(ticker, size, structure_id="s1"):
    leg = LegState(
        contract=Contract(ticker=ticker, asset_class="equity"),
        leg_id="L1", current_size=size,
    )
    structure = StrategyStructure(structure_id=structure_id, legs=[leg])
    trade = Trade(trade_id="t1")
    trade.active_structures = [structure]
    trade.structure_history = [structure]
    return trade


def _target_group(trade, ticker, size, *, structure_id="s1", date="2024-01-03"):
    return _new_group(
        [_leg(ticker, size)],
        structure_id=structure_id,
        trade_id=trade.trade_id,
    )


class TestExecutionBackendInterface:
    def test_is_abstract(self):
        with pytest.raises(TypeError):
            ExecutionBackend()

    def test_simulated_execution_is_a_backend(self):
        assert isinstance(SimulatedExecution(), ExecutionBackend)


class TestSimulatedExecution:
    def test_missing_data_blocks(self):
        p = _StubPricer({})  # no price -> None
        (rep,) = SimulatedExecution().execute_group(
            _new_group([_leg("SPY", 5)]), _ctx(p)
        )
        assert rep.outcome is ExecutionOutcome.BLOCKED
        assert rep.blocked_code == "DATA_MISSING"
        assert rep.fills == () and rep.fill_time is None and rep.fees is None
        assert rep.probe_status is OrderOutcome.BLOCKED
        assert rep.blocked_by == "DATA_MISSING"

    def test_fill_has_per_leg_details_and_fill_time(self):
        p = _StubPricer({"SPY": 100.0})
        (rep,) = SimulatedExecution().execute_group(
            _new_group([_leg("SPY", 5)]), _ctx(p)
        )
        assert rep.outcome is ExecutionOutcome.FILLED
        assert rep.probe_status is OrderOutcome.FILLED
        assert rep.blocked_by is None
        assert rep.fill_time == "2024-01-02"
        assert rep.fills == (LegFill("SPY", 5.0, 100.0),)

    def test_fill_carries_lineage(self):
        p = _StubPricer({"SPY": 100.0})
        group = _new_group([_leg("SPY", 5)], order_id="o9", action_id="a9")
        (rep,) = SimulatedExecution().execute_group(group, _ctx(p))
        assert rep.order_id == "o9"
        assert rep.action_id == "a9"
        assert rep.order_group_id == group.order_group_id
        assert rep.action_group_id == "i1"
        assert rep.strategy_id == "s"
        assert rep.date == "2024-01-02"

    def test_multi_leg_fill_preserves_sign(self):
        p = _StubPricer({"SPY": 10.0, "QQQ": 20.0})
        (rep,) = SimulatedExecution().execute_group(
            _new_group([_leg("SPY", 5), _leg("QQQ", -3)]), _ctx(p)
        )
        assert [(f.ticker, f.size, f.price) for f in rep.fills] == [
            ("SPY", 5.0, 10.0), ("QQQ", -3.0, 20.0)]

    def test_execute_group_does_not_mutate_the_context(self):
        p = _StubPricer({"SPY": 100.0})
        ctx = _ctx(p)
        before = ctx.active_trades
        SimulatedExecution().execute_group(
            _new_group([_leg("SPY", 5)]), ctx
        )
        assert ctx.active_trades is before

    def test_missing_asset_class_field_raises(self):
        p = _StubPricer({})
        group = _new_group([
            OrderLeg(ticker="SPY", side=OrderSide.BUY, quantity=5)
        ])
        with pytest.raises(ValueError, match="asset_class"):
            SimulatedExecution().execute_group(group, _ctx(p))

    def test_unknown_asset_class_raises(self):
        p = _StubPricer({})
        group = _new_group([_leg("SPY", 5, asset_class="crypto")])
        with pytest.raises(ValueError, match="Unknown asset class"):
            SimulatedExecution().execute_group(group, _ctx(p))

    def test_pricer_is_called_once_per_leg_on_a_fill(self):
        p = _StubPricer({"SPY": 100.0})
        calls = []
        orig = p.price

        def counting(contract, date):
            calls.append((contract.ticker, date))
            return orig(contract, date)

        p.price = counting
        SimulatedExecution().execute_group(
            _new_group([_leg("SPY", 5)]), _ctx(p)
        )
        assert calls == [("SPY", "2024-01-02")]


class TestGroupAtomicity:
    def test_one_failure_blocks_the_whole_group(self):
        p = _StubPricer({"SPY": 100.0})  # QQQ has no price
        group = OrderGroup(orders=(
            Order(action_id="a1", order_id="o_good",
                  legs=(_leg("SPY", 5),)),
            Order(action_id="a1", order_id="o_bad",
                  legs=(_leg("QQQ", 5),)),
        ))
        with pytest.warns(UserWarning, match="data not available"):
            reports = SimulatedExecution().execute_group(group, _ctx(p))

        assert len(reports) == 2
        good, bad = reports
        assert good.outcome is ExecutionOutcome.BLOCKED
        assert good.probe_status is OrderOutcome.FILLED
        assert good.blocked_by == "GROUP_ATOMICITY:o_bad"
        assert good.blocked_code == "GROUP_ATOMICITY"
        assert good.fills == ()
        assert bad.outcome is ExecutionOutcome.BLOCKED
        assert bad.probe_status is OrderOutcome.BLOCKED
        assert bad.blocked_by == "DATA_MISSING"
        assert bad.blocked_code == "DATA_MISSING"

    def test_all_passing_probes_fill_every_order(self):
        p = _StubPricer({"SPY": 100.0, "QQQ": 20.0})
        group = OrderGroup(orders=(
            Order(action_id="a1", order_id="o1",
                  legs=(_leg("SPY", 5),)),
            Order(action_id="a1", order_id="o2",
                  legs=(_leg("QQQ", 3),)),
        ))
        reports = SimulatedExecution().execute_group(group, _ctx(p))
        assert [r.outcome for r in reports] == [
            ExecutionOutcome.FILLED, ExecutionOutcome.FILLED
        ]
        assert [r.fills for r in reports] == [
            (LegFill("SPY", 5.0, 100.0),),
            (LegFill("QQQ", 3.0, 20.0),),
        ]


class TestSimulatedExecutionBlockedUnwind:
    def test_blocked_unwind_leaves_the_book_unchanged(self):
        p = _StubPricer({})  # price None -> block
        trade = _trade("SPY", 100.0)
        group = _target_group(trade, "SPY", -100)
        # _trade always attaches one populated structure, so the [0].legs[0]
        # index below is guaranteed valid.
        before_history = list(trade.structure_history)
        before_active = list(trade.active_structures)
        before_size = trade.structure_history[0].legs[0].current_size
        before_exit = trade.exit_date

        (rep,) = SimulatedExecution().execute_group(
            group, _ctx(p, [trade], date="2024-01-03")
        )
        log = ExecutionLog()
        rec = log.append(rep)

        assert rep.outcome is ExecutionOutcome.BLOCKED
        assert rep.blocked_code == "DATA_MISSING"
        assert len(log) == 1
        assert rec.status == "BLOCKED" and rec.fill_id is None
        # the backend never mutates, and the engine commits only on FILLED
        assert list(trade.structure_history) == before_history
        assert list(trade.active_structures) == before_active
        assert trade.structure_history[0].legs[0].current_size == before_size
        assert trade.exit_date == before_exit
        assert trade.structure_history[0].legs[0].current_size == 100.0
        assert trade.exit_date is None


class TestSimulatedExecutionUnwindSign:
    def test_closing_a_long_fills_negative(self):
        p = _StubPricer({"SPY": 100.0})
        trade = _trade("SPY", 100.0)
        (rep,) = SimulatedExecution().execute_group(
            _target_group(trade, "SPY", -100),
            _ctx(p, [trade], date="2024-01-03"),
        )
        assert rep.outcome is ExecutionOutcome.FILLED
        assert rep.fills == (LegFill("SPY", -100.0, 100.0),)

    def test_closing_a_short_fills_positive(self):
        p = _StubPricer({"SPY": 100.0})
        trade = _trade("SPY", -100.0)
        (rep,) = SimulatedExecution().execute_group(
            _target_group(trade, "SPY", 100),
            _ctx(p, [trade], date="2024-01-03"),
        )
        assert rep.outcome is ExecutionOutcome.FILLED
        assert rep.fills == (LegFill("SPY", 100.0, 100.0),)

    def test_whole_book_unwind_fans_out_one_order_per_structure(self):
        p = _StubPricer({"SPY": 100.0, "QQQ": 50.0})
        t_long = _trade("SPY", 100.0, structure_id="s1")
        t_two = _trade("QQQ", -50.0, structure_id="s2")
        t_two.trade_id = "t2"
        group = OrderGroup(orders=(
            Order(action_id="a1", order_id="o1",
                  legs=(_leg("SPY", -100),),
                  structure_id="s1", trade_id="t1"),
            Order(action_id="a1", order_id="o2",
                  legs=(_leg("QQQ", 50),),
                  structure_id="s2", trade_id="t2"),
        ))
        reports = SimulatedExecution().execute_group(
            group, _ctx(p, [t_long, t_two], date="2024-01-03")
        )
        assert [f.size for r in reports for f in r.fills] == [-100.0, 50.0]


class TestLegDictMapping:
    def test_signed_size_and_extras(self):
        leg = OrderLeg(
            ticker="SPX",
            side=OrderSide.SELL,
            quantity=5,
            asset_class="equity_option",
            multiplier=100,
            currency="USD",
            cost_leg=True,
            tags=("hedge",),
            params=(("strike", 5000), ("expiry", "2025-12-19")),
        )
        assert leg_dict_from_order_leg(leg) == {
            "ticker": "SPX",
            "size": -5,
            "asset_class": "equity_option",
            "multiplier": 100,
            "currency": "USD",
            "cost_leg": True,
            "tags": ["hedge"],
            "strike": 5000,
            "expiry": "2025-12-19",
        }

    def test_absent_optionals_are_not_emitted(self):
        assert leg_dict_from_order_leg(_leg("SPY", 5)) == {
            "ticker": "SPY",
            "size": 5,
            "asset_class": "equity",
        }


class TestWriteCostExposures:
    def _structure(self, ticker, size, cost_leg=False):
        return StrategyStructure(
            structure_id="s1",
            legs=[LegState(
                contract=Contract(ticker=ticker, asset_class="equity"),
                leg_id="L1", current_size=size, cost_leg=cost_leg,
            )],
        )

    def test_uses_pricer_per_unit_not_price_times_size(self):
        p = _StubPricer({"SPY": 5.0})
        out = write_cost_exposures(self._structure("SPY", 100.0),
                                   "2024-01-02",
                                   {"equity": AssetClassConfig(pricer=p)})
        # per-unit metric is the pricer's, never price*size (500)
        assert out == {"L1": {"notional_per_unit": 5.0}}
        assert p.cost_calls == [("SPY", "2024-01-02")]

    def test_warns_when_pricer_returns_none_for_marked_cost_leg(self):
        p = _StubPricer({})
        with pytest.warns(UserWarning, match="compute_cost_exposure returned None"):
            out = write_cost_exposures(
                self._structure("SPY", 100.0, cost_leg=True),
                "2024-01-02",
                {"equity": AssetClassConfig(pricer=p)},
            )
        assert out == {}

    def test_fallback_does_not_warn_when_unmarked(self):
        p = _StubPricer({})
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # any warning would fail here
            out = write_cost_exposures(
                self._structure("SPY", 100.0, cost_leg=False),
                "2024-01-02",
                {"equity": AssetClassConfig(pricer=p)},
            )
        # The unmarked single-leg fallback finds None and stays silent; this
        # pins the pre-existing 5a behaviour explicitly.
        assert out == {}
