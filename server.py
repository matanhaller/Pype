"""Central server of app.
"""

# Imports
import logging
import socket
import select
from sets import Set


class PypeServer(object):

	"""App server class.

	Attributes:
	    ADDR (tuple): Address to which the server is bound.
	    connection_lst (list): List of all active connections.
	    LISTEN_QUEUE_SIZE (int): Number of connections that server can queue
	     before accepting (5 is typically enough).
	    MAX_RECV_SIZE (int): Maximum number of bytes to receive at once.
	    server_listener (socket.socket): Server socket.
	    task_lst (list): List of all pending tasks.
	"""

	ADDR = ('0.0.0.0', 5050)
	LISTEN_QUEUE_SIZE = 5
	MAX_RECV_SIZE = 65536

	def __init__(self):
		"""Constructor method.
		"""

		self.server_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.server_listener.bind(PypeServer.ADDR)
		self.server_listener.listen(PypeServer.LISTEN_QUEUE_SIZE)
		self.connection_lst = []
		self.task_lst = []

	def run():
		"""Server mainloop method.
		"""

		while True:
			read_set, write_set, err_set = select.select(
			    self.connection_lst + [self.server_listener],
			    *((self.connection_lst,) * 2))
            read_set, write_set, err_set = set(read_set),
             	set(write_set), set(err_set)

    def handle_readables(self, read_set):
        """Handles all readable connections in mainloop.

        Args:
            read_set (Set): Readable connections set.
        """

        for conn in read_set:
        	# Handling new connections
        	if conn is self.server_listener:
        		new_conn, addr = self.server_listener.accept()
        		self.connection_lst.append(new_conn)
        	else:
        		if self.conn.type == socket.SOCK_STREAM:
        			data = conn.recvfrom(PypeServer.MAX_RECV_SIZE)
        		else:
            		data, addr = conn.recvfrom(PypeServer.MAX_RECV_SIZE)

	            # Parsing JSON data
	            data = json.loads(data)

	            # Join requests
	            if data['type'] == 'join':
	                pass
