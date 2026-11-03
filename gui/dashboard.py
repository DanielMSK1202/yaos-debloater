from __future__ import annotations

import customtkinter as ctk


class Dashboard(ctk.CTkFrame):
    """Always populated overview, including a first-run disconnected state."""

    def __init__(self, master, on_connect):
        super().__init__(master, fg_color="transparent")
        self.on_connect = on_connect
        self.grid_columnconfigure(0, weight=1)

        connection = ctk.CTkFrame(self, corner_radius=14, fg_color="#1b1c20")
        connection.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        connection.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(connection, text="TV connection", font=ctk.CTkFont(size=15, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(13, 0))
        self.status = ctk.CTkLabel(connection, text="●  No device connected", text_color="#f0bd72",
                                   anchor="e", font=ctk.CTkFont(size=12, weight="bold"))
        self.status.grid(row=0, column=1, sticky="e", padx=16, pady=(13, 0))
        fields = ctk.CTkFrame(connection, fg_color="transparent")
        fields.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(8, 13))
        self.host_entry = ctk.CTkEntry(fields, placeholder_text="TV IP address", width=210,
                                       height=40, border_color="#3a3c44")
        self.host_entry.insert(0, "192.168.0.103")
        self.host_entry.pack(side="left", padx=4)
        self.port_entry = ctk.CTkEntry(fields, placeholder_text="Port", width=88,
                                       height=40, border_color="#3a3c44")
        self.port_entry.insert(0, "5555")
        self.port_entry.pack(side="left", padx=4)
        self.connect_button = ctk.CTkButton(fields, text="Connect TV", width=132, height=40,
                                            font=ctk.CTkFont(size=13, weight="bold"),
                                            command=self.on_connect)
        self.connect_button.pack(side="left", padx=(7, 4))

        metrics = ctk.CTkFrame(self, fg_color="transparent")
        metrics.grid(row=1, column=0, sticky="ew", pady=(0, 16))
        self.values: dict[str, ctk.CTkLabel] = {}
        for column, (key, title) in enumerate((("identity", "DEVICE"), ("memory", "MEMORY"), ("storage", "STORAGE"))):
            card = ctk.CTkFrame(metrics, corner_radius=12, fg_color="#1b1c20")
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
            metrics.grid_columnconfigure(column, weight=1)
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=10, weight="bold"),
                         text_color="#8c8f98").pack(anchor="w", padx=14, pady=(13, 5))
            value = ctk.CTkLabel(card, text="—", font=ctk.CTkFont(size=14, weight="bold"),
                                 anchor="w", justify="left", wraplength=210, text_color="#e7e8eb")
            value.pack(fill="x", padx=14, pady=(0, 13))
            self.values[key] = value

        self.empty_state = ctk.CTkFrame(self, corner_radius=16, fg_color="#191a1f",
                                        border_width=1, border_color="#2b2d34")
        self.empty_state.grid(row=2, column=0, sticky="nsew")
        self.rowconfigure(2, weight=1)
        body = ctk.CTkFrame(self.empty_state, fg_color="transparent")
        body.place(relx=0.5, rely=0.49, anchor="center")
        ctk.CTkLabel(body, text="⌁", text_color="#7fa2ff",
                     font=ctk.CTkFont(size=38, weight="bold")).pack(pady=(0, 4))
        ctk.CTkLabel(body, text="No device connected", font=ctk.CTkFont(size=23, weight="bold")).pack()
        ctk.CTkLabel(body, text="Connect your Android TV to view its device information and applications.",
                     text_color="#a1a4ad", font=ctk.CTkFont(size=13), wraplength=510,
                     justify="center").pack(pady=(8, 16))
        steps = ctk.CTkFrame(body, fg_color="#202126", corner_radius=10)
        steps.pack(fill="x", pady=(0, 16))
        instructions = (
            "1  Connect this Mac and your TV to the same network.",
            "2  Enable Network / ADB debugging in the TV settings.",
            "3  Enter the TV IP and port above, then choose Connect TV.",
            "4  Approve the debugging prompt on the TV if it appears.",
        )
        ctk.CTkLabel(steps, text="\n".join(instructions), text_color="#c4c6ce",
                     font=ctk.CTkFont(size=12), justify="left", anchor="w").pack(
                         padx=18, pady=14, anchor="w")
        self.error_label = ctk.CTkLabel(body, text="", text_color="#ff8a8a",
                                        font=ctk.CTkFont(size=12), wraplength=500)
        self.error_label.pack(pady=(0, 10))
        ctk.CTkButton(body, text="Connect TV", width=180, height=42,
                      font=ctk.CTkFont(size=14, weight="bold"), command=self.on_connect).pack()

    def focus_connection(self):
        self.host_entry.focus_set()

    def set_connecting(self, connecting: bool):
        self.connect_button.configure(state="disabled" if connecting else "normal",
                                      text="Connecting…" if connecting else "Connect TV")
        self.error_label.configure(text="")

    def show_disconnected(self, error: str | None = None):
        self.status.configure(text="●  No device connected", text_color="#f0bd72")
        for label in self.values.values():
            label.configure(text="—")
        self.connect_button.configure(state="normal", text="Connect TV")
        self.error_label.configure(text=error or "")
        self.empty_state.grid()

    def show_connected(self, serial: str):
        self.status.configure(text=f"●  Connected · {serial}", text_color="#75c9a0")
        self.error_label.configure(text="")
        self.connect_button.configure(state="normal", text="Connect TV")
        self.empty_state.grid_remove()

    def update_device(self, device: dict):
        manufacturer = device.get("manufacturer") or "Unknown manufacturer"
        model = device.get("model") or "Unknown model"
        self.values["identity"].configure(text=f"{manufacturer} {model}\nAndroid {device.get('android_version') or '?'} · SDK {device.get('sdk') or '?'}")
        memory = device.get("memory", {})
        total, available = memory.get("total_kb"), memory.get("available_kb")
        if total and available is not None:
            self.values["memory"].configure(text=f"{(total-available)/1024:.0f} / {total/1024:.0f} MiB used")
        elif memory.get("error"):
            self.values["memory"].configure(text="Unavailable")
        storage = device.get("storage", {})
        if storage.get("size"):
            total_gb = storage["size"] / (1024 * 1024)
            used_gb = storage["used"] / (1024 * 1024)
            self.values["storage"].configure(text=f"{used_gb:.1f} / {total_gb:.1f} GiB used")
        elif storage.get("error"):
            self.values["storage"].configure(text="Unavailable")
        self.show_connected(device.get("serial", "ADB device"))
