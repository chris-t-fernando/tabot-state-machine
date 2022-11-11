from abc import ABC, abstractmethod
from pandas import DataFrame


class ITA(ABC):
    @abstractmethod
    def do_ta(ohlc_data: DataFrame):
        ...
