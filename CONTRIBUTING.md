# Contributing to chaosblade-exec-python

Welcome to ChaosBlade world! Here is a list of contributing guidelines for you. If you find something incorrect or missing, please submit an issue or PR to fix it.

## What Can You Do

Every action to make the project better is encouraged. On GitHub, every improvement can be made via a PR (pull request).

* If you find a typo, try to fix it!
* If you find a bug, try to fix it!
* If you find some redundant codes, try to remove them!
* If you find some test cases missing, try to add them!
* If you could enhance a feature, please **DO NOT** hesitate!
* If you find code implicit, try to add comments to make it clear!
* If you find code ugly, try to refactor that!
* If you can help to improve documents, it could not be better!
* If you find the document incorrect, just do it and fix that!
* ...

Actually, it is impossible to list them completely. Just remember one principle:

**WE ARE LOOKING FORWARD TO ANY PR FROM YOU.**

## Contributing

### Preparation

Before you contribute, you need to register a GitHub ID. Prepare the following environment:

* Python 3.9+
* pip (latest version)
* git

### Workflow

We use the `master` branch as the development branch, which indicates that this is an unstable branch.

Here are the workflow for contributors:

1. Fork to your own
2. Clone fork to the local repository
3. Create a new branch and work on it
4. Keep your branch in sync
5. Commit your changes (make sure your commit message is concise)
6. Push your commits to your forked repository
7. Create a pull request

Please follow [the pull request template](./.github/PULL_REQUEST_TEMPLATE.md).
Please make sure the PR has a corresponding issue.

After creating a PR, one or more reviewers will be assigned to the pull request.
The reviewers will review the code.

Before merging a PR, squash any fix review feedback, typo, merged, and rebased sorts of commits.
The final commit message should be clear and concise.

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/chaosblade-io/chaosblade-exec-python.git
cd chaosblade-exec-python

# Install in development mode
pip install -e ".[dev]"

# Run tests to verify setup
make test
```

### Code Style

We follow standard Python coding conventions:

* **PEP 8** — Use [Black](https://github.com/psf/black) for auto-formatting (line length: 100)
* **Type hints** — All public APIs must have type annotations
* **Docstrings** — Use Google-style docstrings for modules, classes, and public methods
* **Imports** — Use [isort](https://github.com/PyCQA/isort) for import ordering

### Commit Rules

#### Commit Message

Commit message should help reviewers better understand the purpose of submitted PR. We advocate the following commit message types:

* `feat`: A new feature
* `fix`: A bug fix
* `docs`: Documentation only changes
* `style`: Changes that do not affect the meaning of the code
* `refactor`: A code change that neither fixes a bug nor adds a feature
* `perf`: A code change that improves performance
* `test`: Adding missing or correcting existing tests
* `chore`: Changes to the build process or auxiliary tools

We discourage contributors from committing messages like:

* ~~fix bug~~
* ~~update~~
* ~~add doc~~

If you get lost, please see [How to Write a Git Commit Message](http://chris.beams.io/posts/git-commit/) for a start.

#### Commit Content

Contents in one single commit should be complete and reviewable, and can pass CI independently. Avoid:

* Very large changes in a single commit
* Incomplete or non-compilable commits

### Pull Request

We use [GitHub Issues](https://github.com/chaosblade-io/chaosblade-exec-python/issues) and [Pull Requests](https://github.com/chaosblade-io/chaosblade-exec-python/pulls) for trackers.

If you find a typo in the document, find a bug in code, or want new features, or want to give suggestions, you can [open an issue on GitHub](https://github.com/chaosblade-io/chaosblade-exec-python/issues/new) to report it.

If you want to contribute, please follow the [contribution workflow](#workflow) and create a new pull request.
If your PR contains large changes, e.g. component refactor or new components, please write detailed documents about its design and usage.

Note that a single PR should not be too large. If heavy changes are required, it's better to separate the changes into a few individual PRs.

### Code Review

All code should be well reviewed by one or more committers. Some principles:

- **Readability**: Important code should be well-documented. Comply with our code style.
- **Elegance**: New functions, classes or components should be well designed.
- **Testability**: Important code should be well-tested (high unit test coverage).

### Running Tests

```bash
# Run all tests
make test

# Run tests with coverage
make test-cov

# Run a specific test file
pytest tests/test_injector.py -v
```

## Community

### Contact Us

#### Mailing list
If you have any questions or advice, please contact chaosblade.io.01@gmail.com.

#### DingDing
You can search the ID: `23177705` in DingDing (钉钉) app to join the ChaosBlade group.

#### Slack
https://chaosblade-io.slack.com/archives/CRTNFPWE8

## Others

### Code of Conduct

See details of [CONTRIBUTOR COVENANT CODE OF CONDUCT](CODE_OF_CONDUCT.md).

### Sign Your Work

The sign-off is a simple line at the end of the explanation for the patch, which certifies that you wrote it or otherwise have the right to pass it on as an open-source patch.

Then you just add a line to every git commit message:

```
Signed-off-by: Joe Smith <joe.smith@email.com>
```

Use your real name (sorry, no pseudonyms or anonymous contributions.)

If you set your `user.name` and `user.email` git configs, you can sign your commit automatically with `git commit -s`.
