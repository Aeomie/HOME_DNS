# Python sockets reference

This lesson covers the names used by Python's `socket` module and how they
apply to the DNS server.

## What a socket is

A socket is an operating-system communication endpoint. Python gives us an
object that can send and receive bytes through a network protocol.

```python
import socket

server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
```

The two arguments describe different things:

```text
socket.AF_INET       address family: IPv4
socket.SOCK_DGRAM    socket type: datagram, normally UDP
```

They are not interchangeable:

- `AF_INET` answers: "What format do the network addresses use?"
- `SOCK_DGRAM` answers: "How are bytes transported?"

## Address families

### `AF_INET`: IPv4

IPv4 addresses contain four decimal octets:

```text
127.0.0.1
192.168.1.25
1.1.1.1
```

An IPv4 address and port are represented by a two-item tuple:

```python
("127.0.0.1", 5353)
```

The DNS project currently uses:

```python
socket.AF_INET
```

### `AF_INET6`: IPv6

IPv6 addresses are longer hexadecimal addresses:

```text
::1
2001:db8::1
```

An IPv6 address and port are normally represented by a four-item tuple:

```python
("::1", 5353, 0, 0)
```

The extra values are the flow information and scope ID. A future IPv6 DNS
socket may look like:

```python
socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
```

`127.0.0.1` is the IPv4 loopback address. `::1` is its IPv6 equivalent.
`localhost` may resolve to either one depending on the operating system.

## Socket types

### `SOCK_DGRAM`: UDP datagrams

UDP is connectionless. Each call sends one independent datagram, and the
receiver receives one datagram at a time.

```python
udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
udp_socket.sendto(data, ("1.1.1.1", 53))
data, address = udp_socket.recvfrom(4096)
```

Important UDP properties:

- No connection handshake
- Each datagram keeps its message boundary
- Delivery is not guaranteed
- Datagrams may be lost, duplicated, or reordered
- There is no built-in retry
- `recvfrom()` returns both bytes and the sender address

DNS normally starts with UDP because DNS requests are small and quick.

### `SOCK_STREAM`: TCP byte streams

TCP is connection-oriented. It provides a reliable ordered stream of bytes,
not separate messages.

```python
tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
```

A TCP server normally uses:

```text
socket()
  -> bind()
  -> listen()
  -> accept()
  -> recv() / send()
```

A TCP client normally uses:

```text
socket()
  -> connect()
  -> send() / recv()
```

Important TCP properties:

- Connection handshake
- Reliable and ordered delivery
- No message boundaries
- `recv(4096)` may return fewer bytes than requested
- The application protocol must define message boundaries

DNS uses TCP as a fallback when a response is too large or a client requires
TCP. It is a later milestone for this project.

## Common socket operations

### `socket()`

Creates the endpoint:

```python
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
```

### `bind()`

Assigns a local address and port to a socket:

```python
sock.bind(("127.0.0.1", 5353))
```

The first tuple item is the local interface/address. The second is the port.

Common bind addresses:

```text
127.0.0.1  this computer only; useful for development
0.0.0.0    every IPv4 interface; avoid until access is intentionally controlled
192.168.1.20  one specific LAN interface
```

For this project, use `127.0.0.1:5353` first. Port 53 is the normal DNS port,
but it often requires administrator privileges.

### `sendto()` and `recvfrom()`

These are the usual UDP operations:

```python
sock.sendto(request_bytes, ("1.1.1.1", 53))
response_bytes, upstream_address = sock.recvfrom(4096)
```

`sendto()` takes bytes and a destination address. `recvfrom()` returns the
received bytes and the address that sent them.

### `send()` and `recv()`

These are normally used after a TCP connection has been established:

```python
connection.send(request_bytes)
response_bytes = connection.recv(4096)
```

Unlike UDP, TCP `recv(4096)` does not mean "receive one complete message".
It means "receive up to 4096 currently available bytes".

### `listen()` and `accept()`

These are TCP server operations:

```python
server_socket.listen()
connection, client_address = server_socket.accept()
```

`listen()` puts a bound TCP socket into server mode. `accept()` waits for a
client and returns a new connected socket. The original socket remains the
listening socket.

### `connect()`

TCP clients use `connect()`:

```python
sock.connect(("example.com", 443))
```

UDP can also use `connect()` in Python, but it does not create a TCP-style
handshake. It selects a default peer and allows `send()`/`recv()` instead of
`sendto()`/`recvfrom()`.

## Timeouts

Without a timeout, `recvfrom()` can wait forever:

```python
sock.settimeout(2.0)
```

After two seconds, Python raises `socket.timeout`. DNS resolvers need
timeouts so one unavailable upstream cannot block every client indefinitely.

```python
try:
    data, address = sock.recvfrom(4096)
except socket.timeout:
    # Try the next upstream or return SERVFAIL.
    pass
```

## DNS-specific socket values

```text
DNS client/server port: 53
Development port:       5353
Cloudflare DNS:         1.1.1.1:53
Quad9 DNS:              9.9.9.9:53
```

The number `4096` in:

```python
sock.recvfrom(4096)
```

is the maximum number of bytes Python will place in the receive buffer for
that call. It is a buffer size, not a DNS port or a protocol setting.

## Bytes versus addresses

Sockets send bytes, not Python strings or dictionaries:

```python
request = b"\x12\x34..."
sock.sendto(request, ("127.0.0.1", 5353))
```

Convert text to bytes explicitly:

```python
domain_bytes = "example.com".encode("ascii")
domain = domain_bytes.decode("ascii")
```

The DNS packet parser is responsible for interpreting those bytes. The socket
layer should only receive and send them.

## Resource cleanup

Use a context manager so the operating-system socket is closed:

```python
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
    sock.bind(("127.0.0.1", 5353))
    data, address = sock.recvfrom(4096)
```

When the block exits, Python closes the socket even if an exception occurs.

## Current project mapping

In `dns_filter/server.py`:

```python
socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
```

means:

```text
IPv4 + UDP
```

```python
server_socket.bind(("127.0.0.1", 5353))
```

means:

```text
listen on this computer's IPv4 loopback interface, port 5353
```

```python
data, client_address = server_socket.recvfrom(4096)
```

means:

```text
wait for one UDP datagram, reading at most 4096 bytes, and remember who sent it
```

The server currently only inspects the datagram. It does not send a response
yet. The next DNS milestone will use `sendto()` to return a valid response.

## Quick vocabulary

| Term | Meaning |
|---|---|
| Address family | Address format, such as IPv4 or IPv6 |
| Endpoint | Address plus port, such as `127.0.0.1:5353` |
| Port | Number identifying an application/service |
| Datagram | One independent UDP message |
| Stream | Ordered TCP byte sequence |
| Bind | Assign a local address and port |
| Peer | The remote endpoint |
| Loopback | This machine itself |
| Buffer | Temporary memory used for received bytes |
| Timeout | Maximum wait before an operation fails |
