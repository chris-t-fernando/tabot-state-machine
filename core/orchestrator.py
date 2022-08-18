from broker_api import alpaca, back_test
from parameter_store.ssm import Ssm
from strategies.macd import (
    MacdStateEnteringPosition,
    MacdStateStoppingLoss,
    MacdStateTakingProfit,
    MacdStateWaiting,
    MacdStateTerminated,
    MacdTA,
    MacdInstanceTemplate,
)
from core.abstracts import (
    ControllerConfig,
    Controller,
    Symbol,
    StateEnteringPosition,
    StateWaiting,
    StateTerminated,
    StateStoppingLoss,
    StateTakingProfit,
)
import btalib
import logging

log = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self) -> None:
        pass

    def add_template(self, template):
        ...


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
symbol_map = {
    "category": "crypto-alt",
    "exchange": alpaca,
    "symbols": ["BTC-USD", "ADA-USD", "SOL-USD"],
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

# do something with all of this
# instantiate symbols, register with backtest broker
# boot up the PlayController objects

store = Ssm()
_PREFIX = "tabot"
api_key = store.get(f"/{_PREFIX}/paper/alpaca/api_key")
security_key = store.get(f"/{_PREFIX}/paper/alpaca/security_key")

broker = back_test.BackTestAPI(sell_metric="Close", buy_metric="High")

symbol = Symbol(
    yf_symbol="DOGE-USD", min_price_increment=0.00001, back_testing=True
)  # need to do api calls to generate increments etc

broker._put_symbol(symbol)

symbol.ohlc.apply_ta(btalib.sma)
symbol.ohlc.apply_ta(MacdTA.macd)

current_interval_key = 3500
# current_interval = symbol.ohlc.bars.index[current_interval_key]
bar_len = len(symbol.ohlc.bars)

symbol.period = symbol.ohlc.bars.index[current_interval_key]

controller = Controller(symbol, play_config, broker)  # also creates a play telemetry object
controller.start_play()

while current_interval_key < bar_len:
    # TODO need an object to track the ticks
    this_period = symbol.ohlc.bars.index[current_interval_key]
    symbol.period = this_period
    broker.period = this_period

    current_interval = symbol.ohlc.bars.index[current_interval_key]
    if current_interval_key % 100 == 0:
        log.debug(f"Checking loc {current_interval_key} at {current_interval}")

    controller.run()

    current_interval_key += 1

# so who decides the wait period?
# InstanceController? but then how do multiple symbols run in parallel
# from here? then InstanceController can just make a call to get latest, without knowing why it was called again?
# otherwise i could make it so that each instancecontroller is its own process, and each can sleep as long as it wants
# that would make startup and shutdown a lot faster. might get into issues with request throttling though?


# TODO
# build an Orchestrator
# fix the logic above to simplify backtesting vs not
