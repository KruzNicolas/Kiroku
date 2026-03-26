import logging


LOG_FORMAT = (
    "%(asctime)s %(levelname)s %(name)s "
    "request_id=%(request_id)s method=%(method)s path=%(path)s "
    "source=%(source)s source_message_id=%(source_message_id)s "
    "source_user_id=%(source_user_id)s message=%(message)s"
)


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        if not hasattr(record, "method"):
            record.method = "-"
        if not hasattr(record, "path"):
            record.path = "-"
        if not hasattr(record, "source"):
            record.source = "-"
        if not hasattr(record, "source_message_id"):
            record.source_message_id = "-"
        if not hasattr(record, "source_user_id"):
            record.source_user_id = "-"
        return True


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if root.handlers:
        return

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.addFilter(RequestContextFilter())

    root.setLevel(level)
    root.addHandler(handler)
