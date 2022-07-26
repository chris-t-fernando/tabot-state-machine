from broker_api import AlpacaAPI, BackTestAPI
from parameter_store import Ssm

from strategies import (
    MacdStateEnteringPosition,
    MacdStateStoppingLoss,
    MacdStateTakingProfit,
    MacdStateWaiting,
    MacdStateTerminated,
    MacdTA,
    MacdInstanceTemplate,
)
from symbol import Symbol
from core import ControllerConfig, PlayController
import btalib
import logging
from time import sleep

logger = logging.getLogger()
stream_handler = logging.StreamHandler()
formatter = logging.Formatter(
    "%(asctime)s - %(name)16s - %(levelname)8s - %(funcName)15s - %(message)s"
)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)
logger.setLevel(logging.CRITICAL)

level = logging.DEBUG

# logging.getLogger("symbol.symbol_data").setLevel(logging.CRITICAL)
logging.getLogger("symbol").setLevel(logging.CRITICAL)
logging.getLogger("core").setLevel(level)
logging.getLogger("strategies").setLevel(level)
# logging.getLogger("broker_api.back_test").setLevel(level)

# TODO stop loss signal at high/low/close
play_template_1 = MacdInstanceTemplate(
    name="template1",
    buy_signal_strength=1,
    buy_timeout_intervals=2,
    buy_order_type="limit",
    take_profit_risk_multiplier=1.5,
    take_profit_pct_to_sell=0.5,
    stop_loss_type="market",
    stop_loss_trigger_pct=0.99,
    stop_loss_hold_intervals=1,
)

play_template_2 = MacdInstanceTemplate(
    name="template2",
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
    state_waiting=MacdStateWaiting,
    state_entering_position=MacdStateEnteringPosition,
    state_taking_profit=MacdStateTakingProfit,
    state_stopping_loss=MacdStateStoppingLoss,
    state_terminated=MacdStateTerminated,
    buy_budget=200,
    play_templates=[play_template_1, play_template_2],
)

store = Ssm()
_PREFIX = "tabot"
api_key = store.get(f"/{_PREFIX}/paper/alpaca/api_key")
security_key = store.get(f"/{_PREFIX}/paper/alpaca/security_key")

broker = AlpacaAPI(
    alpaca_key_id=api_key,
    alpaca_secret_key=security_key,
)

# broker = back_test.BackTestAPI(sell_metric="High", buy_metric="Low")
back_testing = False
symbol = Symbol(
    yf_symbol="DOGE-USD", min_price_increment=0.00001, back_testing=back_testing
)  # need to do api calls to generate increments etc

# broker._put_symbol(symbol)

symbol.ohlc.apply_ta(btalib.sma)
symbol.ohlc.apply_ta(MacdTA.macd)

current_interval_key = 3500
# current_interval = symbol.ohlc.bars.index[current_interval_key]
bar_len = len(symbol.ohlc.bars)


symbol.period = symbol.ohlc.bars.index[current_interval_key]

controller = PlayController(
    symbol, play_config, broker
)  # also creates a play telemetry object
controller.start_play()

while True:
    controller.run()
    sleep(300)

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
