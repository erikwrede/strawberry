"""Default :class:`~strawberry.types.execution.Executor` implementation.

The seam itself lives in :mod:`strawberry.types.execution` so that the
``Executor`` Protocol can be referenced from ``Schema.__init__`` without
introducing an import cycle. The default implementation here is a thin
adapter over :func:`graphql.parse` and :func:`graphql.validate.validate`;
it preserves Strawberry's pre-seam behaviour byte-for-byte.

A third-party executor (e.g. a Rust-backed parser/validator) can be plugged
in by passing ``executor_class=`` to :class:`strawberry.Schema`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from graphql import parse as gql_parse
from graphql.validation import validate as gql_validate

if TYPE_CHECKING:
    from graphql import ASTValidationRule
    from graphql.error.graphql_error import GraphQLError
    from graphql.language import DocumentNode

    from strawberry.schema import Schema
    from strawberry.types.execution import ParseOptions


class GraphQlCoreExecutor:
    """Default :class:`~strawberry.types.execution.Executor` implementation.

    Delegates ``parse`` and ``validate`` to graphql-core, mirroring the
    behaviour Strawberry shipped before the executor seam landed. The
    :class:`~strawberry.Schema` reference is held so that subclasses (and
    future executors that need it, e.g. a Rust-backed compiler that wants
    the SDL) can reach it without per-call plumbing.
    """

    def __init__(self, schema: Schema) -> None:
        self._schema = schema

    def parse(
        self,
        query: str,
        *,
        parse_options: ParseOptions,
    ) -> DocumentNode:
        """Parse ``query`` using :func:`graphql.parse`."""
        return gql_parse(query, **parse_options)

    def validate(
        self,
        document: DocumentNode,
        *,
        validation_rules: tuple[type[ASTValidationRule], ...],
    ) -> list[GraphQLError]:
        """Validate ``document`` against the schema using graphql-core."""
        return gql_validate(self._schema._schema, document, validation_rules)


__all__ = ["GraphQlCoreExecutor"]
