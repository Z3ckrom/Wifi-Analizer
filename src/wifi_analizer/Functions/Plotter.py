import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import tkinter as tk
# -------------------------
# Curve functions
# -------------------------
def laplace(center, width_mhz=20, x_min=1, x_max=165, points=800):
   x = np.linspace(x_min, x_max, points)
   # sigma scales with channel width (20MHz baseline)
   sigma = max(0.4, (width_mhz / 20.0) * 1.2)
   y = np.exp(-0.5 * ((x - center) / sigma) ** 2)
   return x, y

# -------------------------
# Plotter
# -------------------------
def plot_networks(networks, canvas_frame, band_var):
   fig, ax = plt.subplots(figsize=(10, 6))
   ax.set_facecolor("black")
   band = band_var
   ax.set_title(f"Wi-Fi Channel Overlap ({band} GHz)", fontsize=10, color="white")
   for ssid, ch, strength, color, width in networks:
       if ch is None:
           continue
       # Clamp strength and convert to dBm plotting range
       strength = max(-100.0, min(-30.0, float(strength)))
       # Choose x-range based on band for performance/readability
       if band == "2.4":
           x_min, x_max, points = 1, 14, 400
       else:
           x_min, x_max, points = 30, 165, 800
       x, y = laplace(ch, width_mhz=width, x_min=x_min, x_max=x_max, points=points)
       # Map normalized y (0..1) into dBm range (-100..-30) with peak at `strength`
       curve_depth = 30
       y_dbm = strength - (1 - y) * curve_depth
       ax.fill_between(x, y_dbm, -100, color=color, alpha=0.55)
       # place label slightly above peak
       peak_y = (np.max(y_dbm))
       ax.text(ch, peak_y + 1.5, f"{ssid} ({width}MHz)", color="white", ha="center", va="bottom", fontsize=8,
               bbox=dict(facecolor=color, alpha=0.25, edgecolor="none"))
   # Axis setup
   if band == "2.4":
       ax.set_xlim(0.5, 13.5)
       ax.set_xticks(range(1, 14))
   else:
       ax.set_xlim(30, 165)
       ax.set_xticks(range(30, 166, 10))
   ax.set_ylim(-100, -30)
   ax.set_yticks(range(-100, -20, 10))
   ax.set_xlabel("Wi-Fi Channel", fontsize=9, color="white")
   ax.set_ylabel("Signal Strength (dBm)", fontsize=9, color="white")
   ax.tick_params(colors="white")
   ax.grid(True, color="gray", alpha=0.25)
   for w in canvas_frame.winfo_children():
       w.destroy()
   canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
   canvas.draw()
   canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)