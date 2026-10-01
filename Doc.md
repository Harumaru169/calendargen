# Publishing to PyPI (maintainers)

Publishing is triggered by pushing a `v<version>` tag, such as `v0.1.0`. GitHub Actions checks the tag against the version in `pyproject.toml`, runs the tests and Ruff, builds the distributions, and uploads them to PyPI through Trusted Publishing. Creating a GitHub Release is optional.

Before the first tag push, create a GitHub environment named `pypi`. In PyPI, register a Trusted Publisher (or a pending publisher for a new project) with owner `Harumaru169`, repository `calendargen`, workflow `publish.yml`, and environment `pypi`. No PyPI token needs to be stored in this repository or GitHub Secrets.

For the first release, confirm that the project version is `0.1.0`. For later releases, update it with `uv version <new-version>` and commit the resulting `pyproject.toml` and `uv.lock` changes. Run `make check` and `make build`, commit the release changes, and push them to `main`. Then tag that same commit and push the tag:

```sh
VERSION=0.1.0  # Use the version in pyproject.toml; change this for later releases.
git tag "v${VERSION}"
git push origin "v${VERSION}"
```

Check that the publish workflow succeeded and that the new version appears on PyPI. Each release needs a new version number.