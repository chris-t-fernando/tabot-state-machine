from broker_api import AlpacaAPI, BackTestAPI, ITradeAPI
from parameter_store import Ssm
from strategies.macd import (
    MacdStateEnteringPosition,
    MacdStateStoppingLoss,
    MacdStateTakingProfit,
    MacdStateWaiting,
    MacdStateTerminated,
    MacdTA,
    MacdInstanceTemplate,
)

from symbol import Symbol

from core import (
    ControllerConfig,
    PlayController,
    StateEnteringPosition,
    StateWaiting,
    StateTerminated,
    StateStoppingLoss,
    StateTakingProfit,
)
from core import TimeManager
import btalib
from time import sleep
from typing import Set

import logging

stream_handler = logging.StreamHandler()
formatter = logging.Formatter(
    "%(asctime)s - %(name)16s - %(levelname)8s - %(funcName)15s - %(message)s"
)
stream_handler.setFormatter(formatter)
root_logger = logging.getLogger()
root_logger.setLevel(logging.CRITICAL)
root_logger.addHandler(stream_handler)

level = 9
log = logging.getLogger(__name__)
log.setLevel(level)
logging.getLogger("core.abstracts").setLevel(level)
logging.getLogger("strategies.macd").setLevel(level)


# TODO what's the plan for this object? how does it differ to SymbolGroup?
class Orchestrator:
    def __init__(self) -> None:
        pass

    def add_template(self, template):
        ...


class SymbolGroup:
    def __init__(
        self,
        name: str,
        time_manager,
        play_config: ControllerConfig = None,
        broker: ITradeAPI = None,
        back_testing: bool = False,
    ) -> None:
        self._symbols: Set[Symbol]
        self._play_controllers: Set[PlayController]
        self.active_play_controllers: Set[PlayController]

        self._symbols = set()
        self._ta_algos = set()
        self.started = False
        self._play_controllers = set()
        self.name = name
        self.back_testing = back_testing
        self._tm = time_manager

        if play_config:
            self.play_config = play_config

        if broker:
            self.broker = broker

    def __repr__(self) -> str:
        return f"{self.name} ({len(self._symbols)} symbols)"

    def register_ta(self, ta_algo):
        self._ta_algos.add(ta_algo)
        self._apply_ta()

    def add_symbol(self, symbol: Symbol):
        self._symbols.add(symbol)
        # TODO broker should return true/false if backtesting
        if self.broker.back_testing:
            self.broker._put_symbol(symbol)

        self._apply_ta()

    def _apply_ta(self):
        for a in self._ta_algos:
            for s in self._symbols:
                s.ohlc.apply_ta(a)

    def start(self):
        if self.started:
            raise RuntimeError(f"SymbolGroup {self.name} is already started")

        if len(self._symbols) == 0:
            raise RuntimeError(
                f"Failed to SymbolGroup {self.name} - must add symbols to the group first"
            )

        for s in self._symbols:
            _new_controller = PlayController(s, self._play_config, self.broker)
            self._play_controllers.add(_new_controller)
            _new_controller.start_play()

        self.started = True

    @property
    def active_play_controllers(self) -> set:
        active = set()
        for c in self._play_controllers:
            if len(c.instances) > 0:
                active.add(c)

        return active

    def stop(self, hard_stop: bool = False):
        for c in self.active_play_controllers:
            c.stop(hard_stop=hard_stop)
            if len(c.instances) > 0:
                log.warning(
                    f"Tried stopping {c} but still {len(c.instances)} instances running (hard_stop={hard_stop})"
                )

    def run(self):
        # need a way to mark retiring play controllers so that they don't get started up again
        log.info(f"Running for period {self.period}")
        for c in self.active_play_controllers:
            c.run()

    @property
    def play_config(self) -> ControllerConfig:
        return self._play_config

    @play_config.setter
    def play_config(self, new_config: ControllerConfig) -> bool:
        if self.started:
            raise RuntimeError(
                f"Can't change play config for {self.name} while play is running"
            )

        self._play_config = new_config

    @property
    def broker(self) -> ITradeAPI:
        return self._broker

    @broker.setter
    def broker(self, new_broker: ITradeAPI):
        if self.started:
            raise RuntimeError(
                f"Can't change broker for {self.name} while play is running"
            )

        self._broker = new_broker

    # use a property here to keep broker and symbol in sync!
    @property
    def period(self):
        return self._tm.now

    # @period.setter
    # def period(self, new_period):
    #    self._period = new_period

    #    if self.back_testing:
    #        self.broker.period = new_period

    #        for s in self._symbols:
    #            s.period = new_period


"""
set a play template for each category
query for conditions

filter through running PlayControllers that do not match the conditions, and tell them to terminate
boot up PlayControllers for the matched permutations

conditions
{
    "crypto-stable": "choppy",
    "crypto-alt": "bull",
    "nyse": "flat"
}

symbols
{
    "category": "crypto-alt",
    "exchange": alpaca,
    "symbols": ["BTC-USD", "ADA-USD"]
}

playtemplate
{
    "category": "crypto-alt",
    "conditions": "bull",
    "max_play_size": 200,
    "buy_timeout_intervals": 2,
    "buy_order_type": "limit",
    "take_profit_risk_multiplier": 1.5,
    "take_profit_pct_to_sell": 0.5,
    "stop_loss_type": "market",
    "stop_loss_trigger_pct": 0.99,
    "stop_loss_hold_intervals": 1,
    "state_waiting": MacdStateWaiting,
    "state_entering_position": MacdStateEnteringPosition,
    "state_taking_profit": MacdStateTakingProfit,
    "state_stopping_loss": MacdStateStoppingLoss,
    "state_terminated": MacdStateTerminated,
}

"""
symbol_map = {}
symbol_map["crypto-alt"] = {
    "category": "crypto-alt",
    "exchange": "alpaca",
    "symbols": ["ATOM-USD", "ADA-USD", "SOL-USD"],
}

play_library = {}
play_library["crypto-alt"] = {}
play_library["crypto-alt"]["bull"] = {
    "max_play_size": 200,
    "buy_timeout_intervals": 2,
    "buy_order_type": "limit",
    "take_profit_risk_multiplier": 1.5,
    "take_profit_pct_to_sell": 0.5,
    "stop_loss_type": "limit",
    "stop_loss_trigger_pct": 0.99,
    "stop_loss_hold_intervals": 1,
    "state_waiting": MacdStateWaiting,
    "state_entering_position": MacdStateEnteringPosition,
    "state_taking_profit": MacdStateTakingProfit,
    "state_stopping_loss": MacdStateStoppingLoss,
    "state_terminated": MacdStateTerminated,
}

play_library["crypto-alt"]["choppy"] = {
    "max_play_size": 100,
    "buy_timeout_intervals": 2,
    "buy_order_type": "limit",
    "take_profit_risk_multiplier": 1.3,
    "take_profit_pct_to_sell": 0.75,
    "stop_loss_type": "market",
    "stop_loss_trigger_pct": 0.97,
    "stop_loss_hold_intervals": 0,
    "state_waiting": StateWaiting,
    "state_entering_position": StateEnteringPosition,
    "state_taking_profit": StateTakingProfit,
    "state_stopping_loss": StateStoppingLoss,
    "state_terminated": StateTerminated,
}

conditions_start = {"crypto-stable": "choppy", "crypto-alt": "bull", "nyse": "flat"}
conditions_changed = {"crypto-stable": "choppy", "crypto-alt": "choppy", "nyse": "flat"}

symbol_groups = ["crypto-alt"]

tm = TimeManager()
broker = BackTestAPI(time_manager=tm, sell_metric="Close", buy_metric="High")

play = play_library["crypto-alt"]["bull"]

play_template = MacdInstanceTemplate(
    name="template",
    buy_signal_strength=0.9,
    buy_order_type="market",
    buy_timeout_intervals=2,
    take_profit_risk_multiplier=1.5,
    take_profit_pct_to_sell=0.5,
    stop_loss_type="limit",
    stop_loss_trigger_pct=0.90,
    stop_loss_hold_intervals=0.9,
    check_sma=False,
)

play_config = ControllerConfig(
    state_waiting=play["state_waiting"],
    state_entering_position=play["state_entering_position"],
    state_taking_profit=play["state_taking_profit"],
    state_stopping_loss=play["state_stopping_loss"],
    state_terminated=play["state_terminated"],
    buy_budget=200,
    play_templates=[play_template],
)

back_testing = True
sg = SymbolGroup(
    name="crypto-alt",
    play_config=play_config,
    broker=broker,
    back_testing=back_testing,
    time_manager=tm,
)

for group in symbol_groups:
    for symbol in symbol_map[group]["symbols"]:
        sg.add_symbol(Symbol(symbol, time_manager=tm, back_testing=back_testing))

sg.register_ta(MacdTA.macd)
sg.register_ta(btalib.sma)
sg.start()

# now make the loop
if back_testing:
    tm.now = tm.first
    while tm.now < tm.last:
        sg.run()
        tm.tick()

else:
    # this is where you do the sleep stuff
    ...
