# Method

What YANI actually computes, in the order it computes it. The
[overview](index.md) states the equation; this page is the rest of it. Every
choice here has a reason, and where a cheaper option was measured and rejected
that is recorded rather than quietly omitted.

## The solve

One timestep is a matrix exponential, $\mathbf{N}(t) = e^{At}\mathbf{N}(0)$,
evaluated by CRAM at order 48 following [Pusa 2010][pusa2010] and
[Pusa 2015][pusa2015], in the incomplete partial fraction form.

Two consequences worth knowing:

**A step is exact at any length, for a fixed spectrum.** $A$ is built from decay
constants and $\sigma\phi$ rates and does not depend on the composition, so it
is constant over a step and the exponential is solved exactly. One year in a
single step and one year in 365 agree to round-off. Shortening steps to chase
accuracy buys nothing.

**What a long step does miss is the spectrum changing as the composition does**,
which `transmute()` cannot see, because the flux is your input rather than
something it solves for. If the field would harden or soften appreciably over a
campaign, split the schedule and give each pulse its own `source`. That is a
statement about the physics being fed in, not about the solver.

The 24 poles are not independent. The incomplete partial fraction form is a
sequential recurrence, so they cannot be evaluated in parallel, and the sparse
LU is run single-threaded on purpose: partitioning by thread count changes the
order of the floating point additions and therefore the last bits of the answer.
The symbolic factorization is reused across the poles, which is where the
structure does pay.

## Building the matrix

The exponential is published coefficients. The work is in the coefficients of
$A$, which come from two places.

**The transmutation network** supplies decay constants, decay branching,
reaction products and fission yields. Which library supplies which of those is
four independent settings, so a network can mix sources by subsection. See
[Nuclear data settings](usage.md#nuclear-data-settings).

**The collapse** supplies each $\sigma\phi$, by folding your spectrum against
the pointwise cross section:

$$
\sigma_{\text{eff}} = \frac{\sum_g \sigma_g \phi_g}{\sum_g \phi_g},
\qquad
R = 10^{-24}\,\sigma_{\text{eff}} \sum_g \phi_g = 10^{-24} \int \sigma(E)\,\psi(E)\,\mathrm{d}E
$$

with $\psi$ the piecewise-constant flux density implied by your group fluxes.
The total flux cancels, so the rate is an integral of the cross section against
your spectrum and nothing else. The cross section is read at the energy
resolution of the evaluation, so the only averaging is the one your own spectrum
implies.

### Which nuclides get loaded

Rather than truncating the network at a fixed number of reaction or decay steps,
which silently drops real nuclides when set too low and loads data nothing needs
when set too high, YANI computes an upper bound on the density every candidate
nuclide could reach given the actual irradiation time and rates, and keeps the
ones that can clear a floor.

The bound is taken over the whole reachable closure in one pass rather than
grown outward in rounds. Zeroing an unloaded nuclide's edges does not give a
bound, because a node fed by enough individually sub-floor parents clears the
floor while the zeroed edges hide it. Growing the set in rounds and finishing
with a ceiling sweep is sound but pointless: measured on the ENDF/B-VIII.1 chain
from Fe56, the sweep terminates only once 1059 of 1060 nodes are loaded, and
returns exactly what rating the closure outright returns in one pass instead of
thirteen.

## Isomeric branching

A reaction leaving part of its product in a metastable state is modelled as a
branch to that state, with its own half-life and its own decay chain, rather
than lumped into the ground state. The branching fraction is held as a curve
against incident energy and folded against your spectrum at rate-compute time,
so two runs with different spectra on the same target can legitimately get
different branching fractions. `get_isomeric_branching()` reports the split each
step was solved with. See
[Weighted, from a solve](usage.md#weighted-from-a-solve).

## Self-shielding

The collapse above treats your spectrum as the flux *inside* the material. What
you usually have is the flux in the surrounding field, and inside a lump the two
differ wherever the total cross section is large: the flux is depressed across a
resonance, so the true rate is below what the unshielded fold reports.

What is corrected is the shape of the flux *within* each group. The group totals
you supplied are preserved exactly, because they are your measurement or your
transport result and this has no business rescaling them. So the correction is a
per-group, per-reaction weighting, and a nuclide with no resonances in a group
comes back with the number it had before.

**The escape term is given, never guessed.** Both the flux depression and the
escape probability need to know how easily a neutron leaves the lump, which is
geometry, and a `Material` has none. So you give a shape or a mean chord
$4V/S$, and no shape is ever inferred. Absent means no shielding at all, and a
result bit-identical to a run without the module.

**One method is offered.** The flux inside the lump solves

$$
\left(\Sigma_t(u) + \Sigma_e\right)\phi(u) =
\int_{u-\Delta u}^{u} \Sigma_s(u')\,\phi(u')\,\frac{e^{-(u-u')}}{1-\alpha}\,\mathrm{d}u' + \Sigma_e
$$

marched down in lethargy, so the in-scattering source is whatever the flux above
it actually was. It assumes nothing about resonances being narrow.

The cheaper narrow-resonance approximation, which takes that source at its
asymptotic $1/E$ form, was implemented, measured, and deliberately not shipped.
It over-shields anything carrying strong *elastic* resonances, whose real
in-scattering fills the capture dips an asymptotic source leaves empty: on a
$1/E$ field at 50 µm it is 41% low on Co59, 63% low on W186 and 16% low on Mn55,
while agreeing inside 1% on Rh103, Fe56, Eu151 and Nb93. A measurement settles
it rather than the comparison alone. W186(n,γ) in FNG-tung is 1.29 b, where this
solve gives C/E 0.80 and narrow resonance gives 0.46, twice as far from the
measurement as applying no correction at all. Whether a given run sits in the
safe case depends on its field and composition, which is not something a caller
can state up front, so the option is not offered. See
[Self-shielding](usage.md#self-shielding).

## Nuclear-data uncertainty

The solve is deterministic and every entry of its matrix is a rate, so the
uncertainty is propagated by perturbing what those rates are made of and running
the same solve again. That is exact to all orders in the matrix exponential:
nothing is linearised, the sandwich rule is not used, and the solver is not
touched at all, only its input.

### Folding the covariance

A reaction rate is linear in the cross section, and MF=33 states a covariance
that is constant on each cell of the evaluation's own energy grid. Together
those give

$$
\operatorname{Cov}(R_i, R_j) = \sum_{k,l} C_{ij}[k,l]\; r_i[k]\; r_j[l]
$$

where $r_i[k]$ is reaction $i$'s rate restricted to covariance interval $k$.
That is exact, and it never projects the covariance onto your group structure:
the integration grid *is* the covariance grid. Each block folds on its own grid
and the contributions add, because the sum over blocks is outside the
contraction.

One layout is the exception. An LB=8 block is a short-range variance, stated in
barns squared rather than relative to the cross section, and ENDF-102 section
33.2.2.2 says that the average over an interval $\Delta E_j$ inside its
interval $\Delta E_k$ has variance $F_k\,\Delta E_k/\Delta E_j$, uncorrelated
with any other such interval. What it contributes to a rate therefore depends
on how the flux varies inside $\Delta E_k$, which is the one place your flux
groups enter. The fold cuts $\Delta E_k$ at the group boundaries, where the
flux density $\psi$ is constant, so the rule applies exactly to every piece and
the rate's variance is $F_k\,\Delta E_k \sum_j \psi_j^2\,\Delta E_j$. A flux
flat over the whole interval gives the plain absolute diagonal, and is the
smallest this term can be for a given flux in the interval. The more the flux
is concentrated inside an LB=8 interval, the larger the term, as the evaluation
says it should be: ENDF/B-VIII.1 Cr52 (n,p) is 17.7% for a flux flat over the
tape's own [14, 16] MeV interval and 22.5% for a flux in a single 0.2 MeV group
at 14.1 MeV.

A covariance grid need not span the whole flux range. Rate coming from outside
it is rate the evaluation states no uncertainty for, so it enters the
denominator and not the numerator, and the relative uncertainty comes out
smaller than the covariance grid alone would suggest. That is the honest answer
rather than a bug, but it is also invisible, which is why
`rate_fraction_covered` records the share of each rate that carries a stated
uncertainty: the dilute rate from energies where the reaction's own diagonal
variance is nonzero, over the dilute rate across the flux range. Relative and
absolute blocks both count, each summed over the reaction's own blocks of that
scale. An interval a grid spans with a variance of zero counts as uncovered,
since it states no uncertainty either. Both integrals use the dilute cross
section, so on a self-shielded or tallied rate the share is not the covered
share of that rate, which is not computed, and the production-weighted
`rate_fraction_covered_total` is reported as `None` on such a run.

The implementation departs from this in places, all tracked in
[#166][core166] and not fixed yet:

- The ENDF parser splits an LB=0 to 4 block's energy table in the wrong place,
  so the upper part of its grid is dropped: 773 ENDF/B-VIII.1 blocks are
  affected, and at 14 MeV Ni58 `(n,a)` reads 0.0% where the evaluation gives
  19.8%, and Cr52 `(n,p)` 0.4% against 17.1%. The LB=4 expansion also swaps its
  two tables, which affects one block, FENDL-3.2d Ni58 `(n,p)`.
- The LB=8 short-range fold described above is not in the code yet. An LB=8
  block is read as a relative variance on its own grid, like an LB=1 block.
- With a shape or a chord, the fold divides dilute partial rates by the
  shielded rate, which overstates the sigma of a shielded resonance channel:
  4.61% against 1.70% with shielded partials, for Au197 capture in a 0.1 mm
  foil under $1/E$. On a yamc transport run the partials are folded dilute
  against a tallied rate that is shielded within each tally bin, so the same
  mismatch applies wherever a bin shields strongly.
- A block whose `MAT1` names the evaluation's own MAT is dropped as if it
  correlated with another evaluation. That is 585 of the 598 such blocks in
  FENDL-3.2d, and it loses correlations between channels, not variances.

### Drawing a replica

For the cross sections, one replica is

$$
L = V\sqrt{\Lambda}, \qquad z \sim N(0, I), \qquad \delta = Lz
$$

from the eigendecomposition of the *relative* covariance. Each $\delta_i$ is
normal with standard deviation $\sigma_i = \sqrt{\sum_j L_{ij}^2}$ and carries
channel $i$'s correlations with the others. It moves the rate through the
lognormal marginal matched to it in mean and variance:

$$
s_i^2 = \ln\left(1 + \sigma_i^2\right), \qquad
R_i' = R_i \exp\left(s_i\,\frac{\delta_i}{\sigma_i} - \frac{s_i^2}{2}\right)
$$

so the mean of $R_i'$ is $R_i$ and its variance is $\sigma_i^2 R_i^2$, both
exactly, and no sampled rate can be negative. The linear form
$R_i(1 + \delta_i)$ can, and did: on the FNS decay-heat benchmark it sent 8.3%
of all sampled rates below zero, 13% on iron, and flooring them at zero biases
the mean upward. For a small $\sigma_i$ the two differ only at order
$\sigma_i^2$, so a well known cross section samples almost exactly as it would
under the linear form, and only the channels a Gaussian cannot describe move.
What the transform does not keep exactly is the linear correlation between
channels: the deviates keep their Gaussian dependence and each is transformed
monotonically, so rank correlation is preserved exactly and the Pearson
correlation shifts by a factor that goes to one as $\sigma$ goes to zero.

The evaluation states a covariance and no distribution, so the lognormal shape
is a choice, and for a channel whose sigma is near 1 or above it is that choice,
not the data, that sets the tails. Such a channel is heavy-tailed enough that
its sampled spread converges slowly: at 1024 replicas, the most the driver adds
on its own, the median sample standard deviation is 0.98 of sigma at
$\sigma = 1$, 0.92 at 2, 0.83 at 3 and 0.50 at 9. TENDL-2017 has channels at
$10^4$% and more, and the report names every sampled channel of a populated
nuclide whose evaluated relative sigma is at least 1 or at least 10 in
`sigma_at_least_one` and `sigma_at_least_ten`. The channels at 1 or more of
nuclides outside the populated bound described below are named in
`sigma_at_least_one_outside_bound`, since a draw on exactly such a channel can
sit orders above nominal and populate the nuclide.

The eigendecomposition is a cyclic Jacobi rotation rather than a library call:
the matrices are one per nuclide over that nuclide's activation channels, single
digits to low tens on a side, where Jacobi is fast, needs no dependency, is
bit-reproducible because it is pure arithmetic in a fixed order, and gives the
eigenvectors the clipping needs anyway. A Cholesky would be the obvious choice
if the matrices were positive definite, and the point is that they are not:
MF=33 matrices are frequently not PSD as evaluated, so negative eigenvalues are
clipped to zero. That repair only ever adds variance, and it can give a spread
to a channel whose evaluated variance is zero. A matrix counts as repaired
when its correlation matrix $R = D^{-1/2} C D^{-1/2}$, over the channels with a
positive stated variance, has an eigenvalue below $-n \cdot 10^{-12}$, $n$ the
number of those channels, or when a channel is stated with a negative variance,
or with a zero one and a covariance to another channel. $R$ is congruent to
that block of $C$, so one is PSD exactly when the other is, and on $R$ the
round-off of the decomposition is about $n$ times machine epsilon whatever the
spread of the channels, so a PSD matrix whose smallest eigenvalue comes back a
few ulps below zero is not a repair. The test is not on $\lambda_\text{min}$
of $C$ against its $\lambda_\text{max}$ because TENDL-2017 has channels at a
relative sigma up to $5.6 \times 10^8$, a variance near $3 \times 10^{17}$,
and one of those beside ordinary channels would set a whole-matrix threshold
far above a real repair among them. `covariance_repaired` lists the distinct
nuclides with a repaired channel a draw can move (a positive rate on a spectrum
the schedule irradiates with), and any makes `has_gaps` true. The report covers
the nuclides the material can populate: the fold takes every chain nuclide with
data, which from almost any composition is the chain's whole closure, so a
nuclide is reported only when an upper bound on its density over the schedule,
at nominal rates, reaches the solver's floor of $10^{-30}$ atoms/b-cm. One the
bound leaves out cannot move any nominal density by as much as that floor, but
a replica's rates on a wide channel can sit orders above nominal, so repaired
nuclides outside the bound with a channel a draw can move are named in
`covariance_repaired_outside_bound`, and any of those makes `has_gaps` true as
well, since the bound says nothing about a replica. `covariance_repairs`
records, per repaired populated nuclide and spectrum, $\lambda_\text{min}$,
$\lambda_\text{max}$, the variance added over the stated trace, and each
channel's evaluated variance (kept as stated, even when negative) beside the
sigma it is sampled at. Clipping can only widen a channel, and a small
$|\lambda_\text{min}| / \lambda_\text{max}$ does not mean a small widening of
the channel that matters, so the headline is the sigmas themselves:
`worst_sigma_inflation` is the largest sampled over evaluated sigma, minus one,
over the repaired channels a draw can move, and `rate_weighted_sigma_inflation`
is the weighted mean of each channel's own sampled over evaluated sigma, minus
one, each channel weighted by its rate at unit flux, its spectrum's fluence in
the schedule and its parent's initial density. Weighting the inflation rather
than the sigma keeps a wide channel with a small rate from drowning out a
repair on the channels that carry the reactions, and the initial density makes
it a first-generation measure: a produced nuclide carries no weight, and its
repairs show in the other two. The sampled sigma is read off the
factorization for every matrix, so a matrix below the repair threshold shows
its round-off there as it is.

The other sources are drawn on their own stated sigma. The flux is drawn once
per replica, per group, from the pulse's `flux_std_dev` or through the factor of
its `flux_covariance`, and shared by every rate collapsed against that spectrum,
because every reaction that sees a group sees the same flux in it. A rate is
linear in the flux, so the perturbed rate is the collapse's own per-group terms
reweighted, exactly, with nothing collapsed again. A half-life is drawn per
nuclide from the decay data's sigma on it, and a decay energy from the sigma on
each beta, gamma and alpha component that states one, or on the total when no
component states a sigma. In a transport run the tallied rates are drawn jointly
from their per-history covariance.

The decay data states a sigma on each value and no distribution or correlation,
so the normal shape, and the independence between a nuclide's decay-energy
components and between different nuclides' half-lives, are choices. These draws
are normal, with a floor where a draw would leave the physical range. A flux bin
or a tallied rate below zero is set to zero and counted in `flux_bins_floored`
or `statistical_floored`. A half-life at or below zero is set to a millionth of
its nominal value and counted in `half_lives_floored`. A decay energy below zero
is set to zero and not counted. A floor biases that source's mean upward, as it
did for the linear cross-section form, so a nonzero count says the normal is
being used past where it describes the data.

Seeds are pure functions of their arguments. A cross-section, half-life or
decay-energy draw depends on `(seed, replica, nuclide)` and on nothing else: not
on how many replicas were run, not on the order they ran in, and not on which
other nuclides were in the material. The flux draw is keyed on
`(seed, replica, spectrum)`, the spectrum's place among the schedule's spectra.
The statistical draw is keyed on `(seed, replica)` and made jointly over the
material's tallied rates, so adding or removing a tallied rate changes the draws
of the others. A seed reproduces a given run in every case.

### Derived quantities

Activity, decay heat, contact dose and every photon line are evaluated once per
replica, with that replica's own half-lives, and the spread taken over the
results, rather than combined from per-nuclide sigmas.

Quadrature would be wrong: every Mn56 atom in an irradiated iron foil came out
of an Fe56 atom, so the two densities move against each other and their spreads
partly cancel, and adding in quadrature double-counts a variance that is not
there. Evaluating once from the mean inventory would also be wrong: activity and
decay heat are linear in $N$, so that gives the right mean and a spread of
exactly zero, which reads as a confident result rather than a missing one. And
contact dose is not linear in the densities at all, since a replica that makes
more of an emitter also absorbs more of it.

The half-lives have to be the replica's here as well as in the solve. A
saturated activity is $\lambda N = R$, so it barely depends on its own
half-life, and evaluating it with the nominal $\lambda$ would hand it the whole
spread of $N = R / \lambda$ instead. A line's intensity per atom is its emission
per decay times $\lambda$, so it is rescaled with the replica's $\lambda$ for the
same reason, which keeps the emission per decay at its evaluated value. Decay
energies enter only here: they are drawn where decay heat is evaluated and move
nothing else.

### What is not propagated

Five sources are propagated: the activation cross sections, the flux spectrum
(on `Material.transmute`), the half-lives, the decay energies, and the tallies'
statistical error (on a transport run). Everything below is held at its
evaluated or nominal value in every replica. Most of these carry an uncertainty
or a model error of their own that is then missing from the sigma, so holding
them understates it, and for some results it is the largest term. Two can go
either way, because holding them also removes a feedback that narrows the
spread: self-shielding, and the flux's response to the cross sections of a
material that shapes its own flux. Their bullets say which way each goes, and
where. The covariance blocks that are skipped because they state only a
correlation (the `MAT1 != 0` blocks, and the same-MAT blocks read as
cross-material) can also go either way: dropping a covariance term lowers the
variance of a sum when the term is positive and raises it when it is negative.

- **Decay branching ratios and fission yields.** Both have published
  uncertainties, per decay mode and per yield, that are not propagated yet. The
  weights that mix a nuclide's yield sets by incident energy come from the
  nominal spectrum in every replica, so a flux draw does not move them.
- **Isomeric branching.** The split of a reaction's product between the ground
  state and an isomer. The split comes from MF=9 or MF=10 (the name
  `not_perturbed` gives it), and where an evaluation states its uncertainty it
  does so in MF=40, which is parsed and not used yet. With the branching overlay
  configured (`transmutation_branch_ratios`), the flux-weighted split is folded
  once against the nominal spectrum, so on `Material.transmute` a flux draw
  moves the rates and never the split. The `(n,n')` channels the overlay adds to
  reach a metastable state, In115 to In115m among them, have no group-averaged
  cross section behind them. They carry no cross-section covariance, and on
  `Material.transmute` no flux-spectrum uncertainty either.
- **Resonance-parameter covariance (MF=32).** ENDF-6 gives the cross-section
  covariance in the resonance range as an MF=32 part plus the MF=33 part, and
  many evaluations keep the whole resonance-range uncertainty in MF=32 and leave
  MF=33 at zero there. The ENDF parser reads MF=32, and the fold does not use it
  yet: it folds MF=33 only, so a capture rate driven by resonance flux can come
  back with a sigma near zero: for capture in a $1/E$ field, NJOY ERRORR gives
  ENDF/B-VIII.1 W186 1.53% with MF=32 and 0.00% from MF=33 alone. The coverage
  report shows it: W186's capture block states zero variance from $10^{-5}$ eV
  to 10 keV, where nearly all of a capture rate is, so on the FNS spectrum its
  `rate_fraction_covered` reads about 0.07. W186 is still listed under
  `perturbed`, since the block's other intervals are used ([#166][core166]). The
  same check gives 6.32% against 0.01% on the JEFF-4.0 Ag109 tape and 4.71%
  against 0.00% on the TENDL-2025 Co59 tape. yani's TENDL-2025 covariance is not
  published yet, so a run on it today lists Co59 under `no_covariance_data`
  instead.
- **MF=33 blocks that are not used.** Blocks with `MAT1 != 0`, which state
  covariance with another evaluation (the links to the standards among them)
  and today also include blocks naming the evaluation's own MAT; blocks stated
  through other reactions' covariances (NC); lumped reactions (MT=851 to 870),
  which state the uncertainty of a sum of reactions; and blocks stated on
  partial levels (MT=600 to 849 and 875 to 891) where the chain drives the
  total. `skipped_cross_material` and `skipped_nc` count the first two, blocks
  on reactions the chain does not drive among them, summed over the material's
  spectra, and both set `has_gaps`. The lumps and the partial levels are not
  counted, and the rates they would cover count as uncovered in
  `rate_fraction_covered_total`. A nuclide whose blocks are all of these kinds,
  or all on reactions the chain does not drive, has no usable block and is
  listed under `no_covariance_data`, which sets `has_gaps`.
  Tungsten's `(n,2n)` is lumped: ENDF/B-VIII.1, JEFF-4.0 and FENDL-3.2d state it
  only together with `(n,2np)`. JEFF-4.0 Be9 states its `(n,2n)` only on the
  levels MT=875 to 890, and ENDF/B-VIII.1 Ca40 its `(n,p)` and `(n,a)` only on
  MT=600 and 800, so Ca40 is listed under `perturbed` through its capture alone
  ([#166][core166]).
- **Self-shielding.** With a shape or a chord, every replica uses the flux
  depression solved from the evaluated cross sections, and holding it drops two
  terms that pull opposite ways. A larger capture cross section would deepen its
  own dip, a feedback that narrows the spread, and it does not. The elastic and
  total covariance never reaches the correction either, a term that widens the
  spread where MF=33 states a resonance-range uncertainty for elastic
  scattering. Which wins depends on the evaluation. For a 0.1 mm Au197 foil
  under $1/E$ on VITAMIN-J-175, ENDF/B-VIII.1 states no resonance-range elastic
  uncertainty, and the held sigma is too large by 1.8x (1.70% held against 0.96%
  with the feedback). TENDL-2017 states one, and there the held sigma is too
  small: 5.34% held against 6.07% with the feedback and the elastic term
  together (2.23% with the feedback alone). These figures fold the shielded
  partials correctly, and the fold defect above overstates on top of them
  ([#167][core167]).
- **The flux's response to the cross sections.** In yamc's
  `Model.simulate_transmutation`, a replica's cross sections rescale the tallied
  rates and leave the tallied flux as it was. For a trace activation product
  that is exact to first order in its own cross section. A material that shapes
  its own flux is not: a larger Li6(n,t) cross section in a breeder depresses
  the flux it sees, the same narrowing feedback as self-shielding, so holding
  the flux overstates that rate's sigma. The covariance is folded per nuclide,
  so the cross sections of the materials the neutrons passed through (a shield,
  a multiplier, a breeder) never move the flux on either path, and that missing
  term understates the sigma of a product behind many mean free paths of steel.
  On `Material.transmute` the spectrum's uncertainty is only what the pulse is
  given. The coupled method refuses `data_uncertainty` because its step-to-step
  tally noise is not propagated yet ([#162][core162]); it is also where the
  flux's response to a perturbed cross section would come in ([#166][core166]).
- **Decay photon line intensities.** Each line's emission per decay stays the
  evaluated one, so a line's band is the band on the activity of the nuclides
  emitting it. The decay data states a sigma on 99.6% of ENDF/B-VIII.1 gamma
  lines. On contact dose it is negligible for Co60 (0.014%) and not for Mn56
  (0.6 to 1.8%) or W187 (0.8 to 3.7%), the range running across ENDF/B-VIII.1,
  JEFF-4.0 and JENDL-5.0 and from independent lines to fully correlated ones
  ([#163][core163]).
- **Dose constants and build-up.** Contact dose uses the same photon attenuation
  coefficients, the same response (air energy absorption, or the ICRP-116
  coefficients for effective dose) and the same constant build-up factor in
  every replica. None of those tables publishes a per-value uncertainty, and the
  build-up factor is a model choice whose error is the larger term: the default
  of 2 reads 16 to 17% high for Co60 in steel against a photon transport
  calculation of the same half-space ([#164][core164]).
- **Material composition and natural abundances.** Element and impurity
  fractions, density and natural isotopic abundances are the same in every
  replica. For activation driven by a trace impurity this is often the largest
  omission: in a 316L-like steel with 0.1 wt% cobalt, the contact dose at 10
  years is 99.6% Co60 and moves 0.69% per 1% on the cobalt fraction. A material
  carries only the elements it is given, and the bundled PNNL compendium's
  `Steel, Stainless 316L` lists no cobalt, niobium, tantalum or silver
  ([#165][core165]).

`not_perturbed` in `get_data_uncertainty_info` names every input in this list
on every run: decay branching, fission yields, isomeric branching (MF=9/MF=10),
cross-material, NC and lumped MF=33 blocks, resonance-parameter covariance
(MF=32), decay photon line energies and intensities, the photon attenuation,
energy-absorption and fluence-to-dose coefficients, the contact-dose build-up
factor, and the material composition, density, natural abundances and atomic
masses. It adds an entry for each source a run switches off (half-life, decay
energy, activation cross section), the flux spectrum on `Material.transmute`
when that source is off or some or all spectra have no sigma, the tallied-rate
statistics when a transport run does not draw them, the self-shielding
correction when shielding is on, and the flux response to perturbed cross
sections on a transport run that perturbs the cross sections.

Some held inputs on this page have no entry of their own: MF=33 blocks on
partial levels (MT=600-849, 875-891), which the chain drives no rate for, so
they are neither listed nor counted; the overlay's `(n,n')` channels; the
isomeric split and fission-yield weights held at the nominal spectrum under a
flux draw; and, on `Material.transmute`, the flux's response to the cross
sections of the materials the neutrons passed through.

`has_gaps` looks only at the sources the run perturbs, and is True when one of
them met a nuclide with no usable MF=33 block, a skipped cross-material or NC
block, a block whose layout is unsupported or malformed, a channel whose
partial rates add up to more, or less, than its rate (`partials_above_rate`,
`partials_below_rate`), a covariance repaired past round-off on a channel a
draw can move (inside the populated bound or outside it), a spectrum with no
flux sigma, or a reachable unstable nuclide with no stated half-life sigma, or
with a decay energy but no stated sigma on it. Until the fold weights a
shielded rate with shielded partials ([#166][core166] item 4), a self-shielded
run lists most channels a relative block names under `partials_above_rate`, so
`has_gaps` is True on it. Of the inputs in this list, the skipped
cross-material and NC blocks set it, and the lumped and partial-level blocks
set it only through `no_covariance_data`, when they are all a nuclide has. A
sigma is the spread from the five sources above with everything in this list
held. See
[Nuclear-data uncertainty](usage.md#nuclear-data-uncertainty).

## Reproducibility

Three properties are enforced by tests rather than intended:

- **Thread count does not change the answer.** A 1-thread and a 7-thread run
  agree to the last bit, including the per-replica ensemble, the sigmas and the
  truncation counters.
- **A seed reproduces a run.** See the seeding rule above.
- **Optimisation does not change the answer.** Every performance change in the
  collapse is checked bit-identical against the previous implementation, by
  hex-float inventory comparison and by a golden of the per-group terms,
  one-group rates and fission-yield weights.

Nothing happens unless asked: with no `data_uncertainty`, no covariance is read
from disk, no matrix is folded or factorised, and the step loop runs once. The
means are bit-identical to a build without any of it.

[pusa2010]: https://doi.org/10.13182/NSE09-14
[pusa2015]: https://doi.org/10.13182/NSE15-26
[core162]: https://github.com/fusion-neutronics/core/issues/162
[core163]: https://github.com/fusion-neutronics/core/issues/163
[core164]: https://github.com/fusion-neutronics/core/issues/164
[core165]: https://github.com/fusion-neutronics/core/issues/165
[core166]: https://github.com/fusion-neutronics/core/issues/166
[core167]: https://github.com/fusion-neutronics/core/issues/167
