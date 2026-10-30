# Domain Name System (DNS)

The Domain Name System, or DNS, translates human-readable domain names into
information that computers can use.

For example:

```text
example.com -> 93.184.216.34
```

The address is represented by an `A` record. DNS can also provide IPv6
addresses, mail servers, aliases, text records, and other information.

## Why DNS exists

Applications work with network addresses, but people prefer names. Without
DNS, users would need to remember an IP address for every website or service.
DNS provides a distributed naming system that lets clients ask:

```text
What information is associated with example.com?
```

The answer may come from a local cache, a home DNS server, an upstream
recursive resolver, or an authoritative name server.

## The basic lookup path

For this project, the simplified lookup path is:

```text
Application
    |
    v
Operating system resolver
    |
    v
Home DNS filter
    |
    +--> blocked? return a local blocking response
    |
    +--> cached? return the cached response
    |
    v
Upstream recursive resolver
    |
    v
DNS response returned to the client
```

The home DNS filter will initially be a forwarding proxy. It will inspect a
client's request, apply the blocklist, check its cache, and forward permitted
requests to an upstream resolver such as Cloudflare or Quad9.

It will not initially implement the entire DNS hierarchy or perform full
recursive resolution itself.

## DNS names are hierarchical

DNS names are organized as a tree:

```text
root
└── com
    └── example
        └── www
```

This represents the name:

```text
www.example.com.
```

Each part between dots is a label. The final dot represents the DNS root and
is often omitted in normal usage.

## DNS messages

DNS clients and servers exchange binary messages. A message can contain:

```text
Header
Question
Answer
Authority
Additional
```

The header is always 12 bytes. The other sections vary depending on whether
the message is a query or a response and how much information it contains.

A basic question asks for:

```text
QNAME + QTYPE + QCLASS
```

For example:

```text
example.com + A + IN
```

This means:

```text
Find the IPv4 address for example.com in the Internet class.
```

## DNS records and caching

DNS information is stored in resource records. Common examples include:

| Record | Purpose |
|---|---|
| `A` | IPv4 address |
| `AAAA` | IPv6 address |
| `CNAME` | Alias to another domain name |
| `MX` | Mail server |
| `NS` | Authoritative name server |
| `PTR` | Reverse DNS name |
| `TXT` | Text data |

Records have a TTL, or time to live. A resolver may cache a response until
its TTL expires. That is why this project's future cache will store both the
raw response and its expiration time.

## Recommended reading order

Read the lessons in this order:

1. [RFC 1034 summary](./rfc1034.md)  
   Learn the concepts: domain hierarchy, zones, delegation, resolvers,
   recursion, and caching.
2. [RFC 1035 summary](./rfc1035.md)  
   Learn the implementation: message sections, records, compression,
   transport, and response codes.
3. [Packet mechanics](../how_it_works.md)  
   Connect those concepts to the bytes parsed by this project.
4. [Socket reference](../sockets.md)  
   Learn how Python receives and sends DNS datagrams.

## Project scope

The first version of this project will:

- Receive DNS requests over IPv4 UDP.
- Parse one question.
- Log the requested domain and record type.
- Forward allowed requests to configured upstream resolvers.
- Block configured domains.
- Cache valid responses in memory.

Later versions may add TCP fallback, IPv6, asynchronous networking,
configuration reloads, statistics, and an administration interface.
