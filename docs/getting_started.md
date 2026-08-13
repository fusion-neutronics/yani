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

Each takes a library keyword, which is downloaded and cached on first use.
The split above is not arbitrary: TENDL is a neutron-only evaluation, so it
publishes reactions and isomeric branching but no decay data and no fission
yields, and those two have to come from ENDF/B-VIII.1 or JEFF-4.0. Setting a
subsection to a library that does not publish it fails immediately, listing
what that library does have, rather than 404ing mid-download.

TENDL is worth reaching for on the reactions network because it covers far
more parent nuclides than ENDF/B-VIII.1 does, which is what decides whether an
activation product appears in your inventory at all.

These are the same five settings, with the same accepted values (a library
keyword, a directory, or an explicit per-nuclide mapping), as yamc's. The
[Nuclear data](https://fusion-neutronics.github.io/yamc/nuclear_data/) page documents them in full, including which
library keywords are available and how a keyword resolves to a download.

Activation runs read only the sections activation needs, not a whole library.

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
