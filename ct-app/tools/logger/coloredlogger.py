# Custom logger class with multiple destinations
import logging

from .coloredformatter import ColoredFormatter, formatter_message


class ColoredLogger(logging.Logger):
    """
    A logger that allows to color the output of the logger.
    """

    FORMAT = "[$DATE][$BOLD%(name)s$RESET][%(levelname)-8s] %(message)s"

    COLOR_FORMAT = formatter_message(FORMAT, True)

    def __init__(self, name):
        logging.Logger.__init__(self, name, logging.DEBUG)

        color_formatter = ColoredFormatter(self.COLOR_FORMAT, False)

        console = logging.StreamHandler()
        console.setFormatter(color_formatter)

        self.addHandler(console)
        return


logging.setLoggerClass(ColoredLogger)
