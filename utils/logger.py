from enum import Enum
from typing import IO
from functools import total_ordering


@total_ordering
class LogLevel(Enum):
    OFF = 0
    ERROR = 1
    WARNING = 2
    INFO = 3

    def __lt__(self, other: "LogLevel") -> bool:
        return self.value < other.value


class Logger:
    file: IO
    level: LogLevel

    def __init__(self, file: IO, level: LogLevel):
        self.file = file
        self.level = level

    def info(self, message: str) -> None:
        self.log(LogLevel.INFO, message)

    def warn(self, message: str) -> None:
        self.log(LogLevel.WARNING, message)

    def error(self, message: str) -> None:
        self.log(LogLevel.ERROR, message)

    def log(self, level: LogLevel, message: str) -> None:
        if level <= self.level:
            print(f"{level.name.upper()}: {message}", file=self.file)
