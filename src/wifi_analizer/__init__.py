import threading, time
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
import tkinter as tk
from wifi_analizer.Functions.NetworkScaner import scan_wifi_win
from wifi_analizer.Functions.Plotter import plot_networks
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from matplotlib.figure import Figure

iface_status = ""
wifi_iface = True


def getNetworkFeed(band_var):
    return scan_wifi_win(band_var)
    
    # root.after(int(refresh_var.get()) * 1000, lambda: getNetworkFeed(band_var, canvas_frame, fig, ax))

def startGetNetworkFeed():
    process = executor.submit(getNetworkFeed, band_var.get())
    checkProcess(process)

def checkProcess(process):
    if process.done():
        if process.result(): 
            print(process.result())
            plot_networks(fig, ax, process.result(), canvas_frame,band_var.get(), listOfNetworks, canvas)
            
            root.after(int(refresh_var.get()) * 1000, startGetNetworkFeed)
    else:
        root.after(100, checkProcess, process)
        

# -------------------------
# UX Display
# -------------------------
def main() -> None:
    global root, refresh_var, fig, ax, canvas_frame, band_var, executor, listOfNetworks, canvas
    listOfNetworks = {}
    executor = ProcessPoolExecutor()
    root = tk.Tk()
    refresh_var = tk.StringVar(value="6")
    root.title("Wi-Fi Analyzer")
    root.geometry('1200x750')
    band_var = tk.StringVar(value="2.4")
    ctrl_frame = tk.Frame(root)
    ctrl_frame.pack(pady=6)
    # Canvas - Wifi display
    canvas_frame = tk.Frame(root, bg="black")
    canvas_frame.pack(fill=tk.BOTH, expand=True)

    # Grid set up
    
    fig = Figure(figsize=(12,7))
    ax = fig.add_subplot(111)
    fig.patch.set_facecolor('#050B0F')
    ax.set_ylim(-100,-35)
    ax.set_yticks([-100,-90,-80,-70,-60,-50,-40])
    ax.yaxis.tick_right()
    ax.yaxis.set_label_position('right')
    ax.set_ylabel('dBm',color='white')
    ax.tick_params(colors='white',labelsize=12)
    ax.grid(True,color='#666666',alpha=0.30)
    ax.spines['top'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_color('#AAAAAA')
    ax.spines['right'].set_color('#AAAAAA')
    ax.set_facecolor('#050B0F')
    ax.set_title(f'Wi‑Fi Analyzer - Starting Up', color='white', fontsize=16)
    ax.set_xlim(0.5, 14.5)
    ax.set_ylim(-100, -20)
    ax.set_xticks(range(1, 15))
    ax.set_xlabel("Channel", color="white")
    ax.set_ylabel("RSSI (dBm)", color="white")
    canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    
    #Buttons above
    tk.Label(ctrl_frame, text="Wi-Fi Band:").grid(row=0, column=0, padx=6)
    tk.Radiobutton(ctrl_frame, text="2.4 GHz", variable=band_var, value="2.4").grid(row=0, column=1)
    tk.Radiobutton(ctrl_frame, text="5 GHz", variable=band_var, value="5").grid(row=0, column=2)
    tk.Label(ctrl_frame, text="Refresh (sec):").grid(row=0, column=3, padx=6)
    tk.OptionMenu(ctrl_frame, refresh_var, "3", "6", "9", "12").grid(row=0, column=4)
    # scan_btn = tk.Button(ctrl_frame, text="Force Scan", command=startGetNetworkFeed)
    # scan_btn.grid(row=0, column=5, padx=8)
    # Status
    iface_label = tk.Label(root, text=iface_status, fg="green" if wifi_iface else "red")
    iface_label.pack(pady=4)
    
    # Display the result as set up refresh
    root.after(200, startGetNetworkFeed)
    root.mainloop()
    

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
    

