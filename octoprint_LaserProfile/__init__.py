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
import logging
import re
import os
import math
from . import G_Code_Rip as G_Code_Rip
from scipy.interpolate import CubicSpline

class LaserprofilePlugin(octoprint.plugin.SettingsPlugin,
    octoprint.plugin.AssetPlugin,
    octoprint.plugin.StartupPlugin,
    octoprint.plugin.SimpleApiPlugin,
    octoprint.plugin.TemplatePlugin
):

    def __init__(self):
        self.plot_data = []
        self.spline = None
        self.x_coords = []
        self.z_coords = []
        self.tool_length = 0
        self.min_B = float(0)
        self.max_B = float(0)
        self.x_steps = float(0)
        self.power = float(0)
        self.start_max = False
        self.axis = 'X'
        self.side = "front"
        self.feed = 1.0
        self.arotate = 0.0
        self.segments = 0
        self.datafolder = None
        #self.watched_path = self._settings.global_get_basefolder("watched")

    def initialize(self):
        self.datafolder = self.get_plugin_data_folder()
        self.gcr = G_Code_Rip.G_Code_Rip()
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
    
    def creategraph(self, filepath):
        folder = self._settings.getBaseFolder("uploads")
        filename = f"{folder}/{filepath}"
        
        datapoints = []
        with open(filename,"r") as file:
            for line in file:
                stripped_line = line.strip()
                if stripped_line == ";X":
                    self.axis = 'X'
                if stripped_line == ";Z":
                    self.axis = 'Z'
                if not stripped_line.startswith(";"):
                    # Split the line by comma and convert to floats
                    try:
                        datapoints.append([float(x) for x in stripped_line.split(",")])
                    except ValueError:
                        pass
        self._logger.info(datapoints)
        #sort, must be increasing
        if self.axis == 'Z':
            datapoints = sorted(datapoints, key=lambda x: x[1])
            min = datapoints[0][1] #smallest X value, should be 0
            max = datapoints[-1][1] #largest X value
        if self.axis == 'X':
            datapoints = sorted(datapoints, key=lambda x: x[0])
            min = datapoints[0][0] #smallest X value, should be 0
            max = datapoints[-1][0] #largest X value

        self._logger.info(datapoints)
        self._logger.info(self.axis)

        generated_data = []

        if self.axis == 'Z':
            z_profile, x_profile = zip(*datapoints)
        else:
            x_profile, z_profile = zip(*datapoints)

        self.spline = CubicSpline(x_profile, z_profile)

        increment = 0.5 #should this be adjustable?
        i = min
        while i <= max:
            z_val = self.spline(i)
            z_val = float(z_val)
            z_val = f"{z_val:.3f}"
            x_val = f"{x_val:.3f}"
            generated_data.append([x_val,z_val])
            i = i+increment
        self._logger.info(generated_data)

        #send generated_data to plotly at the front end
        data = dict(type="graph", probe=generated_data, axis=self.axis)
        self._plugin_manager.send_plugin_message('LaserProfile', data)

    def create_spline(self):
        self.x_coords = []
        self.z_coords = []

        if self.axis == "X":
            for each in self.plot_data:
                self.x_coords.append(float(each["x"]))
                self.z_coords.append(float(each["z"]))
        if self.axis == "Z":
            for each in self.plot_data:
                self.z_coords.append(float(each["x"]))
                self.x_coords.append(float(each["z"]))

        self.spline = CubicSpline(self.x_coords, self.z_coords)

    def calc_coords(self, coord):
        if coord not in self.x_coords:
            raise ValueError("Value is not in list")
        
        #B angle smoothing, would be nice if there was more control for this
        slopes = []
        coord_i = self.x_coords.index(coord)
        slopes.append(coord)
        slopes.extend(self.x_coords[max(0, coord_i-2):coord_i])
        slopes.extend(self.x_coords[coord_i+1:coord_i+3])
        s=0
        
        for each in slopes:
            s = s + self.spline.derivative()(each)
        z_value = self.spline(coord)
        
        #Average of slope
        slope = s/len(slopes)
        
        #normal angle calculation
        if self.axis == "X":
            normal = math.atan2(slope, 1)
        if self.axis == "Z" and self.side == "back":
            normal = math.atan2(1/abs(slope), 1)
        if self.axis == "Z" and self.side == "front":
            normal = math.atan2(1/abs(slope),1) - math.pi
        
        b_angle = math.degrees(normal)
        
        #adjust normal angle if beyond limits
        if b_angle > 0 and b_angle > self.max_B:
            b_angle = self.max_B
        if b_angle < 0 and b_angle < self.min_B:
            b_angle = self.min_B
        #recalculate normal in case it is outside B range
        normal = math.radians(b_angle)
        
        self._logger.info(f"Normal angle: {normal}, slope: {slope},  B angle: {b_angle}")
        
        if self.axis == "X":
            normal = normal + math.pi / 2 
            x_center = coord + ((self.tool_length) * math.cos(normal))
            z_center = z_value + ((self.tool_length) * math.sin(normal))
            return_coord = {"X": x_center, "Z": z_center-self.tool_length, "B": b_angle}
        #may need to have this specific for front and back cases
        if self.axis == "Z":
            x_center = coord + ((self.tool_length) * math.sin(normal))
            z_center = z_value - ((self.tool_length) * math.cos(normal))
            return_coord = {"X": z_center, "Z": x_center-self.tool_length, "B": b_angle}
        return return_coord
    
    def generate_laser_job(self):
        command_list = []
        pass_list = []
        profile_points = []
        
        #truncate profile beween vMin and vMax
        for each in self.x_coords:
            if each < self.vMin:
                continue
            if each > self.vMax:
                continue
            profile_points.append(each)
        #A axis rotation per segment
        seg_rot = self.arotate/(len(profile_points)-1)
        self._logger.info(f"Segment rotation: {seg_rot}")
        A_rot = 360/self.segments

        #Preamble stuff here
        command_list.append("G21")
        command_list.append("G90")
        #move to start
        start = self.calc_coords(profile_points[0])
        command_list.append(f"G0 X{start['X']:0.4f} Z{start['Z']:0.4f} A0 B{start['B']:0.4f}")
        if self.test:
            command_list.append("M4 S5")
        else:
            command_list.append(f"M4 S{self.power}")
        
        #this is to handle A rotations
        i = -1
        for each in profile_points:
            i+=1 
            coord = self.calc_coords(each)
            pass_list.append(f"G93 G90 G1 X{coord['X']:0.3f} Z{coord['Z']:0.3f} A{seg_rot*i:0.3f} B{coord['B']:0.3f} F{self.feed}")
        #make sure we move back to last A position before starting reverse pass
        pass_list.append(f"G0 A{seg_rot*i:0.3f}")    
        
        i = 1
        while i <= self.segments:
            command_list.append(f"(Starting segment {i} of {self.segments})")
            command_list.extend(pass_list)
            pass_list = pass_list[::-1]
            if self.test and i == 1:
                command_list.append("G4 P2")
                command_list.append("(test pass)")
                command_list.extend(pass_list)
                command_list.append("G4 P2")
                command_list.append("M0")
                command_list.append(f"M4 S{self.power}")
                pass_list = pass_list[::-1]
                command_list.extend(pass_list)
                pass_list = pass_list[::-1]
            #rotate
            command_list.append("G0 A0") #return A to 0 first
            command_list.append(f"G0 A{A_rot:0.3f}")
            command_list.append("G92 A0")
            i += 1
        command_list.append("M5")
        command_list.append("M30")
        #self._logger.info(command_list)
        output_name = "LASERtest.gcode"
        path_on_disk = "{}/{}".format(self._settings.getBaseFolder("watched"), output_name)

        with open(path_on_disk,"w") as newfile:
            for line in command_list:
                newfile.write(f"\n{line}")

    def get_api_commands(self):
        return dict(
            write_job=[],
            go_to_position=[],
            creategraph=[],
        )
    
    def on_api_command(self, command, data):
        
        if command == "creategraph":
            filePath = data["filepath"]
            self.creategraph(filePath)
            return
        
        if command == "write_job":
            self.plot_data = data["plot_data"]
            self.mode = data["mode"]
            self.tool_length = float(data["tool_length"])
            self.max_B = float(data["max_B"])
            self.min_B = float(data["min_B"])
            self.clearance = float(data["clear"])
            self.side = data["side"]
            #self.name = data["name"]
            self.arotate = float(data["arotate"])
            self.segments = int(data["segments"])
            self.vMax = float(data["vMax"])
            self.vMin = float(data["vMin"])
            #must sort data first
            if self.axis == "X":
                self.plot_data = sorted(self.plot_data, key=lambda x: x["x"])
            if self.axis == "Z":
                self.plot_data = sorted(self.plot_data, key=lambda x: x["z"])
                #self._logger.info(self.plot_data)
            self.create_spline()

            if self.mode == "laser":
                self.test = bool(data["test"])
                self.power = int(data["power"])
                self.feed = int(data["feed"])
                #self.start_max = bool(data["start"])
                self.generate_laser_job()
            if self.mode == "flute":
                self.generate_flute()


        if command == "go_to_position":
            self.plot_data = data["plot_data"]
            self.target = float(data["target"])
            self.clearance = float(data["clear"])
            self.tool_length = float(data["tool_length"])
            self.max_B = float(data["max_B"])
            self.min_B = float(data["min_B"])
            self.side = data["side"]
            #must sort data first
            if self.axis == "X":
                self.plot_data = sorted(self.plot_data, key=lambda x: x["x"])
            if self.axis == "Z":
                self.plot_data = sorted(self.plot_data, key=lambda x: x["z"])
            self.create_spline()

            sign = ""
            safe = None
            if self.axis == "X":
                safe = "Z"
            if self.axis == "Z":
                if self.side == "back":
                    sign = "-"
                safe = "X"
            
            #self._logger.info(self.x_coords)
            #Move to safe position
            gcode = ["G90","G21",f"G0 {safe}{sign}{10+self.clearance:0.4f}"]
            coord = self.calc_coords(self.target)
            gcode.append(f"G93 G90 G1 X{coord['X']:0.4f} F200")
            gcode.append(f"G93 G90 G1 Z{coord['Z']:0.4f} B{coord['B']:0.4f} F200")

            self._logger.info(gcode)
            self._printer.commands(gcode)


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
