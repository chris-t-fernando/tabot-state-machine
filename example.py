from strategies.macd import (
    MacdStateEnteringPosition,
    MacdStateStoppingLoss,
    MacdStateTakingProfit,
    MacdStateWaiting,
    MacdStateTerminated,
)
from core.abstracts import InstanceTemplate, ControllerConfig, InstanceController, Symbol
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
logging.getLogger("symbol_data").setLevel(logging.DEBUG)
logging.getLogger("strategy_machine").setLevel(logging.DEBUG)
logging.getLogger("strategy_macd").setLevel(logging.DEBUG)

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
    yf_symbol="BTC-USD", alp_symbol="BTCUSD"
)  # need to do api calls to generate increments etc


controller = InstanceController(symbol, play_config)  # also creates a play telemetry object
controller.start_play()
controller.run()
controller.run()
controller.run()
controller.run()
controller.run()


# so who decides the wait period?
# InstanceController? but then how do multiple symbols run in parallel
# from here? then InstanceController can just make a call to get latest, without knowing why it was called again?
# otherwise i could make it so that each instancecontroller is its own process, and each can sleep as long as it wants
# that would make startup and shutdown a lot faster. might get into issues with request throttling though?
