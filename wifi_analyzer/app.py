"""Tkinter application for channel analysis and access-point hunting."""

from __future__ import annotations

import math
import platform
import queue
import re
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .models import Network, ScanResult
from .radio import matches_band, normalize_bssid, stable_color
from .scanners import BaseScanner
from .tracker import SignalTracker

class WifiAnalyzerApp:
    # RF sampling is intentionally independent from the expensive analyzer redraw.
    HUNTER_INTERVAL_MS = 800
    GAUGE_FRAME_MS = 50

    def __init__(self, root: tk.Tk, scanner: BaseScanner):
        self.root = root
        self.scanner = scanner
        self.result_queue: queue.Queue[tuple[str, Optional[str], ScanResult]] = queue.Queue()
        self.scan_running = False
        self.active_scan_kind: Optional[str] = None
        self.pending_analyzer_scan = False
        self.analyzer_after_id: Optional[str] = None
        self.hunter_after_id: Optional[str] = None
        self.poll_after_id: Optional[str] = None
        self.beep_after_id: Optional[str] = None
        self.gauge_after_id: Optional[str] = None
        self.gauge_resize_after_id: Optional[str] = None
        self.closing = False
        self.tracking = False
        self.networks: list[Network] = []
        self.network_by_bssid: dict[str, Network] = {}
        self.tracker = SignalTracker()

        self.gauge_target = 0.0
        self.gauge_display = 0.0
        self.gauge_caption = "Select an SSID and BSSID"
        self.gauge_items: dict[str, int] = {}
        self.gauge_geometry = (0.0, 0.0, 0.0)

        self.band_var = tk.StringVar(value="2.4")
        self.refresh_var = tk.StringVar(value="5")
        self.status_var = tk.StringVar(value=f"Ready — {scanner.description}")
        self.ssid_var = tk.StringVar()
        self.bssid_var = tk.StringVar()
        self.audio_var = tk.BooleanVar(value=False)
        self.metric_vars = {
            name: tk.StringVar(value="—")
            for name in ("current", "smoothed", "average", "peak", "trend", "samples", "elapsed", "channel", "security")
        }

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.poll_after_id = self.root.after(100, self._poll_queue)
        self.root.after(250, lambda: self.start_analyzer_scan(force=True))
        self._set_gauge_target(0, self.gauge_caption, immediate=True)

    def _build_ui(self) -> None:
        self.root.title("Wi-Fi Analyzer + AP Hunter")
        self.root.geometry("1120x760")
        self.root.minsize(900, 650)
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        controls = ttk.Frame(self.root, padding=(10, 8))
        controls.pack(fill=tk.X)
        ttk.Label(controls, text="Wi-Fi band:").pack(side=tk.LEFT)
        for text, value in (("2.4 GHz", "2.4"), ("5 GHz", "5")):
            ttk.Radiobutton(
                controls,
                text=text,
                variable=self.band_var,
                value=value,
                command=self._band_changed,
            ).pack(side=tk.LEFT, padx=(5, 0))
        ttk.Separator(controls, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=12)
        ttk.Label(controls, text="Refresh:").pack(side=tk.LEFT)
        refresh_box = ttk.Combobox(
            controls, textvariable=self.refresh_var, values=("2", "5", "10", "20"), width=4, state="readonly"
        )
        refresh_box.pack(side=tk.LEFT, padx=5)
        refresh_box.bind("<<ComboboxSelected>>", lambda _event: self._schedule_analyzer_scan())
        self.scan_button = ttk.Button(controls, text="Scan now", command=lambda: self.start_analyzer_scan(force=True))
        self.scan_button.pack(side=tk.LEFT, padx=8)
        ttk.Label(controls, textvariable=self.status_var).pack(side=tk.LEFT, padx=12)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.analyzer_tab = ttk.Frame(self.notebook)
        self.hunter_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.analyzer_tab, text="Channel Analyzer")
        self.notebook.add(self.hunter_tab, text="AP Hunter")
        self._build_analyzer_tab()
        self._build_hunter_tab()
    def _build_analyzer_tab(self) -> None:
        pane = ttk.Panedwindow(self.analyzer_tab, orient=tk.VERTICAL)
        pane.pack(fill=tk.BOTH, expand=True)
        plot_frame = ttk.Frame(pane)
        table_frame = ttk.Frame(pane, padding=(0, 6, 0, 0))
        pane.add(plot_frame, weight=4)
        pane.add(table_frame, weight=1)
        self.figure = Figure(figsize=(10, 5), dpi=100, facecolor="black")
        self.axis = self.figure.add_subplot(111)
        self.figure.subplots_adjust(left=0.07, right=0.98, bottom=0.12, top=0.9)
        self.plot_canvas = FigureCanvasTkAgg(self.figure, master=plot_frame)
        self.plot_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        columns = ("ssid", "bssid", "channel", "rssi", "security")
        self.network_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=6)
        headings = {"ssid": "SSID", "bssid": "BSSID", "channel": "Channel", "rssi": "RSSI", "security": "Security"}
        widths = {"ssid": 230, "bssid": 180, "channel": 80, "rssi": 90, "security": 150}
        for column in columns:
            self.network_tree.heading(column, text=headings[column])
            self.network_tree.column(column, width=widths[column], anchor=tk.CENTER if column in ("channel", "rssi") else tk.W)
        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.network_tree.yview)
        self.network_tree.configure(yscrollcommand=scrollbar.set)
        self.network_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.network_tree.bind("<Double-1>", self._track_tree_selection)
    def _build_hunter_tab(self) -> None:
        outer = ttk.Frame(self.hunter_tab, padding=12)
        outer.pack(fill=tk.BOTH, expand=True)
        select_frame = ttk.LabelFrame(outer, text="Target access point", padding=10)
        select_frame.pack(fill=tk.X)
        ttk.Label(select_frame, text="SSID:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.ssid_combo = ttk.Combobox(select_frame, textvariable=self.ssid_var, state="readonly", width=34)
        self.ssid_combo.grid(row=0, column=1, sticky=tk.EW, padx=(0, 15))
        self.ssid_combo.bind("<<ComboboxSelected>>", self._ssid_selected)
        ttk.Label(select_frame, text="BSSID / radio:").grid(row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.bssid_combo = ttk.Combobox(select_frame, textvariable=self.bssid_var, state="readonly", width=43)
        self.bssid_combo.grid(row=0, column=3, sticky=tk.EW)
        select_frame.columnconfigure(1, weight=1)
        select_frame.columnconfigure(3, weight=1)
        content = ttk.Frame(outer)
        content.pack(fill=tk.BOTH, expand=True, pady=10)
        left = ttk.Frame(content)
        right = ttk.LabelFrame(content, text="Live measurements", padding=12)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(12, 0))
        self.gauge = tk.Canvas(left, bg="#111111", highlightthickness=0, height=410)
        self.gauge.pack(fill=tk.BOTH, expand=True)
        self.gauge.bind("<Configure>", self._gauge_resized)
        metric_labels = (
            ("Current RSSI", "current"),
            ("Smoothed RSSI", "smoothed"),
            ("Rolling average", "average"),
            ("Peak RSSI", "peak"),
            ("Trend", "trend"),
            ("Samples", "samples"),
            ("Elapsed", "elapsed"),
            ("Channel / band", "channel"),
            ("Security", "security"),
        )
        for row, (label, key) in enumerate(metric_labels):
            ttk.Label(right, text=label + ":").grid(row=row, column=0, sticky=tk.W, pady=5, padx=(0, 15))
            ttk.Label(right, textvariable=self.metric_vars[key], font=("TkDefaultFont", 10, "bold")).grid(
                row=row, column=1, sticky=tk.W, pady=5
            )
        buttons = ttk.Frame(outer)
        buttons.pack(fill=tk.X)
        self.start_button = ttk.Button(buttons, text="Start tracking", command=self.start_tracking)
        self.start_button.pack(side=tk.LEFT)
        self.stop_button = ttk.Button(buttons, text="Stop", command=self.stop_tracking, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=7)
        ttk.Button(buttons, text="Reset peak/history", command=self.reset_tracker).pack(side=tk.LEFT)
        ttk.Checkbutton(buttons, text="Audio proximity beeps", variable=self.audio_var, command=self._audio_changed).pack(
            side=tk.LEFT, padx=15
        )
        ttk.Label(
            buttons,
            text="RSSI indicates relative proximity only; reflections, walls and antenna orientation affect it.",
            foreground="#555555",
        ).pack(side=tk.RIGHT)
    def start_analyzer_scan(self, force: bool = False) -> None:
        if self.closing:
            return
        if self.analyzer_after_id is not None:
            self.root.after_cancel(self.analyzer_after_id)
            self.analyzer_after_id = None
        if self.scan_running:
            self.pending_analyzer_scan = True
            if force:
                self.status_var.set("A scan is already running; analyzer refresh queued…")
            return
        self.pending_analyzer_scan = False
        self._start_scan_worker("analyzer", self.band_var.get())
        self.scan_button.configure(state=tk.DISABLED)
        self.status_var.set("Scanning all access points…")

    def start_hunter_scan(self) -> None:
        if self.closing or not self.tracking or not self.tracker.target_bssid:
            return
        if self.hunter_after_id is not None:
            self.root.after_cancel(self.hunter_after_id)
            self.hunter_after_id = None
        if self.scan_running:
            self.hunter_after_id = self.root.after(150, self.start_hunter_scan)
            return
        self._start_scan_worker("hunter", self.band_var.get(), self.tracker.target_bssid)

    def _start_scan_worker(self, kind: str, band: str, target_bssid: Optional[str] = None) -> None:
        self.scan_running = True
        self.active_scan_kind = kind
        threading.Thread(
            target=self._scan_worker,
            args=(kind, band, target_bssid),
            daemon=True,
        ).start()

    def _scan_worker(self, kind: str, band: str, target_bssid: Optional[str]) -> None:
        try:
            result = (
                self.scanner.scan_target(band, target_bssid)
                if kind == "hunter" and target_bssid
                else self.scanner.scan(band)
            )
        except Exception as exc:  # Keep worker failures away from Tk's main loop.
            result = ScanResult([], error=f"Unexpected scanner error: {exc}")
        self.result_queue.put((kind, target_bssid, result))

    def _poll_queue(self) -> None:
        if self.closing:
            return
        try:
            while True:
                kind, requested_target, result = self.result_queue.get_nowait()
                self._handle_scan_result(kind, requested_target, result)
        except queue.Empty:
            pass
        self.poll_after_id = self.root.after(50, self._poll_queue)

    def _handle_scan_result(
        self,
        kind: str,
        requested_target: Optional[str],
        result: ScanResult,
    ) -> None:
        self.scan_running = False
        self.active_scan_kind = None
        self.scan_button.configure(state=tk.NORMAL)

        if kind == "analyzer":
            if result.error:
                self.status_var.set(result.error)
            else:
                self.status_var.set(result.status or f"Found {len(result.networks)} access point radios.")
            # Do not discard the last usable list on a transient scan error.
            if result.networks or not result.error:
                self.networks = result.networks
                self.network_by_bssid = {network.bssid: network for network in self.networks}
                self._draw_plot()
                self._refresh_network_table()
                self._refresh_target_controls()
            if self.tracking:
                self._update_tracker_from_scan(result.networks)
            self._schedule_analyzer_scan()
        else:
            # A target can change while an OS scan is still completing. Ignore
            # stale results instead of counting them as a miss for the new AP.
            target_is_current = (
                self.tracking
                and requested_target is not None
                and normalize_bssid(requested_target) == self.tracker.target_bssid
            )
            if target_is_current:
                self._update_tracker_from_scan(result.networks)
                if result.error and self.tracker.misses >= 2:
                    self.status_var.set(f"AP Hunter scan error: {result.error}")
                elif self.tracker.target_bssid:
                    self.status_var.set(
                        f"Tracking {self.tracker.target_bssid} — {self.tracker.sample_count} samples"
                    )
            self._schedule_hunter_scan()

        if self.pending_analyzer_scan:
            self.pending_analyzer_scan = False
            self.root.after_idle(lambda: self.start_analyzer_scan(force=True))

    def _schedule_analyzer_scan(self) -> None:
        if self.closing:
            return
        if self.analyzer_after_id is not None:
            self.root.after_cancel(self.analyzer_after_id)
        delay = max(2, int(self.refresh_var.get())) * 1000
        self.analyzer_after_id = self.root.after(delay, self.start_analyzer_scan)

    def _schedule_hunter_scan(self, immediate: bool = False) -> None:
        if self.closing or not self.tracking:
            return
        if self.hunter_after_id is not None:
            self.root.after_cancel(self.hunter_after_id)
        delay = 0 if immediate else self.HUNTER_INTERVAL_MS
        self.hunter_after_id = self.root.after(delay, self.start_hunter_scan)

    def _band_changed(self) -> None:
        if self.tracking:
            self.stop_tracking()
        self.start_analyzer_scan(force=True)

    def _draw_plot(self) -> None:
        axis = self.axis
        axis.clear()
        axis.set_facecolor("black")
        band = self.band_var.get()
        axis.set_title(f"Wi-Fi Channel Overlap ({band} GHz)", fontsize=11, color="white")
        x_min, x_max, points = ((0.5, 14.5, 400) if band == "2.4" else (30, 177, 800))
        x_values = np.linspace(x_min, x_max, points)
        for network in self.networks:
            if not matches_band(network.channel, band):
                continue
            strength = max(-100.0, min(-30.0, network.rssi))
            sigma = max(0.5, (network.width / 20.0) * 1.2)
            normalized = np.exp(-0.5 * ((x_values - network.channel) / sigma) ** 2)
            y_values = -100 + normalized * (strength + 100)
            color = stable_color(network.bssid)
            axis.fill_between(x_values, y_values, -100, color=color, alpha=0.5)
            axis.text(
                network.channel,
                strength + 1.5,
                f"{network.ssid}\n{network.bssid[-8:]}",
                color="white",
                ha="center",
                va="bottom",
                fontsize=7,
                bbox=dict(facecolor=color, alpha=0.25, edgecolor="none"),
            )
        if band == "2.4":
            axis.set_xlim(0.5, 14.5)
            axis.set_xticks(range(1, 15))
        else:
            axis.set_xlim(30, 177)
            common_channels = (range(30, 166, 10))
            axis.set_xticks(common_channels)
        axis.set_ylim(-100, -25)
        axis.set_yticks(range(-100, -20, 10))
        axis.set_xlabel("Wi-Fi channel", fontsize=9, color="white")
        axis.set_ylabel("Signal strength (dBm)", fontsize=9, color="white")
        axis.tick_params(colors="white")
        axis.grid(True, color="gray", alpha=0.25)
        for spine in axis.spines.values():
            spine.set_color("#777777")
        self.plot_canvas.draw_idle()
    def _refresh_network_table(self) -> None:
        """Update changed rows in place instead of rebuilding the Treeview."""
        desired = {network.bssid: network for network in self.networks}
        existing = set(self.network_tree.get_children())
        for stale in existing - desired.keys():
            self.network_tree.delete(stale)
        for position, network in enumerate(sorted(self.networks, key=lambda n: n.rssi, reverse=True)):
            values = (network.ssid, network.bssid, network.channel, f"{network.rssi:.1f} dBm", network.security)
            if network.bssid in existing:
                if tuple(self.network_tree.item(network.bssid, "values")) != tuple(str(value) for value in values):
                    self.network_tree.item(network.bssid, values=values)
                self.network_tree.move(network.bssid, "", position)
            else:
                self.network_tree.insert("", position, iid=network.bssid, values=values)

    def _refresh_target_controls(self) -> None:
        # Keep the locked target visible while hunting, even if one scan misses it.
        # Otherwise a transient miss could make the disabled selector jump to a
        # different radio that happens to advertise the same SSID.
        if self.tracking:
            return
        previous_ssid = self.ssid_var.get()
        ssids = sorted({network.ssid for network in self.networks}, key=str.casefold)
        self.ssid_combo["values"] = ssids
        if previous_ssid in ssids:
            self.ssid_var.set(previous_ssid)
        elif ssids:
            self.ssid_var.set(ssids[0])
        else:
            self.ssid_var.set("")
        self._set_bssid_choices()
    def _ssid_selected(self, _event=None) -> None:
        if self.tracking:
            self.stop_tracking()
        self._set_bssid_choices()
    def _set_bssid_choices(self, preferred_bssid: Optional[str] = None) -> None:
        selected_ssid = self.ssid_var.get()
        matches = [network for network in self.networks if network.ssid == selected_ssid]
        labels = [f"{n.bssid}  |  ch {n.channel}  |  {n.rssi:.1f} dBm" for n in matches]
        current_bssid = preferred_bssid or self._selected_bssid()
        self.bssid_combo["values"] = labels
        chosen = next((label for label in labels if label.startswith(current_bssid or "\0")), "")
        if not chosen and labels:
            chosen = labels[0]
        self.bssid_var.set(chosen)
    def _selected_bssid(self) -> Optional[str]:
        match = re.match(r"([0-9A-Fa-f:]{17})", self.bssid_var.get())
        return normalize_bssid(match.group(1)) if match else None
    def _track_tree_selection(self, _event=None) -> None:
        selection = self.network_tree.selection()
        if not selection:
            return
        network = self.network_by_bssid.get(selection[0])
        if not network:
            return
        self.ssid_var.set(network.ssid)
        self._set_bssid_choices(network.bssid)
        self.notebook.select(self.hunter_tab)
    def start_tracking(self) -> None:
        bssid = self._selected_bssid()
        if not bssid or bssid not in self.network_by_bssid:
            messagebox.showwarning("Select a target", "Select an SSID and a BSSID/radio before starting AP Hunter.")
            return
        target = self.network_by_bssid[bssid]
        if self.band_var.get() != target.band:
            self.band_var.set(target.band)
        self.tracker.set_target(bssid)
        self.tracking = True
        self.start_button.configure(state=tk.DISABLED)
        self.stop_button.configure(state=tk.NORMAL)
        self.ssid_combo.configure(state=tk.DISABLED)
        self.bssid_combo.configure(state=tk.DISABLED)
        self.status_var.set(f"Tracking {target.ssid} ({bssid})…")
        self._update_metric_labels(target)
        self._set_gauge_target(0, "Waiting for a fresh target sample…", immediate=True)
        self._schedule_hunter_scan(immediate=True)
        self._schedule_beep()
    def stop_tracking(self) -> None:
        self.tracking = False
        self.start_button.configure(state=tk.NORMAL)
        self.stop_button.configure(state=tk.DISABLED)
        self.ssid_combo.configure(state="readonly")
        self.bssid_combo.configure(state="readonly")
        if self.hunter_after_id is not None:
            self.root.after_cancel(self.hunter_after_id)
            self.hunter_after_id = None
        if self.beep_after_id is not None:
            self.root.after_cancel(self.beep_after_id)
            self.beep_after_id = None
        self.status_var.set("Tracking stopped.")
    def reset_tracker(self) -> None:
        target = self.tracker.target_bssid
        self.tracker.reset()
        self.tracker.target_bssid = target
        self._update_metric_labels(None)
        self._set_gauge_target(0, "Waiting for a target sample…" if target else "Select an SSID and BSSID", immediate=True)
    def _update_tracker_from_scan(self, networks: list[Network]) -> None:
        if not self.tracking or not self.tracker.target_bssid:
            return
        target = next((n for n in networks if n.bssid == self.tracker.target_bssid), None)
        if target is None:
            self.tracker.miss()
            self.metric_vars["elapsed"].set(self.tracker.elapsed)
            self.metric_vars["trend"].set("Target not seen")
            if self.tracker.misses >= 3:
                self._set_gauge_target(0, "Target not seen in recent scans")
            return
        score = self.tracker.add(target.rssi, target.signal_percent)
        self._update_metric_labels(target)
        self._set_gauge_target(score, self.tracker.trend)
        if self.audio_var.get() and self.beep_after_id is None:
            self._schedule_beep()
    @staticmethod
    def _format_dbm(value: Optional[float]) -> str:
        return "—" if value is None else f"{value:.1f} dBm"
    def _update_metric_labels(self, target: Optional[Network]) -> None:
        self.metric_vars["current"].set(self._format_dbm(self.tracker.current))
        self.metric_vars["smoothed"].set(self._format_dbm(self.tracker.smoothed))
        self.metric_vars["average"].set(self._format_dbm(self.tracker.average))
        self.metric_vars["peak"].set(self._format_dbm(self.tracker.peak))
        self.metric_vars["trend"].set(self.tracker.trend if self.tracker.sample_count else "—")
        self.metric_vars["samples"].set(str(self.tracker.sample_count))
        self.metric_vars["elapsed"].set(self.tracker.elapsed)
        self.metric_vars["channel"].set(f"{target.channel} / {target.band} GHz" if target else "—")
        self.metric_vars["security"].set(target.security if target else "—")
    def _set_gauge_target(self, score: float, caption: str, immediate: bool = False) -> None:
        self.gauge_target = max(0.0, min(100.0, float(score)))
        self.gauge_caption = caption
        if not self.gauge_items:
            self._rebuild_gauge()
        elif "caption" in self.gauge_items:
            self.gauge.itemconfigure(self.gauge_items["caption"], text=caption)
        if immediate:
            self.gauge_display = self.gauge_target
            self._update_gauge_dynamic()
        if self.gauge_after_id is None and not immediate:
            self.gauge_after_id = self.root.after(self.GAUGE_FRAME_MS, self._animate_gauge)

    def _gauge_resized(self, _event=None) -> None:
        if self.gauge_resize_after_id is not None:
            self.root.after_cancel(self.gauge_resize_after_id)
        self.gauge_resize_after_id = self.root.after(75, self._rebuild_gauge)

    def _rebuild_gauge(self) -> None:
        self.gauge_resize_after_id = None
        canvas = self.gauge
        canvas.delete("all")
        width = max(canvas.winfo_width(), 320)
        height = max(canvas.winfo_height(), 300)
        center_x, center_y = width / 2, height * 0.67
        radius = max(100.0, min(width * 0.34, height * 0.48))
        self.gauge_geometry = (center_x, center_y, radius)
        box = (center_x - radius, center_y - radius, center_x + radius, center_y + radius)
        arc_width = max(14, min(28, int(radius / 7)))
        canvas.create_arc(*box, start=180, extent=-60, style=tk.ARC, width=arc_width, outline="#D9534F")
        canvas.create_arc(*box, start=120, extent=-60, style=tk.ARC, width=arc_width, outline="#F0AD4E")
        canvas.create_arc(*box, start=60, extent=-60, style=tk.ARC, width=arc_width, outline="#5CB85C")
        for tick in range(0, 101, 10):
            angle = math.radians(180 - tick * 1.8)
            inner = radius - 25
            outer = radius + 2
            canvas.create_line(
                center_x + inner * math.cos(angle),
                center_y - inner * math.sin(angle),
                center_x + outer * math.cos(angle),
                center_y - outer * math.sin(angle),
                fill="#DDDDDD",
                width=2,
            )
            label_radius = radius + 34
            canvas.create_text(
                center_x + label_radius * math.cos(angle),
                center_y - label_radius * math.sin(angle),
                text=str(tick),
                fill="#CCCCCC",
                font=("TkDefaultFont", 9),
            )
        self.gauge_items = {
            "needle": canvas.create_line(center_x, center_y, center_x - radius + 38, center_y, fill="#D9534F", width=6, arrow=tk.LAST),
            "hub": canvas.create_oval(center_x - 11, center_y - 11, center_x + 11, center_y + 11, fill="#EEEEEE", outline=""),
            "value": canvas.create_text(center_x, center_y + 55, text="0%", fill="white", font=("TkDefaultFont", 30, "bold")),
            "caption": canvas.create_text(center_x, center_y + 91, text=self.gauge_caption, fill="#DDDDDD", font=("TkDefaultFont", 13, "bold")),
        }
        canvas.create_text(center_x, 28, text="AP PROXIMITY", fill="#AAAAAA", font=("TkDefaultFont", 11, "bold"))
        self._update_gauge_dynamic()

    def _animate_gauge(self) -> None:
        self.gauge_after_id = None
        difference = self.gauge_target - self.gauge_display
        if abs(difference) < 0.1:
            self.gauge_display = self.gauge_target
        else:
            self.gauge_display += difference * 0.18
        self._update_gauge_dynamic()
        if abs(self.gauge_target - self.gauge_display) >= 0.1 and not self.closing:
            self.gauge_after_id = self.root.after(self.GAUGE_FRAME_MS, self._animate_gauge)

    def _update_gauge_dynamic(self) -> None:
        if not self.gauge_items:
            return
        center_x, center_y, radius = self.gauge_geometry
        clamped = max(0.0, min(100.0, self.gauge_display))
        angle = math.radians(180 - clamped * 1.8)
        needle_length = radius - 38
        needle_x = center_x + needle_length * math.cos(angle)
        needle_y = center_y - needle_length * math.sin(angle)
        needle_color = "#5CB85C" if clamped >= 67 else "#F0AD4E" if clamped >= 34 else "#D9534F"
        self.gauge.coords(self.gauge_items["needle"], center_x, center_y, needle_x, needle_y)
        self.gauge.itemconfigure(self.gauge_items["needle"], fill=needle_color)
        self.gauge.itemconfigure(self.gauge_items["value"], text=f"{clamped:.0f}%")

    def _audio_changed(self) -> None:
        if self.audio_var.get() and self.tracking:
            self._schedule_beep()
        elif self.beep_after_id is not None:
            self.root.after_cancel(self.beep_after_id)
            self.beep_after_id = None
    def _schedule_beep(self) -> None:
        if self.beep_after_id is not None:
            self.root.after_cancel(self.beep_after_id)
            self.beep_after_id = None
        if not (self.tracking and self.audio_var.get() and self.tracker.smoothed is not None):
            return
        try:
            if platform.system() == "Windows":
                import winsound
                winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
            else:
                self.root.bell()
        except (ImportError, RuntimeError, tk.TclError):
            pass
        delay = int(max(140, 1300 - self.tracker.score * 11.0))
        self.beep_after_id = self.root.after(delay, self._schedule_beep)
    def close(self) -> None:
        self.closing = True
        for after_id in (
            self.analyzer_after_id,
            self.hunter_after_id,
            self.poll_after_id,
            self.beep_after_id,
            self.gauge_after_id,
            self.gauge_resize_after_id,
        ):
            if after_id is not None:
                try:
                    self.root.after_cancel(after_id)
                except tk.TclError:
                    pass
        self.root.destroy()
