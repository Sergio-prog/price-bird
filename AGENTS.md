This is a hobby project, which I want to make as **working product** in future. This is replacement of @drops bot, which I don't really like to use.

# Instructions
- use `uv`
- try to create migrations through alembic cli. the reason is alembic creates correct names and ids for versions.
- create tests, but don't overcomplicate them. if the function obviously works fine, then u shouldn't create tests for it. i don't have 100% coverage goal.
- consider that i want to make it production ready. think about that.
- Default to production-minded choices: timeouts, retries, idempotency, rate-limit handling, and clear failure modes.