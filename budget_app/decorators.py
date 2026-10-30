from functools import wraps
from time import perf_counter
from typing import Callable, TypeVar, Any
F = TypeVar("F", bound=Callable[..., Any])


def timed(func: F) -> F:
    """호출 결과와 예외 여부에 관계없이 함수 실행 시간을 출력합니다."""
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        started = perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            # finally에서 측정해 함수가 예외를 내도 실행 시간이 표시됩니다.
            print(f"[실행시간] {func.__name__}: {perf_counter() - started:.3f}s")
    return wrapper  # type: ignore[return-value]
