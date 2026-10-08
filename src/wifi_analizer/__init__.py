import tkinter as tk
from wifi_analizer.Functions.NetworkScan import scan_wifi_win
from wifi_analizer.Functions.Plotter import plot_networks
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
iface_status = ""
wifi_iface = True

def getNetworkFeed(band_var, canvas_frame, fig, ax):
    listOfNetworks = scan_wifi_win(band_var)
    plot_networks(fig, ax, listOfNetworks, canvas_frame ,band_var)


# -------------------------
# UX Display
# -------------------------
def main() -> None:
    root = tk.Tk()
    root.title("Wi-Fi Analyzer")
    root.geometry("1000x650")
    band_var = tk.StringVar(value="2.4")
    refresh_var = tk.StringVar(value="5")
    ctrl_frame = tk.Frame(root)
    ctrl_frame.pack(pady=6)
    # Canvas - Wifi display
    canvas_frame = tk.Frame(root, bg="black")
    canvas_frame.pack(fill=tk.BOTH, expand=True)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_facecolor("black")
    canvas = FigureCanvasTkAgg(fig, master=canvas_frame)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    #Buttons above
    tk.Label(ctrl_frame, text="Wi-Fi Band:").grid(row=0, column=0, padx=6)
    tk.Radiobutton(ctrl_frame, text="2.4 GHz", variable=band_var, value="2.4").grid(row=0, column=1)
    tk.Radiobutton(ctrl_frame, text="5 GHz", variable=band_var, value="5").grid(row=0, column=2)
    tk.Label(ctrl_frame, text="Refresh (sec):").grid(row=0, column=3, padx=6)
    tk.OptionMenu(ctrl_frame, refresh_var, "2", "5", "10", "20").grid(row=0, column=4)
    scan_btn = tk.Button(ctrl_frame, text="Force Scan Now", command=lambda:getNetworkFeed(band_var.get(), canvas_frame, fig, ax))
    scan_btn.grid(row=0, column=5, padx=8)
    # Status
    iface_label = tk.Label(root, text=iface_status, fg="green" if wifi_iface else "red")
    iface_label.pack(pady=4)
    
    # Display the GUI
    root.mainloop()

if __name__ == "__main__":
    main()
    
