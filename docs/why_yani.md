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
[Where the data comes from](getting_started.md#where-the-data-comes-from).

**The license stack is fully permissive.** YANI itself is MIT. Nothing in the
dependency chain forces a copyleft license onto whatever you build with it, so
using it in a closed pipeline or a commercial tool is not a licensing
question, just an engineering one.

**A WASM build is on the roadmap.** The solver is Rust, which compiles to
`wasm32` cleanly, so running a calculation entirely client-side, with a
try-it-now demo in the browser, is planned rather than requiring a server. Not
live yet.

## Accurate

**Continuous-energy cross sections, not a multigroup collapse.** A multigroup
library has already averaged the cross section over each group using someone
else's assumed spectrum shape, and resonance structure inside a group is gone
before you ever see it. YANI folds your actual spectrum against the pointwise
cross section directly, at the energy resolution the evaluation was measured
at, so the only averaging is the one your own spectrum implies. This matters
most exactly where it is usually skipped: narrow resonances that a coarse
group structure smears across a bin.

**Gamma lines, not a binned photon response.** `decay_photon_spectrum()`
returns discrete energy/intensity pairs, not a spectrum pre-collapsed onto a
group structure. A binned response answers "how much energy in this
window"; lines answer "which nuclide is that", which is what you need for
identifying an isotope from an emitted spectrum or feeding a photon transport
run without inheriting someone else's binning choice.

**Isomeric branching is tracked, not folded into the ground state.** A
reaction that leaves a fraction of its product in a metastable state is
modeled as a branch to that state, with its own half-life and its own decay
chain, rather than lumped into the ground-state inventory. `Ag110_m1`
dominating the activity of a silver foil for years after `Ag110` itself has
decayed away, as in the [getting started](getting_started.md) example, is the
kind of result that disappears if branching is not tracked.

**Verification and validation runs against every open benchmark we have
found**, CONDERC among them. The rest is a todo, honestly labeled: if you know
of an open, reproducible benchmark this list is missing, tell us and we will
add a reproducible V&V script for it.

## Fast

**No transport solve stands between your spectrum and an answer.** Point a
`Material` at whatever spectrum you already have and call `transmute()`; there
is no geometry to build and no particle transport run to get through first.
Contrast this with a coupled depletion operator that needs a transport model
to produce reaction rates, or a transport-independent one that still needs
multigroup microscopic cross sections from somewhere, typically a separate
transport run of its own. YANI folds continuous-energy cross sections against
your spectrum directly, in-process.

**Parsed nuclear data stays loaded for the life of the process.** Cross
section libraries and transmutation chains are parsed once per source, a
library keyword or a file path, into a process-wide cache keyed on exactly
that, and reused from then on. Looping over many materials, spectra or
schedule variants in one script pays the parse cost once, not once per
`transmute()` call, and a later call that needs a wider slice of the same
source (say, more reactions) tops the cache up rather than re-parsing it from
scratch. Downloads are cached the same way, to disk under `~/.cache/yamc`, so
a second run of the script does not refetch either.

## Flexible

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
