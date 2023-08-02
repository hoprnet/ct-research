from tools import getlogger


def main():
    logger = getlogger()

    logger.debug("1 2, 1 2, is this thing on?")
    logger.info("1 2, 1 2, is this thing on?")
    logger.warning("1 2, 1 2, is this thing on?")
    logger.error("1 2, 1 2, is this thing on?")
    logger.critical("1 2, 1 2, is this thing on?")


if __name__ == "__main__":
    main()
