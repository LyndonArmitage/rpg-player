# Testing

Testing should be split up into unit testing and integration testing at the
repository level.

All tests should be in the `tests/` directory.

The `pytest` library is used for testing.

## Writing Tests

When creating integrations against external systems, like AWS services, REST
APIs or databases, you should create tests using mocks at the unit level as
well as more sophisticated mocks.

For example, if a piece of code communicates with DynamoDB, you should
implement tests that mock the calls to the DynamoDB client as one set of tests.
Then additionally (normally in a separate file) implement tests that use a
higher-level/more sophisticated mock service like `moto`.

Tests should be valid when linted with:

```py
uv run basedpyright tests
```

As well as `ruff` and formatted with `black`.

See `docs/code-quality.md` for more information on type checking.

## Running Tests

Tests should be run with `pytest` via `uv`.

To run all tests:

```sh
uv run pytest
```

You can get more details about the running tests by appending the verbose flags
`-v`, `-vv`, and `-vvv` to the end of the `uv run pytest` command.

```sh
uv run pytest -vvv
```

For more information on flags and environment variables you can run:

```sh
uv run pytest --help
```

### Run Specific Tests

You can run all the tests in a folder by suffixing it on the `uv run pytest`
command:

```sh
uv run ptest tests/example/
```

Individual test files can be run by suffixing the `uv run pytest` command:

```sh
uv run pytest tests/test_request_processor.py
```

You can run specific tests by specifying the exact tests to run by suffixing
the `uv run pytest` command:

```sh
uv run pytest tests/test_request_processor.py::test_checking_timeout
```

### Test Reports

Test coverage reports can be created via adding flags to the `uv run pytest`
commands.

For example:

```sh
uv run pytest \
  --cov=rpg_player \
  --cov-report term \
  --cov-report html \
  --junitxml=report.xml \
  --cov-report=xml:coverage.xml
```

Will create coverage reports in both the terminal output, a HTML output and an
XML output.

These reports can be read by various tools to determine how well tested the
code is.
