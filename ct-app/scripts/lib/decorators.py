import asyncio
import functools


def asynchronous(func):
    """
    Decorator to run async functions synchronously. Helpful espacially for the main function,
    when used alongside the click library.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    return wrapper
