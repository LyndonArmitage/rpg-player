# Code Quality

Code quality of this project is maintained by the use of several tools as well
as writing unit and integration level tests.

## Tools

The primary code quality tools used are:

- `prek` for running tools before Git commits
- `pytest` for testing code
- `ruff` for linting code
- `basedpyright` for type checking code
- `black` for formatting code

### prek

[prek](https://prek.j178.dev/) is used to run other code quality tools and
scripts before a Git commit is created.

It can be manually run with:

```sh
uv run prek
```

### pytest

For more information on testing, including how to write and run tests see
`docs/testing.md`

### ruff

[ruff](https://docs.astral.sh/ruff/) is used as a linter for Python code.

It is run via:

```sh
uv run ruff check
```

### basedpyright

[basedpyright](https://docs.basedpyright.com/latest/) is a static type-checker
for Python code.

It can be run via:

```sh
uv run basedpyright
```

Its settings are managed in `pyrightconfig.json`.

When it highlights type-issues related to stubs, you can attempt to generate
stub files in the `typings/` directory by running the command:

```sh
uv run basedpyright --createstub library
```

This may still not be enough. In which case you can make careful use of
comments like:

```py
# pyright: ignore
```

Or you can edit the `pyrightconfig.json` file and add libraries to the
`allowedUntypedLibraries` array.

### black

[black](https://black.readthedocs.io/en/stable/) is a code formatter for
Python.

You can run `black` directly on a given file using:

```sh
uv run black path/to/file.py
```

All code including tests should be formatted.

When running `black`, you should only run one command at a time.
