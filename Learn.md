For DNS, the foundational document is RFC 1035. It describes:

The DNS packet format
UDP and TCP transport
Record types (A, AAAA, MX, etc.)
Domain name encoding
Response codes
Name compression

When you implement your server, you're effectively writing software that follows RFC 1035.


STEP 1 :
(*Note*) TCP almost always uses SOCK_STREAM and UDP uses SOCK_DGRAM.
INET is IPV4 & INET6 is IPV6.

Start by making a udp server

Learn about Sockets : https://docs.python.org/3/library/socket.html
https://docs.oracle.com/cd/E19120-01/open.solaris/817-4415/sockets-18552/index.html
