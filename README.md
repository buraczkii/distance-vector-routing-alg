#### distance-vector-routing-alg

## How to start up a network of routers
Routers are defined in `/config`. To start up all routers for a given network topology:
```bash
    python start_router.py config/network-{1..n}
```

### Router Initialization
When the router is started, a couple things happen. First, the router's local information is initialized. This includes the forwarding table, the router id, the list of neighbors, the current md5 hash of the config file, the initial distance vector, and the link costs. Second, 2 threads are started. The first thread periodically reads the router's config file and sends out copies of the router's distance vector to its neighbors. The second thread waits and listens for messages from the router's neighbors.

### Periodic closure
The router has a thread that does work periodically (default interval is every 5 seconds). The router keeps the hash result from the last time the config file was changed. This periodic thread compares the result of hashing the file to the stored hash value. If they are different, there has been some change in the config file and the forwarding table is recalculated. Then, copies of the router's distance vectors are sent to all its neighbors. Messages are sent to neighbors whether or not the config file or forwarding table has changed.

### Receiving messages from neighbors
The router has a thread that sits and listens for incoming messages. It extracts the neighbor's distance vector from the message received. The router contains copies of the most recently received distance vectors from its neighbors. If the distance vector received is different than the router's copy, the router updates its copy and recalculates the forwarding table. The router also keeps the most recent snapshot of the forwarding table. If the table's snapshot has changed after recalculating, the router updates the table snapshot and sends out copies of its distance vector to all its neighbors.

### Testing convergence times: bad news vs. good news
The router is able to detect changes in the config file (see **Periodic closure**). In addition, the router prints timestamped (microsecond accuracy) logs when significant events occur. It prints a log statement whenever a change is detected in the config file and whenever the table has been updated. Using this information, we know when a certain router detects a change (triggering update messages to all its neighbors) and when neighboring routers update their tables. The time of convergence is equal to ((time of last router's table update) - (time of config file change)). This calculation assumes one change occurs at a time and that routers in the network are given time to converge before the next change occurs.

##### Small network {1-3}
_Bad news_:

_Good news_:

##### Large network {1-10}
_Bad news_:

_Good news_:
