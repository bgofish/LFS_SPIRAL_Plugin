#!/usr/bin/env python3
"""
Standalone JSON Camera Generator GUI
GUI application for creating circular camera animations in JSON format.
No Blender required - generates JSON files directly using mathematical calculations.
Compatible with SuperSplat camera format.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import sys
import threading
from pathlib import Path

# Import the standalone generator
try:
    from standalone_camera_json import StandaloneCameraGenerator
except ImportError:
    # If not found, try to add the current directory to the path
    sys.path.insert(0, os.path.dirname(__file__))
    from standalone_camera_json import StandaloneCameraGenerator

class StandaloneJSONGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Standalone JSON Camera Generator")
        self.root.geometry("800x950")
        
        # Variables
        self.radius = tk.DoubleVar(value=10.0)
        self.center_x = tk.DoubleVar(value=0.0)
        self.center_y = tk.DoubleVar(value=0.0)
        self.center_z = tk.DoubleVar(value=0.0)
        self.target_x = tk.DoubleVar(value=0.0)
        self.target_y = tk.DoubleVar(value=0.0)
        self.target_z = tk.DoubleVar(value=-10.0)
        self.frames = tk.IntVar(value=180)
        self.fps = tk.IntVar(value=24)
        self.focal_length = tk.DoubleVar(value=35.0)
        self.sensor_size = tk.DoubleVar(value=32.0)  # Camera sensor width in mm
        self.output_path = tk.StringVar()
        
        # Animation variables
        self.animation_type = tk.StringVar(value="circular")
        self.direction = tk.StringVar(value="clockwise")
        # Spiral parameters
        self.spiral_loops = tk.DoubleVar(value=2.0)
        self.start_radius = tk.DoubleVar(value=5.0)
        self.end_radius = tk.DoubleVar(value=15.0)
        self.start_height = tk.DoubleVar(value=0.0)
        self.end_height = tk.DoubleVar(value=10.0)
        
        # Spiral follow-Y parameters
        self.spiral_follow_y = tk.BooleanVar(value=False)
        self.spiral_y_offset = tk.DoubleVar(value=0.0)

        # JSON-specific parameters
        self.convert_coords = tk.BooleanVar(value=False)  # Z-up to Y-up conversion
        self.nightly_build  = tk.BooleanVar(value=True)   # Lichtfeld Nightly vs stable 0.5.1
        self.precision = tk.IntVar(value=6)  # Decimal precision
        self.target_distance = tk.DoubleVar(value=10.0)  # Target distance for auto-calc
        self.use_auto_target = tk.BooleanVar(value=False)  # Auto-calculate target
        self.keyframe_step = tk.IntVar(value=1)  # Keyframe every N frames
        
        self.create_widgets()
        
    def create_widgets(self):
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        row = 0
        
        # Title
        title_label = ttk.Label(main_frame, text="Standalone JSON Camera Generator", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=row, column=0, columnspan=3, pady=(0, 10))
        row += 1
        
        # Subtitle
        # subtitle_label = ttk.Label(main_frame, text="No Blender Required - Pure Python Generation", 
                                 # font=("Arial", 12, "italic"), foreground="green")
        # subtitle_label.grid(row=row, column=0, columnspan=3, pady=(0, 20))
        # row += 1
        
        # Lichtfeld version toggle
        version_frame = ttk.LabelFrame(main_frame, text="Lichtfeld Version", padding="6")
        version_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        ttk.Checkbutton(version_frame, text="Nightly Build  (uncheck for stable 0.5.1)",
                        variable=self.nightly_build).pack(side=tk.LEFT)
        row += 1

        # Animation parameters section
        ttk.Label(main_frame, text="Animation Parameters:", font=("Arial", 12, "bold")).grid(
            row=row, column=0, columnspan=3, sticky=tk.W, pady=(10, 5))
        row += 1
        
        # Animation type selection
        type_frame = ttk.Frame(main_frame)
        type_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 10))
        
        ttk.Label(type_frame, text="Animation Type:", font=("Arial", 10, "bold")).grid(
            row=0, column=0, sticky=tk.W, padx=(0, 15))
        
        ttk.Radiobutton(type_frame, text="Circular", variable=self.animation_type, 
                       value="circular", command=self.on_animation_type_change).grid(
            row=0, column=1, padx=(0, 10))
        ttk.Radiobutton(type_frame, text="Spiral", variable=self.animation_type, 
                       value="spiral", command=self.on_animation_type_change).grid(
            row=0, column=2, padx=(0, 15))
        
        # Direction selection
        ttk.Label(type_frame, text="Direction:", font=("Arial", 10, "bold")).grid(
            row=0, column=3, sticky=tk.W, padx=(15, 10))
        ttk.Radiobutton(type_frame, text="Clockwise", variable=self.direction, 
                       value="clockwise").grid(row=0, column=4, padx=(0, 5))
        ttk.Radiobutton(type_frame, text="Counter-clockwise", variable=self.direction, 
                       value="counterclockwise").grid(row=0, column=5)
        row += 1
        
        # Circular parameters frame
        self.circular_frame = ttk.LabelFrame(main_frame, text="Circular Animation Parameters", padding="10")
        self.circular_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 10))
        
        # Radius (for circular)
        ttk.Label(self.circular_frame, text="Radius (meters):").grid(
            row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self.circular_frame, textvariable=self.radius, width=15).grid(
            row=0, column=1, sticky=tk.W, padx=(5, 0), pady=2)
        row += 1
        
        # Spiral parameters frame
        self.spiral_frame = ttk.LabelFrame(main_frame, text="Spiral Animation Parameters", padding="10")
        self.spiral_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(5, 10))
        
        # Spiral loops
        ttk.Label(self.spiral_frame, text="Number of loops:").grid(
            row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self.spiral_frame, textvariable=self.spiral_loops, width=10).grid(
            row=0, column=1, sticky=tk.W, padx=(5, 20), pady=2)
        
        # Start and end radius
        ttk.Label(self.spiral_frame, text="Start radius (m):").grid(
            row=0, column=2, sticky=tk.W, pady=2)
        ttk.Entry(self.spiral_frame, textvariable=self.start_radius, width=10).grid(
            row=0, column=3, sticky=tk.W, padx=(5, 20), pady=2)
        
        ttk.Label(self.spiral_frame, text="End radius (m):").grid(
            row=0, column=4, sticky=tk.W, pady=2)
        ttk.Entry(self.spiral_frame, textvariable=self.end_radius, width=10).grid(
            row=0, column=5, sticky=tk.W, padx=(5, 0), pady=2)
        
        # Start and end height
        ttk.Label(self.spiral_frame, text="Start height (m):").grid(
            row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self.spiral_frame, textvariable=self.start_height, width=10).grid(
            row=1, column=1, sticky=tk.W, padx=(5, 20), pady=2)
        
        ttk.Label(self.spiral_frame, text="End height (m):").grid(
            row=1, column=2, sticky=tk.W, pady=2)
        ttk.Entry(self.spiral_frame, textvariable=self.end_height, width=10).grid(
            row=1, column=3, sticky=tk.W, padx=(5, 0), pady=2)

        # Follow-Y target row
        ttk.Checkbutton(
            self.spiral_frame, text="Target follows camera Y",
            variable=self.spiral_follow_y,
            command=self.on_spiral_follow_y_change
        ).grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(6, 2))

        ttk.Label(self.spiral_frame, text="Y offset (m):").grid(
            row=2, column=2, sticky=tk.W, padx=(0, 5), pady=(6, 2))
        self.spiral_y_offset_spin = tk.Spinbox(
            self.spiral_frame, textvariable=self.spiral_y_offset,
            from_=-100.0, to=100.0, increment=0.5, width=8, format="%.2f",
            state="disabled"
        )
        self.spiral_y_offset_spin.grid(row=2, column=3, sticky=tk.W, padx=(5, 0), pady=(6, 2))
        
        row += 1
        
        # JSON-specific parameters section
        json_frame = ttk.LabelFrame(main_frame, text="JSON Export Options", padding="10")
        json_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(10, 10))
        
        # Coordinate system conversion
        # ttk.Checkbutton(json_frame, text="Convert coordinates to SuperSplat Y-up system", 
                       # variable=self.convert_coords).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=2)
        
        # Precision setting
        ttk.Label(json_frame, text="Decimal precision:").grid(row=1, column=0, sticky=tk.W, pady=2)
        precision_combo = ttk.Combobox(json_frame, textvariable=self.precision, width=10, 
                                     values=[3, 4, 5, 6, 7, 8], state="readonly")
        precision_combo.grid(row=1, column=1, sticky=tk.W, padx=(5, 20), pady=2)
        
        # Auto-target calculation
        auto_target_check = ttk.Checkbutton(json_frame, text="Auto-calculate target (override manual target)", 
                                          variable=self.use_auto_target, command=self.on_auto_target_change)
        auto_target_check.grid(row=1, column=2, columnspan=2, sticky=tk.W, padx=(20, 0), pady=2)
        
        ttk.Label(json_frame, text="Target distance (m):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.target_distance_entry = ttk.Entry(json_frame, textvariable=self.target_distance, width=10)
        self.target_distance_entry.grid(row=2, column=1, sticky=tk.W, padx=(5, 0), pady=2)
        
        # Keyframe step control
        ttk.Label(json_frame, text="Keyframe every:").grid(row=2, column=2, sticky=tk.W, padx=(20, 5), pady=2)
        keyframe_combo = ttk.Combobox(json_frame, textvariable=self.keyframe_step, width=8, 
                                    values=[1, 2, 5, 10, 20, 25, 50, 100, 150, 200], state="readonly")
        keyframe_combo.grid(row=2, column=3, sticky=tk.W, padx=(0, 5), pady=2)
        ttk.Label(json_frame, text="frames").grid(row=2, column=4, sticky=tk.W, pady=2)
        
        row += 1
        
        # Center coordinates
        ttk.Label(main_frame, text="Center coordinates:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, columnspan=3, sticky=tk.W, pady=(10, 2))
        row += 1
        
        center_frame = ttk.Frame(main_frame)
        center_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=2)
        
        ttk.Label(center_frame, text="X:").grid(row=0, column=0, padx=(0, 5))
        center_x_entry = tk.Entry(center_frame, textvariable=self.center_x, width=10, bg="#ffdddd")  # Light red
        center_x_entry.grid(row=0, column=1, padx=(0, 10))
        ttk.Label(center_frame, text="Y:").grid(row=0, column=2, padx=(0, 5))
        center_y_entry = tk.Entry(center_frame, textvariable=self.center_y, width=10, bg="#90EE90")  # Light green
        center_y_entry.grid(row=0, column=3, padx=(0, 10))
        ttk.Label(center_frame, text="Z:").grid(row=0, column=4, padx=(0, 5))
        center_z_entry = tk.Entry(center_frame, textvariable=self.center_z, width=10, bg="#ddffff")  # Light blue
        center_z_entry.grid(row=0, column=5)
        row += 1
        
        # Target coordinates
        ttk.Label(main_frame, text="Target coordinates:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, columnspan=3, sticky=tk.W, pady=(10, 2))
        row += 1
        
        self.target_frame = ttk.Frame(main_frame)
        self.target_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=2)
        
        ttk.Label(self.target_frame, text="X:").grid(row=0, column=0, padx=(0, 5))
        self.target_x_entry = tk.Entry(self.target_frame, textvariable=self.target_x, width=10, bg="#ffdddd")  # Light red
        self.target_x_entry.grid(row=0, column=1, padx=(0, 10))
        ttk.Label(self.target_frame, text="Y:").grid(row=0, column=2, padx=(0, 5))
        self.target_y_entry = tk.Entry(self.target_frame, textvariable=self.target_y, width=10, bg="#90EE90")  # Light green
        self.target_y_entry.grid(row=0, column=3, padx=(0, 10))
        ttk.Label(self.target_frame, text="Z:").grid(row=0, column=4, padx=(0, 5))
        self.target_z_entry = tk.Entry(self.target_frame, textvariable=self.target_z, width=10, bg="#ddffff")  # Light blue
        self.target_z_entry.grid(row=0, column=5)
        row += 1
        
        # Animation settings
        ttk.Label(main_frame, text="Animation settings:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, columnspan=3, sticky=tk.W, pady=(10, 2))
        row += 1
        
        anim_frame = ttk.Frame(main_frame)
        anim_frame.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=2)
        
        ttk.Label(anim_frame, text="Frames:").grid(row=0, column=0, padx=(0, 5))
        ttk.Entry(anim_frame, textvariable=self.frames, width=10).grid(row=0, column=1, padx=(0, 15))
        ttk.Label(anim_frame, text="FPS:").grid(row=0, column=2, padx=(0, 5))
        ttk.Entry(anim_frame, textvariable=self.fps, width=10).grid(row=0, column=3, padx=(0, 15))
        ttk.Label(anim_frame, text="Focal Length (mm):").grid(row=0, column=4, padx=(0, 5))
        ttk.Entry(anim_frame, textvariable=self.focal_length, width=10).grid(row=0, column=5)
        
        # Second row for sensor size
        ttk.Label(anim_frame, text="Sensor Size (mm):").grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        sensor_combo = ttk.Combobox(anim_frame, textvariable=self.sensor_size, width=12, 
                                  values=[24.0, 32.0, 36.0], state="readonly")
        sensor_combo.grid(row=1, column=2, padx=(0, 5), pady=(5, 0))
        ttk.Label(anim_frame, text="(24=APS-C, 32=Standard, 36=Full-frame)").grid(row=1, column=3, columnspan=3, sticky=tk.W, pady=(5, 0))
        row += 1
        
        # Output path section
        ttk.Label(main_frame, text="Output:", font=("Arial", 12, "bold")).grid(
            row=row, column=0, columnspan=3, sticky=tk.W, pady=(20, 5))
        row += 1
        
        ttk.Entry(main_frame, textvariable=self.output_path, width=60).grid(
            row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
        ttk.Button(main_frame, text="Browse", command=self.browse_output).grid(
            row=row, column=2, padx=(5, 0), pady=(0, 5))
        row += 1
        
        # Preset buttons
        preset_frame = ttk.Frame(main_frame)
        preset_frame.grid(row=row, column=0, columnspan=3, pady=(10, 0))
        
        # Circular presets
        ttk.Label(preset_frame, text="Circular Presets:", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(preset_frame, text="Close Orbit\n(3m, 120 frames)", 
                  command=self.load_close_orbit).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(preset_frame, text="Medium Orbit\n(10m, 180 frames)", 
                  command=self.load_your_example).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Button(preset_frame, text="Wide Orbit\n(20m, 240 frames)", 
                  command=self.load_wide_orbit).pack(side=tk.LEFT, padx=(0, 20))
        
        # Spiral presets
        ttk.Label(preset_frame, text="Spiral Presets:", font=("Arial", 9, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(preset_frame, text="Rising Spiral\n(5-15m, 2 loops)", 
                  command=self.load_rising_spiral).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(preset_frame, text="Descending Spiral\n(20-5m, 3 loops)", 
                  command=self.load_descending_spiral).pack(side=tk.LEFT)
        row += 1
        
        # Generate button
        ttk.Button(main_frame, text="Generate JSON File", command=self.generate_json,
                  style="Accent.TButton").grid(row=row, column=0, columnspan=3, 
                                              pady=(20, 10), ipadx=20, ipady=10)
        row += 1
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate')
        self.progress.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        row += 1
        
        # Output text
        ttk.Label(main_frame, text="Output Log:", font=("Arial", 10, "bold")).grid(
            row=row, column=0, columnspan=3, sticky=tk.W)
        row += 1
        
        self.output_text = scrolledtext.ScrolledText(main_frame, height=6, width=70)
        self.output_text.grid(row=row, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        main_frame.rowconfigure(row, weight=1)
        
        # Initialize UI state
        self.on_animation_type_change()
        self.on_auto_target_change()
    
    def on_spiral_follow_y_change(self):
        """Enable/disable the Y-offset spinbox based on the follow-Y toggle."""
        if self.spiral_follow_y.get():
            self.spiral_y_offset_spin.configure(state="normal")
        else:
            self.spiral_y_offset_spin.configure(state="disabled")

    def on_auto_target_change(self):
        """Handle auto-target checkbox change"""
        if self.use_auto_target.get():
            # Disable target coordinate entries
            self.target_x_entry.configure(state='disabled')
            self.target_y_entry.configure(state='disabled')
            self.target_z_entry.configure(state='disabled')
            self.target_distance_entry.configure(state='normal')
        else:
            # Enable target coordinate entries
            self.target_x_entry.configure(state='normal')
            self.target_y_entry.configure(state='normal')
            self.target_z_entry.configure(state='normal')
            self.target_distance_entry.configure(state='disabled')
    
    def browse_output(self):
        """Browse for output file location"""
        filename = filedialog.asksaveasfilename(
            title="Save JSON file as",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            self.output_path.set(filename)
    
    def load_your_example(self):
        """Load the user's original example parameters"""
        self.animation_type.set("circular")
        self.on_animation_type_change()
        
        self.radius.set(10.0)
        self.center_x.set(0.0)
        self.center_y.set(5.0)
        self.center_z.set(0.0)
        self.target_x.set(0.0)
        self.target_y.set(0.0)
        self.target_z.set(0.0)
        self.frames.set(180)
        self.fps.set(24)
        
        if not self.output_path.get():
            default_output = os.path.join(os.getcwd(), "your_example_camera.json")
            self.output_path.set(default_output)
    
    def load_close_orbit(self):
        """Load close orbit preset"""
        self.animation_type.set("circular")
        self.on_animation_type_change()
        
        self.radius.set(3.0)
        self.center_x.set(0.0)
        self.center_y.set(1.5)
        self.center_z.set(0.0)
        self.target_x.set(0.0)
        self.target_y.set(0.0)
        self.target_z.set(0.0)
        self.frames.set(120)
        self.fps.set(24)
        
        if not self.output_path.get():
            default_output = os.path.join(os.getcwd(), "close_orbit_camera.json")
            self.output_path.set(default_output)
    
    def load_wide_orbit(self):
        """Load wide orbit preset"""
        self.animation_type.set("circular")
        self.on_animation_type_change()
        
        self.radius.set(20.0)
        self.center_x.set(0.0)
        self.center_y.set(10.0)
        self.center_z.set(0.0)
        self.target_x.set(0.0)
        self.target_y.set(0.0)
        self.target_z.set(0.0)
        self.frames.set(240)
        self.fps.set(24)
        
        if not self.output_path.get():
            default_output = os.path.join(os.getcwd(), "wide_orbit_camera.json")
            self.output_path.set(default_output)
    
    def on_animation_type_change(self):
        """Handle animation type change to show/hide appropriate parameter frames"""
        if self.animation_type.get() == "circular":
            self.circular_frame.grid()
            self.spiral_frame.grid_remove()
        else:
            self.circular_frame.grid_remove()
            self.spiral_frame.grid()
    
    def load_rising_spiral(self):
        """Load rising spiral preset"""
        self.animation_type.set("spiral")
        self.on_animation_type_change()
        
        self.spiral_loops.set(2.0)
        self.start_radius.set(5.0)
        self.end_radius.set(5.0)
        self.start_height.set(0.0)
        self.end_height.set(10.0)
        
        self.center_x.set(0.0)
        self.center_y.set(0.0)
        self.center_z.set(5.0)  # Middle of start/end heights
        self.target_x.set(0.0)
        self.target_y.set(0.0)
        self.target_z.set(5.0)
        
        self.frames.set(240)  # More frames for spiral motion
        self.fps.set(24)
        self.direction.set("counterclockwise")
        
        if not self.output_path.get():
            default_output = os.path.join(os.getcwd(), "rising_spiral_camera.json")
            self.output_path.set(default_output)
    
    def load_descending_spiral(self):
        """Load descending spiral preset"""
        self.animation_type.set("spiral")
        self.on_animation_type_change()
        
        self.spiral_loops.set(3.0)
        self.start_radius.set(20.0)
        self.end_radius.set(5.0)
        self.start_height.set(15.0)
        self.end_height.set(0.0)
        
        self.center_x.set(0.0)
        self.center_y.set(0.0)
        self.center_z.set(7.5)  # Middle of start/end heights
        self.target_x.set(0.0)
        self.target_y.set(0.0)
        self.target_z.set(7.5)
        
        self.frames.set(300)  # Even more frames for complex spiral
        self.fps.set(24)
        self.direction.set("clockwise")
        
        if not self.output_path.get():
            default_output = os.path.join(os.getcwd(), "descending_spiral_camera.json")
            self.output_path.set(default_output)
    
    def log_message(self, message):
        """Add message to output log"""
        self.output_text.insert(tk.END, f"{message}\n")
        self.output_text.see(tk.END)
        self.root.update()
    
    def validate_inputs(self):
        """Validate all inputs before generation"""        
        if not self.output_path.get():
            messagebox.showerror("Error", "Please specify output file path")
            return False
        
        if self.radius.get() <= 0:
            messagebox.showerror("Error", "Radius must be greater than 0")
            return False
        
        if self.frames.get() <= 0:
            messagebox.showerror("Error", "Frames must be greater than 0")
            return False
        
        if self.fps.get() <= 0:
            messagebox.showerror("Error", "FPS must be greater than 0")
            return False
        
        return True
    
    def generate_json_thread(self):
        """Generate JSON file in separate thread"""
        try:
            generator = StandaloneCameraGenerator()
            
            # Prepare parameters
            center = (self.center_x.get(), self.center_y.get(), self.center_z.get())
            target = None if self.use_auto_target.get() else (self.target_x.get(), self.target_y.get(), self.target_z.get())
            target_distance = self.target_distance.get() if self.use_auto_target.get() else None
            
            self.log_message("Calculating camera positions...")
            
            # Generate animation data
            data = generator.generate_camera_animation(
                animation_type=self.animation_type.get(),
                direction=self.direction.get(),
                center=center,
                target=target,
                target_distance=target_distance,
                radius=self.radius.get(),
                start_radius=self.start_radius.get(),
                end_radius=self.end_radius.get(),
                start_height=self.start_height.get(),
                end_height=self.end_height.get(),
                spiral_loops=self.spiral_loops.get(),
                frames=self.frames.get(),
                fps=self.fps.get(),
                focal_length=self.focal_length.get(),
                sensor_size=self.sensor_size.get(),
                convert_coords=self.convert_coords.get(),
                nightly_build=self.nightly_build.get(),
                precision=self.precision.get(),
                keyframe_step=self.keyframe_step.get(),
                spiral_follow_y=self.spiral_follow_y.get(),
                spiral_y_offset=self.spiral_y_offset.get(),
            )
            
            self.log_message("Saving JSON file...")
            
            # Save to file
            generator.save_json(data, self.output_path.get())
            
            self.log_message("")
            self.log_message("✓ SUCCESS! JSON file generated successfully!")
            self.log_message(f"✓ File location: {self.output_path.get()}")
            self.log_message("")
            self.log_message("Ready for SuperSplat:")
            self.log_message("1. Open SuperSplat")
            self.log_message("2. Import your JSON camera file")
            self.log_message("3. Load your camera animation in the Camera Poses panel")
            
            # Show success message
            self.root.after(0, lambda: messagebox.showinfo(
                "Success", 
                f"JSON file generated successfully!\n\nLocation: {self.output_path.get()}\n\nYou can now import this into SuperSplat."
            ))
            
        except Exception as e:
            self.log_message(f"✗ ERROR: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to generate JSON file:\n{str(e)}"))
        
        finally:
            # Stop progress bar
            self.root.after(0, self.progress.stop)
    
    def generate_json(self):
        """Generate JSON file"""
        if not self.validate_inputs():
            return
        
        # Clear output log
        self.output_text.delete(1.0, tk.END)
        
        # Show parameters
        self.log_message("=== Standalone JSON Camera Generator ===")
        self.log_message(f"Animation Type: {self.animation_type.get()}")
        self.log_message(f"Direction: {self.direction.get()}")
        
        if self.animation_type.get() == "circular":
            self.log_message(f"Radius: {self.radius.get()}m")
        else:
            self.log_message(f"Spiral Loops: {self.spiral_loops.get()}")
            self.log_message(f"Start Radius: {self.start_radius.get()}m -> End Radius: {self.end_radius.get()}m")
            self.log_message(f"Start Height: {self.start_height.get()}m -> End Height: {self.end_height.get()}m")
            if self.spiral_follow_y.get():
                self.log_message(f"Target follows camera Y  (offset: {self.spiral_y_offset.get():+.2f}m)")
            
        self.log_message(f"Center: ({self.center_x.get()}, {self.center_y.get()}, {self.center_z.get()})")
        
        if self.use_auto_target.get():
            self.log_message(f"Target: Auto-calculated (distance: {self.target_distance.get()}m)")
        else:
            self.log_message(f"Target: ({self.target_x.get()}, {self.target_y.get()}, {self.target_z.get()})")
            
        self.log_message(f"Frames: {self.frames.get()}")
        self.log_message(f"FPS: {self.fps.get()}")
        self.log_message(f"Focal Length: {self.focal_length.get()}mm")
        
        # Calculate and show FOV
        from standalone_camera_json import focal_length_to_fov
        fov = focal_length_to_fov(self.focal_length.get(), self.sensor_size.get())
        self.log_message(f"Sensor Size: {self.sensor_size.get()}mm")
        self.log_message(f"Field of View: {fov:.1f}°")
        self.log_message(f"Keyframe Step: Every {self.keyframe_step.get()} frame{'s' if self.keyframe_step.get() > 1 else ''}")
        self.log_message(f"Precision: {self.precision.get()} decimal places")
        self.log_message(f"Coordinate Conversion: {'Yes' if self.convert_coords.get() else 'No'}")
        self.log_message(f"Output: {self.output_path.get()}")
        self.log_message("")
        
        # Start progress bar
        self.progress.start()
        
        # Run generation in separate thread
        thread = threading.Thread(target=self.generate_json_thread)
        thread.daemon = True
        thread.start()

def main():
    root = tk.Tk()
    app = StandaloneJSONGUI(root)
    
    # Load your example by default
    app.load_your_example()
    
    root.mainloop()

if __name__ == "__main__":
    main()
