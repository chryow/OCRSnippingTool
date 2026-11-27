"""Cross-platform multi-monitor screen capture with HiDPI-aware cropping."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image


@dataclass
class ScreenCapture:
    """Holds a full virtual-desktop screenshot and its coordinate metadata."""

    image: Image.Image
    left: int
    top: int
    width: int
    height: int

    def crop_from_overlay_rect(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        overlay_width: int,
        overlay_height: int,
    ) -> Image.Image:
        """Crop a region selected on the overlay widget, compensating for HiDPI scaling."""
        img_w, img_h = self.image.size
        scale_x = img_w / max(overlay_width, 1)
        scale_y = img_h / max(overlay_height, 1)

        px1 = max(0, min(img_w, int(round(x * scale_x))))
        py1 = max(0, min(img_h, int(round(y * scale_y))))
        px2 = max(px1 + 1, min(img_w, int(round((x + w) * scale_x))))
        py2 = max(py1 + 1, min(img_h, int(round((y + h) * scale_y))))
        return self.image.crop((px1, py1, px2, py2))


def capture_virtual_desktop() -> ScreenCapture:
    """Capture the entire virtual desktop across all monitors.

    Prefers `mss` for speed and multi-monitor reliability; falls back to
    `PIL.ImageGrab` if needed.
    """
    try:
        import mss

        with mss.mss() as sct:
            # monitors[0] is the bounding box of all connected monitors combined
            monitor = sct.monitors[0]
            raw = sct.grab(monitor)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            return ScreenCapture(
                image=img,
                left=int(monitor["left"]),
                top=int(monitor["top"]),
                width=int(monitor["width"]),
                height=int(monitor["height"]),
            )
    except Exception:
        from PIL import ImageGrab

        img = ImageGrab.grab(all_screens=True).convert("RGB")
        w, h = img.size
        return ScreenCapture(image=img, left=0, top=0, width=w, height=h)
