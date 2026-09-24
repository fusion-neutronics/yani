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

A decay curve wants points at cumulative times, while `Cooldown` takes the
duration of its own step, so a sweep means differencing the times by hand.
`cooldown_steps()` does that for you:

<!-- doctest: skip -->
```python
schedule = yani.PulseSchedule(steps=[
    yani.Pulse(rate=1e14, duration=(2, "h"), source=spectrum),
    *yani.cooldown_steps(start=(1, "h"), stop=(10, "a"), n=40),
])
```

The steps land at cumulative times from `start` to `stop`, log-spaced by
default: decay is exponential, so a linear sweep spends its points on the flat
tail and misses the early fall. `spacing="linear"` is the other one, and
anything else raises.

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

Two of them reach far past the evaluations. `CCFE-709` and `UKAEA-1102` top out
at 1 GeV, while most ENDF/B-VIII.1 evaluations stop at 20 MeV, so a spectrum on
one of those structures with flux in its top groups is refused, naming the
nuclide and the energy its evaluation stops at. Leaving those groups empty is
the normal case and costs nothing. Which library reaches how far is in
[Energy range](libraries.md#energy-range).

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

`per` is the way out of needing a size at all. `per="cm3"` gives Bq/cm³ or W/cm³
and needs neither `volume` nor `density`, and `per="g"` gives Bq/g or W/g and
needs only `density`. The decay photon spectrum takes the same argument:

<!-- doctest: skip -->
```python
final.activity(per="cm3")                  # Bq/cm3, no volume needed
final.decay_heat(per="g")                  # W/g, needs only density
final.decay_photon_spectrum(per="cm3")     # photons/s/cm3
```

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

## Clearance and waste classification

YANI computes what a material becomes, not what a regulator makes of it. The
limits are jurisdiction, and they belong in a package that tracks them.
[`radiological-material-clearance-finder`][rmcf] is one: 22 limit sets covering
clearance, exemption and disposal classification for the UK, Germany, the US,
the EU and the IAEA, each generated from the official source and carrying its
provenance.

It is not a dependency of YANI and does not need to be. Its input is a mapping
of nuclide to atom density in atoms per barn-cm, which is exactly what
`get_material_nuclides()` returns.

<!-- doctest: skip -->
```python
from radiological_material_clearance_finder import Material as Clearance
from radiological_material_clearance_finder import clearance_index, time_to_clear

results = steel.transmute(schedule=schedule)
material_id = steel.id or 0

# One Pulse before the cooldowns, so step 1 is shutdown. `times` carries one
# more entry than the schedule has steps, because step 0 is the material as
# it went in.
shutdown = 1
series = {}
for step in range(shutdown, results.num_steps + 1):
    densities = results.get_material_nuclides(material_id, step)
    if densities is None:  # a material_id the run does not carry
        continue
    series[results.times[step] - results.times[shutdown]] = (
        Clearance.from_atom_densities(densities, volume=steel.volume)
    )

print(clearance_index(series[max(series)], "IAEA_GSR3_clearance").index)
print(time_to_clear(series, "IAEA_GSR3_clearance"))
```

**Start the series at shutdown, not at step 0.** Step 0 is the unirradiated
material, which clears trivially, and a series that begins there has an index
that falls below the limit and then climbs. `time_to_clear` refuses that with
an `IngrowthError` rather than reporting the first crossing, which is the right
answer to the wrong series.

A daughter growing in faster than its parent decays can do the same thing to a
series that does start at shutdown, so the refusal is not only about step 0.
That is a real property of the inventory and worth seeing rather than
smoothing over.

For SS316 held in a 14 MeV field at 1e14 n/cm²/s for a year, `time_to_clear`
returns `None` against both the IAEA and EU sets: it has not cleared after 100
years of cooling, where the index is still 1.4e5. Long-lived activation
products are what a clearance limit is for, and an answer of "not within the
window you sampled" is the honest form of that.

[rmcf]: https://github.com/fusion-energy/radiological_material_clearance_finder

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
practice. A dilute run fills `would_shield` instead: nuclides whose own
resonances are structured enough to have suppressed a reaction, each mapped to
how strongly.

`would_shield` is an indicator, not a correction and not a bound. There is no
geometry in it. The weight is `1 / (1 + N * sigma_x)` on that one reaction and
that nuclide's own density, which fixes the background at 1/cm, while the
correction proper uses `1 / chord_cm` against the material's total with
in-scattering. So it can sit either side of the real factor: a lump thinner than
a centimetre of chord shields less, and a material whose other nuclides dominate
the total across a resonance dips the flux further than one reaction can
express. On the FNS tungsten foil it reads 0.634 for W186, against a
slowing-down correction that gives 0.750 at a 1 mm chord and saturates at 0.730.

Read it as "this answer may be high, and this is a resonance absorber", which
is the warning a dilute run should carry rather than silence. For the size of
the effect, ask for a shielded run.

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

for kind1, via, _ in edges["W186"]:              # two-step routes from W186 to Ta183
    for kind2, end, _ in edges.get(via, []):
        if end == "Ta183":
            print(f"W186{kind1}{via}({kind2}){end}")

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

### Weighted, from a solve

The walk above can enumerate routes but not rank them, and the branching it
reads is the file's, not the one the solve used. `get_production_routes()`
answers the same question from a solve that has happened. Asked for the Ta183 of
the example above:

<!-- doctest: skip -->
```python
routes = results.get_production_routes(material_id=mid, product="Ta183", step=0)
for route in routes or []:          # None if the material or the step is unknown
    print(f"{route['route']:<32} {route['share']:.1%}")

# W183(n,p)Ta183                    72.4%
# W186(n,a)Hf183(BETA-)Ta183        16.1%   <- the one that needs the decay edge
# W184(n,np)Ta183                    7.1%
# W184(n,d)Ta183                     4.4%
```

Each entry also carries `steps`, the same route as `(parent, kind, target)`
triples with the chain's own spellings (`('Hf183', 'beta-', 'Ta183')`), where the
`route` string uppercases decay kinds the way the published pathway tables print
them.

The walk starts from the nuclides the material began with, which a bare chain
cannot do. Asked what makes W187, a chain lists
`Os190(n,a)` and `Ir192(n,npa)` as readily as `W186(n,gamma)`, and nothing in a
tungsten foil is osmium.

`share` is the fraction of that product's production arriving down the route: the
atoms it starts from, times what its reaction drove per atom of its parent over
the step, times the branching of every decay it passes through, so a route
through a 1% branch delivers 1% of what the reaction made. Reaction steps carry
the step duration too, so `reaction_depth=2` is in the same units as the default
1 and comes out smaller by roughly a factor of the fluence. `production` is the
same number unnormalised, in atoms per barn-cm, because 100% of almost nothing
and 100% of the inventory read alike otherwise.

The flux-weighted isomeric branching comes from the same place:

<!-- doctest: skip -->
```python
branching = results.get_isomeric_branching(material_id=mid, step=0) or []
branching[0]
# {'parent': 'W186', 'reaction': '(n,2n)', 'production': 9.35e-14,
#  'split': [('W185_m1', 0.535), ('W185', 0.465)]}
```

Channels come back ordered by what they made, the channel's rate times its
parent's atom density at the start of the step, rather than by rate alone. A
rate is per atom of its parent, so ordering on that promotes whatever sits on a
trace isotope: on the FNS tungsten foil `W180 (n,2n)` has the highest per-atom
rate of any channel in the foil, and W180 is 0.12% of it, so weighted by what it
actually made the channel falls to fifth, two orders of magnitude below the
`W186 (n,2n)` carrying most of that foil's decay heat. A parent the step did not
start with has a production of `0.0` and sorts last rather than being dropped.

Which state a reaction leaves its product in is energy dependent, so the one
number describing a spectrum is the branching collapsed against it, and that
exists only inside a solve. In the chain file that same channel reads
`W186 (n,2n) -> W185 1.000000` and `-> W185_m1 0.000000`, a placeholder the
overlay replaces at solve time. Only channels landing in more than one final
state are returned, since a single-product channel has no branching to report and
listing it at 1.0 buries the ones that do.

This is what separates a disagreement caused by a cross section from one caused
by a branching ratio. On a foil whose decay heat comes from an isomer, getting it
wrong is a factor of several.

### Where in energy a rate came from

A one-group rate cannot say which part of the spectrum made it.
`get_reaction_rate_spectrum()` resolves one channel's rate onto the groups of
the spectrum that drove it:

<!-- doctest: skip -->
```python
capture = results.get_reaction_rate_spectrum(
    material_id=mid, nuclide="W186", kind="(n,gamma)", step=0
) or {}

edges = capture["boundaries"]     # group boundaries in eV, one longer than rates
per_group = capture["rates"]      # each group's contribution, 1/s

sum(per_group)                    # the rate get_reaction_rates() reports
```

The two agree because they come from the same walk of the same cross sections,
self-shielding included, so this is a decomposition of the rate the solve used
rather than a second estimate of it.

The attribution is what the single number hides. A capture cross section spans
decades, and an effective one-group value of tens of millibarns against a
spectrum that is almost all fast is either a fast-capture rate or a
resonance-region rate. Which one it is decides whether a disagreement belongs to
the resonance processing or to the fast cross section, and those are different
data and different fixes:

<!-- doctest: skip -->
```python
below_100_keV = sum(r for lo, r in zip(edges, per_group) if lo < 1.0e5)
print(f"{below_100_keV / sum(per_group):.1%} of the capture rate is resonance region")
```

It is also the per-group form of what `rate_fraction_covered` reports as one
number: whether a covariance grid that stops short of the spectrum stops short of
anywhere the rate actually is. On a shielded run it says which groups the flux
depression moved, which `strongest_factor` gives only as a worst case.

Nothing is stored for it. One reaction over a 709-group structure is cheap to
walk when asked, and keeping the breakdown for every channel would be tens of
megabytes, so a run that never asks pays nothing. `None` comes back for a step
that drove no flux, for a nuclide or channel the data does not carry, for
`(n,n')`, whose rate comes from the branching overlay rather than from a group
average, and for a coupled yamc run, which scores its rates at the collision
energy and keeps no group structure to resolve them onto.

## Nuclear data settings

Five module-level settings, read and written like attributes:

| setting | supplies | decides | left unset |
| --- | --- | --- | --- |
| `cross_section_data` | continuous-energy cross sections per nuclide | how fast each channel runs | nothing at all: every `sigma * phi` is zero |
| `transmutation_reactions` | which reaction on which nuclide gives which product, and its Q | which products exist to be made | `endf-b8.1` |
| `transmutation_decay_data` | half-lives, decay modes, mean decay energies, photon lines | how the inventory decays and what it emits | `endf-b8.1` |
| `transmutation_fission_yields` | fission product yields | what a fission makes | `endf-b8.1` |
| `transmutation_branch_ratios` | isomeric branching against incident energy | which product is left in a metastable state | no overlay, so every product lands in its ground state |

Each takes a library keyword or a path, and each can point somewhere different,
so a network can mix libraries by subsection: a TENDL reactions network
borrowing ENDF/B-VIII.1 decay data is the usual arrangement. They are global
process state, not per-call arguments. See
[Nuclear data libraries](libraries.md) for which library publishes which
subsection, and how much is in each.

Note which way the last column goes. Four of the five have a default and answer
something without being set. `cross_section_data` has none: leave it alone and
there are no cross sections to fold, so every rate is zero, the composition comes
back as it went in and the decay heat is `0.0` with nothing to say why.

### The two that both say reactions

`cross_section_data` and `transmutation_reactions` are halves of one calculation
rather than alternatives, and the rate collapse is where they meet. For each
nuclide, the network lists the channels it has; each channel's name is mapped to
an MT number; and the cross sections are what that MT is priced with. So the
network decides **which channels are considered at all** and the cross sections
decide **how fast each one runs**. Neither substitutes for the other: swap the
library behind `transmutation_reactions` and products appear or disappear, swap
the one behind `cross_section_data` and the same products arrive at different
rates.

Two consequences follow from that loop, and both are quiet:

* A channel the network names whose MT the cross sections do not carry is
  skipped. `(n,n')` is the standing example: it has no transport MT, so its rate
  comes from the branching overlay's partials rather than from a group average,
  which is why it is absent from a `get_reaction_rate_spectrum()` answer.
* The two fail differently. A missing `cross_section_data` is silent, per the
  column above. A network pointed at the wrong material is refused before the
  solve, naming what the material holds against what the network drives.

`transmutation_reactions` and `transmutation_fission_yields` additionally accept
`False`, which turns that subsection off. A decay-only calculation carries no
reaction rates, so it needs no reaction topology; a material nothing in which
fissions needs no yields, and neither does a library that publishes none of its
own. Off is not the same as unset: for these two `None` restores the default
library, whereas `False` says the subsection is absent on purpose. A rate that then needs it is
refused when the burnup matrix is built, naming the nuclide and the reaction,
rather than being solved as though the reaction produced nothing.

A reactions network built for one material and pointed at another is refused on
the same terms. Networks are often scoped to the nuclides they were built from,
because walking a whole library to activate one foil is wasted work. The cost is
that two scoped networks look alike from the outside: two conversions writing to
the same output path leave the second network under a filename that names the
first. Solving against the wrong one does not fail. Every step runs, no rate is
negative, and the composition comes back as it went in, so the mistake surfaces
as a decay heat of exactly zero much later with nothing to point at. An
irradiated schedule whose material has no drivable nuclide is therefore refused
up front, naming both what the material holds and what the network has reactions
for. A decay-only schedule is exempt, since driving nothing is correct for it.

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

Both network converters record which nuclides carry reactions of their own, as
`parents` on each subsection of the manifest they write. A nuclide that appears
only as somebody else's product is not a parent. That distinction is what lets
an irradiated solve refuse a network scoped to a different material instead of
returning the starting composition unchanged.

### What the converters report about the library

Neither converter corrects its input. What they do is say what the input claims
that cannot be right, so that a number carrying your decay heat can be looked up
before it is believed.

The `decay` subsection's `provenance.json` carries two records:

* `decay_energy_placeholders` names every nuclide whose average decay energies
  are the Q/3 stand-in rather than an evaluated scheme, and the rule used to
  detect them. Listed by name rather than counted, because the question a reader
  asks is whether a nuclide carrying heat in their inventory is one of them.
* `decay_inconsistencies` lists, per kind, the records that cannot all be true:
  flagged unstable with a half-life of zero, branching ratios that do not sum to
  one, and isomeric transitions whose light and electromagnetic averages do not
  add up to the transition's Q. That last one matters most for decay heat, since
  an isomeric transition emits no neutrino and so must pay out its whole Q.
  ENDF/B-VIII.1 books Hf177m1 at 1.52 MeV against a 1.32 MeV transition.

`convert_branching` returns a dict rather than writing one, since a build script
is what decides whether to publish:

* `level_routes` counts how each excited production level was matched to an
  isomeric state: by energy, by energy within a tenth, by level index, as the
  only candidate, or not at all. A level matched by index is right only while
  two level schemes happen to agree, so a rebuild against another decay library
  moving levels out of `energy` is the regression the plain counts hide.
* `flagged_levels` is one line per level worth reading before publishing.
* `partial_sum_mismatches` is one line per reaction whose MF=10 partial cross
  sections do not reconstruct its MF=3 total, or whose MF=9 yields do not sum to
  one, by more than 2% of the nonelastic cross section. The rates are shared out
  in the partials' proportions either way, so this does not move a yani answer;
  it moves a code that folds the partials as they stand, and it points at the
  evaluation. TENDL-2017's Ir191 (n,2n) partials sum to 95% of MF=3 at 14 MeV
  because the file lists two of Ir190's three states.

### Filling placeholder decay energies

Where the decay library has no evaluated scheme for a nuclide and another
library does, the second one's average energies can be substituted:

<!-- doctest: skip -->
```python
yani.convert_transmutation(
    decay_files=decay, fpy_files=fpy, neutron_files=neutron,
    output_path="out/transmutation_endf-b8.1.arrow",
    library="endf-b8.1",
    decay_fill_files=jendl_decay, decay_fill_library="jendl-5.0",
)
```

Only a placeholder is replaced, only from a record that is not itself a
placeholder, and only when the two half-lives agree within 25%, which is what
keeps a differently-assigned isomer out. Only the mean energy and its
uncertainty move: half-lives, decay modes and spectra stay as the decay library
has them, so the network's topology is untouched. Every substitution is written
to `provenance.json` as `decay_energy_fill`, with the value before and after, and
each nuclide's `decay_energy_source` reads `evaluation`, `placeholder` or
`filled:<library>`.

Without `decay_fill_files` nothing is substituted and the numbers are
byte-identical to what the decay library published, so the placeholder list is
worth reading even when you do not act on it.

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
them, which is how a contribution is measured. Naming a
source this build cannot perturb raises.
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
    info["rate_fraction_covered_total"]  # ... and over the run, weighted by production
    info["not_perturbed"]          # sources this does not propagate
    info["sources"]                # the ones it did
    info["has_gaps"]               # True if anything was left out
```

Read `rate_fraction_covered_total` before any sigma above it. A count of
nuclides with MF=33 measures how much covariance exists. This measures how much
of it lands on the reactions the run drove, weighted by rate and by the parent's
own density.

Tungsten shows how far the two can diverge. Two major libraries state
covariance for all five natural tungsten isotopes, so a count reads as complete
coverage, and what they state it for is `(n,3n)` and `(n,gamma)`: the `(n,2n)`
making 98% of a tungsten foil's decay heat has none. The ensemble perturbs about
6% of the production and reports a spread under 0.1%.

Both weights are needed. Rate alone, without the density of the parent each rate
belongs to, counts a channel on a trace isotope the same as one on the bulk: on
an iron foil that is 32% against 96%.

For a decay-only schedule there is no production to weight by, so the value is
`None`, not zero.

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
under which two lines' spreads are taken over the same sample. `emitting` keeps
that zero-fill visible, so a dim line and an intermittent one stay
distinguishable.

`get_uncertainty_inventories(material_id=mid, step=step)` is still there for a
quantity these four do not cover, and returns every replica's full inventory to
take the spread over yourself.

## Limits worth knowing

- **A step is exact at any length, for a fixed spectrum.** The burnup matrix is
  built from decay constants and `sigma*phi` rates and does not depend on the
  composition, so it is constant over a step and the matrix exponential is
  solved exactly. One year in a single step and one year in 365 agree to
  round-off. Shortening steps to chase accuracy buys nothing here.

  What a long step **does** miss is the spectrum changing as the composition does,
  which `transmute()` cannot see because the flux is your input rather than
  something it solves for. If the field would harden or soften appreciably over
  the campaign, split the schedule and give each pulse its own spectrum. That is
  a statement about the physics you are feeding it, not about the solver.
- `data_uncertainty` covers the activation cross sections, and the flux spectrum
  when a pulse carries `flux_std_dev`. Without one the flux is taken as exact,
  since nothing is transported here. Half-lives, decay branching ratios and
  fission yields are held at their evaluated values throughout. Cross-material
  covariance (`MAT1 != 0`) and covariances derived from a standards evaluation
  are not consumed; both are counted in `data_uncertainty_info`.
- Nothing is self-shielded unless you give a shape or a chord, so a dilute run
  of a resonance absorber reads high. `self_shielding_info["would_shield"]`
  flags which nuclides on the run that skipped it, and how strongly their own
  resonances could bite. It is a screen, not a bound: only a shielded run says
  by how much.
- The network is only as complete as the chain you configure. A product whose
  parent reaction is missing from `transmutation_reactions` never appears, and
  neither does any route through it.
- A route table covers one step, to the depth you ask for. Each route is weighted
  by what its own reactions drove over that step, which is right while the
  intermediates barely burn. A route needing more reactions than `reaction_depth`
  or more decays than `decay_depth` does not appear, and the shares are shares of
  the routes that did. Raise the depths before reading an absence as impossible.
- Nuclides many decades below the largest inventory carry no significant figures.
  Treat a deep trace as a bound, not a number.
