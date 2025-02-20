import json
import logging
import platform
import sys
import time
import traceback


class JSONFormatter:
    def __init__(self, **tags):
        self.tags = tags

    def format(self, record):
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + (".%03dZ" % (1000 * (record.created % 1)))

        result = {
            'timestamp':        timestamp,
            'severity':         record.levelname,
            'logger':           record.name,
            'message':          record.msg % record.args,
            'host':             platform.node(),
            'process_id':       record.process,
            'thread':           record.threadName,
            'location_info': {
                'filename':     record.filename,
                'line_number':  record.lineno
            }
        }

        if self.tags:
            result['tags'] = self.tags

        if (record.exc_info):
            result['exception'] = traceback.format_exception(
                record.exc_info[0], record.exc_info[1], record.exc_info[2])

        return json.dumps(result)


def configure_logging():
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JSONFormatter(application="ctdapp"))
    logging.basicConfig(level=logging.DEBUG, handlers=[handler])
    logging.getLogger("asyncio").setLevel(logging.WARNING)
