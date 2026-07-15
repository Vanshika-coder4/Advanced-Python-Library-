# src/my_advanced_lib/core/decorators.py
import time
import functools
from typing import Any, Callable, TypeVar, cast
from typing_extensions import ParamSpec
import logging
from datetime import datetime, timedelta
from collections.abc import Hashable

P = ParamSpec('P')
T = TypeVar('T')

logger = logging.getLogger(__name__)

class RetryError(Exception):
    """Custom exception for retry decorator"""
    pass

def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator that retries a function on failure.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between attempts in seconds
        backoff: Multiplier for delay after each attempt
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception = None
            current_delay = delay
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {e}"
                    )
                    
                    if attempt == max_attempts:
                        raise RetryError(
                            f"Function {func.__name__} failed after {max_attempts} attempts"
                        ) from last_exception
                    
                    time.sleep(current_delay)
                    current_delay *= backoff
            
            # This should never be reached due to the raise above
            raise RetryError("Unexpected error in retry decorator")
        
        return wrapper
    return decorator

class Cache:
    """Cache decorator with TTL support"""
    
    def __init__(self, ttl: int = 3600):
        self.ttl = ttl
        self._cache: dict[Hashable, tuple[Any, float]] = {}
    
    def __call__(self, func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Create cache key from function name and arguments
            cache_key = self._make_key(func.__name__, args, kwargs)
            
            # Check cache
            current_time = time.time()
            if cache_key in self._cache:
                cached_value, timestamp = self._cache[cache_key]
                if current_time - timestamp < self.ttl:
                    logger.debug(f"Cache hit for {func.__name__}")
                    return cast(T, cached_value)
                else:
                    # Cache expired
                    del self._cache[cache_key]
            
            # Cache miss or expired
            logger.debug(f"Cache miss for {func.__name__}")
            result = func(*args, **kwargs)
            self._cache[cache_key] = (result, current_time)
            return result
        
        return wrapper
    
    def _make_key(self, func_name: str, args: tuple, kwargs: dict) -> Hashable:
        """Create a hashable cache key"""
        key_parts = [func_name]
        
        # Add args (handle unhashable types)
        for arg in args:
            if isinstance(arg, Hashable):
                key_parts.append(arg)
            else:
                key_parts.append(str(arg))
        
        # Add kwargs (sorted for consistency)
        for key in sorted(kwargs.keys()):
            value = kwargs[key]
            key_parts.append(key)
            if isinstance(value, Hashable):
                key_parts.append(value)
            else:
                key_parts.append(str(value))
        
        return tuple(key_parts)
    
    def clear(self):
        """Clear the cache"""
        self._cache.clear()
        logger.info("Cache cleared")

def timer(func: Callable[P, T]) -> Callable[P, T]:
    """Decorator that measures execution time"""
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        
        execution_time = end_time - start_time
        logger.info(
            f"Function {func.__name__} executed in {execution_time:.4f} seconds"
        )
        
        return result
    return wrapper

# src/my_advanced_lib/core/generators.py
from typing import Iterator, Any, Optional, Callable
import csv
import json
from pathlib import Path

class DataPipeline:
    """Generator-based data processing pipeline"""
    
    def __init__(self):
        self.processors: list[Callable] = []
    
    def add_processor(self, processor: Callable):
        """Add a processing function to the pipeline"""
        self.processors.append(processor)
        return self
    
    def process_large_file(self, filepath: str) -> Iterator[dict]:
        """Process large files line by line using generators"""
        path = Path(filepath)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        # Determine file type and create appropriate reader
        if path.suffix == '.csv':
            yield from self._read_csv(path)
        elif path.suffix == '.jsonl':
            yield from self._read_jsonl(path)
        elif path.suffix == '.txt':
            yield from self._read_text(path)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")
    
    def _read_csv(self, path: Path) -> Iterator[dict]:
        """Read CSV file line by line"""
        with open(path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                processed_row = self._apply_processors(row)
                yield processed_row
    
    def _read_jsonl(self, path: Path) -> Iterator[dict]:
        """Read JSON Lines file line by line"""
        with open(path, 'r', encoding='utf-8') as file:
            for line in file:
                if line.strip():  # Skip empty lines
                    try:
                        row = json.loads(line)
                        processed_row = self._apply_processors(row)
                        yield processed_row
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON line: {e}")
                        continue
    
    def _read_text(self, path: Path) -> Iterator[dict]:
        """Read text file line by line"""
        with open(path, 'r', encoding='utf-8') as file:
            for line_num, line in enumerate(file, 1):
                row = {'line_number': line_num, 'content': line.strip()}
                processed_row = self._apply_processors(row)
                yield processed_row
    
    def _apply_processors(self, data: dict) -> dict:
        """Apply all processors to the data"""
        result = data
        for processor in self.processors:
            result = processor(result)
        return result

# Batch processing generator
def batch_generator(iterable: Iterator[Any], batch_size: int = 1000) -> Iterator[list]:
    """Yield items from iterable in batches"""
    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= batch_size:
            yield batch
            batch = []
    if batch:
        yield batch

# Infinite sequence generator
def fibonacci_generator() -> Iterator[int]:
    """Generate Fibonacci sequence indefinitely"""
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b