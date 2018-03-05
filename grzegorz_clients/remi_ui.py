import random, os, time, shutil, sys
from threading import Timer
import remi.gui as gui
from remi import App
from .utils import Namespace, call_as_thread, get_youtube_metadata, seconds_to_timestamp
from . import api
from .colors import *

#globals:
WIDTH = 512

class RemiApp(App):
	def __init__(self, *args):
		res_path = os.path.join(os.path.dirname(__file__), 'res')
		super(RemiApp, self).__init__(*args, static_file_path=res_path)

	def main(self):
		container = gui.VBox(width=WIDTH)
		container.style.update({"margin-left": "auto", "margin-right":"auto"})
		
		#logo:
		container.append(gui.Image('/res/logo.png', width=WIDTH))
		
		#playback controls
		self.playback = Namespace()
		
		self.playback.playing = gui.Label("Now playing: None")# (TODO): update this
		
		self.playback.previous, self.playback.play, self.playback.next \
			= map(lambda x: gui.Button(f'<i class="fas fa-{x}"></i>', margin="3px", width="2.8em"), 
			("step-backward", "play", "step-forward"))
		self.playback.previous.set_on_click_listener(self.playback_previous)
		self.playback.play.set_on_click_listener(self.playback_play)
		self.playback.next.set_on_click_listener(self.playback_next)
		
		self.playback.volume_label = gui.Label("Volume:")
		self.playback.volume_label.style["font-size"] = "0.8em"
		self.playback.volume_slider = gui.Slider(100, 0, 100, 1, width="150px")
		self.playback.volume_slider \
			.style.update({"margin-left": "20px", "margin-bottom":"13px"})
		self.playback.volume_slider.set_oninput_listener(self.change_volume)
		
		self.playback.seek_slider = gui.Slider(0, 0, 100, 1, width="85%", height=20, margin='10px')
		self.playback.seek_slider.set_oninput_listener(self.change_seek)
		
		self.playback.timestamp = gui.Label("--:-- - --:--")
		
		container.append(self.playback.playing)
		
		playback_container = gui.HBox()
		playback_container.append(self.playback.previous)
		playback_container.append(self.playback.play)
		playback_container.append(self.playback.next)
		volume_container = gui.VBox()
		volume_container.append(self.playback.volume_label)
		volume_container.append(self.playback.volume_slider)
		playback_container.append(volume_container)
		container.append(playback_container)
		container.append(self.playback.seek_slider)
		container.append(self.playback.timestamp)
		
		#playlist
		self.playlist = Namespace()
		self.playlist.table = gui.Table(width="100%", margin="10px")
		self.playlist.table.append_from_list([['#', 'Name', "length", "", "", ""]], fill_title=True)
		
		container.append(self.playlist.table)
		
		#input
		container.append(gui.Label("Add song:"))
		input_container = gui.HBox(width=WIDTH)
		self.input = Namespace()
		self.input.field = gui.TextInput(single_line=True, height="20px", margin="5px")
		self.input.field.style["border"]     = "1px solid %s" % COLOR_BLUE
		self.input.field.style["box-shadow"] = "0px 0px 5px 0px %s" % COLOR_BLUE_SHADOW
		self.input.submit = gui.Button("Submit!", margin="5px")
		self.input.field.set_on_enter_listener(self.input_submit)
		self.input.submit.set_on_click_listener(self.input_submit)
		
		input_container.append(self.input.field)
		input_container.append(self.input.submit)
		container.append(input_container)
		
		#return the container
		self.mainLoop()
		return container
	def mainLoop(self):
		#self.playback.seek_slider.get_value()
		self.playback_update()
		self.playlist_update()
		
		Timer(1, self.mainLoop).start()

	# events:
	@call_as_thread
	def playback_previous(self, widget):
		api.playlist_previous()
	@call_as_thread
	def playback_play(self, widget):# toggle playblack
		if api.is_playing():
			api.set_playing(False)
			self.set_playing(False)
		else:
			api.set_playing(True)
			self.set_playing(True)
	@call_as_thread
	def playback_next(self, widget):
		api.playlist_next()
	@call_as_thread
	def input_submit(self, widget, value=None):
		if value is None:
			value = self.input.field.get_text()
		self.input.field.set_text("")
		
		self.input.field.set_enabled(False)
		self.input.submit.set_enabled(False)
		try:
			data = get_youtube_metadata(value)
		finally:
			self.input.field.set_enabled(True)
			self.input.submit.set_enabled(True)
		
		api.load_path(value, data)
	@call_as_thread
	def change_seek(self, widget, value):
		api.seek_percent(value)
	@call_as_thread
	def change_volume(self, widget, value):
		api.set_volume(value)
	def on_table_row_click(self, row_widget, playlist_item):
		print("row", playlist_item)
	@call_as_thread
	def on_table_item_move_click(self, row_widget, playlist_item, down = True):
		index = playlist_item["index"]
		dest = index + 2 if down else index-1
		api.playlist_move(index, dest)
	@call_as_thread
	def on_table_item_remove_click(self, row_widget, playlist_item):
		api.playlist_remove(playlist_item["index"])
	@call_as_thread
	def on_playlist_clear_click(self, row_widget):
		api.playlist_clear()
		
	# playback steps:
	@call_as_thread
	def playback_update(self, times_called=[0]):
		is_playing = api.is_playing()
		self.set_playing(is_playing)

		if is_playing:
			try:
				playback_pos = api.get_playback_pos()
			except api.APIError:
				playback_pos = None
			if playback_pos:
				slider_pos = playback_pos["current"] / playback_pos["total"] * 100
				if self.playback.seek_slider.get_value() != slider_pos:
					self.playback.seek_slider.set_value(slider_pos)
				self.playback.timestamp.set_text(
					seconds_to_timestamp(playback_pos["current"])
					+ " - " + 
					seconds_to_timestamp(playback_pos["total"])
					)
			else:
				self.playback.timestamp.set_text("--:-- - --:--")
				
		if times_called[0] % 5 == 0:
			volume = api.get_volume()
			if volume > 100: volume = 100
			if self.playback.volume_slider.get_value() != volume:
				self.playback.volume_slider.set_value(volume)
		times_called[0] += 1
	@call_as_thread
	def volume_update(self):
		self.volume.slider.set_value(api.get_volume())
	@call_as_thread
	def playlist_update(self):
		playlist = api.get_playlist()
		
		N = len(playlist)
		table = []
		for i, playlist_item in enumerate(playlist):
			name = playlist_item["filename"]
			length = "--:--"
			if "data" in playlist_item:
				if "title" in playlist_item["data"]:
					name = playlist_item["data"]["title"]
				if "length" in playlist_item["data"]:
					length = playlist_item["data"]["length"]
			
			if playlist_item.get("current", False):
				self.playback.previous.set_enabled(i != 0)
				self.playback.next.set_enabled(i != N-1)

			table.append([
				playlist_item["index"],
				name,
				length,
				'<i class="fas fa-arrow-up"></i>',
				'<i class="fas fa-arrow-down"></i>',
				'<i class="fas fa-trash"></i>',
			])

		self.playlist.table.empty(keep_title=True)
		self.playlist.table.append_from_list(table)
		
		for row_widget, playlist_item in zip(
				map(self.playlist.table.get_child, self.playlist.table._render_children_list[1:]),
				playlist):
			if "current" in playlist_item:
				row_widget.style["background-color"] = COLOR_LIGHT_BLUE
			else:
				row_widget.style["color"] = COLOR_GRAY_DARK
			row_widget.set_on_click_listener(self.on_table_row_click, playlist_item)
			for index, (key, item_widget) in enumerate(zip(row_widget._render_children_list,
					map(row_widget.get_child, row_widget._render_children_list))):
				if index >= 3:
					item_widget.style["width"] = "1.1em"
					item_widget.style["color"] = COLOR_TEAL
				if index == 3:
					item_widget.set_on_click_listener(self.on_table_item_move_click, playlist_item, False)
					if playlist_item["index"] == 0:
						item_widget.style["color"] = COLOR_GRAY_LIGHT
				if index == 4:
					item_widget.set_on_click_listener(self.on_table_item_move_click, playlist_item, True)
					if playlist_item["index"] == N-1:
						item_widget.style["color"] = COLOR_GRAY_LIGHT
				if index == 5:
					item_widget.style["color"] = COLOR_RED
					item_widget.set_on_click_listener(self.on_table_item_remove_click, playlist_item)
				#print(index, key, item_widget)

	#helpers
	def set_playing(self, is_playing:bool):
		self.playback.play.set_text('<i class="fas fa-pause"></i>' if is_playing else '<i class="fas fa-play"></i>')
		self.playback.seek_slider.set_enabled(is_playing)
		
