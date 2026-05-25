"""Central CustomTkinter appearance settings."""
from __future__ import annotations

import customtkinter as ctk


def apply_theme() -> None:
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
