# DNS Server Project

## Proposed Architecture

```
app/
├── main.py
├── network/
│   ├── udp_server.py
│   ├── tcp_server.py
│   └── client.py
├── dns/
│   ├── packet.py
│   ├── header.py
│   ├── question.py
│   ├── answer.py
│   ├── parser.py
│   ├── serializer.py
│   └── compression.py
├── resolver/
│   ├── upstream.py
│   ├── cache.py
│   ├── blocklist.py
│   └── resolver.py
├── storage/
│   ├── sqlite.py
│   └── blocklists.py
├── api/
│   └── fastapi.py
└── config/
    └── config.py
```

### 1. DNS Server

**Responsible for:**
- Listening on UDP port 53
- Receiving packets
- Sending replies

**Skills you'll learn:**
- Sockets
- UDP/TCP
- Binary protocols

**Python libraries:**
- `socket`
- `asyncio`
- (or `dnslib`)

> **Tip:** Avoid `dnslib` initially. Parsing packets yourself teaches you far more about how DNS works.

### 2. DNS Packet Parser

Convert bytes into structured DNS data:
- Transaction ID
- Flags
- Questions
- Answer count
- Domain
- Record type
- Class

**Example:**
```
google.com
A
IN
```

> This is where you'll really understand the DNS protocol.

### 3. Blocklist Engine

Store blocked domains in memory:

```python
blocked = {
    "doubleclick.net",
    "ads.google.com",
    "tracker.example"
}
```

**Lookup:** `O(1)` lookup time

**Future enhancements:**
- Wildcard matching
- Regex patterns
- Allowlists

### 4. Cache

Probably the most interesting component.

```python
cache = {
    "google.com": (
        dns_response,
        expiry_time
    )
}
```

**Workflow:**
```
Request → Cache? → Yes → Return
                 → No → Query upstream → Store → Return
```

**Future enhancements:**
- LRU cache
- TTL expiration
- Background cleanup

### 5. Upstream Resolver

If not blocked, forward the DNS packet to upstream servers:
- `1.1.1.1` (Cloudflare)
- `9.9.9.9` (Quad9)

Receive answer and return unchanged. Very simple.

### 6. Logging

Log every query with:
- Time
- Client
- Domain
- Allowed/Blocked status
- Cache hit
- Response time

**Eventually:** SQLite storage

### 7. Configuration

Example configuration:

```yaml
port: 53
upstream:
  - 1.1.1.1
  - 9.9.9.9
cache: true
cache_size: 50000
blocklists:
  - ads.txt
```

## Directory Structure

```
dnsfilter/
├── server.py
├── parser.py
├── resolver.py
├── cache.py
├── blocklist.py
├── config.py
├── logger.py
├── protocol/
│   ├── dns.py
│   ├── packet.py
│   └── records.py
├── data/
│   └── blocked.txt
├── tests/
└── main.py
```

Very modular.

## Development Roadmap

### Phase 1
Receive UDP packet → Print domain

Nothing else.

### Phase 2
Return a valid DNS response (no forwarding, no cache).

### Phase 3
Forward to Cloudflare.

**Congratulations!** You now have a DNS proxy.

### Phase 4
Add blocking (e.g., `ads.google.com` → `NXDOMAIN`).

### Phase 5
Add cache (huge performance improvement).

### Phase 6
SQLite logging.

### Phase 7
HTTP API with FastAPI:
- `GET /queries`
- `GET /stats`
- `POST /block`
- `DELETE /block`

### Phase 8
Web dashboard.

## Stretch Goals

Eventually, you could add:

- DNS-over-HTTPS (DoH)
- DNS-over-TLS (DoT)
- IPv6 (AAAA records)
- Wildcard matching
- Multiple upstream resolvers
- ECS (EDNS Client Subnet)
- Rate limiting
- Per-client blocklists
- Metrics endpoint (Prometheus format)
- DNSSEC validation
- Automatic blocklist updates
- Hot-reloading configuration