"""Async helpers for running blocking operations in thread pool"""
import asyncio
import functools
from typing import Callable, TypeVar, Coroutine, Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import logging

logger = logging.getLogger(__name__)

# Create a thread pool executor for blocking operations
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="flowmind_async")

T = TypeVar('T')

async def run_in_thread(
    func: Callable[..., T],
    *args,
    timeout: float = 300.0,  # 5 minutes default timeout
    **kwargs
) -> T:
    """
    Run a blocking function in a thread pool with timeout.
    
    Args:
        func: The blocking function to run
        *args: Positional arguments for func
        timeout: Maximum time to wait in seconds (default: 300)
        **kwargs: Keyword arguments for func
    
    Returns:
        The result of func(*args, **kwargs)
    
    Raises:
        asyncio.TimeoutError: If the operation exceeds the timeout
        Exception: Any exception raised by func
    """
    try:
        loop = asyncio.get_event_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(_executor, functools.partial(func, *args, **kwargs)),
            timeout=timeout
        )
        return result
    except asyncio.TimeoutError:
        logger.error(f"Operation {func.__name__} timed out after {timeout} seconds")
        raise asyncio.TimeoutError(f"Operation {func.__name__} timed out after {timeout} seconds")
    except Exception as e:
        logger.error(f"Error in {func.__name__}: {str(e)}")
        raise


def with_timeout(timeout: float = 300.0):
    """
    Decorator to add timeout to async functions.
    
    Usage:
        @with_timeout(timeout=60.0)
        async def my_function():
            ...
    """
    def decorator(func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            except asyncio.TimeoutError:
                logger.error(f"Function {func.__name__} timed out after {timeout} seconds")
                raise asyncio.TimeoutError(f"Function {func.__name__} timed out after {timeout} seconds")
        return wrapper
    return decorator

