"""DNS values represented as integer-compatible enumerations."""

from enum import IntEnum


class QueryType(IntEnum):
    """DNS record types that may appear in a question."""

    A = 1
    NS = 2
    MD = 3
    MF = 4
    CNAME = 5
    SOA = 6
    MB = 7
    MG = 8
    MR = 9
    NULL = 10
    WKS = 11
    PTR = 12
    HINFO = 13
    MINFO = 14
    MX = 15
    TXT = 16
    AAAA = 28
    SRV = 33
    HTTPS = 65


class QueryClass(IntEnum):
    """DNS classes that may appear in a question."""

    IN = 1
    CS = 2
    CH = 3
    HS = 4


# Compatibility aliases matching the terminology used in RFC 1035.
QTYPE = QueryType
QCLASS = QueryClass
