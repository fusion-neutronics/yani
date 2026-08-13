"""YANI logo: a sibling of the YAMC mark, with capture instead of a track.

YAMC shows a particle traversing the letters, which is what a transport code
does. yani transmutes, so the motif is a full reaction: a neutron arrives from
the left and is absorbed into a large nuclide sitting on the seam between "A"
and "N", the colour boundary the wordmark already has. The compound nuclide
splits into an alpha particle, which drops away, and a recoiling daughter,
which is what emits the gamma continuing on through the letters. Same
typeface weight, same three colours, sampled from the YAMC png.
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
an_seam = PAD + d.textlength("YA", font=font)   # x where "A" ends and "N" begins


def disc(cx, cy, r, fill, ring=WHITE, ring_w=5):
    if ring_w:
        d.ellipse([cx - r - ring_w, cy - r - ring_w, cx + r + ring_w, cy + r + ring_w],
                  fill=ring)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)


def nucleon_cluster(cx, cy, positions, colours, nucleon_r, halo_r):
    """A ring-fenced blob of nucleon discs, white-haloed so it reads over a letter."""
    d.ellipse([cx - halo_r, cy - halo_r, cx + halo_r, cy + halo_r], fill=WHITE)
    for (ox, oy), colour in zip(positions, colours):
        disc(cx + ox, cy + oy, nucleon_r, colour, ring_w=0)


# --- the reaction sits on the A/N seam ---------------------------------------
# Everything here is deliberately compact: the wordmark has to stay readable,
# so the motif rides over the letters rather than covering one. The nuclide
# sits high, clear of the letter bowls.
nx, ny = int(an_seam), int(H * 0.35)
start = (int(W * 0.04), int(H * 0.84))

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
    d.line(seg_pts, fill=WHITE, width=17 * SS)
    d.line(seg_pts, fill=GREEN, width=8 * SS)
    pos += seg + gap
disc(start[0] + ux * (travel + 14 * SS), start[1] + uy * (travel + 14 * SS),
     11 * SS, GREEN, ring_w=5 * SS)

# the large nuclide the neutron is absorbed into: enough nucleons, in two
# rings, to read as "large" next to the four-nucleon alpha below it
big_positions = []
for a in (i * math.pi / 3 for i in range(6)):
    big_positions.append((16 * SS * math.cos(a), 16 * SS * math.sin(a)))
for a in (i * math.pi / 4 + 0.4 for i in range(8)):
    big_positions.append((30 * SS * math.cos(a), 30 * SS * math.sin(a)))
big_colours = [BLUE if i % 2 == 0 else GREEN for i in range(len(big_positions))]
nucleon_cluster(nx, ny, big_positions, big_colours, nucleon_r=10 * SS, halo_r=44 * SS)

# the alpha particle, dropped straight down so its track reads apart from the
# neutron's incoming line rather than as a continuation of it
ax_, ay_ = nx - 6 * SS, ny + 92 * SS
d.line([nx - 6 * SS, ny + 40 * SS, ax_, ay_ - 22 * SS], fill=WHITE, width=13 * SS)
d.line([nx - 6 * SS, ny + 40 * SS, ax_, ay_ - 22 * SS], fill=GREEN, width=6 * SS)
alpha_positions = [(-9 * SS, -9 * SS), (9 * SS, -9 * SS), (-9 * SS, 9 * SS), (9 * SS, 9 * SS)]
alpha_colours = [BLUE, GREEN, GREEN, BLUE]
nucleon_cluster(ax_, ay_, alpha_positions, alpha_colours, nucleon_r=10 * SS, halo_r=24 * SS)

# --- outgoing gamma from the recoiling daughter, up and right through N and I -
gx, gy = nx + 18 * SS, ny - 14 * SS
pts = []
for k in range(110):
    t = k / 109
    px = gx + t * (W * 0.30)
    py = gy - t * 30 * SS + math.sin(t * math.pi * 3.0) * 11 * SS
    pts.append((px, py))
# White halo first: the gamma crosses the orange letters, so orange-on-orange
# would disappear. Drawn in blue over the halo, the way YAMC's track reads
# against its orange half.
d.line(pts, fill=WHITE, width=17 * SS, joint="curve")
d.line(pts, fill=BLUE, width=8 * SS, joint="curve")
(px0, py0), (px1, py1) = pts[-10], pts[-1]
ang = math.atan2(py1 - py0, px1 - px0)
head = [
    (px1 + 24 * SS * math.cos(ang), py1 + 24 * SS * math.sin(ang)),
    (px1 + 11 * SS * math.cos(ang + 2.5), py1 + 11 * SS * math.sin(ang + 2.5)),
    (px1 + 11 * SS * math.cos(ang - 2.5), py1 + 11 * SS * math.sin(ang - 2.5)),
]
d.polygon([(hx + 4 * SS * math.cos(ang), hy + 4 * SS * math.sin(ang)) for hx, hy in head],
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
