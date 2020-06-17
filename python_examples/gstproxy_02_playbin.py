#!/usr/bin/env python
# Shows how two pipelines can be connected, using proxysink/proxysrc
# This example uses Playbin to read a file, and send the video and audio to separate proxies.
# Unlike just using playbin directly, this will never end, as the other pipelines will continue 'listening'.
import gi

gi.require_version("Gst", "1.0")
gi.require_version("GLib", "2.0")
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gst, Gtk

import os
import sys
from datetime import datetime

# To generate dot graphs
os.environ["GST_DEBUG_DUMP_DOT_DIR"] = "/tmp"


def gen_pipe_dot(pipeline, name):
    """Generate dot graph"""

    date_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    dot_filename = "{}_pipeline_{}".format(name, date_time)

    # Print debug info
    print("GST_DEBUG_DUMP_DOT_DIR=" + os.environ["GST_DEBUG_DUMP_DOT_DIR"])

    print(
        "dot {} graph file: {}/{}.dot".format(
            name, os.environ["GST_DEBUG_DUMP_DOT_DIR"], dot_filename
        )
    )

    # dot graph generation
    Gst.debug_bin_to_dot_file(pipeline, Gst.DebugGraphDetails.ALL, dot_filename)

    return


class Window(Gtk.Window):
    """Simple window"""

    def __init__(self, pipes=[]):
        super(Window, self).__init__()
        self.set_size_request(900, 100)
        self.set_title("Simple player")
        self.connect("destroy", self.on_destroy)

        self.grid = Gtk.Grid()
        self.add(self.grid)

        self.pipes = pipes

        # auto layout
        self.play_buttons = []
        self.paused_buttons = []
        self.sliders = []
        self.sliders_hdl = []
        self.auto_buttons()

        self.show_all()

    def auto_buttons(self):
        for idx, pipes in enumerate(self.pipes):
            pipe_name = pipes.get_property("name")
            play_button = Gtk.Button.new_with_label("Play [{}]".format(pipe_name))
            play_button.connect("clicked", self.play, idx)
            if idx == 0:
                self.grid.add(play_button)
            else:
                self.grid.attach(play_button, 0, idx, 1, 1)

            self.play_buttons.append(play_button)

            paused_button = Gtk.Button.new_with_label("Paused [{}]".format(pipe_name))
            paused_button.connect("clicked", self.paused, idx)
            self.grid.attach(paused_button, 1, idx, 1, 1)
            self.paused_buttons.append(paused_button)

            slider = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 0.5)
            slider_handler_id = slider.connect("value-changed", self.slider, idx)
            slider.set_hexpand(True)
            self.grid.attach(slider, 2, idx, 1, 1)
            self.sliders.append(slider)
            self.sliders_hdl.append(slider_handler_id)

    def on_destroy(self, widget):
        Gtk.main_quit()

    def update_slider(self, idx, position):
        self.sliders[idx].handler_block(self.sliders_hdl[idx])
        self.sliders[idx].set_value(float(position) / Gst.SECOND)
        self.sliders[idx].handler_unblock(self.sliders_hdl[idx])

    def slider(self, widget, pipeline_idx):
        seek_time_secs = self.sliders[pipeline_idx].get_value()
        self.pipes[pipeline_idx].seek_simple(
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
            seek_time_secs * Gst.SECOND,
        )

    def play(self, widget, pipeline_idx):
        print("playing: {}".format(self.pipes[pipeline_idx].get_property("name")))
        self.pipes[pipeline_idx].set_state(Gst.State.PLAYING)

    def paused(self, widget, pipeline_idx):
        print("paused: {}".format(self.pipes[pipeline_idx].get_property("name")))
        self.pipes[pipeline_idx].set_state(Gst.State.PAUSED)

if len(sys.argv) != 2:
    print("Need 1 parameter")
    sys.exit(1)

file = sys.argv[1]

Gst.init(None)

pipe1 = Gst.parse_launch("playbin uri=\"file://" + file + "\"")
playsink = pipe1.get_by_name('playsink')

psink1 = Gst.ElementFactory.make("proxysink", "psink1")
psink2 = Gst.ElementFactory.make("proxysink", "psink2")
playsink.set_property('video-sink', psink1)
playsink.set_property('audio-sink', psink2)

pipe2 = Gst.parse_launch("proxysrc name=psrc1 ! autovideosink")
psrc1 = pipe2.get_by_name('psrc1')
psrc1.set_property('proxysink', psink1)

pipe3 = Gst.parse_launch("proxysrc name=psrc2 ! autoaudiosink")
psrc2 = pipe3.get_by_name('psrc2')
psrc2.set_property('proxysink', psink2)

clock = Gst.SystemClock.obtain()
pipe1.use_clock(clock)
pipe2.use_clock(clock)
pipe3.use_clock(clock)
clock.unref()

pipe1.set_base_time(0)
pipe2.set_base_time(0)
pipe3.set_base_time(0)

pipelines = [pipe1, pipe2, pipe3]

# gtk window
w = Window(pipelines)

pipe1.set_state(Gst.State.PLAYING)
pipe2.set_state(Gst.State.PLAYING)
pipe3.set_state(Gst.State.PLAYING)

mainloop = GLib.MainLoop()

def on_error(bus, message):
    print(message.parse_error())

def timeout(loop, pipeline, w, idx):
    _, position = pipeline.query_position(Gst.Format.TIME)
    print(
        "Position[{}]: {}\r".format(
            pipeline.get_property("name"), Gst.TIME_ARGS(position)
        )
    )
    w.update_slider(idx, position)

    if position > 5 * Gst.SECOND and position < 6 * Gst.SECOND:
        gen_pipe_dot(pipeline, pipeline.get_property("name"))

    return True

bus1 = pipe1.get_bus()
bus1.add_signal_watch()
bus1.connect('message::error', on_error)

for idx, pipeline in enumerate(pipelines):
    GLib.timeout_add_seconds(1, timeout,
                             mainloop, pipeline, w, idx)

mainloop.run()
