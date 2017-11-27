# distance-vector-routing-alg

### How to start up routers
Routers are defined in `/config`. To start up all routers for a given network topology:
```bash
    python start_router.py config/network-{1..n}
```

- can talk about how periodically sending out messages with random seed can prevent oscillation (textbook)