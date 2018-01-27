"""Main app file (GUI component).
"""

# Imports
import json
import threading
import socket
import re

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.properties import StringProperty, ListProperty

import peer


class EntryScreen(Screen):

    """Entry screen class (see .kv file for structure).

    Attributes:
        bottom_lbl (Label): Bottom label to be added 
         (when username is invalid or taken).
        USERNAME_REGEX (str): Regex of valid username format: Non-empty, doesn't
         start with spaces and is no longer than 256 characters.
    """

    USERNAME_REGEX = r'[^\s]{1}.{0,255}$'

    def __init__(self):
        """Constructor method,
        """

        Screen.__init__(self, name='entry_screen')

    def on_join_btn_press(self):
        """Sends join request to server.
        """

        app = App.get_running_app()
        username = self.ids.username_input.text

        # Checking if username is valid
        if not re.match(EntryScreen.USERNAME_REGEX, username):
            err_msg = 'Invalid username'
            if hasattr(self, 'bottom_lbl'):
                self.bottom_lbl.text = err_msg
            else:
                self.bottom_lbl = Label(text=err_msg)
                self.ids.main_layout.add_widget(self.bottom_lbl)
        else:
            # Notifying communication component
            app.send_gui_event({
                'type': 'join',
                'subtype': 'request',
                'username': username
            })


class MainScreen(Screen):

    """Main screen class (see .kv file for structure).

    Attributes:
        user_lst (list): List of online users.
        username (str): Username.
    """

    def __init__(self, username, user_lst):
        """Constructor method

        Args:
            username (str): Username.
            user_lst (list): List of online users.
        """

        self.username = username
        self.user_lst = user_lst
        Screen.__init__(self, name='main_screen')


class PypeApp(App):

    """Main app class.

    Attributes:
        gui_event_port (int): Port of GUI event listener.
        gui_event_sender (socket.socket): UDP socket that sends GUI events to
         the communication component of app.
        peer (PypePeer): App's communication component.
        root_sm (ScreenManager): Root screen manager.
    """

    def send_gui_event(self, data):
        """Sends GUI event to communication component of app.

        Args:
            data (dict): Event data (in JSON format).
        """

        self.gui_event_sender.sendto(json.dumps(
            data), ('localhost', self.gui_event_port))

    def on_stop(self):
        """Application close event callback.
        """

        self.send_gui_event({
            'type': 'terminate'
        })

    def build(self):
        """App builder.

        Returns:
            ScreenManager: Root screen manager.
        """

        # Creating root object with all app screens
        self.root_sm = ScreenManager()
        self.root_sm.add_widget(EntryScreen())

        # Creating communication thread
        self.peer = peer.PypePeer()
        self.gui_event_port = self.peer.get_gui_event_port()
        threading.Thread(target=self.peer.run).start()

        # Creating user event sender
        self.gui_event_sender = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM)

        return self.root_sm


# Running app
if __name__ == '__main__':
    PypeApp().run()
