from __future__ import annotations

import queue
import threading
from tkinter import filedialog, messagebox, simpledialog
import json
from pathlib import Path

import customtkinter as ctk

from core.adb_manager import ADBManager
from core.application_analyzer import analyze_packages
from core.device_scanner import scan_device
from core.package_manager import scan_packages
from core.report_manager import export_report
from core.safe_debloater import SafeDebloater, BACKUP_DIR
from core.user_preferences import load_preferences
from gui.application_manager import ApplicationManager
from gui.dashboard import Dashboard
from gui.safe_debloater import SafeDebloaterView
from gui.performance import PerformanceView


class YaOSApp(ctk.CTk):
    def __init__(self, adb_path: str):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title("YaOS Debloater")
        self.geometry("1120x760")
        self.minsize(900, 640)
        self.configure(fg_color="#111216")
        self.adb = ADBManager(adb_path)
        self.debloater = SafeDebloater(self.adb)
        self.events: queue.Queue = queue.Queue()
        self.devices = []
        self.selected_serial: str | None = None
        self.device_data: dict = {}
        self.package_data: list[dict] = []
        self._pending_auto_scan = False
        self._connect_checks = 0
        self._active_page = "Overview"
        self._build()
        self.after(100, self._drain_events)
        self.after(350, self.refresh_devices)

    def _build(self):
        shell = ctk.CTkFrame(self, fg_color="transparent")
        shell.pack(fill="both", expand=True)

        # Navigation is part of the permanent application shell, not device content.
        self.sidebar = ctk.CTkFrame(shell, width=218, corner_radius=0, fg_color="#17181d")
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        ctk.CTkLabel(self.sidebar, text="YAOS", font=ctk.CTkFont(size=24, weight="bold"),
                     text_color="#f2f3f5").pack(anchor="w", padx=22, pady=(26, 0))
        ctk.CTkLabel(self.sidebar, text="SMART TV TOOLS", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#858892").pack(anchor="w", padx=23, pady=(1, 24))
        self.sidebar_connect = ctk.CTkButton(self.sidebar, text="＋  Connect TV", height=42,
                                             font=ctk.CTkFont(size=13, weight="bold"),
                                             command=self.connect)
        self.sidebar_connect.pack(fill="x", padx=14, pady=(0, 22))
        ctk.CTkLabel(self.sidebar, text="WORKSPACE", font=ctk.CTkFont(size=10, weight="bold"),
                     text_color="#737680").pack(anchor="w", padx=20, pady=(0, 7))
        self.nav_buttons = {}
        for page, glyph in (("Overview", "◫"), ("Applications", "▦"), ("Application Manager", "◇"),
                            ("Safe Debloater", "♢"), ("Performance Optimizer", "↗")):
            button = ctk.CTkButton(self.sidebar, text=f"{glyph}   {page}", height=40, anchor="w",
                                   fg_color="transparent", hover_color="#292a31",
                                   text_color="#d5d6dc", command=lambda name=page: self.show_page(name))
            button.pack(fill="x", padx=9, pady=2)
            self.nav_buttons[page] = button
        spacer = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        spacer.pack(fill="both", expand=True)
        ctk.CTkFrame(self.sidebar, height=1, fg_color="#2b2d34").pack(fill="x", padx=15, pady=(0, 12))
        ctk.CTkLabel(self.sidebar, text="●  SINGLE-PACKAGE MODE", text_color="#75c9a0",
                     fg_color="#1c3028", corner_radius=9, padx=10, pady=8,
                     font=ctk.CTkFont(size=10, weight="bold")).pack(anchor="w", padx=14, pady=(0, 18))

        self.workspace = ctk.CTkFrame(shell, fg_color="transparent")
        self.workspace.pack(side="left", fill="both", expand=True, padx=(22, 24))
        topbar = ctk.CTkFrame(self.workspace, fg_color="transparent")
        topbar.pack(fill="x", pady=(23, 14))
        self.page_title = ctk.CTkLabel(topbar, text="Overview", font=ctk.CTkFont(size=24, weight="bold"))
        self.page_title.pack(side="left")
        self.device_menu = ctk.CTkOptionMenu(topbar, values=["No device connected"], width=210,
                                             command=self._select_device)
        self.device_menu.set("No device connected")
        self.device_menu.pack(side="right", padx=(8, 0))
        self.disconnect_button = ctk.CTkButton(topbar, text="Disconnect", width=94, height=34,
                                               state="disabled", fg_color="#34353b", hover_color="#45464d",
                                               command=self.disconnect)
        self.disconnect_button.pack(side="right", padx=(8, 0))
        self.scan_button = ctk.CTkButton(topbar, text="Scan Device", width=110, height=34,
                                         state="disabled", command=self.scan)
        self.scan_button.pack(side="right", padx=(8, 0))

        self.views = ctk.CTkFrame(self.workspace, fg_color="transparent")
        self.views.pack(fill="both", expand=True)
        self.dashboard = Dashboard(self.views, on_connect=self.connect)
        self.dashboard.pack(fill="both", expand=True)
        self.apps = ApplicationManager(self.views, on_rescan=self.scan_packages_only)
        self.apps.pack_forget()
        self.safe = SafeDebloaterView(self.views, on_dry_run=self.safe_dry_run,
                                     on_backup=self.safe_backup, on_disable=self.safe_disable,
                                     on_restore=self.safe_restore)
        self.safe.pack_forget()
        self.performance = PerformanceView(self.views, self)

        footer = ctk.CTkFrame(self.workspace, fg_color="transparent")
        footer.pack(fill="x", pady=(10, 14))
        self.status = ctk.CTkLabel(footer, text="No device connected", text_color="#a1a4ad", anchor="w")
        self.status.pack(side="left", fill="x", expand=True)
        self.export_button = ctk.CTkButton(footer, text="Export JSON report", width=150,
                                           state="disabled", fg_color="#34353b", hover_color="#45464d",
                                           command=self.save_report)
        self.export_button.pack(side="right")
        self.show_page("Overview")

    def show_page(self, page: str):
        self._active_page = page
        self.page_title.configure(text=page)
        self.dashboard.pack_forget()
        self.apps.pack_forget()
        self.safe.pack_forget()
        self.performance.pack_forget()
        (self.performance if page == "Performance Optimizer" else self.dashboard if page == "Overview" else self.safe if page == "Safe Debloater" else self.apps).pack(fill="both", expand=True)
        for name, button in self.nav_buttons.items():
            button.configure(fg_color="#292a31" if name == page else "transparent")

    def _background(self, fn, success, label, failure=None):
        self.status.configure(text=label)
        def work():
            try:
                self.events.put((success, fn(), None, failure))
            except Exception as exc:
                self.events.put((success, None, exc, failure))
        threading.Thread(target=work, daemon=True).start()

    def _drain_events(self):
        try:
            while True:
                callback, result, error, failure = self.events.get_nowait()
                if error:
                    (failure or self._show_error)(error)
                else:
                    callback(result)
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def _show_error(self, error: Exception):
        self.status.configure(text=f"Error: {error}")

    def _safe_error(self, error: Exception):
        self.status.configure(text=f"Operation error: {error}")
        self.safe.result.configure(text=str(error))
        messagebox.showerror("Operation failed", str(error), parent=self)

    def refresh_devices(self):
        self._background(self.adb.devices, self._devices_updated, "Checking ADB devices…",
                          failure=self._devices_failed)

    def _devices_failed(self, error: Exception):
        if not self.selected_serial:
            self.dashboard.show_disconnected(f"Could not check ADB devices: {error}")
            self.status.configure(text="No device connected · ADB check failed")
        self.after(5000, self.refresh_devices)

    def _devices_updated(self, devices):
        self.devices = devices
        ready = [device for device in devices if device.state == "device"]
        names = [device.serial for device in ready] or ["No device connected"]
        current = self.selected_serial if self.selected_serial in names else names[0]
        self.device_menu.configure(values=names)
        self.device_menu.set(current)

        if current == "No device connected":
            self.selected_serial = None
            self.scan_button.configure(state="disabled")
            self.disconnect_button.configure(state="disabled")
            self.export_button.configure(state="disabled")
            self.device_data = {}
            self.package_data = []
            self.apps.set_packages([])
            self.safe.set_packages([])
            self.dashboard.show_disconnected()
            unauthorized = any(device.state == "unauthorized" for device in devices)
            self.status.configure(text=("ADB authorization needed · approve the prompt on your TV" if unauthorized
                                        else "No device connected"))
            if self._pending_auto_scan:
                self._connect_checks += 1
                if self._connect_checks >= 8:
                    self._pending_auto_scan = False
                    self.dashboard.show_disconnected(
                        "No authorized TV appeared. Check the IP and port, same-network connection, and TV ADB authorization.")
                    self.status.configure(text="Connection timed out · check the TV address and ADB authorization")
                    self.after(5000, self.refresh_devices)
                else:
                    self.after(1500, self.refresh_devices)
            else:
                self.after(5000, self.refresh_devices)
            return

        self.selected_serial = current
        self.scan_button.configure(state="normal")
        self.disconnect_button.configure(state="normal")
        self.dashboard.show_connected(current)
        if self._pending_auto_scan:
            self._pending_auto_scan = False
            self.scan()
        else:
            self.status.configure(text=f"Connected · {current}")
        self.after(5000, self.refresh_devices)

    def _select_device(self, serial):
        self.selected_serial = serial if serial != "No device connected" else None
        if self.selected_serial:
            self.dashboard.show_connected(serial)
            self.scan()

    def connect(self):
        self.show_page("Overview")
        host, port = self.dashboard.host_entry.get().strip(), self.dashboard.port_entry.get().strip()
        try:
            port_number = int(port)
        except ValueError:
            self.dashboard.show_disconnected("Enter a numeric port between 1 and 65535.")
            self.status.configure(text="Invalid port")
            return
        if not host or not 1 <= port_number <= 65535:
            self.dashboard.show_disconnected("Enter a TV IP address and a port from 1 to 65535.")
            self.status.configure(text="Invalid connection address")
            return
        self._pending_auto_scan = True
        self._connect_checks = 0
        self.dashboard.set_connecting(True)
        self.status.configure(text=f"Connecting to {host}:{port_number}…")
        self._background(lambda: self.adb.connect(host, port_number), self._connected,
                         f"Connecting to {host}:{port_number}…", failure=self._connection_failed)

    def _connected(self, message):
        self.status.configure(text=f"ADB accepted connection · {message or 'checking device'}")
        self.refresh_devices()

    def _connection_failed(self, error: Exception):
        self._pending_auto_scan = False
        readable = str(error).strip() or "ADB could not connect to this address."
        self.dashboard.show_disconnected(f"Connection failed: {readable}")
        self.status.configure(text=f"Connection failed: {readable}")

    def disconnect(self):
        if not self.selected_serial:
            self.status.configure(text="No device connected")
            return
        serial = self.selected_serial
        self._background(lambda: self.adb.disconnect(serial), self._disconnected,
                         f"Disconnecting {serial}…", failure=self._show_error)

    def _disconnected(self, message):
        self._pending_auto_scan = False
        self.status.configure(text=message or "Disconnected")
        self.selected_serial = None
        self.refresh_devices()

    def scan(self):
        serial = self.selected_serial
        if not serial:
            self.status.configure(text="No device connected · scanning is unavailable")
            return
        def scan_all():
            device = scan_device(self.adb, serial)
            packages = scan_packages(self.adb, serial, progress=self._package_progress)
            packages = analyze_packages(packages, device)
            return device, packages
        self._background(scan_all, self._scan_complete, f"Reading information from {serial}…",
                         failure=self._scan_failed)

    def _package_progress(self, current: int, total: int, package: str):
        self.events.put((self._show_package_progress, (current, total, package), None, None))

    def _show_package_progress(self, progress):
        current, total, package = progress
        self.status.configure(text=f"Scanning applications {current}/{total} · {package}")

    def scan_packages_only(self):
        serial = self.selected_serial
        if not serial:
            self.status.configure(text="No connected device; application scan unavailable")
            return
        self.apps.rescan_button.configure(state="disabled", text="Scanning…")
        def scan_apps():
            if not self.device_data:
                self.device_data = scan_device(self.adb, serial)
            raw = scan_packages(self.adb, serial, progress=self._package_progress)
            return analyze_packages(raw, self.device_data)
        self._background(scan_apps,
                         self._packages_complete, "Reading installed applications…",
                         failure=self._packages_failed)

    def _packages_complete(self, packages):
        packages = analyze_packages(packages, self.device_data) if self.device_data else packages
        self.package_data = packages
        self.apps.set_packages(packages)
        self.safe.set_packages(packages)
        self.apps.rescan_button.configure(state="normal", text="Rescan Applications")
        self.status.configure(text=f"Application scan complete · {len(packages)} packages")

    def _packages_failed(self, error: Exception):
        self.apps.rescan_button.configure(state="normal", text="Rescan Applications")
        self.status.configure(text=f"Application scan failed: {error}")
        self.apps.empty.configure(text=f"Application scan failed: {error}")

    def _scan_complete(self, data):
        if not self.selected_serial or data[0].get("serial") != self.selected_serial:
            return
        self.device_data, self.package_data = data
        self.dashboard.update_device(self.device_data)
        self.apps.set_packages(self.package_data)
        self.safe.set_packages(self.package_data)
        self.export_button.configure(state="normal")
        self.status.configure(text=f"Scan complete · {len(self.package_data)} packages")

    def safe_dry_run(self):
        row, serial = self.safe.selected, self.selected_serial
        if not row or not serial: return
        self._background(lambda: self.debloater.dry_run(serial, row, load_preferences().get(row["package"])),
                         self.safe.show_plan, "Verifying package on TV…")

    def safe_backup(self):
        row, serial = self.safe.selected, self.selected_serial
        if not row or not serial: return
        def done(path):
            self.safe.backup_path = path
            self.safe.result.configure(text=f"State backup saved: {path.name}. Application data was not backed up.")
            self.safe._set_actions()
            self.status.configure(text="Package state backup saved")
        self._background(lambda: self.debloater.backup(serial, row), done, "Saving package state…")

    def safe_disable(self):
        row, serial, plan = self.safe.selected, self.selected_serial, self.safe.verified_plan
        if not row or not serial or not plan or not plan.get("eligible") or plan.get("package") != row.get("package") or plan.get("device", {}).get("serial") != serial:
            return
        package = row["package"]
        consequences = str(row.get("potential_consequences") or "Consequences are unknown.")
        answer = simpledialog.askstring("Confirm Disable", f"Only this package will be disabled:\n{package}\n\n"
                                       f"Potential consequences:\n{consequences}\n\n"
                                       "Type the exact package ID to confirm:", parent=self)
        if answer != package: return
        if not messagebox.askyesno("Disable application?", f"Disable {package} for user 0?\n\n"
                                   "A state backup will be saved first. Application data is not backed up.", parent=self):
            return
        def done(path):
            self.safe.backup_path = path
            self.safe.verified_plan = None
            self.safe.result.configure(text="Disabled state verified on TV. The package can now be restored.")
            self.safe._set_actions()
            self.scan()
        self._background(lambda: self.debloater.disable(serial, row, load_preferences().get(package),
                                                         confirmed_package=package), done, "Disabling one package and verifying the result…",
                         failure=self._safe_error)

    def safe_restore(self):
        serial = self.selected_serial
        if not serial: return
        selected = filedialog.askopenfilename(title="Select a package state backup", initialdir=BACKUP_DIR,
                                              filetypes=[("JSON", "*.json")])
        if not selected: return
        path = Path(selected)
        try:
            if path.resolve().parent != BACKUP_DIR.resolve():
                raise ValueError("Select a backup from the application backup folder.")
            record = json.loads(path.read_text(encoding="utf-8"))
            package = record["package"]
        except (OSError, ValueError, KeyError) as exc:
            self._show_error(exc)
            return
        answer = simpledialog.askstring("Confirm Restore", f"Restore package {package}?\n"
                                       "Type the exact package ID:", parent=self)
        if answer != package: return
        def done(_result):
            self.status.configure(text=f"Package {package} is enabled again and verified on TV")
            self.scan()
        self._background(lambda: self.debloater.restore(serial, path, confirmed_package=package), done,
                         "Restoring package and verifying the result…", failure=self._safe_error)

    def _scan_failed(self, error: Exception):
        self.status.configure(text=f"Scan failed: {error}")
        self.dashboard.error_label.configure(text=f"Scan failed: {error}")

    def save_report(self):
        if not self.device_data:
            self.status.configure(text="Scan a connected TV before exporting a report.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON report", "*.json")],
                                            initialfile="yaos-diagnostics.json")
        if not path:
            return
        try:
            export_report(path, self.device_data, self.package_data)
            self.status.configure(text=f"Report saved: {path}")
        except OSError as exc:
            self.status.configure(text=f"Could not save report: {exc}")
