"""Generate OG image and favicons from existing logos."""

import os

from PIL import Image, ImageDraw, ImageFont

base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "img")

# --- Favicons from the shield logo ---
escudo = Image.open(os.path.join(base, "ligademaestros_escudo.png"))

sizes = {
    "favicon-16.png": 16,
    "favicon-32.png": 32,
    "apple-touch-icon.png": 180,
    "android-chrome-192.png": 192,
    "android-chrome-512.png": 512,
}

for name, size in sizes.items():
    resized = escudo.copy()
    resized.thumbnail((size, size), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    offset = ((size - resized.width) // 2, (size - resized.height) // 2)
    canvas.paste(resized, offset, resized)
    canvas.save(os.path.join(base, name))
    print(f"Created {name} ({size}x{size})")

# --- OG Image 1200x630 ---
og_w, og_h = 1200, 630
og = Image.new("RGBA", (og_w, og_h), (6, 9, 15, 255))

draw = ImageDraw.Draw(og)
# Subtle dark gradient
for y in range(og_h):
    r = int(6 + (y / og_h) * 7)
    g = int(9 + (y / og_h) * 11)
    b = int(15 + (y / og_h) * 20)
    draw.line([(0, y), (og_w, y)], fill=(r, g, b, 255))

# Place the wide logo centered
logo = Image.open(os.path.join(base, "ligademaestroslogo.png"))
logo_w = 700
logo_h = int(logo.height * (logo_w / logo.width))
logo_resized = logo.resize((logo_w, logo_h), Image.LANCZOS)
logo_x = (og_w - logo_w) // 2
logo_y = (og_h - logo_h) // 2 - 60
og.paste(logo_resized, (logo_x, logo_y), logo_resized)

# Add tagline text below
try:
    font = ImageFont.truetype("arial.ttf", 32)
    font_sm = ImageFont.truetype("arial.ttf", 22)
except Exception:
    font = ImageFont.load_default()
    font_sm = font

tagline = "Humanos vs IAs  \u00b7  Jornada a Jornada"
bbox = draw.textbbox((0, 0), tagline, font=font)
tw = bbox[2] - bbox[0]
draw.text(((og_w - tw) // 2, logo_y + logo_h + 30), tagline, fill=(240, 244, 248, 255), font=font)

sub = "Quiniela competitiva con predicciones, rankings y juegos"
bbox2 = draw.textbbox((0, 0), sub, font=font_sm)
tw2 = bbox2[2] - bbox2[0]
draw.text(((og_w - tw2) // 2, logo_y + logo_h + 75), sub, fill=(139, 157, 195, 255), font=font_sm)

# Save as PNG
og_path = os.path.join(base, "og-image.png")
og.convert("RGB").save(og_path, quality=95)
print("Created og-image.png (1200x630)")

# Also create favicon.ico (multi-size 16+32)
ico_sizes = [16, 32]
ico_images = []
for s in ico_sizes:
    resized = escudo.copy()
    resized.thumbnail((s, s), Image.LANCZOS)
    canvas = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    offset = ((s - resized.width) // 2, (s - resized.height) // 2)
    canvas.paste(resized, offset, resized)
    ico_images.append(canvas.convert("RGB"))

ico_path = os.path.join(base, "favicon.ico")
ico_images[0].save(ico_path, format="ICO", sizes=[(s, s) for s in ico_sizes], append_images=ico_images[1:])
print("Created favicon.ico (16+32)")

print("\nDone!")
