"""YANI logo: a sibling of the YAMC mark, with capture instead of a track.

YAMC shows a particle traversing the letters, which is what a transport code
does. yani transmutes, so the motif is a full reaction, sitting at letter
height in a deliberate gap opened up between "A" and "N", the colour boundary
the wordmark already has, rather than on top of either letter: a neutron
arrives from the left and is absorbed into a large nuclide there. The
compound nuclide splits into an alpha particle, which drops away, and a
recoiling daughter, which is what emits the gamma continuing on through "N"
and "I" (a line reads fine crossing a letter; a filled nuclide does not, which
is why only the nuclides get the reserved gap). Bound nucleons are drawn in
their own physical colours, blue neutrons and red protons, rather than the
green used for a neutron in flight; that green, and the letters' blue and
orange, are sampled from the YAMC png.
"""
import math
from PIL import Image, ImageDraw, ImageFont

BLUE = (22, 84, 127, 255)
ORANGE = (238, 118, 27, 255)
GREEN = (73, 150, 89, 255)
RED = (196, 58, 51, 255)
WHITE = (255, 255, 255, 255)

SS = 4                                   # supersample, then downsample to smooth
H = 225 * SS
PAD = 16 * SS
GAP_W = 132 * SS                         # reserved, nuclide-free, between "A" and "N"

im_probe = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
dp = ImageDraw.Draw(im_probe)

# Size the letters against the same target width every earlier version used,
# so opening the gap doesn't shrink the wordmark: the canvas grows by GAP_W
# instead.
TARGET_W = 627 * SS
size = 150 * SS
while True:
    f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    if dp.textlength("YANI", font=f) >= TARGET_W - 2 * PAD or size > 400 * SS:
        break
    size += 4 * SS
font = f
ya_w = dp.textlength("YA", font=font)
ni_w = dp.textlength("NI", font=font)
W = PAD + int(ya_w) + GAP_W + int(ni_w) + PAD

im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
box = d.textbbox((0, 0), "YANI", font=font)
text_y = (H - (box[3] - box[1])) // 2 - box[1]

# --- letters: YA blue, NI orange, matching YAMC's split, with the reaction's
# gap opened up between them --------------------------------------------------
x = PAD
d.text((x, text_y), "YA", font=font, fill=BLUE)
x += ya_w
gap_left = x
x += GAP_W
gap_right = x
d.text((x, text_y), "NI", font=font, fill=ORANGE)
x += ni_w
total_w = x - PAD


def disc(cx, cy, r, fill):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)


def nucleon_cluster(cx, cy, positions, colours, nucleon_r):
    for (ox, oy), colour in zip(positions, colours):
        disc(cx + ox, cy + oy, nucleon_r, colour)


# --- the reaction sits in the gap, at letter height, so no nuclide ever lands
# on a letter; only lines are allowed to cross into the letters themselves ---
nx, ny = int((gap_left + gap_right) / 2) + 8 * SS, int(H * 0.5)
start = (int(W * 0.02), int(H * 0.86))

# incoming neutron, dashed
dx, dy = nx - start[0], ny - start[1]
length = math.hypot(dx, dy)
ux, uy = dx / length, dy / length
travel = length - 56 * SS
seg, gap, pos = 26 * SS, 18 * SS, 0
while pos < travel:
    e = min(pos + seg, travel)
    seg_pts = [start[0] + ux * pos, start[1] + uy * pos,
               start[0] + ux * e, start[1] + uy * e]
    d.line(seg_pts, fill=GREEN, width=8 * SS)
    pos += seg + gap
disc(start[0] + ux * (travel + 14 * SS), start[1] + uy * (travel + 14 * SS),
     11 * SS, GREEN)

# the large nuclide the neutron is absorbed into: enough nucleons, in two
# rings around a centre one, to read as "large" next to the four-nucleon
# alpha beside it. Physical colours: blue neutrons, red protons.
big_positions = [(0, 0)]
for a in (i * math.pi / 3 for i in range(6)):
    big_positions.append((14 * SS * math.cos(a), 14 * SS * math.sin(a)))
for a in (i * math.pi / 4 + 0.4 for i in range(8)):
    big_positions.append((26 * SS * math.cos(a), 26 * SS * math.sin(a)))
big_colours = [BLUE if i % 2 == 0 else RED for i in range(len(big_positions))]
nucleon_cluster(nx, ny, big_positions, big_colours, nucleon_r=8 * SS)

# the alpha particle (2 protons, 2 neutrons), dropped below the nuclide but
# still inside the gap
ax_, ay_ = nx - 40 * SS, ny + 30 * SS
d.line([nx - 18 * SS, ny + 16 * SS, ax_ + 12 * SS, ay_ - 10 * SS], fill=GREEN, width=6 * SS)
alpha_positions = [(-7 * SS, -7 * SS), (7 * SS, -7 * SS), (-7 * SS, 7 * SS), (7 * SS, 7 * SS)]
alpha_colours = [RED, RED, BLUE, BLUE]
nucleon_cluster(ax_, ay_, alpha_positions, alpha_colours, nucleon_r=8 * SS)

# --- outgoing gamma from the recoiling daughter, continuing on through N and I
gx, gy = nx + 16 * SS, ny - 10 * SS
pts = []
for k in range(110):
    t = k / 109
    px = gx + t * (W * 0.30)
    py = gy - t * 30 * SS + math.sin(t * math.pi * 3.0) * 10 * SS
    pts.append((px, py))
d.line(pts, fill=BLUE, width=8 * SS, joint="curve")
(px0, py0), (px1, py1) = pts[-10], pts[-1]
ang = math.atan2(py1 - py0, px1 - px0)
head = [
    (px1 + 24 * SS * math.cos(ang), py1 + 24 * SS * math.sin(ang)),
    (px1 + 11 * SS * math.cos(ang + 2.5), py1 + 11 * SS * math.sin(ang + 2.5)),
    (px1 + 11 * SS * math.cos(ang - 2.5), py1 + 11 * SS * math.sin(ang - 2.5)),
]
d.polygon(head, fill=BLUE)

out_w, out_h = round(W / SS), round(H / SS)
im = im.resize((out_w, out_h), Image.LANCZOS)
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
                cx + r * math.cos(a) + 74, cy + r * math.sin(a) + 74],
               fill=BLUE if k % 2 == 0 else RED)
fd.ellipse([cx - 80, cy - 80, cx + 80, cy + 80], fill=BLUE)
fav.save("favicon.png")
print("wrote favicon.png")
