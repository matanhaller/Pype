"""Central server of app.
"""

# Imports
import logging
import socket
import select
import json
import logging

from task import Task
from bidict import BiDict


class PypeServer(object):

    """App server class.

    Attributes:
        ADDR (tuple): Address to which the server is bound.
        conn_dct (dict): Dictionary mapping all active connections
         to their addresses.
        LISTEN_QUEUE_SIZE (int): Number of connections that server can queue
         before accepting (5 is typically enough). (static)
        logger (logging.Logger): Logging object.
        MAX_RECV_SIZE (int): Maximum number of bytes to receive at once.
        server_listener (socket.socket): Server socket. (static)
        task_lst (list): List of all pending tasks.
        user_dct (BiDict): Dictionary that maps username to connection with peer.
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
        self.conn_dct = {}
        self.task_lst = []
        self.user_dct = BiDict()

    def run(self):
        """Server mainloop method.
        """

        while True:
            read_lst, write_lst, err_lst = select.select(
                self.conn_dct.keys() + [self.server_listener],
                *((self.conn_dct.keys(),) * 2))

            # Handling readables
            self.handle_readables(read_lst)

            # Handling tasks
            self.handle_tasks(write_lst)

    def handle_readables(self, read_lst):
        """Handles all readable connections in mainloop.

        Args:
            read_lst (list): Readable connections list.
        """

        for conn in read_lst:
            # Handling new connections
            if conn is self.server_listener:
                new_conn, addr = self.server_listener.accept()
                self.conn_dct[new_conn] = addr
                self.logger.info('{} connected.'.format(addr))
            else:
                if conn.type == socket.SOCK_STREAM:
                    data = conn.recv(PypeServer.MAX_RECV_SIZE)
                else:
                    data, addr = conn.recvfrom(PypeServer.MAX_RECV_SIZE)

                # Closing socket if disconnected
                if not data:
                    if conn in self.user_dct:
                        # Notifying other users that user has left
                        for user_conn in self.user_dct:
                            if type(user_conn) is socket._socketobject \
                                    and user_conn is not conn:
                                self.task_lst.append(Task(user_conn, {
                                    'type': 'user_leave',
                                    'username': self.user_dct[user_conn]
                                }))
                        self.logger.info(
                            '{} left.'.format(self.user_dct[conn]))
                        del self.user_dct[conn]

                    self.logger.info(
                        '{} disconnected.'.format(self.conn_dct[conn]))
                    del self.conn_dct[conn]
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
                            self.user_dct[conn] = data['username']
                            self.task_lst.append(Task(conn, {
                                'type': 'join',
                                'subtype': 'response',
                                'status': 'ok'
                            }))
                            self.logger.info(
                                '{} joined.'.format(data['username']))
                            # Notifying other users that a new user has joined
                            for user_conn in self.user_dct:
                                if type(user_conn) is socket._socketobject \
                                        and user_conn is not conn:
                                    self.task_lst.append(Task(user_conn, {
                                        'type': 'user_join',
                                        'username': data['username']
                                    }))

    def handle_tasks(self, write_lst):
        """Iterates over tasks and sends messages if possible.

        Args:
            write_lst (list): Writable connections list.
        """

        for task in self.task_lst:
            if task.conn in write_lst:
                task.send_msg()
                self.task_lst.remove(task)

# Running server
if __name__ == '__main__':
    PypeServer().run()
