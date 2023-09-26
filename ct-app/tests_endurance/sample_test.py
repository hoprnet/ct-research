import logging

from tools import getlogger

from .endurance_test import EnduranceTest

log = getlogger()
log.setLevel(logging.ERROR)


class SampleTest(EnduranceTest):
    async def on_start(self):
        pass

    async def task(self) -> bool:
        pass

    async def on_end(self):
        pass

    def metrics(self):
        pass
