from logging import Formatter


class QuantiPyLogger(Formatter):
    def format(self, record: str) -> str:
        log_msg = (
            f"[{record.levelname}] ({record.module}:{record.funcName}) "
            f"{record.msg}"
        )
        return log_msg % record.args
