from abc import ABC, abstractmethod
import parameter_store
import boto3
import botocore
import random
import json
from .constants import RT_BACKTEST, RT_PAPER, RT_REAL, RT_DICT


class ITelemetry(ABC):
    def __init__(self):
        ...

    @abstractmethod
    def emit(self, *args, **kwargs):
        ...


class Sqs(ITelemetry):
    _sqs_url: str
    _sqs_handle: any
    _sqs_message_group_id: int

    def __init__(self, store: parameter_store.IParameterStore, run_type: int):
        # TODO something clever with run_type and queues
        self._sqs_url = store.get("/tabot/telemetry/queue/backtest")
        self._sqs_handle = boto3.client("sqs")
        self._sqs_message_group_id = str(random.randint(1000, 9999))

    def emit(self, event: str, *args, **kwargs):
        if kwargs:
            kwargs["event"] = event
            sorted_kwargs = dict(sorted(kwargs.items()))
        else:
            sorted_kwargs = {"event": event}

        if args:
            sorted_kwargs["other_values"] = args

        self._sqs_handle.send_message(
            QueueUrl=self._sqs_url,
            MessageBody=(json.dumps(sorted_kwargs)),
            MessageGroupId=self._sqs_message_group_id,
        )
