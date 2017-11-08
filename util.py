import threading
import math
import heapq


# Convenient class to run a function periodically in a separate
# thread.
class PeriodicClosure:
  def __init__(self, handler, interval_sec):
    self._handler = handler
    self._interval_sec = interval_sec
    self._timer = None

  def _timeout_handler(self):
    self._handler()
    self.start()

  def start(self):
    self._timer = threading.Timer(self._interval_sec, self._timeout_handler)
    self._timer.start()

  def stop(self):
    if self._timer:
      self._timer.cancel()


class Edge:
  def __init__(self, src, dest, weight):
    self.src = src
    self.dest = dest
    self.weight = weight

  def to_string(self):
    return "[src: " + str(self.src) + ", dest: " + str(self.dest) \
            + ", weight: " + str(self.weight) + "]"


def get_list_of_edges(src, entries):
  """
  Creates a list of edges from the given list of entries from the forwarding table. For each entry,
  adds an edge where the src is the given src, the destination is the router id in the entry, and
  the cost is the cost in the entry. Adds an additional edge representing the opposite direction.
  Assumes the following structure for entries:
      (router_id, next_hop, cost) - returned by ForwardingTable.snapshot()
  """
  edges = []
  for entry in entries:
    edge1 = Edge(src, entry[0], entry[2])
    edge2 = Edge(entry[0], src, entry[2])
    edges.append(edge1)
    edges.append(edge2)
  print([e.to_string() for e in edges])
  return edges


def bellman_ford(vertices, edges, src):
  """
  Runs the Bellman-Ford algorithm on a graph represented by the list of vertices and edges.
  Calculates the shortest path to each node from the given src node. Returns the populated
  distance and parent arrays.
  """
  distance = {i:math.inf for i in vertices}   # initiate distance to all nodes to infinity
  parent = {i:None for i in vertices}         # initiate parent of all nodes to None
  distance[src] = 0

  for i in range(len(vertices)):
    for e in edges:
        if distance[e.src] + e.weight < distance[e.dest]:
          distance[e.dest] = distance[e.src] + e.weight
          parent[e.dest] = e.src

  return distance,parent


# edges = [Edge(4,7,6), Edge(4,3,5), Edge(4,9,3), Edge(7,3,12), Edge(7,9,2), Edge(9,3,11),
#          Edge(7,4,6), Edge(3,4,5), Edge(9,4,3), Edge(3,7,12), Edge(9,7,2), Edge(3,9,11)]
# vertices = [4,7,3,9]
#
# bellman_ford(vertices, edges, 4)
# bellman_ford(vertices, edges, 3)

# src = 4
# entries = [(7,7,6), (9,9,3), (3,3,5)]
# k = get_list_of_edges(src, entries)
#
# for n in k:
#   print(n.to_string())