from typing import TypeVar


T = TypeVar("T")


async def lift_async(value: T ) -> T: 
    """Lift a value into an async context."""
    return value