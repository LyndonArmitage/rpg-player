---
name: unit-test
description: >
  Create or modify unit tests in the tests/ directory. Use this when
  the user asks you to create, or modify tests. It may also be useful when
  dealing with test failures.
---
# Testing in This Repository

This repository uses `pytest` for its testing with tests stored in the `tests/`
directory.

Tests can be run with:

```sh
uv run pytest
```

You can run specific tests by specifying the file and optionally the specific
tests, for example:

```sh
# This following will run all tests in the given file:
uv run pytest tests/test_chat_message.py
# The following will run a single test:
uv run pytest tests/test_chat_message.py::test_messages_have_different_ids
```

You can also run multiple specific tests by separating their definitions with
spaces.

## Test Structure

Tests must be formatted with `black` for example:

```sh
uv run black tests/test_chat_message.py
````

Tests must be type checked with `basedpyright`:

```sh
uv run basedpyright tests/test_chat_message.py
```

Tests must be checked for issues with `ruff`:

```sh
uv run ruff check tests/test_chat_message.py
```

More details on testing can be found in the `docs/testing.md` file from the
root of this repository if needed.
