from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from core.user_preferences import load_preferences, save_preference

NECESSITY_LABELS = {
    "essential": "ESSENTIAL", "optional": "OPTIONAL",
    "potentially_unnecessary": "POTENTIALLY UNNECESSARY", "unknown": "UNKNOWN",
}
RISK_LABELS = {"CRITICAL": "Critical", "HIGH": "High", "MEDIUM": "Medium",
               "LOW": "Low", "NOT_EVALUATED": "Not evaluated"}
PREFERENCE_LABELS = {"keep": "Keep this app", "dont_need": "I do not need this", "unsure": "Not sure yet"}


class ApplicationManager(ctk.CTkFrame):
    COLUMNS = ("application", "package", "necessity", "risk", "state", "memory")
    NECESSITY_FILTERS = ("All categories", *NECESSITY_LABELS.values(), "ALREADY DISABLED")

    def __init__(self, master, on_rescan=None):
        super().__init__(master, fg_color="transparent")
        self.pack(fill="both", expand=True)
        self.on_rescan = on_rescan
        self.packages: list[dict] = []
        self.sort_desc: dict[str, bool] = {}
        self.preferences = load_preferences()
        heading = ctk.CTkFrame(self, fg_color="transparent")
        heading.pack(fill="x", pady=(4, 8))
        ctk.CTkLabel(heading, text="Application Manager", font=ctk.CTkFont(size=21, weight="bold")).pack(side="left")
        self.rescan_button = ctk.CTkButton(heading, text="Rescan Applications", width=150, command=on_rescan)
        self.rescan_button.pack(side="right")
        filters = ctk.CTkFrame(self, fg_color="transparent")
        filters.pack(fill="x", pady=(0, 8))
        self.search = ctk.CTkEntry(filters, placeholder_text="Search by app name or package ID", width=280)
        self.search.pack(side="left", padx=(0, 8))
        self.search.bind("<KeyRelease>", lambda _event: self.refresh())
        self.category_filter = ctk.CTkOptionMenu(filters, values=list(self.NECESSITY_FILTERS),
                                                 command=lambda _v: self.refresh(), width=225)
        self.category_filter.set("All categories")
        self.category_filter.pack(side="left", padx=4)
        self.state_filter = ctk.CTkOptionMenu(filters, values=["Any state", "Enabled", "Disabled"],
                                              command=lambda _v: self.refresh(), width=170)
        self.state_filter.set("Any state")
        self.state_filter.pack(side="left", padx=4)
        self.count_label = ctk.CTkLabel(filters, text="0 applications", text_color="#a1a4ad")
        self.count_label.pack(side="right")

        self.summary = ctk.CTkLabel(self, text="Necessity and disable risk are independent assessments.",
                                    anchor="w", text_color="#aeb0b8")
        self.summary.pack(fill="x", pady=(0, 8))
        self.bind("<Configure>", lambda event: self.summary.configure(wraplength=max(300, event.width - 20)))

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True)
        table_panel = ctk.CTkFrame(content, corner_radius=10)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)
        table_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        table_panel.grid_columnconfigure(0, weight=1)
        table_panel.grid_rowconfigure(0, weight=1)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#17181c", foreground="#e7e8eb", fieldbackground="#17181c", rowheight=34)
        style.configure("Treeview.Heading", background="#222329", foreground="#aeb0b8", relief="flat")
        self.table = ttk.Treeview(table_panel, columns=self.COLUMNS, show="headings", selectmode="browse")
        titles = {"application": "APPLICATION", "package": "PACKAGE ID", "necessity": "NECESSITY",
                  "risk": "DISABLE RISK", "state": "STATE", "memory": "RAM, KiB"}
        widths = {"application": 150, "package": 200, "necessity": 190, "risk": 140, "state": 100, "memory": 90}
        for col in self.COLUMNS:
            self.table.heading(col, text=titles[col], command=lambda key=col: self.sort_by(key))
            self.table.column(col, width=widths[col], anchor="w")
        ybar = ttk.Scrollbar(table_panel, orient="vertical", command=self.table.yview)
        xbar = ttk.Scrollbar(table_panel, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.table.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=(8, 0))
        ybar.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=(8, 0))
        xbar.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        self.table.bind("<<TreeviewSelect>>", self.show_details)

        self.detail = ctk.CTkScrollableFrame(content, width=320, corner_radius=10)
        self.detail.grid(row=0, column=1, sticky="ns")
        self.detail_title = ctk.CTkLabel(self.detail, text="Select an application", font=ctk.CTkFont(size=17, weight="bold"),
                                         wraplength=280, justify="left")
        self.detail_title.pack(anchor="w", padx=12, pady=(12, 8))
        self.detail_body = ctk.CTkLabel(self.detail, text="Select an application to see explanations, evidence and measurements.",
                                        wraplength=280, justify="left", anchor="w")
        self.detail_body.pack(fill="x", padx=12, pady=4)
        ctk.CTkLabel(self.detail, text="My preference", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=12, pady=(16, 4))
        self.preference_var = tk.StringVar(value="")
        self.preference_menu = ctk.CTkOptionMenu(self.detail, values=list(PREFERENCE_LABELS.values()),
                                                  command=self._set_preference, width=245)
        self.preference_menu.pack(anchor="w", padx=12, pady=(0, 16))
        self.empty = ctk.CTkLabel(self, text="Connect your TV and run a scan.", text_color="#9699a2")

    def set_packages(self, packages: list[dict]):
        self.packages = packages
        self.preferences = load_preferences()
        counts = {key: sum(row.get("necessity") == key for row in packages) for key in NECESSITY_LABELS}
        disabled = sum(bool(row.get("disabled")) for row in packages)
        self.summary.configure(text=(f"{len(packages)} applications · Essential {counts['essential']} · "
                                     f"Optional {counts['optional']} · Potentially unnecessary {counts['potentially_unnecessary']} · "
                                     f"Unknown {counts['unknown']} · Already disabled {disabled}. "
                                     "Necessity does not determine disable risk."))
        self.refresh()

    def sort_by(self, key: str):
        self.sort_desc[key] = not self.sort_desc.get(key, False)
        self.refresh(sort=key)

    def refresh(self, sort: str | None = None):
        query = self.search.get().casefold()
        cat, state = self.category_filter.get(), self.state_filter.get()
        rows = []
        label_to_key = {label: key for key, label in NECESSITY_LABELS.items()}
        for row in self.packages:
            package = str(row.get("package", ""))
            app_name = str(row.get("application") or package)
            if query not in app_name.casefold() and query not in package.casefold():
                continue
            if cat == "ALREADY DISABLED" and not row.get("disabled"):
                continue
            if cat in label_to_key and row.get("necessity", "unknown") != label_to_key[cat]:
                continue
            if state == "Enabled" and row.get("disabled"): continue
            if state == "Disabled" and not row.get("disabled"): continue
            rows.append(row)
        if sort:
            reverse = self.sort_desc.get(sort, False)
            if sort == "memory":
                rows.sort(key=lambda row: row.get("process_memory_kb") if row.get("process_memory_kb") is not None else -1,
                          reverse=reverse)
            else:
                key = "application" if sort == "application" else sort
                rows.sort(key=lambda row: str(row.get(key) or "").casefold(), reverse=reverse)
        self.table.delete(*self.table.get_children())
        for row in rows:
            pkg = str(row.get("package", ""))
            necessity = NECESSITY_LABELS.get(row.get("necessity", "unknown"), "UNKNOWN")
            memory = row.get("process_memory_kb")
            self.table.insert("", "end", iid=pkg, values=(row.get("application") or pkg, pkg, necessity,
                               RISK_LABELS.get(row.get("risk"), "Not evaluated"),
                               "Disabled" if row.get("disabled") else "Enabled", memory if memory is not None else "—"))
        self.count_label.configure(text=f"Showing {len(rows)} of {len(self.packages)}")
        if rows:
            self.empty.place_forget()
        else:
            self.empty.configure(text="No matches found." if self.packages else "Connect your TV and run a scan.")
            self.empty.place(relx=0.5, rely=0.5, anchor="center")

    def show_details(self, _event=None):
        selected = self.table.selection()
        if not selected:
            return
        row = next((item for item in self.packages if item.get("package") == selected[0]), None)
        if row is None:
            return
        self._selected_row = row
        pkg = row.get("package", "")
        pref = self.preferences.get(pkg)
        self.preference_menu.set(PREFERENCE_LABELS.get(pref, "Not sure yet"))
        necessity = NECESSITY_LABELS.get(row.get("necessity", "unknown"), "UNKNOWN")
        risk = RISK_LABELS.get(row.get("risk"), "Not evaluated")
        running = row.get("running_process")
        running_text = "Yes, a process was detected" if running is True else "No process detected" if running is False else "Could not verify"
        memory = f"{row['process_memory_kb']} KiB (measured)" if row.get("process_memory_kb") is not None else "Unavailable"
        permissions = "\n".join(row.get("requested_permissions") or []) or "Unavailable or empty"
        body = "\n\n".join((
            f"{necessity} · disable risk: {risk}",
            "Purpose: " + str(row.get("appears_to_do", "Unknown; further investigation is needed.")),
            "Why it may be needed: " + str(row.get("necessity_reason", "Insufficient evidence.")),
            "Background activity: " + running_text,
            "Measured process RAM: " + memory,
            "Permissions:\n" + permissions,
            "Dependencies: " + ("Declared services exist; dependencies may exist." if row.get("services") else "Not established by available evidence."),
            "What could break: " + str(row.get("potential_consequences", "Not established.")),
            "Assessment reason: " + str(row.get("necessity_reason", row.get("risk_reason", "Insufficient evidence.")),),
            "Confidence: " + str(row.get("confidence", "low")),
            "Path: " + str(row.get("path") or "Unavailable"),
            "Package: " + pkg,
        ))
        self.detail_title.configure(text=str(row.get("application") or pkg))
        self.detail_body.configure(text=body)

    def _set_preference(self, label: str):
        row = getattr(self, "_selected_row", None)
        if not row:
            return
        inverse = {value: key for key, value in PREFERENCE_LABELS.items()}
        self.preferences = save_preference(row["package"], inverse[label])
