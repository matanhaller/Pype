"""Main app file (GUI component).
"""

# Imports
import json
import threading
import socket

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.screenmanager import ScreenManager, Screen

from peer import Peer


class EntryScreen(Screen):

    """Entry screen class (see .kv file for structure).
    """

    def on_join_btn_press(self):
        """Sends join request to server.
        """

        app = App.get_running_app()
        username = self.ids['username_input'].text

        # Notifying communication component
        app.send_gui_event(json.dumps({
            'type': 'join',
            'username': username
        }))


class PypeApp(App):

    """Main app class.

    Attributes:
        app_peer (Peer): App's communication component.
        gui_event_port (int): Port of GUI event listener.
        gui_event_sender (socket.socket): UDP socket that sends GUI events to
         the communication component of app.
        root (ScreenManager): Root screen manager.
    """

    def send_gui_event(self, data):
        """Sends GUI event to communication component of app.

        Args:
            data (str): Event data (in JSON format).
        """

        self.gui_event_sender.sendto(data, ('localhost', self.gui_event_port))

    def build(self):
        """App builder.

        Returns:
            ScreenManager: Root screen manager.
        """

        # Creating root object with all app screens
        self.root = ScreenManager()
        self.root.add_widget(EntryScreen())

        # Creating communication thread
        self.app_peer = Peer()
        self.gui_event_port = self.app_peer.get_gui_event_port()
        # threading.Thread(target=self.app_peer.run).start()

        # Creating user event sender
        self.gui_event_sender = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM)

        return self.root


# Running app
if __name__ == '__main__':
    app = PypeApp()
    app.run()
