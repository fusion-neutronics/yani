# Nuclear data libraries

Six libraries are available by keyword. Point a setting at one and the sections it
needs are downloaded on first use and cached under `~/.cache/yamc`; only the
sections activation reads are fetched, never a whole library.

<!-- doctest: skip -->
```python
import yani

yani.cross_section_data = "tendl-2025"
yani.transmutation_reactions = "tendl-2025"
yani.transmutation_decay_data = "endf-b8.1"
```

| keyword | what it is |
| --- | --- |
| `endf-b8.1` | ENDF/B-VIII.1. What the transmutation subsections fall back to when unset. |
| `jeff-4.0` | JEFF-4.0. |
| `jendl-5.0` | JENDL-5. |
| `tendl-2025` | TENDL-2025. The widest isotope coverage of the six. |
| `tendl-2017` | TENDL-2017, for comparing a result against the older release. |
| `fendl-3.2d` | FENDL-3.2d. Cross sections only, no transmutation data. |

Every setting also takes a path to a converted directory instead of a keyword,
and `cross_section_data` takes a dict keyed by nuclide. Which setting does what,
and what each one does when left alone, is in
[Nuclear data settings](usage.md#nuclear-data-settings); `cross_section_data` is
the one with no default.

## What each library publishes

A calculation needs cross sections and four transmutation subsections, and each
is set on its own, so a network can take each part from wherever publishes it.

| library | cross sections | `decay` | `reactions` | `fission_yields` | `branching` |
| --- | --- | :---: | :---: | :---: | :---: |
| `endf-b8.1` | neutron + photon | yes | yes | yes | yes |
| `jeff-4.0` | neutron | yes | yes | yes | yes |
| `jendl-5.0` | neutron + photon | yes | yes | yes | yes |
| `fendl-3.2d` | neutron + photon | -- | -- | -- | -- |
| `tendl-2025` | neutron | -- | yes | -- | yes |
| `tendl-2017` | neutron | -- | yes | -- | yes |

TENDL is a neutron-only evaluation, so it has no decay or fission-yield
sublibrary and those two must come from one of the three that do. It is still
what you want for `reactions`, because it covers far more parent nuclides, and
that is what decides whether an activation product appears in your inventory at
all. `endf-b8.1`, `jeff-4.0` and `jendl-5.0` each supply a complete network from
one library.

Pointing a subsection at a library that does not publish it fails immediately,
naming what that library does have, rather than solving to an inventory that is
quietly missing a route.

The `cross sections` column is about transport rather than about activation:
YANI reads neutron data only, and the photon column matters when a decay photon
spectrum from here is fed into a transport run in yamc. `jeff-4.0` reads as
neutron because its photon sublibrary is photonuclear rather than the photoatomic
and atomic-relaxation pair a photon transport needs, and `fendl-3.2d` publishes
photon cross sections with no atomic relaxation at all.

## How big each library is

Counted from the built trees. `--` means the library does not publish that at
all, rather than publishing an empty one.

| library | neutron | photon | reaction edges | branching channels | decay nuclides | covariance |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `endf-b8.1` | 557 | 100 | 5,175 | 915 | 3,820 | 42% |
| `jeff-4.0` | 593 | -- | 13,513 | 8,303 | 3,851 | 98% |
| `jendl-5.0` | 795 | 100 | 9,902 | 5,349 | 4,070 | 13% |
| `fendl-3.2d` | 192 | 61 | -- | -- | -- | 35% |
| `tendl-2025` | 2,848 | -- | 67,797 | 8,416 | -- | pending |
| `tendl-2017` | 2,801 | -- | 68,827 | 8,365 | -- | pending |

`neutron` and `photon` are evaluations, one per nuclide and one per element.
`reaction edges` is how many `(parent, reaction, product)` triples the network
holds, which is the number that decides whether a product is reachable at all;
the isomeric overlay adds more at solve time, 5,546 rather than 5,175 on
`endf-b8.1`. `covariance` is the share of neutron evaluations carrying
cross-section covariance.

The spread between the two ends is the thing worth noticing: TENDL carries five
times the evaluations of ENDF/B-VIII.1 and thirteen times the reaction edges,
and ENDF/B-VIII.1 carries the decay data that TENDL has none of. That is why the
usual arrangement is a TENDL `reactions` network with ENDF/B-VIII.1 `decay` and
`fission_yields` beside it.

Mixing that way asks the decay subsection to cover everything the reactions
network can reach, and the published pairings do: the TENDL-2025 network puts
3,116 nuclides in play, and both ENDF/B-VIII.1 and JENDL-5 carry decay data for
every one of them. It is worth knowing what the miss would look like, because a
hand-built or scoped chain can produce it. A product with no decay entry gets no
decay term in the burnup matrix, so it accumulates and never decays, reports zero
activity and zero heat, and is indistinguishable from a genuinely stable
product.

### Covariance is presence, not coverage

The percentage counts evaluations that carry cross-section covariance, which is
not the same as covariance landing where your run needs it. Read
`rate_fraction_covered_total` before any sigma; the tungsten case in
[Nuclear-data uncertainty](usage.md#nuclear-data-uncertainty) has all five
natural isotopes covered by the count and 6% of the production covered in fact.

Depth varies as much as presence. JENDL-5 carries covariance for only 13% of its
evaluations, and its Fe56 covers 56 channels against ENDF/B-VIII.1's 7.

Cross sections are the only covariance family that reaches the data. The ENDF
parser also reads angular-distribution and radionuclide-production covariance
(MF=34 and MF=40 against MF=33 for cross sections), and nothing consumes them, so
they cannot be propagated and are reported as not propagated.

### Energy range

Every library reaches past 20 MeV for at least some evaluations, and none is
uniform. Counting evaluations by the ceiling they were converted to:

| library | ceiling |
| --- | --- |
| `endf-b8.1` | 452 at 20 MeV, 34 at 150, 34 at 200, 28 at 30, rest at 28 to 65 |
| `jeff-4.0` | 491 at 200 MeV, 65 at 20, 16 at 150, 10 at 30, rest at 60 to 90 |
| `jendl-5.0` | 579 at 200 MeV, 216 at 20 |
| `fendl-3.2d` | 109 at 200 MeV, 72 at 150, 11 at 60 to 65, none at 20 |
| `tendl-2025` | 200 MeV throughout |
| `tendl-2017` | 200 MeV throughout |

So ENDF/B-VIII.1 is the only one that is mostly a 20 MeV library, and even its
Fe56 and W186 reach 150 MeV. A spectrum whose flux reaches above a nuclide's
ceiling is **refused before the collapse**, naming the nuclide and the energy
its evaluation stops at, because there is no cross section up there to fold
against and any answer would be an invention. So check the ceiling of the
nuclides that carry your reaction rather than the library's headline.

Groups above the ceiling that carry no flux cost nothing, which is what makes a
padded spectrum safe: the fold stops at the last tabulated point and contributes
zero above it, rather than carrying the last value forward to 1 GeV. Those are
different answers whenever the top groups are populated, and the second one is
wrong: a threshold reaction whose cross section is still rising at 20 MeV would
otherwise be priced at its 20 MeV value across two more decades.

### Some decay records are placeholders

A nuclide whose decay scheme nobody has evaluated still gets a decay file. The
conversions from the Nuclear Wallet Cards and from NUBASE carry a half-life and
the decay modes and, in place of measured average energies, book a third of each
beta or electron-capture branch's Q to the light particles, a third to the
photons and the last third to the neutrino. That is not a rough estimate:
electron capture hands most of Q to the neutrino, so for an EC emitter the
placeholder can be several times the recoverable energy. ENDF/B-VIII.1 books
Sn111 at 1.63 MeV per decay against the 0.69 MeV JENDL-5 evaluates from its
decay scheme.

| library | placeholder decay records |
| --- | ---: |
| `endf-b8.1` | 1144 |
| `jeff-4.0` | 1529 |
| `jendl-5.0` | 375 |

They are exotic nuclides, so most runs never touch one, but decay heat at short
cooling times is carried by exactly the short-lived products that tend to be
unevaluated: on the FNS tin, cadmium, palladium and nickel foils these records
carry 12 to 35% of the heat in the first minutes. The converter labels them
rather than hiding them, and can substitute another library's evaluation for
them; see
[Filling placeholder decay energies](usage.md#filling-placeholder-decay-energies).

### Temperatures and size

All six are converted at the same six temperatures, 250, 293.6, 600, 900, 1200
and 2500 K, so a library swap never changes which temperature is available.

Size is per nuclide rather than per library, because only the nuclides in your
material are fetched. Fe56 is 65 MB on `endf-b8.1` and 25 MB on `tendl-2025`;
U235 is 199 MB and 63 MB. The chains are small by comparison, 3.4 MB for a TENDL
network against 21 MB for JENDL-5's complete one.

### TENDL chains are not standalone

`TransmutationChain` cannot open a TENDL chain on its own, because it has no
`decay` subsection and the loader wants a complete one. Set the subsections
individually instead, which is the arrangement the tables above describe:

<!-- doctest: skip -->
```python
yani.transmutation_reactions = "tendl-2025"
yani.transmutation_branch_ratios = "tendl-2025"
yani.transmutation_decay_data = "endf-b8.1"
yani.transmutation_fission_yields = "endf-b8.1"
```
