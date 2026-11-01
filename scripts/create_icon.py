"""Regenerate the original launcher artwork. Requires Pillow, not needed to build/run."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "unity_webgl_launcher" / "assets"
SIZE = 1024


def gradient(top, bottom):
    image = Image.new("RGBA", (SIZE, SIZE))
    draw = ImageDraw.Draw(image)
    for y in range(SIZE):
        t = y / (SIZE - 1)
        color = tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)) + (255,)
        draw.line((0, y, SIZE, y), fill=color)
    return image


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    canvas = Image.new("RGBA", (SIZE, SIZE))
    mask = Image.new("L", canvas.size)
    ImageDraw.Draw(mask).rounded_rectangle((48, 48, 976, 976), radius=216, fill=255)
    canvas.paste(gradient((29, 42, 80), (10, 16, 34)), (0, 0), mask)
    glow = Image.new("RGBA", canvas.size)
    ImageDraw.Draw(glow).ellipse((50, 80, 870, 740), fill=(39, 123, 220, 72))
    glow = glow.filter(ImageFilter.GaussianBlur(100))
    glow.putalpha(Image.composite(glow.getchannel("A"), Image.new("L", canvas.size), mask))
    canvas = Image.alpha_composite(canvas, glow)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((50, 50, 974, 974), radius=215, outline=(101, 144, 205, 85), width=4)

    top = [(512, 200), (786, 351), (512, 508), (238, 351)]
    left = [(238, 369), (503, 521), (503, 823), (238, 670)]
    right = [(521, 521), (786, 369), (786, 670), (521, 823)]
    for points, colors in [(top, ((118, 240, 255), (45, 173, 232))), (left, ((65, 147, 244), (66, 71, 196))), (right, ((99, 132, 250), (105, 56, 197)))]:
        face_mask = Image.new("L", canvas.size)
        ImageDraw.Draw(face_mask).polygon(points, fill=255)
        canvas.paste(gradient(*colors), (0, 0), face_mask)
    draw = ImageDraw.Draw(canvas)
    draw.line([(255, 350), (512, 214), (769, 350)], fill=(176, 250, 255), width=5, joint="curve")
    # A play cutout on the front-right face, with a discreet raised edge.
    play = [(576, 529), (576, 683), (705, 532)]
    shadow = Image.new("RGBA", canvas.size)
    ImageDraw.Draw(shadow).polygon([(x + 4, y + 10) for x, y in play], fill=(13, 28, 78, 120))
    canvas = Image.alpha_composite(canvas, shadow.filter(ImageFilter.GaussianBlur(8)))
    ImageDraw.Draw(canvas).polygon(play, fill=(246, 253, 255))

    icon = canvas.resize((256, 256), Image.Resampling.LANCZOS)
    icon.save(OUTPUT / "launcher.png")
    icon.save(OUTPUT / "launcher.ico", sizes=[(s, s) for s in (16, 20, 24, 32, 40, 48, 64, 128, 256)])
    canvas.resize((512, 512), Image.Resampling.LANCZOS).save(OUTPUT / "launcher-preview.png")

    # Editable vector master of the same design.
    (OUTPUT / "launcher.svg").write_text('''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">
  <defs>
    <linearGradient id="bg" x2="0" y2="1"><stop stop-color="#1d2a50"/><stop offset="1" stop-color="#0a1022"/></linearGradient>
    <linearGradient id="top" x2="0" y2="1"><stop stop-color="#76f0ff"/><stop offset="1" stop-color="#2dade8"/></linearGradient>
    <linearGradient id="left" x2="0" y2="1"><stop stop-color="#4193f4"/><stop offset="1" stop-color="#4247c4"/></linearGradient>
    <linearGradient id="right" x2="0" y2="1"><stop stop-color="#6384fa"/><stop offset="1" stop-color="#6938c5"/></linearGradient>
  </defs>
  <rect x="48" y="48" width="928" height="928" rx="216" fill="url(#bg)" stroke="#658fcd" stroke-opacity=".35" stroke-width="4"/>
  <path d="M512 200 786 351 512 508 238 351Z" fill="url(#top)"/>
  <path d="M238 369 503 521 503 823 238 670Z" fill="url(#left)"/>
  <path d="M521 521 786 369 786 670 521 823Z" fill="url(#right)"/>
  <path d="M255 350 512 214 769 350" fill="none" stroke="#b0faff" stroke-width="5"/>
  <path d="M576 529 576 683 705 532Z" fill="#f6fdff"/>
</svg>
''', encoding="utf-8")


if __name__ == "__main__":
    main()
