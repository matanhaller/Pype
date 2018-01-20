"""Main app file (GUI component).
"""

# Imports
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.screenmanager import ScreenManager, Screen


class EntryScreen(Screen):

    """Entry screen class (see .kv file for structure).
    """

    def on_join_btn_press(self):
        """Sends join request to server.
        """

        username = self.ids['username_input'].text


class PypeApp(App):

    """Main app class.
    """

    def build(self):
        """App builder.

        Returns:
            ScreenManager: root screen manager.
        """

        # Adding all screens to root
        root = ScreenManager()
        root.add_widget(EntryScreen())

        return root

# Running app
if __name__ == '__main__':
    app = PypeApp()
    app.run()
