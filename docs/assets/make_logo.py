"""YANI logo: a sibling of the YAMC mark, with capture instead of a track.

YAMC shows a particle traversing the letters, which is what a transport code
does. yani transmutes, so the motif is an (n,gamma) capture: a neutron arrives
from the left, is absorbed by a nucleus sitting in the letterforms, and a gamma
leaves it. Same typeface weight, same three colours, sampled from the YAMC png.
"""
import math
from PIL import Image, ImageDraw, ImageFont

BLUE = (22, 84, 127, 255)
ORANGE = (238, 118, 27, 255)
GREEN = (73, 150, 89, 255)
WHITE = (255, 255, 255, 255)

SS = 4                                  # supersample, then downsample to smooth
W, H = 627 * SS, 225 * SS
im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(im)

# Size the wordmark to fill the canvas, the way YAMC's does, rather than
# leaving a third of it empty.
PAD = 16 * SS
size = 150 * SS
while True:
    f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    if d.textlength("YANI", font=f) >= W - 2 * PAD or size > 400 * SS:
        break
    size += 4 * SS
font = f
box = d.textbbox((0, 0), "YANI", font=font)
text_y = (H - (box[3] - box[1])) // 2 - box[1]

# --- letters: YA blue, NI orange, matching YAMC's split -----------------------
x = PAD
for chars, colour in (("YA", BLUE), ("NI", ORANGE)):
    d.text((x, text_y), chars, font=font, fill=colour)
    x += d.textlength(chars, font=font)
total_w = x - PAD


def disc(cx, cy, r, fill, ring=WHITE, ring_w=5):
    if ring_w:
        d.ellipse([cx - r - ring_w, cy - r - ring_w, cx + r + ring_w, cy + r + ring_w],
                  fill=ring)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)


# --- capture, crossing the letters like YAMC's track ------------------------
# Everything here is deliberately small: the wordmark has to stay readable, so
# the motif rides over the letters the way YAMC's dots do rather than covering
# one. The nucleus sits high, clear of the letter bowls.
nx, ny = int(W * 0.60), int(H * 0.37)
start = (int(W * 0.05), int(H * 0.80))

dx, dy = nx - start[0], ny - start[1]
length = math.hypot(dx, dy)
ux, uy = dx / length, dy / length
travel = length - 46 * SS
seg, gap, pos = 26 * SS, 18 * SS, 0
while pos < travel:
    e = min(pos + seg, travel)
    seg_pts = [start[0] + ux * pos, start[1] + uy * pos,
               start[0] + ux * e, start[1] + uy * e]
    d.line(seg_pts, fill=WHITE, width=17 * SS)
    d.line(seg_pts, fill=GREEN, width=8 * SS)
    pos += seg + gap
disc(start[0] + ux * (travel + 14 * SS), start[1] + uy * (travel + 14 * SS),
     11 * SS, GREEN, ring_w=5 * SS)

# a compact nucleus: four nucleons, white-ringed so it reads over a letter
d.ellipse([nx - 30 * SS, ny - 30 * SS, nx + 30 * SS, ny + 30 * SS], fill=WHITE)
for a in (0.8, 2.4, 3.9, 5.5):
    disc(nx + 12 * SS * math.cos(a), ny + 12 * SS * math.sin(a),
         11 * SS, BLUE if a < 3 else GREEN, ring_w=0)

# --- outgoing gamma: continues up and right, stopping short of the edge ------
pts = []
for k in range(110):
    t = k / 109
    px = nx + 30 * SS + t * (W * 0.315)
    py = ny - 12 * SS - t * 34 * SS + math.sin(t * math.pi * 3.0) * 11 * SS
    pts.append((px, py))
# White halo first: the gamma crosses the orange letters, so orange-on-orange
# would disappear. Drawn in blue over the halo, the way YAMC's track reads
# against its orange half.
d.line(pts, fill=WHITE, width=17 * SS, joint="curve")
d.line(pts, fill=BLUE, width=8 * SS, joint="curve")
(ax, ay), (bx, by) = pts[-10], pts[-1]
ang = math.atan2(by - ay, bx - ax)
head = [
    (bx + 24 * SS * math.cos(ang), by + 24 * SS * math.sin(ang)),
    (bx + 11 * SS * math.cos(ang + 2.5), by + 11 * SS * math.sin(ang + 2.5)),
    (bx + 11 * SS * math.cos(ang - 2.5), by + 11 * SS * math.sin(ang - 2.5)),
]
d.polygon([(x + 4 * SS * math.cos(ang), y + 4 * SS * math.sin(ang)) for x, y in head],
          fill=WHITE, outline=WHITE, width=6 * SS)
d.polygon(head, fill=BLUE)

im = im.resize((627, 225), Image.LANCZOS)
im.save("logo.png")
print("wrote logo.png", im.size, "letters width", total_w // SS)

# A square favicon crop: the nucleus alone, which is the distinctive part.
fav = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
fd = ImageDraw.Draw(fav)
cx = cy = 256
for k in range(6):
    a = math.pi / 3 * k + 0.4
    r = 108
    fd.ellipse([cx + r * math.cos(a) - 74, cy + r * math.sin(a) - 74,
                cx + r * math.cos(a) + 74, cy + r * math.sin(a) + 74], fill=GREEN)
fd.ellipse([cx - 80, cy - 80, cx + 80, cy + 80], fill=BLUE)
fav.save("favicon.png")
print("wrote favicon.png")
