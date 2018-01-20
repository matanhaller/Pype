"""Communication component of app.

Attributes:
    SERVER_ADDR (tuple): Server address info.
"""

# Imports
import socket
import select

from kivy.app import App

# Consts
SERVER_ADDR = ('10.0.0.17', 5050)


class Peer(object):

    """App peer class.
    
    Attributes:
        connections (list): Active connections.
        gui_event_conn (socket.socket): UDP connection with GUI component of app.
        server_conn (socket.socket): Connection with server.
    """

    def __init__(self):
        """Constructor method.
        """

        self.server_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.gui_event_conn = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.gui_event_conn.bind(('localhost', 0))
        self.connections = [self.server_conn, self.gui_event_conn]

    def get_gui_event_port(self):
    	"""Get random allocated port number of GUI event listener.
    	
    	Returns:
    	    int: The port number.
    	"""

    	return self.gui_event_conn.getsockname()[1]

    def run(self):
        """Peer mainloop method.
        """

        app = App.get_running_app()

        # Connecting to server
        try:
            self.server_conn.connect(SERVER_ADDR)
        except socket.error:
        	pass # (Change to something meaningful later on)

       	# Peer mainloop
       	while True:
       		rlst, wlst, xlst = select.select(*(self.connections * 3))
       		
