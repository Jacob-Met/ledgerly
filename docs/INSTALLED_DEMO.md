# Run the offline demo from an installed wheel

The Ledgerly wheel contains the existing demo and the four fictional emails it
uses. You can run the walkthrough from any working directory after installing
the wheel. Python 3.12 or newer is required; the core has no runtime dependencies.

## Use a received wheel

Create a fresh environment, install the wheel you received, and run the module:

```sh
python3.12 -m venv /absolute/path/new-ledgerly-demo
/absolute/path/new-ledgerly-demo/bin/python -m pip install --no-index --no-deps /absolute/path/ledgerly-0.1.0-py3-none-any.whl
/absolute/path/new-ledgerly-demo/bin/python -I -m ledgerly.demo
```

On Windows, use the environment's `Scripts\python.exe` instead of `bin/python`.
The `-I` option keeps the current directory and Python environment-path settings
out of module lookup, so this invocation uses the installed package.

The scripted walkthrough demonstrates extraction, draft creation, the blocked
unapproved-send check, then automatic mock approvals, a mock payment and reminder
drafting. For explicit decisions at each review, use:

```sh
/absolute/path/new-ledgerly-demo/bin/python -I -m ledgerly.demo --interactive
```

Only a `y` answer approves the shown action; other responses decline it. The
demonstration constructs the existing in-memory `SandboxMock` directly. It does
not contact PayPal, load credentials, send an actual invoice or move money. Each
process starts a new demonstration ledger; it is not a saved accounting ledger.

## Build a wheel from this checkout

Use the existing Python build environment and package metadata:

```sh
python -m pip wheel --no-deps . --wheel-dir /absolute/path/new-wheel-output
```

When setuptools and wheel are already installed locally, the offline equivalent
is `python -m pip wheel --no-deps --no-build-isolation --no-index . --wheel-dir /absolute/path/new-wheel-output`.
The ordinary editable setup in the root README continues to work.

## Fixture maintenance

`ledgerly/_demo_fixtures/` holds exact copies of only the four existing emails used
by the demo. Their canonical `fixtures/` counterparts remain in place for the
test and browser workflows. When one of those four examples changes, update its
packaged copy at the same time. `tests/test_demo_package_resources.py` verifies
the exact four-file set and byte equality, including UTF-8 characters and line
endings. The demo reads these resources through `importlib.resources`, using
explicit UTF-8 decoding.

The fixture-delivery change preserves the existing demo decision loops, Agent,
extractor, provider mock and financial behavior. The separate interactive EOF
contribution remains under its existing owner and is not included by this guide.
