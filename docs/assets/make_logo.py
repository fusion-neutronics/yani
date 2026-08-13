"""YANI logo: a sibling of the YAMC mark, with capture instead of a track.

YAMC shows a particle traversing the letters, which is what a transport code
does. yani transmutes, so the motif is a full reaction, drawn in a band above
the wordmark so the nuclides never sit on top of a letter: a neutron arrives
from the left and is absorbed into a large nuclide sitting above the seam
between "A" and "N", the colour boundary the wordmark already has. The
compound nuclide splits into an alpha particle, which drops away, and a
recoiling daughter, which is what emits the gamma. Bound nucleons are drawn
in their own physical colours, blue neutrons and red protons, rather than the
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
LETTERS_H = 225 * SS                     # the original wordmark-only canvas
BAND_H = 108 * SS                        # clear band above it, for the reaction
W, H = 627 * SS, LETTERS_H + BAND_H
im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
d = ImageDraw.Draw(im)

# Size the wordmark to fill the canvas width, the way YAMC's does, rather than
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
# Centred in the letters-only band, then dropped below the reaction band.
text_y = BAND_H + (LETTERS_H - (box[3] - box[1])) // 2 - box[1]
letters_top = BAND_H + box[1] + (LETTERS_H - (box[3] - box[1])) // 2

# --- letters: YA blue, NI orange, matching YAMC's split -----------------------
x = PAD
for chars, colour in (("YA", BLUE), ("NI", ORANGE)):
    d.text((x, text_y), chars, font=font, fill=colour)
    x += d.textlength(chars, font=font)
total_w = x - PAD
an_seam = PAD + d.textlength("YA", font=font)   # x where "A" ends and "N" begins


def disc(cx, cy, r, fill):
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)


def nucleon_cluster(cx, cy, positions, colours, nucleon_r):
    for (ox, oy), colour in zip(positions, colours):
        disc(cx + ox, cy + oy, nucleon_r, colour)


# --- the reaction lives entirely in the band above the wordmark, on the A/N
# seam, so no nuclide ever sits on a letter -----------------------------------
nx, ny = int(an_seam), int(BAND_H * 0.52)
start = (int(W * 0.03), int(LETTERS_H * 0.86) + BAND_H)

# incoming neutron, dashed, the one thing allowed to cross the letters: it is
# a line, not a filled disc, so it reads fine over either half
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
    big_positions.append((15 * SS * math.cos(a), 15 * SS * math.sin(a)))
for a in (i * math.pi / 4 + 0.4 for i in range(8)):
    big_positions.append((28 * SS * math.cos(a), 28 * SS * math.sin(a)))
big_colours = [BLUE if i % 2 == 0 else RED for i in range(len(big_positions))]
nucleon_cluster(nx, ny, big_positions, big_colours, nucleon_r=9 * SS)

# the alpha particle (2 protons, 2 neutrons), ejected sideways so its track
# stays inside the band instead of dropping into the letters
ax_, ay_ = nx - 78 * SS, ny + 6 * SS
d.line([nx - 24 * SS, ny + 2 * SS, ax_ + 20 * SS, ay_], fill=GREEN, width=6 * SS)
alpha_positions = [(-8 * SS, -8 * SS), (8 * SS, -8 * SS), (-8 * SS, 8 * SS), (8 * SS, 8 * SS)]
alpha_colours = [RED, RED, BLUE, BLUE]
nucleon_cluster(ax_, ay_, alpha_positions, alpha_colours, nucleon_r=9 * SS)

# --- outgoing gamma from the recoiling daughter, arcing right across the band
gx, gy = nx + 20 * SS, ny - 4 * SS
pts = []
for k in range(110):
    t = k / 109
    px = gx + t * (W * 0.32)
    py = gy - t * 12 * SS + math.sin(t * math.pi * 3.0) * 10 * SS
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

out_h = round(H / SS)
im = im.resize((627, out_h), Image.LANCZOS)
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
