# Running the DNS Server

This guide explains how to run the current milestone of the project. The
server receives DNS request packets, parses the question, forwards the
original request to an upstream resolver, and returns the upstream response.
Local allowlists, blocklists, and caching are not implemented yet.

## What Poetry does

Poetry manages this Python project. It uses:

```text
pyproject.toml  project metadata and dependency declarations
poetry.lock     exact dependency versions selected for the project
.venv/          the project's isolated virtual environment
```

Poetry keeps this project's packages separate from packages installed for
other Python projects. For this project, the runtime dependency is PyYAML and
pytest is used for development tests.

The command:

```powershell
py -m poetry install
```

creates or updates the project's virtual environment, installs the versions
recorded in `poetry.lock`, and installs the local `dns-filter` package.

The command:

```powershell
py -m poetry run <command>
```

runs a command inside that environment without requiring you to activate it
manually. This is the recommended way to run the project:

```powershell
py -m poetry run pytest -q
py -m poetry run python -m dns_filter.server
```

`py -m poetry` is used here because it works even if Poetry's executable is
not on the Windows `PATH`. If `poetry` is available directly, these are
equivalent:

```powershell
poetry run pytest -q
poetry run python -m dns_filter.server
```

## One-time setup

Open PowerShell and move to the project root:

```powershell
Set-Location C:\Projects\Servers\DNS_Project
```

Install the project environment:

```powershell
py -m poetry install
```

Verify the environment:

```powershell
py -m poetry env info
```

Run the tests:

```powershell
py -m poetry run pytest -q
```

If the test command succeeds, the project environment is ready.

## Start `server.py`

From the project root, run the module through Poetry:

```powershell
py -m poetry run python -m dns_filter.server
```

The `-m dns_filter.server` form is important. It runs `server.py` as part of
the `dns_filter` package, so its relative imports work correctly:

```python
from .packet import DNSPacketError, parse_question, parse_header
```

Running the file directly like this is not recommended:

```powershell
python dns_filter\server.py
```

When a file uses package-relative imports such as `.packet`, Python may not
know that the file belongs to the `dns_filter` package when it is run
directly.

By default, the server listens on:

```text
127.0.0.1:1053
```

You should see a log message similar to:

```text
INFO listening for DNS requests on 127.0.0.1:1053
```

The server keeps running and waits for UDP datagrams. Leave this PowerShell
window open.

## Change the address or port

The server accepts command-line options:

```powershell
py -m poetry run python -m dns_filter.server --host 127.0.0.1 --port 1053
```

To see the available options:

```powershell
py -m poetry run python -m dns_filter.server --help
```

Use port `1053` during development. Port `53` is the standard DNS port, but
it commonly requires administrator privileges and should only be used after
the server has been tested carefully.

## Send a test request

Open a second PowerShell window. Keep the server running in the first one.
Run:

```powershell
nslookup example.com 127.0.0.1
```

The server now forwards the request to `1.1.1.1` and falls back to `8.8.8.8`.
The important result is that the server logs the received request and returns
the upstream response:
for example:

```text
INFO DNS query client=127.0.0.1 domain=example.com type=1 class=1
```

The values mean:

```text
type=1   A record, an IPv4 address
class=1  IN, the Internet class
```

## Use the project client

The project also includes a small client that sends a DNS request directly to
the configured UDP address. This avoids relying on `nslookup` while the server
is still only an inspector:

```powershell
py -m poetry run python -m dns_filter.client example.com --port 1053
```

The client should print something similar to:

```text
sent 29 bytes for example.com to 127.0.0.1:1053 (transaction ID 4660)
```

The transaction ID is randomly generated, so its number will differ each
time. In the server terminal, you should see:

```text
INFO received UDP datagram from 127.0.0.1:<client-port> (29 bytes)
INFO DNS query client=127.0.0.1 domain=example.com type=1 class=1
```

The client only waits for a response when `--wait` is supplied:

```powershell
py -m poetry run python -m dns_filter.client example.com --port 1053 --wait
```

If both upstream resolvers are unavailable, `--wait` reports a timeout because
the server cannot produce a response. That is an upstream/network failure,
not expected normal behavior.

You can also ask for another record type:

```powershell
nslookup -type=AAAA example.com 127.0.0.1
```

That should produce a log with `type=28`, which is the DNS `AAAA` record
type.

## Stop the server

Return to the PowerShell window running the server and press:

```text
Ctrl+C
```

This sends an interrupt to the Python process. The socket is inside a
`with` block, so Python closes it when the server exits.

## Run the parser tests

The server and parser are separate concerns. You can test packet parsing
without starting a socket:

```powershell
py -m poetry run pytest -q
```

This is useful because the tests are deterministic and do not depend on
another process, a network interface, or an external DNS service.

## Current limitations

The current server:

- Uses IPv4 UDP.
- Listens on port `1053`.
- Parses one DNS question.
- Logs valid queries.
- Logs and ignores malformed packets.
- Forwards requests to `1.1.1.1`, then `8.8.8.8` as fallback.
- Returns successful upstream responses to the client.
- Does not have local allowlist or blocklist policy yet.
- Does not block domains yet.
- Does not cache responses yet.
- Includes a project client for sending test requests.

The next implementation milestone is to create a valid DNS response and send
it back with `sendto()`. After that, the resolver can forward requests to an
upstream DNS server.

## Useful project commands

```powershell
# Install or synchronize the environment
py -m poetry install

# Run tests
py -m poetry run pytest -q

# Start the server
py -m poetry run python -m dns_filter.server

# Inspect the Poetry environment
py -m poetry env info

# Display project dependency information
py -m poetry show
```
