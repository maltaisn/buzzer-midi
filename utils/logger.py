#  Copyright 2021 Nicolas Maltais
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

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
