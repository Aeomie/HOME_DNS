"""Small DNS question parser used by the first server milestone."""

from dataclasses import dataclass
import struct
from .exceptions import DNSPacketError
from .utils import DNSQuestion, DNSResponse



def parse_header(data: bytes) -> DNSQuestion:
    """Parse exactly one uncompressed DNS question from *data*.
    DNS Header is of :
    Bytes 0-1     Transaction ID
    Bytes 2-3     Flags
    Bytes 4-5     QDCOUNT
    Bytes 6-7     ANCOUNT
    Bytes 8-9     NSCOUNT
    Bytes 10-11   ARCOUNT

    Takes : 
    data : bytes : The raw DNS request packet
    returns : DNSQuestion : The parsed DNS question
    raises : DNSPacketError : If the packet is malformed or unsupported
    """

    if len(data) < 12:
        raise DNSPacketError("DNS header is truncated")

    transaction_id, _flags, question_count, _answers, _authority, _additional = (
        struct.unpack("!HHHHHH", data[:12])
    )

    """ Might change later, for now it only accepts one question"""
    if question_count != 1:
        raise DNSPacketError("request must contain exactly one question")

    return DNSResponse(
        transaction_id=transaction_id,
        flags=_flags,
        question_count=question_count,
        answers=_answers,
        authority=_authority,
        additional=_additional,
    )


def parse_question(data: bytes, DNSResponse: DNSResponse) -> DNSQuestion:
    """Parse exactly one uncompressed DNS question from *data*.
    This function is a wrapper around parse_header that returns a DNSQuestion object.

    !H means ""unpack 2 bytes as an unsigned short in network byte order (big-endian)"
    !HHHHHH means "unpack 12 bytes as 6 unsigned shorts in network
    """
    offset = 12     # Header is 12 bytes long
    labels: list[str] = []
    while True:
        if offset >= len(data):
            raise DNSPacketError("domain name is truncated")

        label_length = data[offset]
        offset += 1
        if label_length == 0:
            break
        if label_length > 63:
            raise DNSPacketError("compressed or invalid domain labels are unsupported")
        if offset + label_length > len(data):
            raise DNSPacketError("domain label is truncated")

        # Becausee the label is a slice of bytes, we need to decode it to a string
        label = data[offset : offset + label_length] 
        try:
            labels.append(label.decode("ascii"))
        except UnicodeDecodeError as exc:
            raise DNSPacketError("domain label is not valid ASCII") from exc
        offset += label_length

    # Because the question type and class are 2 bytes each, we need to check if there are at least 4 bytes left in the data
    if offset + 4 > len(data):
        raise DNSPacketError("question type and class are truncated")

    # Unpacks it & splits them into two , two bytes things so perfect for our needs
    query_type, query_class = struct.unpack("!HH", data[offset : offset + 4])
    domain = ".".join(labels).lower().rstrip(".")   # Constructs the URL from the labels

    if not domain:
        raise DNSPacketError("root-only queries are not supported yet")

    return DNSQuestion(
        transaction_id=DNSResponse.transaction_id,
        domain=domain,
        query_type=query_type,
        query_class=query_class,
    )


def build_nxdomain_response(request: bytes) -> bytes:
    """Build an NXDOMAIN response containing the original question."""
    if len(request) < 12:
        raise DNSPacketError("DNS header is truncated")

    parse_header(request)
    offset = 12
    while True:
        if offset >= len(request):
            raise DNSPacketError("domain name is truncated")
        label_length = request[offset]
        offset += 1
        if label_length == 0:
            break
        if label_length > 63:
            raise DNSPacketError("compressed domain labels are unsupported")
        if offset + label_length > len(request):
            raise DNSPacketError("domain label is truncated")
        offset += label_length

    if offset + 4 > len(request):
        raise DNSPacketError("question type and class are truncated")

    transaction_id, flags = struct.unpack("!HH", request[:4])
    response_flags = (flags | 0x8000) & 0xFFF3
    response_flags |= 0x0003
    header = struct.pack("!HHHHHH", transaction_id, response_flags, 1, 0, 0, 0)
    return header + request[12 : offset + 4]


def build_a_response(request: bytes, address: str, ttl: int = 60) -> bytes:
    """Build an authoritative response for an IPv4 local record."""
    if len(request) < 12:
        raise DNSPacketError("DNS header is truncated")

    parse_header(request)
    offset = 12
    while True:
        if offset >= len(request):
            raise DNSPacketError("domain name is truncated")
        label_length = request[offset]
        offset += 1
        if label_length == 0:
            break
        if label_length > 63:
            raise DNSPacketError("compressed domain labels are unsupported")
        if offset + label_length > len(request):
            raise DNSPacketError("domain label is truncated")
        offset += label_length

    if offset + 4 > len(request):
        raise DNSPacketError("question type and class are truncated")

    query_type, query_class = struct.unpack("!HH", request[offset : offset + 4])
    if query_type != 1 or query_class != 1:
        raise DNSPacketError("local records currently support A IN queries only")

    transaction_id, flags = struct.unpack("!HH", request[:4])
    response_flags = (flags | 0x8000 | 0x0400) & 0xFFF0
    response_flags |= 0x0000
    header = struct.pack("!HHHHHH", transaction_id, response_flags, 1, 1, 0, 0)
    answer = struct.pack(
        "!HHHIH4s",
        0xC00C,
        1,
        1,
        ttl,
        4,
        bytes(int(part) for part in address.split(".")),
    )
    return header + request[12 : offset + 4] + answer
