from broker_api import alpaca
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
from core.abstracts import ControllerConfig, Controller, Symbol
import btalib
import logging

logger = logging.getLogger()
stream_handler = logging.StreamHandler()
formatter = logging.Formatter(
    "%(asctime)s - %(name)16s - %(levelname)8s - %(funcName)15s - %(message)s"
)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)
logger.setLevel(logging.CRITICAL)

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
logging.getLogger("symbol.symbol_data").setLevel(logging.WARNING)
logging.getLogger("core.abstracts").setLevel(logging.DEBUG)
logging.getLogger("strategies.macd").setLevel(logging.DEBUG)

play_template_1 = MacdInstanceTemplate(
    name="template1",
    buy_signal_strength=1,
    take_profit_trigger_pct_of_risk=1,
    take_profit_pct_to_sell=1,
    stop_loss_type="market",
    stop_loss_trigger_pct=0.99,
    stop_loss_hold_intervals=1,
)

play_template_2 = MacdInstanceTemplate(
    name="template2",
    buy_signal_strength=0.9,
    take_profit_trigger_pct_of_risk=0.9,
    take_profit_pct_to_sell=0.9,
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

broker = alpaca.AlpacaAPI(
    alpaca_key_id=api_key,
    alpaca_secret_key=security_key,
)

symbol = Symbol(
    yf_symbol="BTC-USD", back_testing=True
)  # need to do api calls to generate increments etc

symbol.ohlc.apply_ta(btalib.sma)
symbol.ohlc.apply_ta(MacdTA.macd)

current_interval_key = 3500
# current_interval = symbol.ohlc.bars.index[current_interval_key]
bar_len = len(symbol.ohlc.bars)

symbol.ohlc.set_period(symbol.ohlc.bars.index[current_interval_key])

controller = Controller(symbol, play_config, broker)  # also creates a play telemetry object
controller.start_play()

while current_interval_key <= bar_len:
    current_interval = symbol.ohlc.bars.index[current_interval_key]
    if current_interval_key % 100 == 0:
        log.debug(f"Checking loc {current_interval_key} at {current_interval}")

    controller.run()

    current_interval_key += 1

    symbol.ohlc.set_period(symbol.ohlc.bars.index[current_interval_key])

# so who decides the wait period?
# InstanceController? but then how do multiple symbols run in parallel
# from here? then InstanceController can just make a call to get latest, without knowing why it was called again?
# otherwise i could make it so that each instancecontroller is its own process, and each can sleep as long as it wants
# that would make startup and shutdown a lot faster. might get into issues with request throttling though?
