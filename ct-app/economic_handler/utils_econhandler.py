from signal import Signals

from .economic_handler import EconomicHandler


def stop_instance(instance: EconomicHandler, signal: Signals):
    """Stop the economic handler instance when a signal is received"""
    print(f">>> Caught signal {signal.name} <<<")
    instance.stop()
