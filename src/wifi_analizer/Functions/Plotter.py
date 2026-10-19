from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.animation import FuncAnimation
import tkinter as tk
from matplotlib.patches import Polygon
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
# Channel Shape
# -------------------------
def wifi_channel_shape(center,width_mhz=20,x_min=1,x_max=14,points=1200):
    
    x = np.linspace(x_min,x_max,points)
    half_width = max(1.5, width_mhz/10)
    d = np.abs(x-center)
    y = 1 - (d/half_width)**2
    y[y < 0] = 0
    y = y**0.75
    return x,y

# -------------------------
# Plotter
# -------------------------
def plot_networks(fig, ax, networks, canvas_frame, band_var, listOfNetworks, canvas):

    ax.clear()


    if band_var == '2.4':
            x_min,x_max=0.5,14.5
            channels=list(range(1,15))
            ax.set_xlim(x_min,x_max)
            ax.set_xticks(channels)
    else:
        x_min,x_max=30,170
        channels=[36,40,44,48,52,56,60,64,100,104,108,112,116,120,124,128,132,136,140,144,149,153,157,161,165]
        # ax.set_xlim(x_min,x_max)
        ax.set_xticks(range(len(channels)))
        ax.set_xticklabels(channels)
        ax.set_xlim(-1, len(channels))
    for c in channels:
        ax.axvline(c,color='#808080',alpha=0.18,linewidth=1,zorder=0)
    
    for ssid,ch,rssi,color,width in networks:
        if ch is None:
            continue
    
        x,y = wifi_channel_shape(ch,width,x_min,x_max)
        y_dbm = rssi - ((1-y)*50)
    
        ax.fill_between(x,y_dbm,-100,color=color,alpha=0.22,zorder=2)
        ax.plot(x,y_dbm,color=color,linewidth=2.5,zorder=3)
    
        ax.text(ch,np.max(y_dbm)+1,f'"{ssid}"',color=color,fontsize=11,fontweight='bold',ha='center')
        ax.set_facecolor('#050B0F')
        ax.set_ylim(-100,-35)
        ax.set_yticks([-100,-90,-80,-70,-60,-50,-40])
        ax.yaxis.tick_right()
        ax.yaxis.set_label_position('right')
        ax.set_ylabel('dBm',color='white')
        ax.set_xlabel("Channel", color="white")
        ax.tick_params(colors='white',labelsize=12)
    
        ax.grid(True,color='#666666',alpha=0.30)
    
        ax.spines['top'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_color('#AAAAAA')
        ax.spines['right'].set_color('#AAAAAA')
    
        ax.set_title(f'Wi‑Fi Analyzer - {band_var} GHz', color='white', fontsize=16)
        canvas.draw_idle()