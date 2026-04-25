from __future__ import annotations

import dataclasses
from typing import (
    TYPE_CHECKING,
    Any,
    runtime_checkable,
)
from typing_extensions import Protocol, TypedDict, deprecated

from graphql import specified_rules

from strawberry.utils.operation import get_first_operation, get_operation_type

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing_extensions import NotRequired

    from graphql import ASTValidationRule
    from graphql.error.graphql_error import GraphQLError
    from graphql.language import DocumentNode, OperationDefinitionNode

    from strawberry.schema import Schema
    from strawberry.schema._graphql_core import GraphQLExecutionResult

    from .graphql import OperationType


@runtime_checkable
class Executor(Protocol):
    """Pluggable parse + validate seam for a :class:`~strawberry.Schema`.

    Implementations MUST produce a graphql-core :class:`DocumentNode` (the
    same type returned by :func:`graphql.parse`); the document is consumed
    by graphql-core's executor downstream. :class:`GraphQLError` instances
    returned from :meth:`validate` MUST carry source ``locations`` so
    Strawberry's error formatter can surface them to clients.

    The executor is constructed once per :class:`~strawberry.Schema` and is
    shared across requests; it MUST be safe for concurrent use from multiple
    coroutines (graphql-core's :func:`parse` and :func:`validate` are pure /
    re-entrant; alternative implementations should mirror that contract).

    Implementations MUST NOT mutate the
    :class:`~strawberry.types.ExecutionContext` — that is the caller's job.
    """

    def __init__(self, schema: Schema) -> None:
        """Build an executor bound to ``schema``.

        Heavy, schema-derived state (e.g. a compiled validator) should be
        constructed here so it can be reused across requests.
        """
        ...

    def parse(
        self,
        query: str,
        *,
        parse_options: ParseOptions,
    ) -> DocumentNode:
        """Parse ``query`` to a graphql-core ``DocumentNode``.

        Raises :class:`GraphQLError` (typically
        :class:`~graphql.error.GraphQLSyntaxError`) on failure.
        """
        ...

    def validate(
        self,
        document: DocumentNode,
        *,
        validation_rules: tuple[type[ASTValidationRule], ...],
    ) -> list[GraphQLError]:
        """Run validation against ``document``.

        Returns an empty list on success.

        ``validation_rules`` is the *complete* tuple of rules to run,
        including any Strawberry-specific rules (``MaybeNullValidationRule``,
        ``OneOfInputValidationRule``) — they are appended by the caller, not
        the executor.
        """
        ...


@dataclasses.dataclass
class ExecutionContext:
    query: str | None
    schema: Schema
    allowed_operations: Iterable[OperationType]
    context: Any = None
    variables: dict[str, Any] | None = None
    parse_options: ParseOptions = dataclasses.field(
        default_factory=lambda: ParseOptions()
    )
    root_value: Any | None = None
    validation_rules: tuple[type[ASTValidationRule], ...] = dataclasses.field(
        default_factory=lambda: tuple(specified_rules)
    )

    # The operation name that is provided by the request
    provided_operation_name: dataclasses.InitVar[str | None] = None

    # Values that get populated during the GraphQL execution so that they can be
    # accessed by extensions
    graphql_document: DocumentNode | None = None
    pre_execution_errors: list[GraphQLError] | None = None
    result: GraphQLExecutionResult | None = None
    extensions_results: dict[str, Any] = dataclasses.field(default_factory=dict)

    operation_extensions: dict[str, Any] | None = None

    def __post_init__(self, provided_operation_name: str | None) -> None:
        self._provided_operation_name = provided_operation_name

    @property
    def operation_name(self) -> str | None:
        if self._provided_operation_name is not None:
            return self._provided_operation_name

        definition = self._get_first_operation()
        if not definition:
            return None

        if not definition.name:
            return None

        return definition.name.value

    @property
    def operation_type(self) -> OperationType:
        graphql_document = self.graphql_document
        if not graphql_document:
            raise RuntimeError("No GraphQL document available")

        return get_operation_type(graphql_document, self.operation_name)

    def _get_first_operation(self) -> OperationDefinitionNode | None:
        graphql_document = self.graphql_document
        if not graphql_document:
            return None

        return get_first_operation(graphql_document)

    @property
    @deprecated("Use 'pre_execution_errors' instead")
    def errors(self) -> list[GraphQLError] | None:
        """Deprecated: Use pre_execution_errors instead."""
        return self.pre_execution_errors


@dataclasses.dataclass
class ExecutionResult:
    data: dict[str, Any] | None
    errors: list[GraphQLError] | None
    extensions: dict[str, Any] | None = None


@dataclasses.dataclass
class PreExecutionError(ExecutionResult):
    """Differentiate between a normal execution result and an immediate error.

    Immediate errors are errors that occur before the execution phase i.e validation errors,
    or any other error that occur before we interact with resolvers.

    These errors are required by `graphql-ws-transport` protocol in order to close the operation
    right away once the error is encountered.
    """


class ParseOptions(TypedDict):
    max_tokens: NotRequired[int]


@runtime_checkable
class SubscriptionExecutionResult(Protocol):
    def __aiter__(self) -> SubscriptionExecutionResult:  # pragma: no cover
        ...

    async def __anext__(self) -> Any:  # pragma: no cover
        ...


__all__ = [
    "ExecutionContext",
    "ExecutionResult",
    "Executor",
    "ParseOptions",
    "SubscriptionExecutionResult",
]
