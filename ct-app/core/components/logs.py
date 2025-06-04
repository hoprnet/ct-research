import json
import logging
import sys
import time
import traceback


class JSONFormatter(logging.Formatter):
    def __init__(self):
        pass

    def format(self, record: logging.LogRecord):
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + (
            ".%03dZ" % (1000 * (record.created % 1))
        )

        result = {
            "timestamp": timestamp,
            "level": record.levelname,
            "threadId": record.threadName,
            "log_file": record.filename,
            "log_line": record.lineno,
            "fields": {"message": record.msg % record.args},
        }

        if isinstance(record.args, dict):
            for key, value in record.args.items():
                result["fields"][key] = value

        if record.exc_info:
            result["full_message"] = traceback.format_exception(
                record.exc_info[0], record.exc_info[1], record.exc_info[2]
            )

        return json.dumps(result)


def configure_logging():
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(JSONFormatter())
    logging.basicConfig(level=logging.DEBUG, handlers=[handler])
    logging.getLogger("asyncio").setLevel(logging.WARNING)
