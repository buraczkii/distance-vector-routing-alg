import struct
import threading

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


def make_update_msg_pkt(distance_vector):
  """
  Given a list of tuples representing link costs with the format (router_id, cost), create an
  msg packet containing the number of entries followed by each router and cost.
  """
  msg_bytelist = []
  entry_count = len(distance_vector)
  msg_bytelist.append(struct.pack('!H', entry_count))

  for id, cost in distance_vector.items():
    msg_bytelist.append(struct.pack('!H', id))  # The router ID
    msg_bytelist.append(struct.pack('!H', cost))  # The corresponding cost
  # print("msg byte list: " + str(msg_bytelist)) # TODO
  return b''.join(msg_bytelist)


def extract_data(msg):
  """
  Given a msg conforming to the following format: [# entries (n)][id 1][cost 1]...[id n][cost n],
  return a dictionary containing each entry where the key is the id and the value is the
  corresponding cost.
  """
  num_entries = struct.unpack("!H", msg[0:2])[0]

  distance_vector = {}
  index = 2
  for i in range(num_entries):
    entry = struct.unpack("!2H", msg[index:index+4])
    distance_vector[entry[0]] = entry[1]
    index += 4
  return distance_vector