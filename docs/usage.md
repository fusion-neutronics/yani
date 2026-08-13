# Usage

## Schedules

An irradiation history is one `PulseSchedule` built from `Pulse` (irradiation) and
`Cooldown` (decay only) steps, in order. Every step carries a duration, either
seconds as a plain number or a `(value, unit)` tuple:

| unit | accepted spellings |
| --- | --- |
| seconds | `s`, `sec`, `second`, `seconds` |
| minutes | `min`, `minute`, `minutes` |
| hours | `h`, `hr`, `hour`, `hours` |
| days | `d`, `day`, `days` |
| years | `a`, `y`, `yr`, `year`, `years` (365.25 days) |

<!-- doctest: skip -->
```python
schedule = yani.PulseSchedule([
    yani.Pulse(rate=1e14, duration=(2, "h"), source=spectrum),
    yani.Cooldown(duration=(30, "min")),
    yani.Pulse(rate=5e13, duration=(2, "h"), source=spectrum),   # different rate
    yani.Cooldown(duration=(1, "a")),
])
```

Each pulse gets its own `rate` and its own `source`, so a campaign whose spectrum
or magnitude changes between phases is expressed directly. `transmute()` returns
one material per step, so the number of results is the number of steps.

!!! note "What `rate` means depends on the entry point"
    For standalone `Material.transmute()`, `rate` is the **total flux magnitude**
    in n/cm²/s: the spectrum supplies the shape and `rate` supplies the size. For
    the coupled `Model.simulate_transmutation()` in yamc, the same field is a
    **source rate** in n/s, because there a transport solve turns emission into
    flux. The `Pulse` docstring gives the latter.

## Spectra

The spectrum rides on the pulse as a `NeutronSource` whose energy distribution is
a `Histogram` of group boundaries and per-group values:

<!-- doctest: skip -->
```python
energy_groups = [1e-5, 0.625, 1e5, 2e7]   # eV, ascending, n+1 boundaries
multigroup_flux = [1e12, 5e12, 1e14]      # n groups: thermal, epithermal, fast

spectrum = yani.NeutronSource(
    energy=yani.sources.Histogram(energy_groups, multigroup_flux)
)
pulse = yani.Pulse(rate=sum(multigroup_flux), duration=(1, "h"), source=spectrum)
```

The `Histogram` normalizes the shape, so a flux spectrum can be passed in with
its own magnitudes and the total handed to `rate`. The source's position and
direction are ignored, since nothing is transported.

### Named group structures

**Any group structure works.** The boundaries argument is just an ascending list
of energies in eV, of whatever length your spectrum happens to have, and nothing
about yani prefers one structure over another. The example above uses three
groups.

What the names below add is convenience for a handful of common structures, so
that if your spectrum is already on one of them you do not type out its
boundaries. They are not privileged, and using one is not required:

<!-- doctest: skip -->
```python
spectrum = yani.NeutronSource(
    energy=yani.sources.Histogram("CCFE-709", flux_709)   # 709 values
)
```

| name | groups | range | typical use |
| --- | ---: | --- | --- |
| `CCFE-709` | 709 | 1e-5 eV to 1 GeV | fine-group fusion neutron spectra |
| `VITAMIN-J-175` | 175 | 1e-5 eV to 19.6 MeV | the long-standing neutron transport standard |
| `VITAMIN-J-42` | 42 | 1 keV to 50 MeV | photon, with resolution at the 511 keV and Co60 lines |
| `CCFE-24-PHOTON` | 24 | 1 keV to 20 MeV | coarse photon |

Passing a name that is not one of these raises with the list of the ones that
are, so a typo never silently becomes something else.

If you need the edges themselves, to bin your own data or to plot against them,
read them back off the histogram:

<!-- doctest: skip -->
```python
edges = yani.sources.Histogram("CCFE-709", [1.0] * 709).boundaries
len(edges)              # 710, one more than the group count
edges[0], edges[-1]     # 1e-05 eV, 1e+09 eV
```

Cross sections are collapsed against each distinct spectrum once and then scaled
by each step's `rate`, rather than recollapsed every step.

## Materials

A composition dict plus a density. Element symbols expand over natural
abundance, nuclide names are taken literally, and chemical formulas are parsed:

<!-- doctest: skip -->
```python
foil = yani.Material({"Ag": 1.0}, density=10.49, volume=1.0)
enriched_li = yani.Material(
    {"Li": yani.enriched(1.0, target="Li6", percent=60.0)}, density=0.534, volume=10.0
)
breeder = yani.Material({"Li4SiO4": 1.0}, density=2.4, volume=100.0)
```

For a standard shielding or structural material, the PNNL Compendium
(PNNL-15870 Rev. 2) ships with the package, 410 materials keyed by the report's
own names, so the composition and density come from a citable source rather
than from your own retyping:

<!-- doctest: skip -->
```python
steel = yani.materials.pnnl.material("Steel, Stainless 316", volume=1000.0)
concrete = yani.materials.pnnl.material("Concrete, Ordinary (NIST)", volume=1e6)

list(yani.materials.pnnl)          # every name in the compendium
```

Pass `volume` at construction for either route: it is what turns the solver's
atom densities into the atom counts that activity and decay heat need.

## Results

`transmute()` returns `list[Material]`, one per step, each holding the inventory
at the end of that step. Extensive quantities need the material's `volume` in cm³:

<!-- doctest: skip -->
```python
results = material.transmute(schedule=schedule)

for step, mat in enumerate(results, start=1):
    print(step, mat.activity(), "Bq", mat.decay_heat(), "W")

final = results[-1]
final.activity(by_nuclide=True)      # dict[str, float], Bq per nuclide
final.decay_heat(by_nuclide=True)    # dict[str, float], W per nuclide
final.nuclides                       # list[(name, fraction)]
final.get_atoms_per_barn_cm()        # dict[str, float], the solver's own units
```

Stable nuclides contribute nothing to activity or decay heat and are omitted from
the by-nuclide dictionaries.

The decay photon line spectrum comes back as the `(x, p)` pair the source
distributions take, in photons per second, so it feeds straight into a photon
transport run in yamc:

<!-- doctest: skip -->
```python
energies, intensities = final.decay_photon_spectrum()
```

## Nuclear data settings

Five module-level settings, read and written like attributes:

| setting | supplies |
| --- | --- |
| `cross_section_data` | continuous-energy cross sections for the rate collapse |
| `transmutation_decay_data` | half-lives, decay modes, mean decay energies, photon lines |
| `transmutation_reactions` | which reaction on which nuclide gives which product |
| `transmutation_fission_yields` | fission product yields |
| `transmutation_branch_ratios` | isomeric branching: which product is left in a metastable state |

Each takes a library keyword or a path, and each can point somewhere different,
so a network can mix libraries by subsection: a TENDL reactions network
borrowing ENDF/B-VIII.1 decay data is the usual arrangement.
`cross_section_data` also accepts a dict keyed by nuclide; the four
`transmutation_*` settings take a single value each. They are global process
state, not per-call arguments. See
[Point it at nuclear data](getting_started.md#point-it-at-nuclear-data) for
which library publishes which subsection.

## Making your own data

The wheel also carries the converters, so producing the Arrow data is a function
call rather than a separate toolchain:

<!-- doctest: skip -->
```python
# Cross sections for the rate collapse, from ENDF (needs NJOY) or from ACE.
yani.convert_neutron_xs("n-026_Fe_056.endf", "out/", njoy_exec="njoy")

# The transmutation network, from decay, fission-yield and neutron evaluations.
yani.convert_transmutation(
    decay_files=decay, fpy_files=fpy, neutron_files=neutron,
    output_path="out/transmutation_tendl-2025.arrow",
)

# Isomeric branching, as an overlay on the network.
yani.convert_branching(
    neutron_files=neutron, decay_files=decay,
    output_path="out/branching.arrow",
)
```

`convert_neutron_transport` and `convert_photon` are present too, since all the
wheels share one bindings crate, but they write sections only transport reads.

NJOY is needed for the ENDF route and nothing avoids it: an ENDF evaluation
describes the resonance region with resonance parameters rather than pointwise
cross sections, so something has to reconstruct and Doppler broaden it.
`source_format="ace"` reads an already-processed table and needs no NJOY, at the
cost of one temperature and no heating sections.

## Limits worth knowing

- One stepper, with beginning-of-step reaction rates. Long steps at high flux
  will drift; shorten them rather than trusting a single step.
- The network is only as complete as the chain you configure. A product whose
  parent reaction is missing from `transmutation_reactions` simply never appears.
- Nuclides many decades below the largest inventory carry no significant figures.
  Treat a deep trace as a bound, not a number.
