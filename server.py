"""Central server of app.
"""

# Imports
import logging
import socket
import select
import json
import logging
from sets import Set

from task import Task


class PypeServer(object):

    """App server class.

    Attributes:
        ADDR (tuple): Address to which the server is bound.
        conn_lst (list): List of all active connections.
        LISTEN_QUEUE_SIZE (int): Number of connections that server can queue
         before accepting (5 is typically enough). (static)
        logger (logging.Logger): Logging object.
        MAX_RECV_SIZE (int): Maximum number of bytes to receive at once.
        server_listener (socket.socket): Server socket. (static)
        task_lst (list): List of all pending tasks.
        user_dct (dict): Dictionary that maps username to connection with peer.
    """

    ADDR = ('0.0.0.0', 5050)
    LISTEN_QUEUE_SIZE = 5
    MAX_RECV_SIZE = 65536

    def __init__(self):
        """Constructor method.
        """

        # Cofiguring logger
        logging.basicConfig(
            format='[%(asctime)s]%(levelname)s: %(message)s',
            datefmt='%d-%m-%Y %H:%M:%S')
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        self.server_listener = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)
        self.server_listener.bind(PypeServer.ADDR)
        self.server_listener.listen(PypeServer.LISTEN_QUEUE_SIZE)
        self.conn_lst = []
        self.task_lst = []
        self.user_dct = {}

    def run(self):
        """Server mainloop method.
        """

        while True:
            read_set, write_set, err_set = select.select(
                self.conn_lst + [self.server_listener],
                *((self.conn_lst,) * 2))
            read_set, write_set, err_set = Set(
                read_set), Set(write_set), Set(err_set)

            # Handling readables
            self.handle_readables(read_set)

            # Handling tasks
            self.handle_tasks(write_set)

    def handle_readables(self, read_set):
        """Handles all readable connections in mainloop.

        Args:
            read_set (Set): Readable connections set.
        """

        for conn in read_set:
            # Handling new connections
            if conn is self.server_listener:
                new_conn, addr = self.server_listener.accept()
                self.conn_lst.append(new_conn)
                self.logger.info('{} connected.'.format(addr))
            else:
                if conn.type == socket.SOCK_STREAM:
                    data = conn.recv(PypeServer.MAX_RECV_SIZE)
                else:
                    data, addr = conn.recvfrom(PypeServer.MAX_RECV_SIZE)

                # Closing socket if disconnected
                if not data:
                    self.logger.info(
                        '{} disconnected.'.format(conn.getsockname()))
                    self.conn_lst.remove(conn)
                    conn.close()
                else:
                    # Parsing JSON data
                    data = json.loads(data)

                    # Join requests
                    if data['type'] == 'join':
                        # Checking if username already exists
                        if data['username'] in self.user_dct:
                            self.task_lst.append(Task(conn, {
                                'type': 'join',
                                'subtype': 'response',
                                'status': 'no'
                            }))
                        else:
                            self.task_lst.append(Task(conn, {
                                'type': 'join',
                                'subtype': 'response',
                                'status': 'ok'
                            }))

    def handle_tasks(self, write_set):
        """Iterates over tasks and sends messages if possible.

        Args:
            write_set (Set): Writable connections set.
        """

        for task in self.task_lst:
            if task.conn in write_set:
                task.send_msg()
                self.task_lst.remove(task)

# Running server
if __name__ == '__main__':
    PypeServer().run()
