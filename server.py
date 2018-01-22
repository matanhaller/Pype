"""Central server of app.
"""

# Imports
import socket
import select

class PypeServer(object):

	ADDR = ('0.0.0.0', 5050)
	LISTEN_QUEUE_SIZE = 5
	MAX_RECV_SIZE = 65536


	def __init__(self):
		self.server_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.server_listener.bind(ADDR)
		self.server_listener.listen(LISTEN_QUEUE_SIZE)

	def run():
		while True:
