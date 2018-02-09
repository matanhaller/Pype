"""Central server of app.
"""

# Imports
import logging
import socket
import select
import json
import logging

from task import Task
from user import User


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
        user_dct (dict): Dictionary that maps username to user object.
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
        self.user_dct = {}

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
                    user = self.get_user_from_conn(conn)
                    if user:
                        self.logger.info('{} left.'.format(user.name))
                        del self.user_dct[user.name]

                        # Notifying other users that user has left
                        for username in self.user_dct:
                            self.task_lst.append(Task(self.user_dct[username].conn, {
                                'type': 'user',
                                'subtype': 'leave',
                                'username': user.name
                            }))

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
                            self.user_dct[data['username']] = User(
                                data['username'], conn)
                            user_info_lst = []
                            for username in self.user_dct:
                                if username != data['username']:
                                    user_info_lst.append(
                                        [username, self.user_dct[username].status])
                            self.task_lst.append(Task(conn, {
                                'type': 'join',
                                'subtype': 'response',
                                'status': 'ok',
                                'username': data['username'],
                                'user_lst': user_info_lst
                            }))
                            self.logger.info(
                                '{} joined.'.format(data['username']))
                            # Notifying other users that a new user has joined
                            for username in self.user_dct:
                                if username != data['username']:
                                    self.task_lst.append(Task(self.user_dct[username].conn, {
                                        'type': 'user',
                                        'subtype': 'join',
                                        'username': data['username']
                                    }))

                    # Call requests
                    if data['type'] == 'call':
                        if data['subtype'] == 'request':
                            self.task_lst.append(Task(self.user_dct[
                                data['username']].conn, {
                                'type': 'call',
                                'subtype': 'participate',
                                'caller': self.get_user_from_conn(conn).name
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

    def get_user_from_conn(self, conn):
        """Retreives user corresponding to connection (if exists).

        Args:
            conn (socket.socket): The connection to check.

        Returns:
            User: The user object corresponding to the connection
             (None if doesn't exist).
        """

        for username in self.user_dct:
            if self.user_dct[username].conn is conn:
                return self.user_dct[username]
        return None

# Running server
if __name__ == '__main__':
    PypeServer().run()
