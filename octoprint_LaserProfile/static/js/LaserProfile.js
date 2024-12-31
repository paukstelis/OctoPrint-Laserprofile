$(function() {
    function LaserprofileViewModel(parameters) {
        var self = this;
        self.xValues = [];
        self.zValues = [];
        self.vMax = null;
        self.vMin = null;
        self.target_position = []; 
        self.smoothedZValues = [];  // Store smoothed Z values
        self.annotations = [];
        self.markerAction = ko.observable("zeroPoint");
        self.tool_length = ko.observable(135);
        self.min_B = ko.observable(-45);
        self.max_B = ko.observable(45);
        self.power = ko.observable(250);
        self.feed = ko.observable(200);
        self.test = ko.observable(1);
        self.start_max = ko.observable(0);
        self.x_steps = ko.observable(1.0);
        self.segments = ko.observable(100);
        self.reversed = false;
        self.isZFile = false;
        self.isXFile = false;
        

        // Fetch the list of .txt files from the uploads/scans directory
        self.fetchProfileFiles = function() {
            OctoPrint.files.listForLocation("local/scans", false)
                .done(function(data) {
                    var scans = data.children;
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
            files.forEach(function(file, i) {
                var option = $("<option>")
                    .text(file.display)
                    .attr("value", file.name)
                    .attr("download",file.refs.download)
                    .attr("index", i); // Store metadata in data attribute
                fileSelector.append(option);
            });
        }

        self.onBeforeBinding = function () {
            self.fetchProfileFiles();
        };

        // Function to plot the profile using Plotly
        function plotProfile(isZFile) {
            var trace = {
                x: self.xValues,
                y: self.zValues,
                mode: 'lines',
                name: 'Profile',
                line: {
                    color: 'blue',
                    width: 2
                }
            };

            var layout = {
                title: 'Profile Plot',
                xaxis: { 
                    title: 'X Axis',
                    scaleanchor: 'y',  // Ensure equal scaling
                    scaleratio: 1
                },
                yaxis: { 
                    title: 'Z Axis',
                    //scaleanchor: 'x',  // Equal scaling with X axis
                    scaleratio: 1,
                    autorange: 'reversed'
                },
                annotations: self.annotations,  // Include any annotations (tags)
                showlegend: false
            };

            // Plot the data
            Plotly.newPlot('profilePlot', [trace], layout)
            .then(function() {
                // Ensure plotly_click is bound AFTER the plot is rendered
                document.getElementById('profilePlot').on('plotly_click', function (data) {
                    if (data && data.points && data.points.length > 0) {
                        var clickedPoint = data.points[0];
                        var clickedX = clickedPoint.x;
                        var clickedZ = clickedPoint.y;
                
                        if (self.markerAction() === "zeroPoint") {
                            // Normalize both X and Z axes
                            self.xValues = self.xValues.map(x => x - clickedX);
                            self.zValues = self.zValues.map(z => z - clickedZ);
                            self.annotations = []; // Clear all annotations
                            self.vMin = null;
                            self.vMax = null;
                            self.target_position = null;
                            plotProfile(self.isZFile); // Replot based on file mode
                            //Plotly.react('profilePlot');
                        } else if (self.isZFile) {
                            // Z-file mode: Handle Z-axis selections
                            if (self.markerAction() === "Max") {
                                self.annotations = self.annotations.filter(a => a.text !== 'Max');
                                if (self.vMin && clickedZ < self.vMin) {
                                    alert("Max must be greater than Min");
                                    return;
                                }
                                self.vMax = clickedZ;
                                self.annotations.push({
                                    x: clickedX,
                                    y: clickedZ,
                                    xref: 'x',
                                    yref: 'y',
                                    text: 'Max',
                                    showarrow: true,
                                    arrowhead: 2,
                                    ax: 30,
                                    ay: -30
                                });
                                plotProfile(true);
                            } else if (self.markerAction() === "Min") {
                                self.annotations = self.annotations.filter(a => a.text !== 'Min');
                                if (self.vMax && clickedZ > self.vMax) {
                                    alert("Min must be less than Max");
                                    return;
                                }
                                self.vMin = clickedZ;
                                self.annotations.push({
                                    x: clickedX,
                                    y: clickedZ,
                                    xref: 'x',
                                    yref: 'y',
                                    text: 'Min',
                                    showarrow: true,
                                    arrowhead: 2,
                                    ax: -30,
                                    ay: -30
                                });
                                plotProfile(true);
                            }
                        } else if (self.isXFile) {
                            // X-file mode: Handle X-axis selections
                            if (self.markerAction() === "Max") {
                                self.annotations = self.annotations.filter(a => a.text !== 'Max');
                                if (self.vMin && clickedX < self.vMin) {
                                    alert("Max must be greater than Min");
                                    return;
                                }
                                self.vMax = clickedX;
                                self.annotations.push({
                                    x: clickedX,
                                    y: clickedZ,
                                    xref: 'x',
                                    yref: 'y',
                                    text: 'Max',
                                    showarrow: true,
                                    arrowhead: 2,
                                    ax: 30,
                                    ay: -30
                                });
                                plotProfile(false);
                            } else if (self.markerAction() === "Min") {
                                self.annotations = self.annotations.filter(a => a.text !== 'Min');
                                if (self.vMax && clickedX > self.vMax) {
                                    alert("Min must be less than Max");
                                    return;
                                }
                                self.vMin = clickedX;
                                self.annotations.push({
                                    x: clickedX,
                                    y: clickedZ,
                                    xref: 'x',
                                    yref: 'y',
                                    text: 'Min',
                                    showarrow: true,
                                    arrowhead: 2,
                                    ax: -30,
                                    ay: -30
                                });
                                plotProfile(false);
                            } else if (self.markerAction() === "targetPoint") {
                                self.annotations = self.annotations.filter(a => a.text !== 'Target');
                                self.target_position = clickedX;
                                self.annotations.push({
                                    x: clickedX,
                                    y: clickedZ,
                                    xref: 'x',
                                    yref: 'y',
                                    text: 'Target',
                                    showarrow: true,
                                    arrowhead: 2,
                                    ax: 20,
                                    ay: 20
                                });
                                plotProfile(false);
                            } 
                        }
                    }
                });
            });
        }

        // When a file is selected, load and plot the profile
        $("#scan_file_select").on("change", function () {
            var filePath = $("#scan_file_select option:selected").attr("download");
            if (!filePath) return;
        
            // Determine the mode based on the file name
            self.isZFile = $("#scan_file_select option:selected").text().startsWith("Z");
            self.isXFile = $("#scan_file_select option:selected").text().startsWith("X");
            self.annotations = [];
            self.vMax = null;
            self.vMin = null;

            // Load the selected file
            $.ajax({
                url: filePath,
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
        
                    // Plot the profile with appropriate Z-axis autorange
                    plotProfile(self.isZFile);
                },
                error: function (err) {
                    console.error("Error loading file: ", err);
                }
            });
        });
        

        // Button click event to reverse the Z values and replot
        $("#reverseZButton").on("click", function () {
            var fileName = $("#scan_file_select option:selected").attr("value");

            //console.log(fileName.charAt(0));
            if (self.isZFile) {
                self.zValues.reverse();
                //self.zValues = self.zValues.map(z => z * -1); 
                plotProfile(true);
            }
            else {
                self.xValues.reverse(); // Reverse the X values
                plotProfile(false);

            }
            //plotProfile();     // Replot with the reversed Z values
        });

        // Handle slider input and update label
        $("#smoothingSlider").on("input", function() {
            $("#sliderValue").text($(this).val());
        });

        // Smoothing function call on button click
        $("#applySmoothingButton").on("click", function() {
            var windowSize = parseInt($("#smoothingSlider").val());
            // Apply Savitzky-Golay smoothing to the Z values
            self.zValues = savitzkyGolay(self.zValues, windowSize);
            plotProfile();  // Pass true to indicate we are plotting smoothed data
        });

        function savitzkyGolay(data, windowSize) {
            var halfWindow = Math.floor(windowSize / 2);
            var smoothed = [];

            for (var i = 0; i < data.length; i++) {
                var start = Math.max(0, i - halfWindow);
                var end = Math.min(data.length - 1, i + halfWindow);
                var sum = 0;

                // Simple smoothing by averaging over the window
                for (var j = start; j <= end; j++) {
                    sum += data[j];
                }

                smoothed[i] = sum / (end - start + 1);
            }
            return smoothed;
        }

        self.getPointsInRange = function() {
            var vMin = self.vMin !== null ? self.vMin : Math.min(...self.xValues);
            var vMax = self.vMax !== null ? self.vMax : Math.max(...self.xValues);
            
            var pointsInRange = [];
        
            for (var i = 0; i < self.xValues.length; i++) {
                if (self.xValues[i] >= vMin && self.xValues[i] <= vMax) {
                    pointsInRange.push({ x: self.xValues[i], z: self.zValues[i].toFixed(2) });
                }
            }
        
            return pointsInRange;
        };

        self.writeGCode = function() {
            //Plot data from min_X to max_X
            var plot = self.getPointsInRange();
            
            console.log(plot);
            var data = {
                plot_data: plot,
                tool_length: self.tool_length(),
                max_B: self.max_B(),
                min_B: self.min_B(),
                power: self.power(),
                feed: self.feed(),
                test: self.test(),
                start: self.start_max(),
                x_steps: self.x_steps(),
                segments: self.segments(),
                z_clear: clearance,
            };
    
            OctoPrint.simpleApiCommand("LaserProfile", "write_job", data)
                .done(function(response) {
                    console.log("GCode written successfully.");
                })
                .fail(function() {
                    console.error("Failed to write GCode.");
                });
        };

        self.gotoposition = function() {
            //check length of target_Position
            var clearance = Math.max(...self.zValues);
            var data = {
                plot_data: self.target_position,
                tool_length: self.tool_length(),
                max_B: self.max_B(),
                min_B: self.min_B(),
                power: self.power(),
                feed: self.feed(),
                test: self.test(),
                start: self.start_max(),
                x_steps: self.x_steps(),
                segments: self.segments(),
                z_clear: clearance,
            };
            console.log(data);
            OctoPrint.simpleApiCommand("LaserProfile", "go_to_position", data)
                .done(function(response) {
                    console.log("Go to target successful.");
                })
                .fail(function() {
                    console.error("Failed to go to target");
                });
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: LaserprofileViewModel,
        dependencies: ["loginStateViewModel", "settingsViewModel"],
        elements: ["#tab_plugin_LaserProfile"]
    });
});
