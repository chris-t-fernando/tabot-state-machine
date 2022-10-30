from .time_manager import ITimeManager
from abc import ABC, abstractmethod


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

    def __init__(self) -> None:
        self._mock_weather = dict()
        self._mock_weather["crypto_alt"] = self.WeatherItem(
            symbols={"ADA, AVAX"}, condition="bull"
        )
        self._mock_weather["crypto_stable"] = self.WeatherItem(
            symbols={"BTC, ETH"}, condition="choppy"
        )

    def get_all(self) -> dict[str, WeatherResult]:
        return self._mock_weather

    def get_one(self, category: str) -> WeatherResult:
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
        self._tm = tm

    def get_all(self) -> dict[str, WeatherResult]:
        return StubWeatherResult().get_all()

    def get_one(self, category: str) -> WeatherResult:
        return StubWeatherResult().get_one(category)
