import os.path
import socket
import table
import threading
import time
import util

_CONFIG_UPDATE_INTERVAL_SEC = 5

_MAX_UPDATE_MSG_SIZE = 1024
_BASE_ID = 8000

def _ToPort(router_id):
  return _BASE_ID + router_id

def _ToRouterId(port):
  return port - _BASE_ID


class Router:
  def __init__(self, config_filename):
    # ForwardingTable has 3 columns (DestinationId,NextHop,Cost). It's threadsafe.
    self._forwarding_table = table.ForwardingTable()
    # Config file has router_id, neighbors, and link cost to reach them.
    self._config_filename = config_filename
    self._router_id = None
    # Socket used to send/recv update messages (using UDP).
    self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Holds a list of my neighbor's id #s
    self._neighbors = []
    # Holds the values read in from the config file
    self._link_costs = []
    # Holds the distance vector {(id:cost)*} for all nodes in the network the router is aware of
    self._distance_vector = {}
    # Holds the distance vectors {(id:distance_vector)*} of the routers immediate neighbors
    self._neighbors_dv = {}
    # Boolean value for the router to keep listening for messages, set to false for shutdown
    self._listening = True


  def start(self):
    # Start a periodic closure to update config.
    self._config_updater = util.PeriodicClosure(
        self.load_config, _CONFIG_UPDATE_INTERVAL_SEC) # TODO: add random increment? to avoid sync
    self._config_updater.start()

    threading.Thread(target=self.listen_to_neighbors, daemon=True).start()
    # TODO: how to prperly shutdown?
    time.sleep(80)
    print("times up")
    self.stop()


  def listen_to_neighbors(self):
    while self._listening:
      try:
        msg, addr = self._socket.recvfrom(_MAX_UPDATE_MSG_SIZE)
        neighbor_id = _ToRouterId(addr[1])
        dv = util.extract_data(msg)
        print("RECEIVED: from router id <" + str(neighbor_id) + "> msg: " + str(dv))
        if not (dv == self._neighbors_dv.get(neighbor_id, None)):
          print("RECEIVED: from router id <" + str(neighbor_id) + "> caused a change in the distance vector.")
          self._neighbors_dv[neighbor_id] = dv
          self.recalculate_forwarding_table()  # TODO: should I check if the dv has changed at all?
      except socket.timeout:
        # If timeout happens, just continue.
        pass



  def stop(self):
    self._listening = False
    if self._config_updater:
      self._config_updater.stop()
    # TODO: clean up other threads. is there anything else to clean up?


  def load_config(self):
    """
    Called by the periodic closure thread. Reads the router's config file, recalculates the
    forwarding table and sends out the router's updated distance vector to its immediate neighbors.
    """
    assert os.path.isfile(self._config_filename)
    with open(self._config_filename, 'r') as f:
      router_id = int(f.readline().strip())
      # Only set router_id when first initialize.
      if not self._router_id:
        self._socket.bind(('localhost', _ToPort(router_id)))
        self._router_id = router_id

      link_costs = [(router_id,0)]
      while True:
        line = f.readline().strip()
        if not line: break
        neighbor, cost = line.split(",")
        link_costs.append((int(neighbor), int(cost)))
    self._link_costs = dict(link_costs) # keep track of config values

    # If this is the first time the config is being read, initialize the forwarding table
    if self._forwarding_table.size() == 0: # TODO: better way to figure out you need to initialize the table?
      self.initialize_forwarding_table()
    else:
      self.recalculate_forwarding_table()
      self.send_distance_vector_to_neighbors()


  def send_distance_vector_to_neighbors(self):
    """
    Sends a copy of this router's distance vector to all of it's neighbors.
    """
    msg_pkt = util.make_update_msg_pkt(self._distance_vector)
    for neighbor in self._neighbors:
      self._socket.sendto(msg_pkt, ('localhost', _ToPort(neighbor)))


  def recalculate_forwarding_table(self):
    vertices = set(self._distance_vector.keys()) # grab all the vertices in the network
    for id,dv in self._neighbors_dv.items():
      vertices.update(dv.keys())
    #print("these are all the vertices: " + str(vertices))
    # TODO: is there a better way to get all vertices? Can I do something clever with my neighbors?

    # TODO: initializing the new distance vector, is there a better way?
    new_distance_vector = dict.fromkeys(vertices, float("-inf")) # default value is -infinity
    next_hop = dict.fromkeys(vertices, None) # default value is None

    for id, cost in self._link_costs.items():
      new_distance_vector[id] = cost
      next_hop[id] = id

    for v in vertices:
      for neighbor_id, dv in self._neighbors_dv.items():
        if self._link_costs[neighbor_id] + dv[v] < new_distance_vector[v]:
          print("updating a link cost. neighborId: " + str(neighbor_id) + " for dest. node: " + str(v) + " with new cost: " + str(self._link_costs[neighbor_id] + dv[v]))
          new_distance_vector[v] = self._link_costs[neighbor_id] + dv[v]
          next_hop[v] = neighbor_id

    # create tuples for the forwarding table
    table_tuples = [(self._router_id, self._router_id, 0)]
    for id,cost in new_distance_vector.items():
      table_tuples.append((id, next_hop[id], cost))

    self._forwarding_table.reset(table_tuples)
    print("Updated table:\n" + self._forwarding_table.__str__())
    # if the new distance vector is different than the current distance vector, send it out to neighbors
    if not (new_distance_vector == self._distance_vector):
      print("the distance vector has changed from: " + str(self._distance_vector) + " to: " + str(new_distance_vector))
      self._distance_vector = new_distance_vector
      self.send_distance_vector_to_neighbors()
    return


  def initialize_forwarding_table(self):
    """
    Initializes the forwarding table using only the values found inside the router's config file.
    Also populates this router's initial distance vector and its list of neighbors.
    """
    # create table entry tuples from the link costs & reset the forwarding table
    table_entries = [(id, id, cost) for id,cost in self._link_costs.items()]
    self._forwarding_table.reset(table_entries)
    print("INITIALIZED TABLE:\n" + self._forwarding_table.__str__())
    self._distance_vector = self._link_costs
    # keep a copy of router's immediate neighbors
    neighbors = list(self._link_costs)
    neighbors.remove(self._router_id)
    self._neighbors = neighbors
    self.send_distance_vector_to_neighbors()
    # TODO: start new thread here to listen to neighbors?
