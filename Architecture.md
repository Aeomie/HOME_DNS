                 Client
        (PC, Phone, Raspberry Pi)
                     │
                     │ UDP/TCP 53
                     ▼
          ┌─────────────────────┐
          │   DNS Server         │
          │  (Python sockets)    │
          └──────────┬───────────┘
                     │
          Parse DNS Packet
                     │
          ┌──────────┴──────────┐
          │                     │
          ▼                     ▼
     Blocklist             Cache lookup
          │                     │
          │ blocked?            │ hit?
          ▼                     ▼
    Return NXDOMAIN      Return cached answer
                     │
                     ▼
             Upstream Resolver
          (1.1.1.1 / 9.9.9.9)
                     │
                     ▼
              Cache Response
                     │
                     ▼
             Return to client