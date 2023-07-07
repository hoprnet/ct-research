from .economic_handler import EconomicHandler
from signal import Signals


def stop_instance(instance: EconomicHandler, signal: Signals):
    """Stop the economic handler instance when a signal is received"""
    print(f">>> Caught signal {signal.name} <<<")
    instance.stop()
