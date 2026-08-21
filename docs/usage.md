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
about YANI prefers one structure over another. The example above uses three
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
| `XMAS-172` | 172 | 1.00001e-5 eV to 19.6403 MeV | the European (XMAS/JEF) lattice set |
| `VITAMIN-J-175` | 175 | 1e-5 eV to 19.64 MeV | the long-standing neutron transport standard |
| `SCALE-252` | 252 | 0 eV to 20 MeV | SCALE/AMPX |
| `TRIPOLI-315` | 315 | 1e-5 eV to 19.64 MeV | TRIPOLI |
| `SHEM-361` | 361 | 0 eV to 19.6403 MeV | resonance self-shielding in thermal lattices |
| `LLNL-616` | 616 | 1e-5 eV to 20 MeV | LLNL |
| `CCFE-709` | 709 | 1e-5 eV to 1 GeV | fine-group fusion activation spectra |
| `SCALE-999` | 999 | 1e-5 eV to 20 MeV | fine-group SCALE/AMPX |
| `UKAEA-1102` | 1102 | 1e-5 eV to 1 GeV | the finer companion to `CCFE-709`, same 1 GeV top |
| `ECCO-1968` | 1968 | 1.00001e-5 eV to 19.64033 MeV | ECCO/ERANOS fine group |
| `VITAMIN-J-42` | 42 | 1 keV to 50 MeV | photon, with resolution at the 511 keV and Co60 lines |
| `CCFE-24-PHOTON` | 24 | 1 keV to 20 MeV | coarse photon |

Passing a name that is not one of these raises with the list of the ones that
are, so a typo never silently becomes something else. Every name except
`CCFE-24-PHOTON` carries the same boundaries as OpenMC's
`openmc.mgxs.GROUP_STRUCTURES` entry of that name, so a spectrum tabulated for
one code can be handed to the other without re-binning. Note that `SCALE-252`
and `SHEM-361` start at exactly 0 eV, which is OpenMC's value; treat their
bottom bin as open-ended.

If you need the edges themselves, to bin your own data, to plot a spectrum
against them, or to fold a cross section over them, ask for them by name:

<!-- doctest: skip -->
```python
edges = yani.group_structure("CCFE-709")
len(edges)              # 710, one more than the group count
edges[0], edges[-1]     # 1e-05 eV, 1e+09 eV

yani.group_structure_names()   # every name in the table above
```

The list is a copy, and the same edges a `Histogram` built on that name bins on.

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

`contact_dose()` is the third of these, and the one that needs no `volume`: it
is the dose someone receives with a hand on the material, from the material's
own decay photons, and a bigger lump of the same material reads the same at
contact.

<!-- doctest: skip -->
```python
final.contact_dose()                          # Gy/h, absorbed dose in air
final.contact_dose(by_nuclide=True)           # dict[str, float], Gy/h per nuclide
final.contact_dose(dose_quantity="effective") # Sv/h, ICRP-116 effective dose
```

It is a slab estimate rather than a transport result. The material is taken to
be a half-space, so half the photons emitted at any depth head for the surface,
and the ones that arrive are the ones the material did not attenuate itself.
Integrating over depth cancels the geometry, which is why no distance and no
volume appear in the answer. A `build_up` factor, 2.0 by default, stands in for
the photons that scatter on the way out and still arrive.

The two NIST tabulations it folds against are public, so a response function of
your own can be built from the same data: `mu/rho` for any element from Z = 1 to
100, and `mu_en/rho` for air. Both read log-log between their tabulated points
and carry the same names as their OpenMC counterparts.

<!-- doctest: skip -->
```python
iron = yani.data.mass_attenuation_coefficient("Fe")   # or by atomic number, 26
iron.interpolate(1.0e6)                               # cm2/g at 1 MeV
air = yani.data.mass_energy_absorption_coefficient("air")
```

The default quantity follows the FISPACT-II methodology and agrees with
OpenMC's `Material.get_photon_contact_dose_rate`. Bremsstrahlung from decay
electrons is not modelled, so a strong beta emitter reads low at contact.

The decay photon line spectrum comes back as the `(x, p)` pair the source
distributions take, in photons per second, so it feeds straight into a photon
transport run in yamc:

<!-- doctest: skip -->
```python
energies, intensities = final.decay_photon_spectrum()
```

## Production routes

`TransmutationChain` carries the topology behind the solve: which nuclide becomes
which, and how. `reactions` holds the neutron-induced edges and `decays` the
radioactive ones, both keyed by parent and both giving
`(kind, target, branching)`:

<!-- doctest: skip -->
```python
chain = yani.TransmutationChain("transmutation-endf-b8.1-sfr.arrow")

chain.reactions["W186"]   # [('(n,2n)', 'W185', 1.0), ..., ('(n,a)', 'Hf183', 1.0)]
chain.decays["Hf183"]     # [('beta-', 'Ta183', 1.0)]
chain.decays["W185_m1"]   # [('IT', 'W185', 1.0)]
```

Stable nuclides have no decay modes and are absent from `decays`, as they are
from `half_lives`. A `target` of `None` means the channel names no single
product: fission on the reaction side, a product outside the chain on the decay
side. Decay modes carry the evaluation's own spellings (`"beta-"`, `"ec/beta+"`,
`"alpha"`, `"IT"`, `"sf"`, and emissions written as `"beta-,n"`), and the
branchings for one parent sum to 1.

The two share a tuple shape, so a route walk can put them in one edge list. With
reactions alone the walk stops at the first product, one step short of most real
routes:

<!-- doctest: skip -->
```python
edges = {}
for parent, es in chain.reactions.items():
    edges.setdefault(parent, []).extend(es)
for parent, es in chain.decays.items():
    edges.setdefault(parent, []).extend(es)

for kind1, mid, _ in edges["W186"]:              # two-step routes from W186 to Ta183
    for kind2, end, _ in edges.get(mid, []):
        if end == "Ta183":
            print(f"W186{kind1}{mid}({kind2}){end}")

# W186(n,3n)W184((n,np))Ta183
# W186(n,4n)W183((n,p))Ta183
# W186(n,a)Hf183(beta-)Ta183      <- the one that needs the decay edge
```

The branching on an edge is a share of its own channel, not a rate: it says how a
channel splits, not how often the channel fires. Two routes into the same product
are not weighted against each other by these numbers alone.

Note that the chain this object holds is the base three-part merge. The isomeric
branching overlay is applied inside the solve, so a `(n,2n)` edge here names the
ground state where the overlay would split it between ground state and isomer.

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
borrowing ENDF/B-VIII.1 decay data is the usual arrangement. They are global
process state, not per-call arguments. See
[Point it at nuclear data](getting_started.md#point-it-at-nuclear-data) for
which library publishes which subsection.

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
converters ship on this wheel: see [Making your own data](#making-your-own-data).

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
