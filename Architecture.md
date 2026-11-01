# Home DNS Filter Architecture

This project is a small DNS forwarding proxy with filtering and caching. It
should be lightweight enough for a Raspberry Pi 4 and structured so the
synchronous socket implementation can later be replaced with `asyncio`.

## Runtime flow

```text
Client (PC, phone, Raspberry Pi)
              |
              | UDP 5353 during development
              | UDP/TCP 53 in deployment
              v
     +-------------------------+
     | Python DNS filter       |
     |                         |
     | 1. Parse request        |
     | 2. Normalize question   |
     | 3. Check blocklist      |
     | 4. Check cache          |
     | 5. Forward upstream     |
     | 6. Return response      |
     +------------+------------+
                  |
                  v
        Cloudflare / Quad9
        1.1.1.1 / 9.9.9.9
```

During local development, bind to `127.0.0.1:5353`. This avoids administrator
privileges and prevents the process from accidentally becoming the network
DNS server. Bind to a configured LAN address and port 53 only after testing
on the Raspberry Pi.

## Initial directory structure

```text
dnsfilter/
├── __init__.py
├── server.py              # UDP socket and request loop
├── packet.py              # DNS header/question parsing and serialization
├── resolver.py            # Upstream forwarding and fallback policy
├── blocklist.py           # Exact normalized domain matching
├── cache.py               # In-memory TTL-aware response cache
├── config.py              # YAML loading and validation
└── logging_config.py      # Application logging
data/
├── blocked/   # every .txt file is a blocked list
└── allowed/   # every .txt file is a list of local records
tests/
├── test_packet.py
├── test_blocklist.py
└── test_cache.py
pyproject.toml
config.example.yaml
```

Keep the first version small. Split `packet.py` into more modules only when
the packet implementation becomes difficult to test or review.

## Component responsibilities

### DNS server

The server owns the socket and request loop. It receives bytes, delegates
processing, and sends response bytes. It should not contain blocklist or cache
policy.

### Packet module

Parse and serialize DNS headers and questions. Initially support one question
and safely reject truncated or malformed packets. Preserve unknown record
types when forwarding instead of trying to interpret every record.

### Resolver

Forward the original request to upstream resolvers. Try `1.1.1.1`, then
`9.9.9.9` after a timeout. Return `SERVFAIL` if every upstream fails.

### Blocklist

Normalize a domain by lowercasing it and removing its trailing dot. Begin with
exact matches from the `.txt` files in `data/blocked/`. Add allowlists and wildcard matching
only after exact matching is tested.

### Cache

Use an in-memory dictionary keyed by `(domain, query_type, query_class)`.
Store raw response bytes and an expiration time. Respect DNS TTLs, cap the
maximum TTL, limit the number of entries, and never cache malformed responses.

### Configuration

Load bind address, port, upstreams, timeouts, cache settings, and blocklist
path from YAML. Validate at startup and fail with a clear error.

## Development roadmap

### Phase 1: Receive and inspect

- Bind a synchronous UDP socket to `127.0.0.1:5353`.
- Receive raw DNS bytes.
- Parse one question: transaction ID, domain, type, and class.
- Log the query.
- Add tests for valid and malformed packets.

### Phase 2: Build valid responses

- Preserve the transaction ID.
- Create response headers and question sections.
- Return deliberate `NXDOMAIN` or `SERVFAIL` responses.
- Validate lengths, labels, and question counts.

### Phase 3: Forward upstream

- Forward the original request to `1.1.1.1`.
- Fall back to `9.9.9.9` after a timeout.
- Return the upstream response unchanged.
- Return `SERVFAIL` when all upstreams fail.

### Phase 4: Add exact blocking

- Normalize case and trailing dots before lookup.
- Load exact domains from the `.txt` files in `data/blocked/`.
- Return `NXDOMAIN` for blocked domains.

### Phase 5: Add the in-memory cache

- Key entries by domain, query type, and query class.
- Store raw responses with `expires_at`.
- Respect DNS TTLs with a configurable maximum.
- Limit cache size and remove expired entries.

### Phase 6: Add YAML configuration

- Load `config.example.yaml` through `config.py`.
- Configure bind address, port, upstreams, timeout, cache size, and blocklist.
- Keep safe defaults for local development.

### Phase 7: Improve concurrency

- Keep synchronous behavior as the reference implementation.
- Add an `asyncio` implementation after resolver and packet tests pass.
- Reuse the same packet, blocklist, cache, and configuration interfaces.
- Run the same pytest cases against both implementations where practical.

### Phase 8: Persistence and administration

- Add structured query logging first.
- Add SQLite only for history and statistics, not the DNS hot path.
- Add an authenticated, localhost-only API later.
- Build a dashboard only after the DNS service is reliable.

## Stretch goals

- IPv6 and AAAA records
- Wildcard matching
- Multiple upstream resolvers
- Rate limiting
- Per-client blocklists
- Prometheus metrics
- DNS-over-HTTPS and DNS-over-TLS
- DNSSEC validation
- Automatic blocklist updates
- Hot-reloading configuration

Do not expose this service as a public Internet resolver. Restrict listening
interfaces, protect administration endpoints, validate packet sizes, and add
rate limiting before exposing it beyond the home LAN.
