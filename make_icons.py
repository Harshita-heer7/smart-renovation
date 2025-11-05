from PIL import Image, ImageDraw, ImageFont
import os

# Make sure the assets folder exists
os.makedirs('assets', exist_ok=True)

# ---------- LOGO 128x128 ----------
img = Image.new('RGBA', (128, 128), (37, 99, 235, 255))  # blue background
draw = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype("arial.ttf", 56)
except:
    font = ImageFont.load_default()

# Get text width and height (works with all Pillow versions)
try:
    bbox = draw.textbbox((0, 0), "SR", font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
except AttributeError:
    w, h = draw.textsize("SR", font=font)

# Center and draw text
draw.text(((128 - w) / 2, (128 - h) / 2), "SR", font=font, fill=(255, 255, 255, 255))
img.save('assets/logo.png')

# ---------- PROVIDER ICON 64x64 ----------
img2 = Image.new('RGBA', (64, 64), (255, 255, 255, 0))  # transparent background
draw2 = ImageDraw.Draw(img2)
draw2.ellipse((4, 4, 60, 60), fill=(255, 153, 51, 255))  # orange circle

try:
    font2 = ImageFont.truetype("arial.ttf", 20)
except:
    font2 = ImageFont.load_default()

# Get text size (works in all Pillow versions)
try:
    bbox2 = draw2.textbbox((0, 0), "P", font=font2)
    w2, h2 = bbox2[2] - bbox2[0], bbox2[3] - bbox2[1]
except AttributeError:
    w2, h2 = draw2.textsize("P", font=font2)

# Draw "P" centered
draw2.text(((64 - w2) / 2, (64 - h2) / 2), "P", font=font2, fill=(255, 255, 255, 255))
img2.save('assets/provider_icon.png')

print("✅ Created assets/logo.png and assets/provider_icon.png successfully!")
