from strategies.macd import (
    MacdStateEnteringPosition,
    MacdStateStoppingLoss,
    MacdStateTakingProfit,
    MacdStateWaiting,
    MacdStateTerminated,
    MacdTA,
)
from core.abstracts import InstanceTemplate, ControllerConfig, InstanceController, Symbol
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

logging.getLogger(__name__).setLevel(logging.DEBUG)
logging.getLogger("symbol.symbol_data").setLevel(logging.WARNING)
logging.getLogger("core.abstracts").setLevel(logging.DEBUG)
logging.getLogger("strategies.macd").setLevel(logging.DEBUG)

play_template_1 = InstanceTemplate(
    buy_signal_strength=1,
    take_profit_trigger_pct_of_risk=1,
    take_profit_pct_to_sell=1,
    stop_loss_type="market",
    stop_loss_trigger_pct=0.99,
    stop_loss_hold_intervals=1,
)

play_template_2 = InstanceTemplate(
    buy_signal_strength=0.9,
    take_profit_trigger_pct_of_risk=0.9,
    take_profit_pct_to_sell=0.9,
    stop_loss_type="limit",
    stop_loss_trigger_pct=0.90,
    stop_loss_hold_intervals=0.9,
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


symbol = Symbol(
    yf_symbol="BTC-USD", alp_symbol="BTCUSD", back_testing=True
)  # need to do api calls to generate increments etc

symbol.ohlc.apply_ta(btalib.sma)
symbol.ohlc.apply_ta(MacdTA.macd)

current_interval_key = 3500
current_interval = symbol.ohlc.bars.index[current_interval_key]
bar_len = len(symbol.ohlc.bars)

symbol.ohlc.set_period(symbol.ohlc.bars.index[current_interval_key])

controller = InstanceController(symbol, play_config)  # also creates a play telemetry object
controller.start_play()

while current_interval_key <= bar_len:
    logger.debug(f"Checking {current_interval}")
    controller.run()

    current_interval_key += 1
    current_interval = symbol.ohlc.bars.index[current_interval_key]
    symbol.ohlc.set_period(symbol.ohlc.bars.index[current_interval_key])

# so who decides the wait period?
# InstanceController? but then how do multiple symbols run in parallel
# from here? then InstanceController can just make a call to get latest, without knowing why it was called again?
# otherwise i could make it so that each instancecontroller is its own process, and each can sleep as long as it wants
# that would make startup and shutdown a lot faster. might get into issues with request throttling though?
