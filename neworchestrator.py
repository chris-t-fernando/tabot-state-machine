import __main__
from broker_api import AlpacaAPI, BackTestAPI, ITradeAPI
from parameter_store import Ssm
from core import PlayOrchestrator
from core import StrategyHandler
from strategies import (
    MacdPlayConfig,
    MacdStateEnteringPosition,
    MacdStateStoppingLoss,
    MacdStateTakingProfit,
    MacdStateTerminated,
    MacdStateWaiting,
    MacdTA,
)

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
logging.getLogger("core.instance_state").setLevel(level)
logging.getLogger("core.orchestrator").setLevel(level)
logging.getLogger("strategies.macd").setLevel(level)

sh = StrategyHandler(globals().copy())

store = Ssm()
po = PlayOrchestrator(store, sh)
po.start()
