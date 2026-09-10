# Upgrading Dependencies

Updating dependencies often is a good way to stay ahead of potential bugs and
security problems.

Using `uv` to upgrade dependencies is mostly a simple case of running:

```sh
uv lock --upgrade
uv sync --all-groups
```

This will upgrade your `uv.lock` file with the latest supported dependencies as
specified in the `pyproject.toml`.

If you only want to upgrade a single dependency you can use a command like:

```sh
uv lock --upgrade-package library
```

### CI/CD Packages

If any of the following packages: `black`, `ruff`, or `basepyright` are
updated, it is prudent to align their `prek` dependencies to be the same as the
new versions inside `prek.toml`.

## Potential Problems

Updating libraries may cause some type checking to fail. You will need to fix
these issues before `basedpyright` will be satisfied.

Some code and tests *can* fail after an update, so you should take the time to
make sure that they pass.
