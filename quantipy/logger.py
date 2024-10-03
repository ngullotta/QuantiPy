import logging
from logging import Formatter


class QuantiPyLogger(Formatter):
    __level_to_symbol = {
        "DEBUG": "+",
        "INFO": "*",
        "WARNING": "?",
        "ERROR": "!",
        "CRITICAL": "!!",
    }

    def format(self, record: logging.LogRecord) -> str:
        symbol = self.__level_to_symbol.get(
            record.levelname, self.__level_to_symbol.get("DEBUG")
        )
        return f"[{symbol}] {record.msg}" % record.args
