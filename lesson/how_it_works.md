# How the Bytes are Resolved

DNS messages are transmitted as bytes, not as ordinary text or Python
dictionaries. The DNS server reads those bytes according to the DNS wire
format defined by the protocol.

Conceptually, a DNS packet is arranged in this order:

```text
+-----------------------+
| Header: 12 bytes      |
+-----------------------+
| Question section      |
+-----------------------+
| Answer section        |
+-----------------------+
| Authority section     |
+-----------------------+
| Additional section    |
+-----------------------+
```

The sections after the header are variable length. A request and a response
can therefore be different sizes. The header is the fixed part that tells us
how to interpret the rest of the packet.

## Header Section Format

The DNS header is exactly 12 bytes, or 96 bits. It contains six fields, each
16 bits wide:

```text
16 bits = 2 bytes
6 fields x 2 bytes = 12 bytes
```

The fields are arranged as follows:

```text
Bytes 0-1     Transaction ID
Bytes 2-3     Flags
Bytes 4-5     QDCOUNT
Bytes 6-7     ANCOUNT
Bytes 8-9     NSCOUNT
Bytes 10-11   ARCOUNT
```

The fields mean:

| Field | Meaning |
|---|---|
| Transaction ID | Identifies this request and its matching response |
| Flags | Query/response state and other DNS behavior flags |
| QDCOUNT | Number of entries in the question section |
| ANCOUNT | Number of answer records |
| NSCOUNT | Number of authority records |
| ARCOUNT | Number of additional records |

In the first version of this project, the parser expects `QDCOUNT` to be
exactly 1. The other counts may be zero in a simple request.

The parser reads this fixed header with:

```python
struct.unpack("!HHHHHH", data[:12])
```

The format string has two parts:

```text
!       network byte order (big-endian)
H       unsigned 16-bit integer, which occupies 2 bytes
```

Therefore:

```text
!HHHHHH
6 unsigned 16-bit values
6 x 2 bytes
12 bytes total
```

`data[:12]` is a Python slice. It means "take bytes from the beginning of
`data` up to, but not including, index 12." The indexes are:

```text
0  1  2  3  4  5  6  7  8  9  10 11
|-------------- fixed 12-byte header --------------|
```

The rest of the DNS packet starts at byte 12:

```python
offset = 12
```

This is a 12-byte minimum, not a 12-byte maximum. A simple
`example.com` query contains:

```text
12-byte header
+ encoded domain name: 07 example 03 com 00
+ 2-byte query type: A
+ 2-byte query class: IN
```

The complete packet is therefore larger than 12 bytes.

For `example.com`, the domain is encoded as length-prefixed labels:

```text
07 example 03 com 00
```

The `07` says that the next label contains seven bytes, `example`. The `03`
says that the next label contains three bytes, `com`. The final `00` marks the
end of the domain name.

The header format is defined in RFC 1035, section 4.1.1:

https://www.rfc-editor.org/rfc/rfc1035#section-4.1.1

## Question Section Format

The question section describes what the DNS client wants to look up. A basic
question has three parts:

```text
QNAME + QTYPE + QCLASS
```

For a query for the IPv4 address of `example.com`, the packet after the
12-byte header is conceptually:

```text
07 example 03 com 00 00 01 00 01
```

This consists of:

```text
07 example 03 com 00   QNAME
00 01                   QTYPE: A
00 01                   QCLASS: IN
```

### QNAME: the encoded domain name

DNS does not send a domain name as one ordinary string. It sends each label
with a one-byte length prefix:

```text
example.com
```

becomes:

```text
07 example 03 com 00
```

The values mean:

```text
07       the next label contains 7 bytes
example  the first label
03       the next label contains 3 bytes
com      the second label
00       the end of the domain name
```

For `www.example.com`, the encoding is:

```text
03 www 07 example 03 com 00
```

The parser reads QNAME one label at a time:

```python
label_length = data[offset]
offset += 1
```

If `label_length` is zero, QNAME has ended. Otherwise, the parser must read
exactly that many bytes as the label.

### Why a label cannot be longer than 63 bytes

The first byte of each DNS label contains both length information and control
bits. In the ordinary label format, only six bits are available for the label
length:

```text
2 control bits + 6 length bits = 8 bits
```

Six bits can represent values from 0 through 63. Therefore, a normal DNS
label can contain at most 63 bytes. This is a limit for one label, not for the
entire domain name.

For example, these are separate labels:

```text
label1.label2.label3
```

The total domain can be much longer than 63 bytes, but no individual label
can exceed 63 bytes. DNS also imposes a separate maximum encoded domain name
length of 255 bytes, including length and terminating bytes.

Values above 63 in the first length byte are not ordinary label lengths. They
may indicate DNS name compression or a reserved/invalid encoding. The first
parser does not implement compression, so it rejects them instead of treating
the value as a normal label length.

### Preventing truncated labels

After reading the length byte, the parser advances `offset` by one. The label
then occupies this range:

```python
data[offset : offset + label_length]
```

Before slicing, the parser checks:

```python
if offset + label_length > len(data):
    raise DNSPacketError("domain label is truncated")
```

This asks:

> Does the requested label end beyond the bytes that actually arrived?

For example, if only five bytes remain but the length byte says that the next
label is seven bytes long, the packet is incomplete. Rejecting it prevents
the parser from silently accepting a partial domain name.

The earlier check:

```python
if offset >= len(data):
    raise DNSPacketError("domain name is truncated")
```

handles the case where the parser needs to read a length byte but there are no
bytes left at all.

### QTYPE: the requested record type

QTYPE is an unsigned 16-bit number describing the record the client wants:

| Number | Name | Meaning |
|---:|---|---|
| 1 | A | IPv4 address |
| 2 | NS | Name server |
| 5 | CNAME | Canonical name alias |
| 12 | PTR | Reverse DNS |
| 15 | MX | Mail server |
| 16 | TXT | Text record |
| 28 | AAAA | IPv6 address |
| 65 | HTTPS | HTTPS service binding |

For an A query:

```text
1 decimal = 0x0001 = 00 01
```

### QCLASS: the network class

QCLASS is another unsigned 16-bit number. Normal home DNS queries use:

```text
1 decimal = 0x0001 = 00 01
```

This is the `IN` class, meaning Internet.

Other defined classes include:

| Number | Name |
|---:|---|
| 1 | IN: Internet |
| 3 | CH: Chaos |
| 4 | HS: Hesiod |

### Reading QTYPE and QCLASS

After QNAME ends at the `00` byte, exactly four bytes are required:

```text
2 bytes QTYPE
2 bytes QCLASS
```

The parser checks this before unpacking:

```python
if offset + 4 > len(data):
    raise DNSPacketError("question type and class are truncated")
```

This asks:

> Are there at least four bytes remaining from the current offset to the end
> of the packet?

If there are fewer than four bytes, `struct.unpack("!HH", ...)` cannot read
the complete QTYPE and QCLASS fields. Checking first produces a clear DNS
packet error instead of allowing a lower-level unpacking exception.

The fields are then read with:

```python
query_type, query_class = struct.unpack(
    "!HH",
    data[offset : offset + 4],
)
```

Here each `H` consumes two bytes:

```text
!      network byte order / big-endian
H      QTYPE, unsigned 16-bit integer
H      QCLASS, unsigned 16-bit integer
```

### Complete question example

For `example.com A IN`, the question bytes are:

```text
07 65 78 61 6d 70 6c 65 03 63 6f 6d 00 00 01 00 01
```

Grouped into fields:

```text
07                         length of "example"
65 78 61 6d 70 6c 65       "example"
03                         length of "com"
63 6f 6d                   "com"
00                         end of QNAME
00 01                      QTYPE: A
00 01                      QCLASS: IN
```

The parser turns this into values similar to:

```python
DNSQuestion(
    domain="example.com",
    query_type=1,
    query_class=1,
)
```

The question section is a request, not the answer. It says:

```text
Please find the A record for example.com in the Internet class.
```

The response's answer section will contain the resulting address. The
question format is defined in RFC 1035, section 4.1.2:

https://www.rfc-editor.org/rfc/rfc1035#section-4.1.2
