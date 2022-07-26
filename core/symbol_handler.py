from symbol import Symbol
from .time_manager import BackTestTimeManager
from .symbol_play import SymbolPlay
from .play_config import PlayConfig
from .controller_config import ControllerConfig
from broker_api import ITradeAPI
from .telemetry import ITelemetry

import logging

log = logging.getLogger(__name__)


class SymbolHandler:
    """Handles SymbolPlay objects"""

    _symbols: dict[Symbol]
    _ta_algos: set
    time_manager: BackTestTimeManager
    started: bool
    _symbol_plays: set[SymbolPlay]
    active_symbol_plays: set[SymbolPlay]
    play_config: PlayConfig
    broker: ITradeAPI
    run_id: str
    telemetry: ITelemetry

    def __init__(
        self,
        symbols: set[Symbol],
        time_manager: BackTestTimeManager,
        play_config: PlayConfig,
        broker: ITradeAPI,
        run_id: str,
        telemetry: ITelemetry,
    ) -> None:
        self._symbols = symbols
        self._ta_algos = set()
        self.started = False
        self._symbol_plays = set()
        self.time_manager = time_manager
        self.play_config = play_config
        self.broker = broker
        self.run_id = run_id
        self.telemetry = telemetry

    def __repr__(self) -> str:
        return f"SymbolGroup {self.play_config.name} ({len(self._symbols)} symbols)"

    @property
    def active_symbol_plays(self) -> set[SymbolPlay]:
        active = set()
        for c in self._symbol_plays:
            if len(c.instances) > 0:
                active.add(c)

        return active

    def start(self):
        if self.started:
            raise RuntimeError(f"SymbolGroup {self.name} is already started")

        if len(self._symbols) == 0:
            raise RuntimeError(
                f"Failed to start SymbolGroup {self.name} - must add symbols to the group first"
            )

        for s, s_obj in self._symbols.items():
            _new_controller = SymbolPlay(
                symbol=s_obj,
                play_config=self.play_config,
                broker=self.broker,
                time_manager=self.time_manager,
                run_id=self.run_id,
                telemetry=self.telemetry,
            )
            self._symbol_plays.add(_new_controller)
            _new_controller.start()

        self.started = True

    def stop(self, hard_stop: bool = False):
        for c in self.active_symbol_plays:
            c.stop(hard_stop=hard_stop)
            if len(c.instances) > 0:
                log.warning(
                    f"Tried stopping {c} but still {len(c.instances)} instances running (hard_stop={hard_stop})"
                )

    def run(self):
        # need a way to mark retiring play controllers so that they don't get started up again
        # log.info(f"Running for period {self.period}")
        for c in self.active_symbol_plays:
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
        return self.time_manager.now
