# Why YANI

Four things, in order of how often they decide the question: it has to be
easy to run, the numbers have to be right, it has to be fast enough to use in
a loop, and it has to bend to the problem you actually have rather than the
one a tool author imagined.

## Easy

**`pip install yani`, on Linux, macOS or Windows.** The wheel carries the
compiled solver. There is no compiler to invoke, no transport stack to build
first, and no system package to hunt down.

**Nuclear data downloads on demand.** Point a setting at a library keyword and
the sections your calculation actually needs are fetched and cached on first
use, not a whole evaluation up front. See
[Where the data comes from](usage.md#where-the-data-comes-from).

**The license stack is fully permissive.** YANI itself is MIT. Nothing in the
dependency chain forces a copyleft license onto whatever you build with it, so
using it in a closed pipeline or a commercial tool is not a licensing
question, just an engineering one.

**A WASM build is on the roadmap.** The solver is Rust, which compiles to
`wasm32` cleanly, so running a calculation entirely client-side, with a
try-it-now demo in the browser, is planned rather than requiring a server. Not
live yet.

**A citable material library ships in the wheel.** The PNNL Compendium
(PNNL-15870 Rev. 2), 410 named materials with their compositions and
densities, is bundled rather than a separate download, so a standard
shielding or structural material is `yani.materials.pnnl.material(key="Steel,
Stainless 316", volume=...)` away instead of a retyping exercise from someone
else's PDF. See [Materials](usage.md#materials).

## Accurate

**Continuous-energy cross sections, not a multigroup collapse.** A multigroup
library has already averaged the cross section over each group using someone
else's assumed spectrum shape, and resonance structure inside a group is gone
before you ever see it. YANI folds your actual spectrum against the pointwise
cross section directly, at the energy resolution the evaluation was measured
at, so the only averaging is the one your own spectrum implies. This matters
most exactly where it is usually skipped: narrow resonances that a coarse
group structure smears across a bin.

**An uncertainty on the answer, not just the answer.** Pass
`data_uncertainty=` and every nuclide density comes back with a standard
deviation beside it. The activation cross sections are resampled from the
evaluation's own ENDF MF=33 covariance, folded against your spectrum, and the
schedule is re-solved for each sample. That is exact to all orders in the
matrix exponential: nothing is linearized, and the sandwich rule is not used,
so correlations between nuclides survive. A parent and its daughter come back
with the same absolute uncertainty, because every daughter atom came out of a
parent atom. If your spectrum arrives from a Monte Carlo run with a per-bin
error, that propagates too, and separately, so you can see which of the two
dominates.

**A sigma of zero says which kind of zero it is.** The hard part of an
uncertainty is not producing one, it is knowing what it left out. A nuclide
whose evaluation publishes no covariance and a nuclide whose covariance is
genuinely small would otherwise both report `0.0`, and only one of those is
reassuring. `data_uncertainty_info` keeps them apart: which nuclides were
perturbed, which have no published covariance, what share of each reaction rate
the covariance grid actually spans, which evaluated matrices were not positive
semi-definite and had to be repaired, and which sources are not propagated at
all. On ENDF/B-VIII.1 that last point is not academic -- 42% of evaluations
carry MF=33, against 100% of TENDL-2025 -- so the same run on two libraries
gives two very different sigmas, and the report is what tells you why.

**Gamma lines, not a binned photon response.** `decay_photon_spectrum()`
returns discrete energy/intensity pairs, not a spectrum pre-collapsed onto a
group structure. A binned response answers "how much energy in this
window"; lines answer "which nuclide is that", which is what you need for
identifying an isotope from an emitted spectrum or feeding a photon transport
run without inheriting someone else's binning choice.

**Isomeric branching is tracked, not folded into the ground state, and it is
flux-weighted rather than a fixed number.** A reaction that leaves a fraction
of its product in a metastable state is modeled as a branch to that state,
with its own half-life and its own decay chain, rather than lumped into the
ground-state inventory. The branching fraction itself is stored as a curve
against incident energy, not a single evaluation-average ratio, and is folded
against your actual spectrum at rate-compute time, so two calculations with
different spectra but the same target nuclide can legitimately get different
branching fractions, because they should. `Ag110_m1` dominating the activity
of a silver foil for years after `Ag110` itself has decayed away, as in the
[getting started](getting_started.md) example, is the kind of result that
disappears if branching is not tracked.

**Verification and validation runs against every open benchmark we have
found**, [CoNDERC][conderc] among them. The rest is a todo, honestly labeled:
if you know of an open, reproducible benchmark this list is missing, tell us
and we will add a reproducible V&V script for it.

[conderc]: https://nds.iaea.org/conderc/

## Fast

**No transport solve stands between your spectrum and an answer.** Point a
`Material` at whatever spectrum you already have and call `transmute()`; there
is no geometry to build and no particle transport run to get through first.
YANI folds continuous-energy cross sections against your spectrum directly,
as one function call.

**Parsed nuclear data stays loaded in RAM, not reloaded from disk.** Cross
section libraries and transmutation chains are parsed once per source, a
library keyword or a file path, into a process-wide cache keyed on exactly
that, and reused from then on. Looping over many materials, spectra or
schedule variants in one script pays the parse cost once, not once per
`transmute()` call, and a later call that needs a wider slice of the same
source (say, more reactions) tops the cache up rather than re-parsing it from
scratch. Downloads are cached separately, to disk under `~/.cache/yamc`, so a
second run of the script does not refetch either, but the in-memory cache is
what saves a second call in the same process from touching disk at all.

**The chain that gets built is exactly the one your material can reach, no
manual depth setting required.** Rather than truncating the transmutation
network at a fixed number of reaction or decay steps from the starting
nuclides, a value that silently drops real nuclides if set too low and loads
data no calculation needs if set too high, YANI computes a provable upper
bound on the density every candidate nuclide could reach given the actual
irradiation time and rates, and only loads and solves for the ones that can
clear a floor. Nothing that could matter is dropped, and nothing that
provably can't is loaded.

**Nuclear data is a binary columnar format, not text to parse.** Cross
sections and transmutation chains are stored as Arrow, so loading them is
reading typed columns straight into memory rather than parsing fixed-width
text records the way an ENDF tape has to be. Converting from ENDF or ACE is a
one-time step; every calculation after that reads the fast format.

## Flexible

**The same solver targets native and the browser.** The Rust core builds for
`wasm32` as a first-class target, not a native tool with a JS wrapper bolted
on afterward, so the identical solver behind `pip install yani` can also run
client-side with no backend to stand up. Where a calculation runs is a
deployment choice, not a rewrite.

**Four independently sourced transmutation subsections, mixed at will.**
`transmutation_reactions`, `transmutation_decay_data`,
`transmutation_fission_yields` and `transmutation_branch_ratios` are each
their own setting, so a network can mix libraries by subsection instead of
committing to one library for everything. A TENDL reactions network borrowing
decay data and fission yields from ENDF/B-VIII.1, the usual arrangement since
TENDL publishes neither, is a first-class configuration, not a data file
hack. See [Nuclear data settings](usage.md#nuclear-data-settings).

**A schedule can mix spectra, not just magnitudes.** Every `Pulse` carries its
own `source`, so a campaign whose neutron spectrum changes shape between
phases, not just intensity, is expressed directly instead of approximated
with one averaged spectrum. A fusion reactor's operating life is the obvious
case: DD-phase pulses and DT-phase pulses each get their own spectrum in the
same `PulseSchedule`, back to back, and the network sees the real spectrum
shape for each phase. See [Schedules](usage.md#schedules).

**Any spectrum group structure works**, not just a preset list. A `Histogram`
takes whatever ascending list of energy boundaries your spectrum happens to
use, of whatever length, and named structures like `CCFE-709` are a
convenience for a handful of common cases, never a requirement. See
[Named group structures](usage.md#named-group-structures).

**Local ENDF files, local Arrow files and premade Arrow files, in any
combination.** Convert your own ENDF evaluations, point settings at your own
converted directories, or use a downloaded keyword, and mix all three within
one calculation: `cross_section_data` alone can be set per-nuclide, so one
network can pull cross sections from a local file for the isotope you care
about and from a downloaded library for everything else. See
[Making your own data](usage.md#making-your-own-data) and
[Nuclear data settings](usage.md#nuclear-data-settings).
