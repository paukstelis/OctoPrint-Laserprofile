# coding=utf-8
from __future__ import absolute_import

### (Don't forget to remove me)
# This is a basic skeleton for your plugin's __init__.py. You probably want to adjust the class name of your plugin
# as well as the plugin mixins it's subclassing from. This is really just a basic skeleton to get you started,
# defining your plugin as a template plugin, settings and asset plugin. Feel free to add or remove mixins
# as necessary.
#
# Take a look at the documentation on what other plugin mixins are available.

import octoprint.plugin
import octoprint.filemanager
import octoprint.filemanager.util
import octoprint.util
import re
import os
import math

class LaserprofilePlugin(octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.SimpleApiPlugin,
    octoprint.plugin.TemplatePlugin
):

    def __init__(self):
        self.plot_data = []
        self.x_coords = []
        self.z_coords = []
        self.tool_length = 0
        self.min_B = float(0)
        self.max_B = float(0)
        self.x_steps = float(0)
        self.power = float(0)
        self.start_max = False
        self.feed = 1.0
        self.segments = 0
        self.datafolder = None
        #self.watched_path = self._settings.global_get_basefolder("watched")

    def initialize(self):
        self.datafolder = self.get_plugin_data_folder()
    ##~~ SettingsPlugin mixin

    def get_settings_defaults(self):
        return {
            # put your plugin's default settings here
        }

    ##~~ AssetPlugin mixin

    def get_assets(self):
        # Define your plugin's asset files to automatically include in the
        # core UI here.
        return {
            "js": ["js/LaserProfile.js", "js/plotly-latest.min.js"],
            "css": ["css/LaserProfile.css"],
        }
    
    def interpolate(self, x_target):
        if x_target <= self.x_coords[0]:
            return self.z_coords[0]
        elif x_target >= self.x_coords[-1]:
            return self.z_coords[-1]
        else:
            for i in range(len(self.x_coords) - 1):
                if self.x_coords[i] <= x_target <= self.x_coords[i + 1]:
                    # Linear interpolation
                    x1, x2 = self.x_coords[i], self.x_coords[i + 1]
                    z1, z2 = self.z_coords[i], self.z_coords[i + 1]
                    z_target = z1 + (z2 - z1) * (x_target - x1) / (x2 - x1)
                    return z_target

    def get_coords(self, x_target):
        #as of now this is unused
        z_target = self.interpolate(x_target)
    
        # Calculate the slope (dz/dx) around the target point using interpolation
        if x_target in self.x_coords:
            idx = self.x_coords.index(x_target)
            if idx == 0:
                idx = 1
            elif idx == len(self.x_coords) - 1:
                idx = len(self.x_coords) - 2
            dz_dx = (self.z_coords[idx + 1] - self.z_coords[idx - 1]) / (self.x_coords[idx + 1] - self.x_coords[idx - 1])
        else:
            # Interpolate slope between nearest two points
            for i in range(len(self.x_coords) - 1):
                if self.x_coords[i] <= x_target <= self.x_coords[i + 1]:
                    x1, x2 = self.x_coords[i], self.x_coords[i + 1]
                    z1, z2 = self.z_coords[i], self.z_coords[i + 1]
                    dz_dx = (z2 - z1) / (x2 - x1)
                    break
        
        # Tangent angle with respect to the X-axis
        tangent_angle = math.atan(dz_dx)
        
        # B angle (rotation of the tool relative to the X-axis)
        b_angle = math.degrees(tangent_angle)
        if b_angle > 0 and b_angle > self.max_B:
            b_angle = self.max_B
        if b_angle < 0 and b_angle < self.min_B:
            b_angle = self.min_B
        tangent_angle = math.radians(b_angle)
        normal_angle = tangent_angle + math.pi / 2
        x_center = x_target + (self.tool_length) * math.cos(normal_angle)
        z_center = z_target + (self.tool_length) * math.sin(normal_angle)
        
        # Append the profile X, Z coordinates and the tool center X, Z, and B angle
        coord = {"X": x_center, "Z": z_center-self.tool_length, "B": b_angle}
        return coord
    
    def generate_job(self):
        command_list = []
        pass_list = []
        A_rot = 360/self.segments
        #not including any feed or power yet
        #assume starting at first X coord
        #Do all preamble stuff here
        command_list.append("G21")
        command_list.append("G90")
        command_list.append("BYPASS")
        #move to start
        start = self.get_coords(self.x_coords[0])
        command_list.append(f"G0 X{start['X']:0.4f} Z{start['Z']:0.4f} B{start['B']:0.4f}")
        if self.test:
            command_list.append("M4 S5")
        else:
            command_list.append(f"M4 S{self.power}")

        for each in self.x_coords:
            coord = self.get_coords(each)
            pass_list.append(f"G93 G90 G1 X{coord['X']:0.4f} Z{coord['Z']:0.4f} B{coord['B']:0.4f} F{self.feed}")

        i = 1
        while i <= self.segments:
            command_list.append(f"(Starting segment {i} of {self.segments})")
            command_list.extend(pass_list)
            pass_list = pass_list[::-1]
            if self.test and i == 1:
                command_list.append("G4 P2")
                command_list.append("(completing test pass)")
                command_list.extend(pass_list)
                command_list.append("G4 P2")
                command_list.append("M0")
                command_list.append(f"M4 S{self.power}")
                pass_list = pass_list[::-1]
                command_list.extend(pass_list)
                pass_list = pass_list[::-1]
            #rotate
            command_list.append(f"G0 A{A_rot:0.3f}")
            command_list.append("G92 A0")
            i += 1
        command_list.append("M5")
        command_list.append("M30")
        self._logger.info(command_list)
        output_name = "LASERtest.gcode"
        path_on_disk = "{}/{}".format(self._settings.getBaseFolder("watched"), output_name)

        with open(path_on_disk,"w") as newfile:
            for line in command_list:
                newfile.write(f"\n{line}")

    def get_api_commands(self):
        return dict(
            write_job=[]
        )
    
    def on_api_command(self, command, data):
        
        if command == "write_job":
            plot_data = data["plot_data"]
            self.tool_length = float(data["tool_length"])
            self.x_steps = float(data["x_steps"])
            self.max_B = float(data["max_B"])
            self.min_B = float(data["min_B"])
            self.test = bool(data["test"])
            self.power = int(data["power"])
            self.feed = int(data["feed"])
            self.start_max = bool(data["start"])
            self.segments = int(data["segments"])
            self.x_coords = []
            self.z_coords = []
            for each in plot_data:
                self.x_coords.append(float(each["x"]))
                self.z_coords.append(float(each["z"]))
            self.generate_job()

    def get_update_information(self):
        # Define the configuration for your plugin to use with the Software Update
        # Plugin here. See https://docs.octoprint.org/en/master/bundledplugins/softwareupdate.html
        # for details.
        return {
            "LaserProfile": {
                "displayName": "Laserprofile Plugin",
                "displayVersion": self._plugin_version,

                # version check: github repository
                "type": "github_release",
                "user": "paukstelis",
                "repo": "OctoPrint-Laserprofile",
                "current": self._plugin_version,

                # update method: pip
                "pip": "https://github.com/paukstelis/OctoPrint-Laserprofile/archive/{target_version}.zip",
            }
        }


# If you want your plugin to be registered within OctoPrint under a different name than what you defined in setup.py
# ("OctoPrint-PluginSkeleton"), you may define that here. Same goes for the other metadata derived from setup.py that
# can be overwritten via __plugin_xyz__ control properties. See the documentation for that.
__plugin_name__ = "Laserprofile Plugin"


# Set the Python version your plugin is compatible with below. Recommended is Python 3 only for all new plugins.
# OctoPrint 1.4.0 - 1.7.x run under both Python 3 and the end-of-life Python 2.
# OctoPrint 1.8.0 onwards only supports Python 3.
__plugin_pythoncompat__ = ">=3,<4"  # Only Python 3

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = LaserprofilePlugin()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }
