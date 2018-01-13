"""Main app file.
"""

# Imports
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button

class EntryScreen(BoxLayout):

	"""Entry screen class (see .kv file for structre).
	"""
	
	pass


class PypeApp(App):

	"""Main app class.
	"""
	
	def build(self):
		"""App builder.
		
		Returns:
		    EntryScreen: Entry screen class.
		"""

		return EntryScreen()

# Running app
if __name__ == '__main__':
    app = PypeApp()
    app.run()
