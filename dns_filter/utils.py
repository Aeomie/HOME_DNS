"""Shared DNS data models and utility types."""

from dataclasses import dataclass


@dataclass(frozen=True)
class QNAME:
    """A decoded DNS name and its wire-format bytes."""

    name: str
    wire_bytes: bytes

    def __str__(self) -> str:
        return self.name

@dataclass(frozen=True)
class DNSQuestion:
    transaction_id: int
    domain: str
    query_type: int
    query_class: int

@dataclass(frozen=True)
class DNSResponse:
    transaction_id: int
    flags: int
    question_count: int
    answers: int
    authority: int
    additional: int