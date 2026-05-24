"""SonicForge Design System
Shared colours, gradients, shadows, and component helpers.
Import this module in all UI files so every component stays visually consistent.
"""

import flet as ft

# ── Colour Palette ─────────────────────────────────────────────────────────────
BG        = "#0d1117"   # page background
SURFACE   = "#161b22"   # card / panel background
BORDER    = "#30363d"   # 1-px card border
PRIMARY   = "#58a6ff"   # primary accent
SECONDARY = "#1f6feb"   # secondary accent
TEXT      = "#c9d1d9"   # primary text 
MUTED     = "#8b949e"   # secondary / label text 
SUCCESS   = "#2ea44f"   # success green (
INPUT_BG  = "#0d1117"   # text-field background
ROW_SEL   = "#152238"   # selected table-row tint 
ROW_HOV   = "#21262d"   # hovered table-row tint 

# ── Shadows ────────────────────────────────────────────────────────────────────
CARD_SHADOW = ft.BoxShadow(
    spread_radius=0,
    blur_radius=28,
    color="#11000000",   # extremely subtle shadow for a flatter
        offset=ft.Offset(0, 6),
)

# ── Gradients ──────────────────────────────────────────────────────────────────
GRADIENT_PRIMARY = ft.LinearGradient(
    begin=ft.Alignment(-1, 0),   # center-left
    end=ft.Alignment(1, 0),     # center-right
    colors=[PRIMARY, SECONDARY],
)

GRADIENT_ARTWORK = ft.LinearGradient(
    begin=ft.Alignment(-1, -1),  # top-left
    end=ft.Alignment(1, 1),     # bottom-right
    colors=[SECONDARY, PRIMARY],   # gorgeous GitHub dark blue → vibrant blue gradient
)


# ── Component helpers ──────────────────────────────────────────────────────────

def card(content: ft.Control, padding: int = 16, **kwargs) -> ft.Container:
    """Wraps *content* in a frosted-glass surface card."""
    return ft.Container(
        content=content,
        bgcolor=SURFACE,
        border_radius=16,
        border=ft.Border.all(1, BORDER),
        shadow=CARD_SHADOW,
        padding=padding,
        **kwargs,
    )


def styled_field(label: str, **kwargs) -> ft.TextField:
    """Returns a consistently-styled TextField matching the design system."""
    return ft.TextField(
        label=label,
        label_style=ft.TextStyle(color=MUTED, size=12),
        color=TEXT,
        bgcolor=INPUT_BG,
        border_color=BORDER,
        focused_border_color=SECONDARY,
        cursor_color=SECONDARY,
        border_radius=8,
        content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        **kwargs,
    )


def gradient_button(text: str, icon: str, on_click, **kwargs) -> ft.Container:
    """A full-width gradient CTA button."""
    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(icon, color=ft.Colors.WHITE, size=18),
                ft.Text(text, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, size=15),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=10,
        ),
        gradient=GRADIENT_PRIMARY,
        border_radius=10,
        on_click=on_click,
        ink=True,
        padding=ft.Padding.symmetric(vertical=14),
        height=52,
        **kwargs,
    )
