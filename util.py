from datetime import datetime
import hashlib
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
    msg_bytelist.append(struct.pack('!H', id))
    msg_bytelist.append(struct.pack('!H', cost))
  return b''.join(msg_bytelist)


def extract_data(msg):
  """
  Given an update message, return a map of entries mapping the router id to its cost.
  """
  num_entries = struct.unpack("!H", msg[0:2])[0]
  distance_vector = {}
  index = 2
  for i in range(num_entries):
    entry = struct.unpack("!2H", msg[index:index+4])
    distance_vector[entry[0]] = entry[1]
    index += 4
  return distance_vector


def now():
  return datetime.now().strftime("[%a %m-%d-%y %H:%M:%S.%f] ")


def log(msg):
  print(now() + msg)


def get_md5_hash(file_name):
  """
  Returns the md5 hash of the file specified by the given file name.
  """
  md5 = hashlib.md5()
  with open(file_name, 'r') as f:
    while True:
      block = f.read(1024)
      if not block: break
      md5.update(str.encode(block))
  return md5.digest()