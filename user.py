"""User class file.
"""

class User(Object):

	"""App user class.
	
	Attributes:
	    conn (socket.socket): Connection with user peer.
	    name (str): Username.
	"""
	
	def __init__(self, name, conn):
		"""Constructor method.
		
		Args:
		    name (str): Username.
		    conn (socket.socket): Connection with user peer.
		"""
		
		self.name = name
		self.conn = conn

