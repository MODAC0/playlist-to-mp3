#!/usr/bin/env python3
"""앱 아이콘 1024x1024 PNG 생성 (Pillow)."""
import math
from PIL import Image, ImageDraw, ImageFont

S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# --- 라운드 사각형(squircle 느낌) 배경 + 세로 그라데이션 ---
margin = 96
radius = 230
top = (124, 58, 237)     # 보라
bot = (37, 99, 235)      # 파랑
grad = Image.new("RGBA", (S, S), (0, 0, 0, 0))
gd = ImageDraw.Draw(grad)
for y in range(S):
    t = y / (S - 1)
    r = int(top[0] + (bot[0] - top[0]) * t)
    g = int(top[1] + (bot[1] - top[1]) * t)
    b = int(top[2] + (bot[2] - top[2]) * t)
    gd.line([(0, y), (S, y)], fill=(r, g, b, 255))

mask = Image.new("L", (S, S), 0)
md = ImageDraw.Draw(mask)
md.rounded_rectangle([margin, margin, S - margin, S - margin],
                     radius=radius, fill=255)
img.paste(grad, (0, 0), mask)

# --- 상단 광택(부드러운 하이라이트) ---
gloss = Image.new("RGBA", (S, S), (0, 0, 0, 0))
gl = ImageDraw.Draw(gloss)
gl.rounded_rectangle([margin, margin, S - margin, margin + 340],
                     radius=radius, fill=(255, 255, 255, 40))
img = Image.alpha_composite(img, Image.composite(
    gloss, Image.new("RGBA", (S, S), (0, 0, 0, 0)), mask))
d = ImageDraw.Draw(img)

# --- 음표(8분음표) ---
white = (255, 255, 255, 255)
# 머리
head_cx, head_cy, hr = 400, 660, 78
d.ellipse([head_cx - hr, head_cy - hr * 0.78,
           head_cx + hr, head_cy + hr * 0.78], fill=white)
# 기둥
stem_x = head_cx + hr - 14
d.rectangle([stem_x, 360, stem_x + 34, head_cy], fill=white)
# 깃발
d.polygon([(stem_x + 34, 360), (stem_x + 34, 470),
           (stem_x + 150, 540), (stem_x + 150, 430)], fill=white)

# --- 재생 삼각형(작은 배지) ---
tri_cx, tri_cy, tr = 660, 600, 92
d.ellipse([tri_cx - tr, tri_cy - tr, tri_cx + tr, tri_cy + tr],
          fill=(255, 255, 255, 235))
d.polygon([(tri_cx - 30, tri_cy - 46), (tri_cx - 30, tri_cy + 46),
           (tri_cx + 48, tri_cy)], fill=(124, 58, 237, 255))

# --- "MP3" 라벨 ---
def load_font(size):
    for p in ["/System/Library/Fonts/SFNS.ttf",
              "/System/Library/Fonts/Helvetica.ttc",
              "/Library/Fonts/Arial Bold.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()

font = load_font(180)
text = "MP3"
bbox = d.textbbox((0, 0), text, font=font)
tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
d.text(((S - tw) / 2 - bbox[0], 770 - bbox[1]), text, font=font, fill=white)

img.save("/Users/admin/Downloads/PlaylistToMP3/icon_1024.png")
print("saved icon_1024.png")
