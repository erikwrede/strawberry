Release type: patch

Speed up `Schema.execute_sync` and `Schema.execute` for fields that have a custom resolver but no field extensions.

The schema converter previously wrapped *every* non-basic field's resolver with a 4-deep extension chain (`extension_resolver` → `wrapped_get_result` → `_get_result` → `field.get_result`) even when the chain was empty, plus an `await_maybe` probe on every async resolver result. For fields with no field extensions that ceremony is wasted: the chain reduce-loop runs over an empty extension list and the probe always finds a coroutine on async fields.

This release adds a fast path to `from_resolver` that calls the resolver directly when `not field.extensions`. Behaviour is unchanged:

- `SchemaExtension.resolve` middlewares still run — they are wired one level above through graphql-core's `MiddlewareManager`.
- Subscription fields keep using `await_maybe` so async generators are passed through untouched.
- Fields that DO carry field extensions are unaffected; they keep the existing extension chain.

Measured impact on `schema.execute_sync` against a query that fans out across multiple sync resolvers (median, n=2000):

| query size       | before     | after      | speedup |
|------------------|------------|------------|---------|
| 10 items         | 1.00 ms    | 952 μs     | 1.05×   |
| 100 items        | 1.59 ms    | 1.52 ms    | 1.05×   |
| 1000 items       | 7.46 ms    | 7.25 ms    | 1.03×   |

Schemas with `SchemaExtension.resolve` middleware see the same proportional improvement. Schemas with field extensions see no regression on the extension-bearing fields, and the speedup on every other field still applies.
