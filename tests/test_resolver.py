import socket
import threading

from dns_filter.client import build_query
from dns_filter.resolver import UpstreamResolver


def test_resolver_forwards_request_to_upstream() -> None:
    received: list[bytes] = []
    ready = threading.Event()

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as upstream:
        upstream.bind(("127.0.0.1", 0))
        upstream_address = upstream.getsockname()

        def serve_once() -> None:
            ready.set()
            request, client_address = upstream.recvfrom(4096)
            received.append(request)
            upstream.sendto(request, client_address)

        thread = threading.Thread(target=serve_once)
        thread.start()
        ready.wait()

        _, request = build_query("example.com")
        resolver = UpstreamResolver(
            upstreams=("127.0.0.1",),
            port=upstream_address[1],
            timeout=1.0,
        )

        assert resolver.resolve(request) == request
        thread.join(timeout=1)

    assert received == [request]
