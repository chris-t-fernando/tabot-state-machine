from broker_api import AlpacaAPI, BackTestAPI, ITradeAPI
from abc import ABC, abstractmethod
from core import TimeManager
from parameter_store import Ssm, IParameterStore
from core import TimeManager, State, SymbolPlay, ControllerConfig, PlayOrchestrator
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


store = Ssm()
po = PlayOrchestrator(store)
po.start()


#    def _enumerate_symbols(self):
#        for cat in self.symbol_categories:
#            new_symbols = set(
#                json.loads(self.store.get(f"{self._store_path}/{cat}/symbols"))
#            )
#            if len(new_symbols & self.uninstantiated_symbols) > 0:
#                log.warning(
#                    f"Symbol appears in more than one category: {new_symbols&self.uninstantiated_symbols}"
#                )
#            self.uninstantiated_symbols |= new_symbols
