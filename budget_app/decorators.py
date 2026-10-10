from functools import wraps
from time import perf_counter
from typing import Callable, TypeVar, Any
F = TypeVar("F", bound=Callable[..., Any])


def timed(func: F) -> F:
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        started = perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            print(f"[실행시간] {func.__name__}: {perf_counter() - started:.3f}s")
    return wrapper  # type: ignore[return-value]
