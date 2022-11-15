from abc import ABC
from symbol import Symbol
from typing import List
from .play_config import PlayConfig
from broker_api import ITradeAPI
import uuid
from .instance import Instance
from .controller_config import ControllerConfig
from .state_terminated import StateTerminated
from .state import State
from .instance_list import InstanceList

import logging

log = logging.getLogger(__name__)


class SymbolPlay(ABC):
    instances: List[Instance]
    symbol: Symbol
    play_config: ControllerConfig
    broker: ITradeAPI
    play_instance_class: Instance
    play_id: str
    terminated_instances: List[Instance]

    def __init__(
        self,
        symbol: Symbol,
        play_config: ControllerConfig,
        broker: ITradeAPI,
        play_instance_class: Instance = Instance,
    ) -> None:
        self.symbol = symbol
        self.play_config = play_config
        self.play_id = self._generate_play_id()
        self.broker = broker
        # PlayInstance class to be use - can be overridden to enable extension
        self.play_instance_class = play_instance_class
        self.instances = []
        self.terminated_instances = []

    def start(self):
        if len(self.instances) > 0:
            raise RuntimeError("Already started plays, can't call start_play() twice")

        # for template in self.play_config.play_templates:
        self.instances.append(self.play_instance_class(self.play_config, self))

    def register_instance(self, new_instance):
        self.instances.append(new_instance)

    def _generate_play_id(self, length: int = 6):
        return "play-" + self.symbol.yf_symbol + uuid.uuid4().hex[:length].upper()

    @property
    def total_gain(self):
        gain = 0
        for i in self.instances:
            if i.total_buy_value != 0:
                gain += i.total_gain
            else:
                log.debug(
                    f"Ignoring instance {i} since it has not taken profit or stopped loss yet"
                )

        return gain

    # @property
    def stop(self, hard_stop: bool = False):
        for i in self.instances:
            i.stop(hard_stop=hard_stop)

    # TODO rewrite this to use @property active instances
    def run(self):
        new_instances = []
        retained_instances = []
        for i in self.instances:
            i.run()

            if isinstance(i.state, StateTerminated):
                # if this instance is terminated, spin up a new one
                self.terminated_instances.append(i)
                new_instances.append(self.play_instance_class(i.config, self))
                # gain = self.total_gain
                # print(f"Total gain for this symbol: {gain:,.2f}")

            else:
                retained_instances.append(i)

        updated_instances = new_instances + retained_instances
        self.instances = updated_instances

        # self.get_instances(self.instances[0].config)

    def fork_instance(self, instance: Instance, new_state: State, **kwargs):
        kwargs["previous_state"] = instance.state
        self.instances.append(
            self.play_instance_class(
                template=instance.config,
                play_controller=self,
                state=new_state,
                state_args=kwargs,
            )
        )

    def get_instances(self, template: PlayConfig):
        all_instances = self.instances + self.terminated_instances
        matched_instances = InstanceList()
        for i in all_instances:
            if i.config == template:
                matched_instances.append(i)

        return matched_instances
