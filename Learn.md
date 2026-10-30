# Home DNS Filter Learning Plan

This project is a small DNS forwarding proxy with filtering and caching. It
teaches Python networking and binary protocols while remaining suitable for a
Raspberry Pi 4.

## First setup

From PowerShell:

```powershell
Set-Location C:\Projects\Servers\DNS_Project
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install pytest PyYAML
```

Use `python3 -m venv .venv` on Raspberry Pi Linux. Keep runtime dependencies
limited to the standard library and PyYAML. Pytest is a development
dependency.

## First working session

### 1. Create the package and tests

Create:

```text
dnsfilter/__init__.py
dnsfilter/server.py
dnsfilter/packet.py
tests/test_packet.py
```

Start with `packet.py`, not the socket loop. A packet parser can be tested
deterministically with byte strings, while socket behavior is harder to debug.

### 2. Learn the DNS request format

Read the relevant parts of RFC 1035:

- Section 4.1.1: header
- Section 4.1.2: question
- Section 4.1.3: resource records
- Section 4.1.4: name compression
- Section 4.2: transport

A normal request contains a 12-byte header followed by encoded domain labels
and a question type/class. Domain names are not sent as normal strings. For
`example.com`, the wire representation is:

```text
07 example 03 com 00
```

The first parser only needs to decode one question. It should reject
truncated labels and invalid lengths with a controlled packet error.

### 3. Write the first tests

Verify:

```text
valid bytes -> example.com, A, IN
mixed-case bytes -> normalized domain
truncated bytes -> a controlled packet error
unsupported question count -> a controlled packet error
```

Run:

```powershell
python -m pytest -q
```

Do not continue to the network layer while packet parsing is untested.

### 4. Add the UDP server

Implement `server.py` with a synchronous `socket.socket` using:

```python
socket.AF_INET
socket.SOCK_DGRAM
```

Bind to `127.0.0.1:5353`. The server should receive a datagram, call the
packet parser, and log the client address and question. Handle malformed input
and socket timeouts without terminating the server.

Test manually:

```powershell
nslookup example.com 127.0.0.1
```

At this milestone, `nslookup` may time out because the server only inspects
requests. The server log must show the domain.

### 5. Add forwarding

Implement `resolver.py` with this small contract:

```text
resolve(request_bytes) -> response_bytes
```

Send the original request to the configured upstream resolver and return its
response without rebuilding it. Add a timeout and try the next upstream when
the first fails. Test with a fake UDP upstream rather than depending on the
Internet.

### 6. Add blocking, then caching

Implement these in order:

1. `blocklist.py`: normalize and perform exact domain matching.
2. `cache.py`: store raw responses with TTL-based expiration.
3. `resolver.py`: block first, cache second, upstream third.

The request path becomes:

```text
parse
  -> blocked? return NXDOMAIN
  -> cache hit? return cached response
  -> upstream query
  -> cache response
  -> return response
```

Use an in-memory set and dictionary first. Do not add SQLite until the DNS
request path is stable.

## Configuration

Use PyYAML with a file like `config.example.yaml`:

```yaml
listen:
  host: 127.0.0.1
  port: 5353
upstream:
  - 1.1.1.1
  - 9.9.9.9
timeout_seconds: 2.0
cache:
  enabled: true
  max_entries: 5000
  max_ttl_seconds: 86400
blocklist:
  path: data/blocked.txt
```

Commit the example configuration, but do not commit machine-specific
configuration or secrets. Configuration errors should stop startup with a
useful message.

## Moving to Raspberry Pi

Develop on the computer first using port 5353. Once forwarding and blocking
tests pass:

1. Copy the project to the Pi.
2. Create the virtual environment there.
3. Run pytest on the Pi.
4. Bind to the Pi's LAN address, not `0.0.0.0`, during initial testing.
5. Configure one test client to use the Pi as its DNS server.
6. Only then create a systemd service and use port 53.

Port 53 normally requires root privileges. Prefer a narrowly scoped systemd
service instead of running development commands as root.

## References

- RFC 1035: https://www.rfc-editor.org/rfc/rfc1035
- Python sockets: https://docs.python.org/3/library/socket.html
- Python `struct`: https://docs.python.org/3/library/struct.html
- Python logging: https://docs.python.org/3/library/logging.html
- PyYAML: https://pyyaml.org/wiki/PyYAMLDocumentation
- pytest: https://docs.pytest.org/

## Rules for keeping the project manageable

- Implement one milestone at a time.
- Add a test before changing packet behavior.
- Keep packet parsing independent of sockets.
- Keep upstream forwarding independent of blocklist policy.
- Preserve synchronous behavior while adding asyncio.
- Never expose an unauthenticated public DNS resolver.
