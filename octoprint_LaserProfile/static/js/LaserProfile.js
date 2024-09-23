/*
 * View model for OctoPrint-Laserprofile
 *
 * Author: Transpiration Turning
 * License: AGPLv3
 */
$(function() {
    function LaserprofileViewModel(parameters) {
        var self = this;
        self.scans = ko.observable
        self.xValues = [];
        self.zValues = [];
        self.scans = ko.observableArray();

    // Fetch the list of .txt files from the uploads/scans directory
    self.fetchProfileFiles = function() {
        OctoPrint.files.listForLocation("local/scans", false)
            .done(function(data) {
                var scans = data.children
                console.log(scans);
                scans.sort((a,b) => { return a.name.localeCompare(b.name) });
                self.scans = scans;
                populateFileSelector(scans, "#scan_file_select", "machinecode");
            })
            .fail(function() {
                console.error("Failed to fetch GCode files.");
            });
    };

    function populateFileSelector(files, elem, type) {
        var fileSelector = $(elem);
        fileSelector.empty();
        fileSelector.append($("<option>").text("Select file").attr("value", ""));
        var i = 0;
        files.forEach(function(file) {
            if (file.type === type) {
                var option = $("<option>")
                    .text(file.display)
                    .attr("value", file.name)
                    .attr("download",file.refs.download)
                    .attr("index", i); // Store metadata in data attribute
                fileSelector.append(option);
            }
            i++;
        });
    }

    self.onBeforeBinding = function () {
        self.fetchProfileFiles();
    }

    // Function to plot the profile using Plotly
    function plotProfile() {
        var trace = {
            x: self.xValues,
            y: self.zValues,
            mode: 'lines',
            name: 'Laser Profile',
            line: {
                color: 'blue',
                width: 2
            }
        };

        var layout = {
            title: 'Laser Profile Plot',
            xaxis: { title: 'X Axis' },
            yaxis: { title: 'Z Axis' },
            showlegend: false
        };

        Plotly.newPlot('profilePlot', [trace], layout);
    }

    // When a file is selected, load and plot the profile
    $("#scan_file_select").on("change", function () {
        var filePath = $(this).val();
        console.log(filePath);
        if (!filePath) return;

        // Load the selected file
        $.ajax({
            url: "/api/files/local/" + filePath,
            type: "GET",
            success: function (fileData) {
                self.xValues = [];
                self.zValues = [];
                var firstX = null, firstZ = null;

                // Split the file into lines
                var lines = fileData.split('\n');

                lines.forEach(function (line) {
                    // Ignore lines that start with a semicolon
                    if (line.trim().startsWith(';')) return;

                    // Split the line by comma to get X and Z values
                    var parts = line.split(',');
                    if (parts.length !== 2) return;

                    var x = parseFloat(parts[0].trim());
                    var z = parseFloat(parts[1].trim());

                    // Capture the first point for normalization
                    if (firstX === null && firstZ === null) {
                        firstX = x;
                        firstZ = z;
                    }

                    // Normalize the values (first point becomes 0,0)
                    self.xValues.push(x - firstX);
                    self.zValues.push(z - firstZ);
                });

                // Plot the profile
                plotProfile();
            },
            error: function (err) {
                console.error("Error loading file: ", err);
            }
        });
    });

    // Button click event to reverse the Z values and replot
    $("#reverseZButton").on("click", function () {
        self.zValues.reverse(); // Reverse the Z values
        plotProfile();     // Replot with the reversed Z values
    });


    }

    /* view model class, parameters for constructor, container to bind to
     * Please see http://docs.octoprint.org/en/master/plugins/viewmodels.html#registering-custom-viewmodels for more details
     * and a full list of the available options.
     */
    OCTOPRINT_VIEWMODELS.push({
        construct: LaserprofileViewModel,
        // ViewModels your plugin depends on, e.g. loginStateViewModel, settingsViewModel, ...
        dependencies: [  "loginStateViewModel", "settingsViewModel"  ],
        // Elements to bind to, e.g. #settings_plugin_LaserProfile, #tab_plugin_LaserProfile, ...
        elements: [ "#tab_plugin_LaserProfile" ]
    });
});
