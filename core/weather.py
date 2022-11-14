from .time_manager import ITimeManager
from abc import ABC, abstractmethod
import math


class WeatherResult:
    """
    SymbolCategory
        Name                        crypto_alt
        Symbols                     {ADA, AVAX}
        Condition                   bull
    SymbolCategory
        Name                        crypto_stable
        Symbols                     {BTC, ETH}
        Condition                   choppy
    """

    class WeatherItem:
        symbols: set[str]
        condition: str

        def __init__(self, symbols, condition) -> None:
            self.symbols = symbols
            self.condition = condition

        def __repr__(self) -> str:
            return f"WeatherItem {str(self.symbols)}"


class StubWeatherResult(WeatherResult):
    _mock_weather: dict[str, WeatherResult.WeatherItem]

    def __init__(self, result) -> None:
        self.__result = result
        self._mock_weather = dict()
        self._mock_weather["crypto_alt"] = self.WeatherItem(
            symbols={"ADA, AVAX"}, condition=result
        )
        self._mock_weather["crypto_stable"] = self.WeatherItem(
            symbols={"BTC, ETH"}, condition=result
        )

    def get_all(self) -> dict[str, WeatherResult]:

        self._mock_weather["crypto_alt"] = self.WeatherItem(
            symbols={"ADA, AVAX"},
            condition=self.__result,
        )
        self._mock_weather["crypto_stable"] = self.WeatherItem(
            symbols={"ADA, AVAX"},
            condition=self.__result,
        )
        return self._mock_weather

    def get_one(self, category: str) -> WeatherResult:
        self.__iteration_count += 1
        self._mock_weather["crypto_alt"] = self.WeatherItem(
            symbols={"ADA, AVAX"},
            condition=self.__result,
        )
        self._mock_weather["crypto_stable"] = self.WeatherItem(
            symbols={"ADA, AVAX"},
            condition=self.__result,
        )
        return self._mock_weather[category]


class IWeatherReader(ABC):
    @abstractmethod
    def __init__(self):
        ...

    @abstractmethod
    def get_all(self) -> dict[str, WeatherResult]:
        ...

    @abstractmethod
    def get_one(self, category: str) -> WeatherResult:
        ...


class StubWeather(IWeatherReader):
    _tm: ITimeManager

    def __init__(self, tm: ITimeManager):
        self.__iteration_count = 0
        self.__conditions = ["choppy", "bull", "bear"]
        self._tm = tm

    def get_all(self) -> dict[str, WeatherResult]:
        self.__iteration_count += 1
        condition = self.__conditions[math.floor(self.__iteration_count / 1000 % 3)]
        return StubWeatherResult(condition).get_all()

    def get_one(self, category: str) -> WeatherResult:
        condition = self.__conditions[math.floor(self.__iteration_count / 1000 % 3)]
        return StubWeatherResult(condition).get_one(category)
