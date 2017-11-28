import os.path
import socket
import table
import threading
import time
import util

_CONFIG_UPDATE_INTERVAL_SEC = 5

_MAX_UPDATE_MSG_SIZE = 1024
_BASE_ID = 8000

INF = float("inf")

def _ToPort(router_id):
  return _BASE_ID + router_id

def _ToRouterId(port):
  return port - _BASE_ID


class Router:
  def __init__(self, config_filename):
    # ForwardingTable has 3 columns (DestinationId,NextHop,Cost). It's threadsafe.
    self._forwarding_table = table.ForwardingTable()
    self._forwarding_table_snapshot = []
    # Config file has router_id, neighbors, and link cost to reach them.
    self._config_filename = config_filename
    # The md5 hash value of the most recently read version of the config file
    self._config_file_hash = b''
    # The router's id
    self._router_id = None
    # Socket used to send/recv update messages (using UDP).
    self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Holds a list of my neighbor's id #s
    self._neighbors = []
    # Holds the values read in from the config file
    self._link_costs = {}
    # Holds the distance vector {(id:cost)*} for all nodes in the network the router is aware of
    self._distance_vector = {}
    # Holds the distance vectors {(id:distance_vector)*} of the routers immediate neighbors
    self._neighbors_dv = {}
    # Boolean value for the router to keep listening for messages, set to false for shutdown
    self._listening = True
    # Holds all known nodes in the network
    self._vertices = set()


  def start(self):
    """
    Starts the router. Initializes router details and starts 2 threads. One to periodically read
    the config file and send the router's distance vectors to its neighbors. The second to listen
    for update messages from neighbors and update the forwarding table as necessary.
    """
    self._config_updater = util.PeriodicClosure(
        self.periodic_read_config, _CONFIG_UPDATE_INTERVAL_SEC)
    listener_thread = threading.Thread(target=self.listen_to_neighbors, daemon=True)

    self._init_router()
    self._config_updater.start()
    listener_thread.start()

    try:
      while True:
        time.sleep(100)
    except KeyboardInterrupt:
      util.log("Shutting down now ...")


  def _init_router(self):
    """
    Reads the router's config file and initializes the router. Binds the socket to its port number.
    Initializes the router's id, config file hash, forwarding table, initial distance vector, list
    of neighbors, and list of vertices (nodes in the network).
     """
    router_id = self.load_config()
    self._socket.bind(('localhost', _ToPort(router_id)))
    self._router_id = router_id
    self._config_file_hash = util.get_md5_hash(self._config_filename)

    table_entries = [(id, id, cost) for id,cost in self._link_costs.items()]
    self._forwarding_table.reset(table_entries)
    util.log("TABLE INITIALIZED:\n"+ self._forwarding_table.__str__())
    self._forwarding_table_snapshot = self._forwarding_table.snapshot()
    self._distance_vector = self._link_costs

    neighbors = list(self._link_costs)
    neighbors.remove(self._router_id)
    self._neighbors = neighbors
    self._vertices.update(list(self._link_costs.keys()))
    #self.send_distance_vector_to_neighbors()


  def listen_to_neighbors(self):
    """
    Listens to immediate neighbors for messages containing their distance vectors. Recalculates the
    forwarding table if the neighbor's distance vector has changed. If the forwarding table changes,
    sends out the updated distance vector to its neighbors.
    """
    while self._listening:
      try:
        msg, addr = self._socket.recvfrom(_MAX_UPDATE_MSG_SIZE)
        neighbor_id = _ToRouterId(addr[1])
        dv = util.extract_data(msg)
        if not (dv == self._neighbors_dv.get(neighbor_id, None)):
          util.log("MSG RECEIVED: router#" + str(neighbor_id) + "'s updated dv: \t" + str(dv) + "\n")
          self._vertices.update(list(dv.keys()))
          self._neighbors_dv[neighbor_id] = dv
          self.recalculate_forwarding_table()

          new_snapshot = self._forwarding_table.snapshot()
          if not new_snapshot == self._forwarding_table_snapshot:
            util.log("TABLE UPDATED (due to change in router#" + str(neighbor_id)
                     + "'s dv):\n" + self._forwarding_table.__str__())
            self._forwarding_table_snapshot = new_snapshot
            self.send_distance_vector_to_neighbors()
        time.sleep(0.5)
      except socket.timeout:
        # If timeout happens, just continue.
        pass


  def stop(self):
    """
    Stop the periodic updater thread and send a message to the listener thread to stop listening.
    """
    self._listening = False
    if self._config_updater:
      self._config_updater.stop()


  def periodic_read_config(self):
    """
    Method for the periodic updater thread. If a change is detected in the config file, recalculates
    the forwarding table. Sends out the current copy of the distance vector to all neighbors.
    """
    current_file_hash = util.get_md5_hash(self._config_filename)
    if not current_file_hash == self._config_file_hash:
      util.log("Change detected in config file.")
      self.load_config()
      self._config_file_hash = current_file_hash
      self.recalculate_forwarding_table()
      new_snapshot = self._forwarding_table.snapshot()
      if not new_snapshot == self._forwarding_table_snapshot:
        util.log("TABLE UPDATED (config file change):\n" + self._forwarding_table.__str__())
        self._forwarding_table_snapshot = new_snapshot
    self.send_distance_vector_to_neighbors()


  def load_config(self):
    """
    Reads the router's config file and stores the link cost info locally.
    """
    assert os.path.isfile(self._config_filename)
    with open(self._config_filename, 'r') as f:
      router_id = int(f.readline().strip())

      self._link_costs = {router_id:0}
      while True:
        line = f.readline().strip()
        if not line: break
        neighbor, cost = line.split(",")
        self._link_costs[int(neighbor)] = int(cost)
    return router_id


  def send_distance_vector_to_neighbors(self):
    """
    Sends a copy of this router's current distance vector to all of it's neighbors.
    """
    msg_pkt = util.make_update_msg_pkt(self._distance_vector)
    for neighbor in self._neighbors:
      self._socket.sendto(msg_pkt, ('localhost', _ToPort(neighbor)))


  def recalculate_forwarding_table(self):
    """
    Recalculates the forwarding table based on the router's current link costs and the copies of
    distance vectors it has from its neighbors.
    """
    new_distance_vector = dict.fromkeys(self._vertices, INF) # default cost is infinity
    next_hop = dict.fromkeys(self._vertices, None) # default next_hop is None

    new_distance_vector.update(self._link_costs)
    next_hop.update({id:id for id,cost in self._link_costs.items()})

    for v in self._vertices:
      for neighbor_id, dv in self._neighbors_dv.items():
        new_cost = new_distance_vector[neighbor_id] + dv.get(v, INF)
        if new_cost < new_distance_vector[v]:
          new_distance_vector[v] = new_cost
          next_hop[v] = neighbor_id

    table_tuples = [((id, next_hop[id], cost)) for id,cost in new_distance_vector.items()]
    self._forwarding_table.reset(table_tuples)
    self._distance_vector = new_distance_vector
