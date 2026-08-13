# Getting started

## Install

```bash
pip install yani
```

The wheel carries the compiled solver, so there is nothing to build and no
transport stack to pull in.

## Point it at nuclear data

Two kinds of data are needed, and they are configured separately.

**Cross sections**, for the `sigma * phi` reaction rates, come from a
continuous-energy library:

<!-- doctest: skip -->
```python
import yani

yani.cross_section_data = "tendl-2025"
```

**The transmutation network**, for the decay constants, reaction products,
fission yields and isomeric branching, is assembled from four independently
sourced subsections, so each is set on its own and a network can mix libraries:

<!-- doctest: skip -->
```python
yani.transmutation_reactions = "tendl-2025"
yani.transmutation_branch_ratios = "tendl-2025"
yani.transmutation_decay_data = "endf-b8.1"
yani.transmutation_fission_yields = "endf-b8.1"
```

The split above is not arbitrary. Each library publishes only some of what a
calculation needs:

| library | cross sections | `decay` | `reactions` | `fission_yields` | `branching` |
| --- | :---: | :---: | :---: | :---: | :---: |
| `tendl-2025` | yes | -- | yes | -- | yes |
| `tendl-2017` | yes | -- | yes | -- | yes |
| `endf-b8.1` | yes | yes | yes | yes | yes |
| `jeff-4.0` | yes | yes | yes | yes | yes |
| `fendl-3.2d` | yes | -- | -- | -- | -- |

TENDL is a neutron-only evaluation, so it has no decay or fission-yield
sublibrary and those two must come from `endf-b8.1` or `jeff-4.0`. It is still
what you want for `reactions`, because it covers far more parent nuclides, and
that is what decides whether an activation product appears in your inventory at
all. `jeff-4.0` is the one alternative that supplies a complete network from a
single library.

Pointing a subsection at a library that does not publish it fails immediately,
with a message listing what that library does have, rather than failing partway
through a download.

!!! warning
    Unconfigured data tends to read as a zero rather than an error. Forgetting
    `cross_section_data` leaves every `sigma * phi` at zero, so an irradiation
    produces nothing and the decay heat comes back `0.0` with no complaint. If a
    result is suspiciously empty or exactly zero, check these settings first.

A keyword is all this page needs. Paths, per-nuclide dicts and where the
download lands are in
[Where the data comes from](usage.md#where-the-data-comes-from).

## A first calculation

An irradiation schedule, a spectrum, and one call:

<!-- doctest: skip -->
```python
import yani

yani.cross_section_data = "tendl-2025"
yani.transmutation_reactions = "tendl-2025"
yani.transmutation_branch_ratios = "tendl-2025"
yani.transmutation_decay_data = "endf-b8.1"      # TENDL has no decay data
yani.transmutation_fission_yields = "endf-b8.1"  # nor fission yields

# A 1 cm3 silver foil. Giving the element rather than the nuclides expands it
# over natural abundance, here Ag107 (51.8%) and Ag109 (48.2%).
#
# A volume is required for anything extensive (activity, decay heat, photon
# lines): the solver works in atoms/barn-cm and the volume turns that into atoms.
foil = yani.Material({"Ag": 1.0}, density=10.49, volume=1.0)

# The spectrum rides on the pulse. The Histogram normalizes the shape, so a
# multigroup flux from a tally can be passed straight in; the pulse `rate` is the
# total flux magnitude in n/cm2/s.
spectrum = yani.NeutronSource(
    energy=yani.sources.Histogram([1e-5, 1e5, 1e6, 1.5e7], [1e12, 1e13, 1e14])
)
# Sample the decay at these times after shutdown, in days. A Cooldown takes the
# duration OF THAT STEP, so the schedule needs the gaps between them.
days = [0.05, 0.2, 1, 5, 20, 100, 400, 1500, 3650]
gaps = [0.05, 0.15, 0.8, 4, 15, 80, 300, 1100, 2150]

schedule = yani.PulseSchedule(
    [yani.Pulse(rate=1.11e14, duration=(1, "a"), source=spectrum)]   # 1 year on
    + [yani.Cooldown(duration=(g, "d")) for g in gaps]               # then cooling
)

results = foil.transmute(schedule=schedule)   # list[Material], one per step
final = results[-1]

print(final.activity(), "Bq")
print(final.decay_heat(), "W")
```

## What comes out

Ask for the results by nuclide and plot them and the shape of an activation
problem appears: which product dominates depends entirely on how long you wait.

![Activity of the foil, by nuclide, against cooling time](images/activity.png)

`Ag106_m1` carries the activity for the first hundred days, then falls away and
`Ag110_m1` takes over, so what dominates depends entirely on when you look.
`Ag106` and `Pd109` are gone within days. Past a few years even `Ag110_m1` has
decayed and the long-lived remainder is what is left. Every point is a real
solve, not a sketch.

<details>
<summary>Plotting code</summary>

```python
import matplotlib.pyplot as plt

cooled = results[1:]                       # drop the irradiation step
per_step = [m.activity(by_nuclide=True) for m in cooled]

# The five largest by peak value, everything else summed into "other".
keys = {k for d in per_step for k in d}
peak = {k: max(d.get(k, 0.0) for d in per_step) for k in keys}
top = [k for k, _ in sorted(peak.items(), key=lambda kv: -kv[1])[:5]]

fig, ax = plt.subplots()
for name in top:
    ax.plot(days, [d.get(name, 0.0) for d in per_step], marker="o", label=name)
ax.plot(days, [sum(v for k, v in d.items() if k not in top) for d in per_step],
        marker="o", color="grey", label="other")

ax.set_xscale("log"); ax.set_yscale("log")
# Six decades. Below that a decayed-away nuclide is numerical dust, and
# letting it set the scale squashes everything that matters.
ax.set_ylim(max(peak.values()) / 1e6, max(peak.values()) * 4)
ax.set_xlabel("time after shutdown [days]"); ax.set_ylabel("activity [Bq]")
ax.legend()
```

</details>

Decay heat is the same call with a different observable, and tells a different
story: `Ag110_m1` matters more here than its activity alone suggests, because
what heats the material is energy per decay, not decays per second.

![Decay heat of the foil, by nuclide, against cooling time](images/decay_heat.png)

<details>
<summary>Plotting code</summary>

```python
import matplotlib.pyplot as plt

cooled = results[1:]                       # drop the irradiation step
per_step = [m.decay_heat(by_nuclide=True) for m in cooled]

# The five largest by peak value, everything else summed into "other".
keys = {k for d in per_step for k in d}
peak = {k: max(d.get(k, 0.0) for d in per_step) for k in keys}
top = [k for k, _ in sorted(peak.items(), key=lambda kv: -kv[1])[:5]]

fig, ax = plt.subplots()
for name in top:
    ax.plot(days, [d.get(name, 0.0) for d in per_step], marker="o", label=name)
ax.plot(days, [sum(v for k, v in d.items() if k not in top) for d in per_step],
        marker="o", color="grey", label="other")

ax.set_xscale("log"); ax.set_yscale("log")
# Six decades. Below that a decayed-away nuclide is numerical dust, and
# letting it set the scale squashes everything that matters.
ax.set_ylim(max(peak.values()) / 1e6, max(peak.values()) * 4)
ax.set_xlabel("time after shutdown [days]"); ax.set_ylabel("decay heat [W]")
ax.legend()
```

</details>

The decay photon spectrum is a set of discrete lines rather than a curve, so it
wants stems. A year after shutdown the strongest are at 658, 723, 885 and
937 keV, which are `Ag110_m1`'s gammas: this is the spectrum a detector outside
the foil would see, and it identifies the nuclide.

![Decay photon line spectrum a year after shutdown](images/photon_spectrum.png)

<details>
<summary>Plotting code</summary>

```python
import matplotlib.pyplot as plt

energies, intensities = results[-1].decay_photon_spectrum()

# 622 lines come back, most of them numerically negligible. Keep the ones
# within five decades of the strongest; the rest are not physics.
pairs = sorted(zip(energies, intensities), key=lambda p: -p[1])
floor = pairs[0][1] / 1e5
keep = [(e / 1e6, i) for e, i in pairs if i >= floor]

fig, ax = plt.subplots()
ax.vlines([e for e, _ in keep], floor, [i for _, i in keep])
ax.set_yscale("log"); ax.set_ylim(floor, pairs[0][1] * 8)
ax.set_xlabel("photon energy [MeV]")
ax.set_ylabel("emission rate [photons/s]")

for e, i in keep[:4]:
    ax.annotate(f"{e * 1000:.0f} keV", xy=(e, i), xytext=(0, 8),
                textcoords="offset points", ha="center")
```

</details>

`days` above is the cumulative cooling time of each step, which is what the
plots use for their x axis.

`transmute()` returns one `Material` per timestep, in order, each carrying the
inventory at the end of that step. They are ordinary materials, so anything you
can ask a material you can ask a result:

<!-- doctest: skip -->
```python
print(final.activity(by_nuclide=True))     # {"Ag110m": ..., "Ag108m": ..., ...}
print(final.decay_heat(by_nuclide=True))   # W per nuclide
print(len(final.nuclides))                 # how much the network grew

energies, intensities = final.decay_photon_spectrum()   # photons/s per line
```

## Next steps

- [Usage](usage.md) for schedules, spectra, results and converting your own data.
- [API reference](api.md) for the full typed surface.
