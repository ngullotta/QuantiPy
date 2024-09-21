import json
import logging


class QuantiPyLogger(logging.Formatter):
    def format(self, record: str) -> str:
        log_msg = (
            f"[{record.levelname}] ({record.module}:{record.funcName}) {record.msg}"
        )
        return log_msg % record.args
