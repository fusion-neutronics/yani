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

## Where the data comes from

A keyword is resolved on first use: the sections needed are downloaded and
cached under `~/.cache/yamc`, then reused. Only the sections activation reads
are fetched, never a whole library, so this is a small fraction of a transport
data set.

Every setting also accepts a **path** to a local converted directory instead of
a keyword:

<!-- doctest: skip -->
```python
yani.transmutation_reactions = "/data/my-network.arrow"
```

`cross_section_data` additionally accepts a **dict** keyed by nuclide, to mix
sources nuclide by nuclide. The four `transmutation_*` settings take a single
value each, since a network is assembled per subsection rather than per nuclide:

<!-- doctest: skip -->
```python
yani.cross_section_data = {
    "Fe56": "tendl-2025",
    "Li6": "endf-b8.1",
    "Be9": "/data/Be9.arrow",
}
```

To build the data yourself from ENDF tapes rather than download it, the
converters ship on this wheel: see
[Making your own data](usage.md#making-your-own-data).

!!! warning
    Unconfigured data tends to read as a zero rather than an error. Forgetting
    `cross_section_data` leaves every `sigma * phi` at zero, so an irradiation
    produces nothing and the decay heat comes back `0.0` with no complaint. If a
    result is suspiciously empty or exactly zero, check these settings first.

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

# A volume is required for anything extensive (activity, decay heat, photon
# lines): the solver works in atoms/barn-cm and the volume turns that into atoms.
steel = yani.materials.pnnl.material("Steel, Stainless 316", volume=1000.0)

# The spectrum rides on the pulse. The Histogram normalizes the shape, so a
# multigroup flux from a tally can be passed straight in; the pulse `rate` is the
# total flux magnitude in n/cm2/s.
spectrum = yani.NeutronSource(
    energy=yani.sources.Histogram([1e-5, 1e5, 1e6, 1.5e7], [1e12, 1e13, 1e14])
)
schedule = yani.PulseSchedule([
    yani.Pulse(rate=1.11e14, duration=(1, "a"), source=spectrum),   # 1 year on
    yani.Cooldown(duration=(1, "d")),                               # 1 day off
])

results = steel.transmute(schedule=schedule)   # list[Material], one per step
final = results[-1]

print(final.activity(), "Bq")
print(final.decay_heat(), "W")
```

`transmute()` returns one `Material` per timestep, in order, each carrying the
inventory at the end of that step. They are ordinary materials, so anything you
can ask a material you can ask a result:

<!-- doctest: skip -->
```python
print(final.activity(by_nuclide=True))     # {"Co60": ..., "Fe55": ..., ...}
print(final.decay_heat(by_nuclide=True))   # W per nuclide
print(len(final.nuclides))                 # how much the network grew

energies, intensities = final.decay_photon_spectrum()   # photons/s per line
```

## Next steps

- [Usage](usage.md) for schedules, spectra, results and converting your own data.
- [API reference](api.md) for the full typed surface.
