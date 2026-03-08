"""Base class for pipeline passes."""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from systemf.surface.result import Result

Input = TypeVar("Input")
Output = TypeVar("Output")
Error = TypeVar("Error")
Context = TypeVar("Context")


class PipelinePass(ABC, Generic[Input, Output, Error, Context]):
    """Abstract base for all pipeline passes.

    A pass is a pure function: (Input, Context) -> Result[Output, Error]
    Passes must be stateless and composable.
    """

    @abstractmethod
    def run(self, input_data: Input, context: Context) -> Result[Output, Error]:
        """Execute the pass.

        Args:
            input_data: The AST or declarations to transform
            context: The context for this pass (ScopeContext, TypeContext, etc.)

        Returns:
            Result containing either transformed output or error
        """
        pass
