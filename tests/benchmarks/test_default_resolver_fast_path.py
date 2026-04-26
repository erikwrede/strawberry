"""Benchmarks for the resolver fast path.

The fast path applies to fields that have a custom resolver but no field
extensions. It skips the ``extension_resolver`` reduce-loop in
``strawberry.schema.schema_converter`` and (for async fields) the
``await_maybe`` probe, while still being fully compatible with
``SchemaExtension.resolve`` middlewares (which are wired one level above
through graphql-core's ``MiddlewareManager``) and with field extensions
(those fields skip the fast path and use the existing chain).

These cases are written to make the difference visible in CodSpeed:

* ``test_execute_no_extensions`` — the fast-path target. Sync resolvers,
  no field extensions, no schema-extension middleware. Should improve.
* ``test_execute_with_schema_extension`` — fast-path resolvers behind a
  ``SchemaExtension.resolve`` middleware. Verifies that adding global
  middleware does NOT regress the per-field path beyond the middleware
  cost itself.
* ``test_execute_with_field_extension`` — at least one field carries a
  field extension. That field stays on the existing extension-chain
  path; the others go through the fast path. Verifies no regression
  on the slow path.
"""

from __future__ import annotations

from typing import Any

import pytest
from pytest_codspeed.plugin import BenchmarkFixture

import strawberry
from strawberry.extensions.base_extension import SchemaExtension
from strawberry.extensions.field_extension import FieldExtension


@strawberry.type
class Item:
    id: strawberry.ID
    name: str
    value: int


def _items(count: int) -> list[Item]:
    return [
        Item(id=strawberry.ID(str(i)), name=f"item-{i}", value=i)
        for i in range(count)
    ]


@strawberry.type
class Query:
    @strawberry.field
    def items(self, count: int = 100) -> list[Item]:
        return _items(count)

    @strawberry.field
    def item(self, id: strawberry.ID) -> Item | None:
        i = int(id)
        return Item(id=id, name=f"item-{i}", value=i)

    @strawberry.field
    def hello(self, name: str = "world") -> str:
        return f"hello {name}"


_QUERY = """
query Items($count: Int!) {
  hello
  items(count: $count) { id name value }
  one: item(id: "1") { id name value }
  two: item(id: "2") { id name value }
}
"""


class _NoopMiddleware(SchemaExtension):
    def resolve(self, _next, root, info, *args: Any, **kwargs: Any) -> Any:
        return _next(root, info, *args, **kwargs)


class _NoopFieldExtension(FieldExtension):
    def resolve(self, next_, source, info, **kwargs: Any) -> Any:
        return next_(source, info, **kwargs)


@strawberry.type
class _QueryWithFieldExtension:
    @strawberry.field
    def hello(self, name: str = "world") -> str:
        return f"hello {name}"

    @strawberry.field(extensions=[_NoopFieldExtension()])
    def items(self, count: int = 100) -> list[Item]:
        return _items(count)

    @strawberry.field
    def item(self, id: strawberry.ID) -> Item | None:
        i = int(id)
        return Item(id=id, name=f"item-{i}", value=i)


@pytest.mark.benchmark
@pytest.mark.parametrize("count", [10, 100, 1000], ids=lambda x: f"items_{x}")
def test_execute_no_extensions(benchmark: BenchmarkFixture, count: int) -> None:
    """Fast-path target: sync resolvers, no field/schema extensions."""
    schema = strawberry.Schema(query=Query)
    result = benchmark(schema.execute_sync, _QUERY, variable_values={"count": count})
    assert result.errors is None


@pytest.mark.benchmark
@pytest.mark.parametrize("count", [10, 100, 1000], ids=lambda x: f"items_{x}")
def test_execute_with_schema_extension(
    benchmark: BenchmarkFixture, count: int
) -> None:
    """Fast-path resolvers behind a SchemaExtension.resolve middleware."""
    schema = strawberry.Schema(query=Query, extensions=[_NoopMiddleware()])
    result = benchmark(schema.execute_sync, _QUERY, variable_values={"count": count})
    assert result.errors is None


@pytest.mark.benchmark
@pytest.mark.parametrize("count", [10, 100, 1000], ids=lambda x: f"items_{x}")
def test_execute_with_field_extension(
    benchmark: BenchmarkFixture, count: int
) -> None:
    """One field carries a field extension; others still use the fast path."""
    schema = strawberry.Schema(query=_QueryWithFieldExtension)
    result = benchmark(schema.execute_sync, _QUERY, variable_values={"count": count})
    assert result.errors is None
