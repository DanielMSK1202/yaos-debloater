"""Review one package at a time before any device state change."""
from __future__ import annotations

import customtkinter as ctk

from core.safe_debloater import eligibility
from core.user_preferences import load_preferences
from gui.application_manager import NECESSITY_LABELS, RISK_LABELS


class SafeDebloaterView(ctk.CTkFrame):
    def __init__(self, master, *, on_dry_run, on_backup, on_disable, on_restore):
        super().__init__(master, fg_color="transparent")
        self.packages = []
        self.selected = None
        self.verified_plan = None
        self.backup_path = None
        self.on_dry_run, self.on_backup = on_dry_run, on_backup
        self.on_disable, self.on_restore = on_disable, on_restore

        ctk.CTkLabel(self, text="Safe Debloater", font=ctk.CTkFont(size=21, weight="bold")).pack(anchor="w", pady=(4, 6))
        ctk.CTkLabel(self, text="One app at a time. Backups preserve package state only, not application data.",
                     text_color="#aeb0b8", anchor="w").pack(fill="x", pady=(0, 12))
        self.summary = ctk.CTkLabel(self, text="Connect your TV and run a scan.", anchor="w")
        self.summary.pack(fill="x", pady=(0, 8))
        self.search = ctk.CTkEntry(self, placeholder_text="Search by app name or package ID")
        self.search.pack(fill="x", pady=(0, 8))
        self.search.bind("<KeyRelease>", lambda _e: self._refresh_list())
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True)
        self.list_frame = ctk.CTkScrollableFrame(content, width=330)
        self.list_frame.pack(side="left", fill="both", expand=False, padx=(0, 12))
        detail = ctk.CTkScrollableFrame(content)
        detail.pack(side="left", fill="both", expand=True)
        self.title_label = ctk.CTkLabel(detail, text="Select an application", font=ctk.CTkFont(size=18, weight="bold"), anchor="w")
        self.title_label.pack(fill="x", padx=14, pady=(14, 8))
        self.details = ctk.CTkLabel(detail, text="Select an application to review the assessment and potential consequences.",
                                    justify="left", anchor="nw", wraplength=520)
        self.details.pack(fill="x", padx=14, pady=8)
        self.result = ctk.CTkLabel(detail, text="", justify="left", anchor="w", wraplength=520,
                                   text_color="#e1bd75")
        self.result.pack(fill="x", padx=14, pady=8)
        actions = ctk.CTkFrame(detail, fg_color="transparent")
        actions.pack(fill="x", padx=14, pady=12)
        self.review_button = ctk.CTkButton(actions, text="Review Details", width=100, command=self._review)
        self.review_button.pack(side="left", padx=(0, 5))
        self.dry_button = ctk.CTkButton(actions, text="Dry Run", width=90, command=on_dry_run)
        self.dry_button.pack(side="left", padx=5)
        self.backup_button = ctk.CTkButton(actions, text="Backup", width=70, command=on_backup)
        self.backup_button.pack(side="left", padx=5)
        self.disable_button = ctk.CTkButton(actions, text="Disable", width=100, command=on_disable,
                                            fg_color="#ad6033", state="disabled")
        self.disable_button.pack(side="left", padx=5)
        self.restore_button = ctk.CTkButton(detail, text="Restore from Backup", command=on_restore,
                                            state="disabled")
        self.restore_button.pack(anchor="w", padx=14, pady=(0, 14))
        self._set_actions()

    def set_packages(self, packages: list[dict]):
        self.packages = packages
        self.selected = None
        self.verified_plan = None
        self.backup_path = None
        prefs = load_preferences()
        candidates = sum(not eligibility(row, prefs.get(row.get("package"))) for row in packages)
        self.summary.configure(text=f"{len(packages)} applications · Preliminary candidates: {candidates}. "
                                    "Every operation requires live TV verification." if packages else
                                    "Connect your TV and run a scan.")
        self.title_label.configure(text="Select an application")
        self.details.configure(text="Select and verify an application before changing its state.")
        self.result.configure(text="")
        self._refresh_list()
        self._set_actions()

    def _refresh_list(self):
        for widget in self.list_frame.winfo_children(): widget.destroy()
        query = self.search.get().casefold()
        prefs = load_preferences()
        for row in self.packages:
            package = str(row.get("package", ""))
            name = str(row.get("application") or package)
            if query not in package.casefold() and query not in name.casefold(): continue
            heading = name if name == package else f"{name}\n{package}"
            risk = RISK_LABELS.get(row.get("risk"), "Not evaluated")
            state = "Disabled" if row.get("disabled") else "Enabled"
            allowed = not eligibility(row, prefs.get(package))
            category = NECESSITY_LABELS.get(row.get("necessity"), "UNKNOWN")
            subtitle = f"{category} · risk: {risk} · {state} · {'Dry Run' if allowed else 'Blocked'}"
            card = ctk.CTkFrame(self.list_frame, fg_color="#272930")
            card.pack(fill="x", pady=3)
            ctk.CTkButton(card, text=heading, anchor="w", height=36, fg_color="transparent",
                          command=lambda item=row: self.select(item)).pack(fill="x", padx=4, pady=(2, 0))
            ctk.CTkLabel(card, text=subtitle, text_color="#aeb0b8", wraplength=295,
                         justify="left", anchor="w").pack(fill="x", padx=10, pady=(0, 4))

    def select(self, row: dict):
        self.selected = row
        self.verified_plan = None
        self.backup_path = None
        self.result.configure(text="")
        self._review()
        self._set_actions()

    def _review(self):
        row = self.selected
        if not row: return
        preference = load_preferences().get(row["package"])
        reasons = eligibility(row, preference)
        self.title_label.configure(text=str(row.get("application") or row["package"]))
        self.details.configure(text="\n\n".join((
            f"Package: {row['package']}",
            f"Necessity: {NECESSITY_LABELS.get(row.get('necessity'), 'UNKNOWN')}",
            f"Disable risk: {RISK_LABELS.get(row.get('risk'), 'Not evaluated')}",
            f"State: {'Disabled' if row.get('disabled') else 'Enabled'}",
            f"Evidence: {row.get('necessity_reason') or row.get('risk_reason') or 'Insufficient evidence.'}",
            f"Potential consequences: {row.get('potential_consequences') or 'Unknown.'}",
            "Eligibility: " + ("Live TV verification required." if not reasons else "BLOCKED — " + "; ".join(reasons)),
        )))

    def show_plan(self, plan: dict):
        if not self.selected or plan.get("package") != self.selected.get("package"):
            return
        self.verified_plan = plan if plan.get("eligible") else None
        self.result.configure(text=("Verification passed. A state backup and explicit single-package confirmation are required." if plan.get("eligible")
                                    else "Operation blocked: " + "; ".join(plan.get("reasons", []))))
        self._set_actions()

    def _set_actions(self):
        selected = self.selected is not None
        self.review_button.configure(state="normal" if selected else "disabled")
        self.dry_button.configure(state="normal" if selected else "disabled")
        self.backup_button.configure(state="normal" if selected else "disabled")
        self.disable_button.configure(state="normal" if self.verified_plan and self.verified_plan.get("eligible") else "disabled")
        self.restore_button.configure(state="normal" if self.packages else "disabled")
