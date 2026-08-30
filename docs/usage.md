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
schedule = yani.PulseSchedule(steps=[
    yani.Pulse(rate=1e14, duration=(2, "h"), source=spectrum),
    yani.Cooldown(duration=(30, "min")),
    yani.Pulse(rate=5e13, duration=(2, "h"), source=spectrum),   # different rate
    yani.Cooldown(duration=(1, "a")),
])
```

Each pulse gets its own `rate` and its own `source`, so a campaign whose spectrum
or magnitude changes between phases is expressed directly. The results carry one
material per step, so the number of results is the number of steps.

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
    energy=yani.sources.Histogram(boundaries=energy_groups, probabilities=multigroup_flux)
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
    energy=yani.sources.Histogram(boundaries="CCFE-709", probabilities=flux_709)   # 709 values
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
edges = yani.group_structure(name="CCFE-709")
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
foil = yani.Material(composition={"Ag": 1.0}, density=10.49, volume=1.0)
enriched_li = yani.Material(
    composition={"Li": yani.enriched(fraction=1.0, target="Li6", percent=60.0)},
    density=0.534,
    volume=10.0,
)
breeder = yani.Material(composition={"Li4SiO4": 1.0}, density=2.4, volume=100.0)
```

For a standard shielding or structural material, the PNNL Compendium
(PNNL-15870 Rev. 2) ships with the package, 410 materials keyed by the report's
own names, so the composition and density come from a citable source rather
than from your own retyping:

<!-- doctest: skip -->
```python
steel = yani.materials.pnnl.material(key="Steel, Stainless 316", volume=1000.0)
concrete = yani.materials.pnnl.material(key="Concrete, Ordinary (NIST)", volume=1e6)

list(yani.materials.pnnl)          # every name in the compendium
```

Pass `volume` at construction for either route: it is what turns the solver's
atom densities into the atom counts that activity and decay heat need.

`transmute()` loads the cross sections it needs into the material and leaves
them there, so calling it again on the same material does no file reading at
all. That is the right trade for a material you transmute more than once and the
wrong one for a sweep over thousands of distinct compositions, each of which
would otherwise hold a few hundred nuclides' data for as long as it lives. Call
`material.release_nuclear_data()` when you are done with one; the material stays
usable, and the next call that needs the data loads it again.

## Results

`transmute()` returns a `TransmutationResults` -- the same object the coupled
`Model.simulate_transmutation()` returns in yamc -- keyed by the material's `id`,
or `0` when it has none. `step_materials()` unpacks it into `list[Material]`, one
per step, each holding the inventory at the end of that step. Extensive
quantities need the material's `volume` in cm³:

<!-- doctest: skip -->
```python
results = material.transmute(schedule=schedule)
steps = results.step_materials(material_id=material.id or 0)

for step, mat in enumerate(steps, start=1):
    print(step, mat.activity(), "Bq", mat.decay_heat(), "W")

final = steps[-1]
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
iron = yani.data.mass_attenuation_coefficient(element="Fe")   # or by atomic number, 26
iron.interpolate(energy=1.0e6)                               # cm2/g at 1 MeV
air = yani.data.mass_energy_absorption_coefficient(material="air")
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

## Self-shielding

A lump of a resonance absorber shields itself: the flux inside it is depressed
exactly where the total cross section is large, so the reaction rate is lower
than the same material spread thin. Nothing is corrected unless you ask, because
a `Material` carries no geometry to infer a size from. Give the lump a shape, or
state its mean chord `4V/S` in cm yourself:

<!-- doctest: skip -->
```python
results = foil.transmute(
    schedule=schedule,
    self_shielding_shape=yani.shapes.FoilLump(thickness=0.1),   # cm
)
```

`SphereLump()` and `CubeLump()` are fixed by the material's `volume` and take no
arguments, while `FoilLump(thickness=)`, `CylinderLump(radius=)` and
`WireLump(radius=)` carry the one dimension a volume cannot imply. Give a shape
or `self_shielding_chord=`, not both. A sphere has the least surface for its
volume, so it has the longest chord and shields more than any other shape of the
same size: an upper bound rather than a safe default, which is why there is no
default at all.

The flux inside the lump comes from a slowing-down solve, which assumes nothing
about resonances being narrow. The cheaper narrow-resonance approximation is
deliberately not offered, because it over-shields strong elastic scatterers
badly enough to be worse than applying no correction at all: on W186(n,gamma) in
FNG-tung, measured at 1.29 b, the slowing-down solve gives C/E 0.80, no
correction gives 0.86 and narrow resonance gives 0.46.

What was done comes back on the results, and a run that shielded nothing says so
rather than staying silent:

<!-- doctest: skip -->
```python
shielding = results.self_shielding_info
if shielding is not None:              # None only for a coupled yamc run
    shielding["method"], shielding["chord_cm"]   # how, and the chord used
    shielding["shielded"]              # nuclides the correction reached
    shielding["not_shielded"]          # and why each of the others was left
    shielding["strongest_factor"]      # smallest factor any group average took
```

A `chord_cm` of `None` means the run was dilute and nothing was corrected. A
`strongest_factor` of `1.0` means the correction ran and changed nothing in
practice, which is a different statement. A dilute run fills `would_shield`
instead: nuclides whose own resonances could have suppressed a reaction, each
mapped to the strongest suppression it could have seen. That bound is computed
from the one reaction, ignoring the rest of the material and the geometry, both
of which push the real factor back toward one, so it says "this answer may be
high, and here is by how much at the very most".

## Production routes

`TransmutationChain` carries the topology behind the solve: which nuclide becomes
which, and how. `reactions` holds the neutron-induced edges and `decays` the
radioactive ones, both keyed by parent and both giving
`(kind, target, branching)`:

<!-- doctest: skip -->
```python
chain = yani.TransmutationChain(path="transmutation-endf-b8.1-sfr.arrow")

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

`transmutation_reactions` and `transmutation_fission_yields` additionally accept
`False`, which turns that subsection off. A decay-only calculation carries no
reaction rates, so it needs no reaction topology; a material nothing in which
fissions needs no yields, and neither does a library that publishes none of its
own. Off is not the same as unset: `None` restores the default library, whereas
`False` says the subsection is absent on purpose. A rate that then needs it is
refused when the burnup matrix is built, naming the nuclide and the reaction,
rather than being solved as though the reaction produced nothing.

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
yani.convert_neutron_xs(
    input_path="n-026_Fe_056.endf",
    output_dir="out/", njoy_exec="njoy")

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

## Nuclear-data uncertainty

Pass a `DataUncertainty` and every nuclide density comes back with a standard
deviation beside it:

<!-- doctest: skip -->
```python
results = material.transmute(
    schedule=schedule,
    data_uncertainty=yani.DataUncertainty(seed=42),
)

mid = material.id or 0
mean = results.get_nuclide_density(material_id=mid, nuclide="Mn56", step=1)
sigma = results.get_nuclide_uncertainty(material_id=mid, nuclide="Mn56", step=1)
```

The activation cross sections are resampled from their ENDF MF=33 covariance,
folded against your own spectrum, and the schedule is re-solved per sample. That
is exact to all orders in the matrix exponential; the solver is untouched and
only its input changes. Omitting the argument costs nothing at all: no
covariance is read, nothing is folded, and the inventories are bit-identical.

A given nuclide's perturbation is a pure function of `(seed, sample, nuclide)`,
so a seed reproduces a run regardless of sample count or iteration order. Leave
`samples` unset and the driver adds samples until the sigmas settle.

Two things are perturbed: the activation cross sections, and the flux spectrum
when you supply an error on it. `DataUncertainty.available_sources()` names them,
`cross_sections` and `flux_spectrum`, and `sources=` restricts a run to one of
them, which is how a contribution is measured rather than guessed. Naming a
source this build cannot perturb raises rather than being quietly ignored.
Half-lives, decay branching ratios, fission yields and the isomeric-branching
overlay stay at their evaluated values.

A spectrum that came from a Monte Carlo run carries a statistical error of its
own. Hand it to the pulse, per bin, in the same order and units as the histogram
values, and it is sampled alongside the cross sections:

<!-- doctest: skip -->
```python
flux_sigma = [2e10, 8e10, 1e12]         # one per group, as the histogram has

pulse = yani.Pulse(
    rate=sum(multigroup_flux),
    duration=(1, "h"),
    source=spectrum,
    flux_std_dev=flux_sigma,
)
```

Omitting it is the common case, since a spectrum taken from a published
reference set carries no stated error. A run then reports the omission in
`data_uncertainty_info["spectra_without_flux_sigma"]` rather than letting the
flux read as known exactly.

Because a zero sigma could mean either "well known" or "nothing published", the
two are separated in `data_uncertainty_info`:

<!-- doctest: skip -->
```python
info = results.data_uncertainty_info
if info is not None:               # None unless data_uncertainty was passed
    info["perturbed"]              # had usable MF=33 covariance
    info["no_covariance_data"]     # evaluation carries none
    info["rate_fraction_covered"]  # share of each rate the covariance grid spans
    info["not_perturbed"]          # sources this does not propagate
    info["sources"]                # the ones it did
    info["has_gaps"]               # True if anything was left out
```

Activity, decay heat and contact dose carry the same band, each as an `Estimate`
holding the unperturbed value and the ensemble's spread on it:

<!-- doctest: skip -->
```python
activity = results.get_activity_uncertainty(material_id=mid, step=1)
activity.nominal                    # the unperturbed run, always present
activity.mean, activity.std_dev     # None below two replicas
activity.relative_std_dev

results.get_decay_heat_uncertainty(material_id=mid, step=1)
results.get_contact_dose_uncertainty(material_id=mid, step=1, dose_quantity="effective")
results.get_activity_uncertainty(material_id=mid, step=1, by_nuclide=True)   # dict[str, Estimate]
```

Each is evaluated once per replica and summed within that replica, so the
correlations between nuclides survive. Building the same number out of the
per-nuclide sigmas is wrong in a specific direction: evaluating from the mean
inventory gives no spread at all, and adding sigmas in quadrature double-counts
a variance that partly cancels, since every Mn56 atom in an irradiated iron foil
came out of an Fe56 atom. `mean` and `std_dev` are `None` below two replicas,
because a spread over one sample is unmeasured rather than zero.

The decay photon spectrum comes back line by line, as `LineEstimate`s over the
union of the lines the unperturbed run and every replica emit:

<!-- doctest: skip -->
```python
lines = results.get_decay_photon_spectrum_uncertainty(material_id=mid, step=1)
for line in lines or []:
    line.energy, line.nominal, line.std_dev
    line.emitting              # replicas that emitted it at all
```

A line a replica does not emit counts as a zero in it, which is the only rule
under which two lines' spreads are taken over the same sample, and `emitting` is
what keeps that zero-fill visible: it is the difference between a line that is
dim and a line that is sometimes not there.

`get_uncertainty_inventories(material_id=mid, step=step)` is still there for a
quantity these four do not cover, and returns every replica's full inventory to
take the spread over yourself.

## Limits worth knowing

- **A step is exact at any length, for a fixed spectrum.** The burnup matrix is
  built from decay constants and `sigma*phi` rates and does not depend on the
  composition, so it is constant over a step and the matrix exponential is
  solved exactly. One year in a single step and one year in 365 agree to
  round-off. Shortening steps to chase accuracy buys nothing here.

  What a long step DOES miss is the spectrum changing as the composition does,
  which `transmute()` cannot see because the flux is your input rather than
  something it solves for. If the field would harden or soften appreciably over
  the campaign, split the schedule and give each pulse its own spectrum. That is
  a statement about the physics you are feeding it, not about the solver.
- `data_uncertainty` covers the activation cross sections, and the flux spectrum
  when a pulse carries `flux_std_dev`. Without one the flux is taken as exact,
  which is a statement about the input rather than a claim about it, since
  nothing is transported here. Half-lives, decay branching ratios and fission
  yields are held at their evaluated values throughout. Cross-material
  covariance (`MAT1 != 0`) and covariances derived from a standards evaluation
  are not consumed, and both are counted in `data_uncertainty_info` rather than
  dropped silently.
- Nothing is self-shielded unless you give a shape or a chord, so a dilute run
  of a resonance absorber reads high. `self_shielding_info["would_shield"]`
  bounds by how much, on the run that skipped it.
- The network is only as complete as the chain you configure. A product whose
  parent reaction is missing from `transmutation_reactions` simply never appears.
- Nuclides many decades below the largest inventory carry no significant figures.
  Treat a deep trace as a bound, not a number.
