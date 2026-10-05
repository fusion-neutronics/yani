# Method

This page describes what YANI computes and in what order. The
[overview](index.md) gives the governing equation. Where a cheaper option was
tried and measured, the result is recorded here as well.

## Overview

A run has six stages:

1. **Network.** The transmutation chain gives each nuclide's decay modes,
   reaction products and fission yields. YANI finds the nuclides the material
   can populate over the schedule and loads only those
   ([Which nuclides get loaded](#which-nuclides-get-loaded)).
2. **Rates.** Each reaction rate per atom is the pointwise cross section folded
   against the spectrum ([The collapse](#the-collapse)), with an optional
   self-shielding correction ([Self-shielding](#self-shielding)). Fission
   yields and isomeric splits are weighted by the same spectrum.
3. **Matrix.** Decay constants and reaction rates are assembled into the sparse
   matrix $A$ ([Building the matrix](#building-the-matrix)).
4. **Solve.** Each step of the schedule is one matrix exponential
   ([The solve](#the-solve), [Schedules](#schedules)).
5. **Derived quantities.** Activity, decay heat, photon emission, contact dose
   and clearance indices are calculated from each step's inventory and the
   decay data
   ([Derived quantities](#derived-quantities)).
6. **Uncertainty.** If requested, stages 2 to 5 are repeated with perturbed
   inputs ([Nuclear-data uncertainty](#nuclear-data-uncertainty)).

## The solve

One timestep is a matrix exponential, $\mathbf{N}(t) = e^{At}\mathbf{N}(0)$,
evaluated by CRAM at order 48 following [Pusa 2010][pusa2010] and
[Pusa 2015][pusa2015], in the incomplete partial fraction form.

$A$ is built from decay constants and $\sigma\phi$ rates and does not depend on
the composition, so it is constant over a step and the exponential is solved
exactly. Step length therefore does not affect accuracy for a fixed spectrum:
one year in a single step and one year in 365 steps agree to round-off.

What a long step does not capture is a change in the spectrum caused by the
changing composition. `transmute()` takes the flux as an input and does not
solve for it. If the spectrum would harden or soften appreciably over a
campaign, split the schedule into several pulses, each with its own `source`.

The 24 poles are evaluated sequentially, because the incomplete partial fraction
form is a recurrence. The sparse LU runs single-threaded so that the order of
floating point additions, and therefore the result, does not depend on the
thread count. The symbolic factorization is computed once and reused for every
pole.

Most of a transmutation network is acyclic, since decay chains only run one
way. The linear solve at each pole is therefore done block by block over the
strongly connected components of the network, in topological order. Blocks
without a cycle are solved by substitution, and only blocks with a cycle (for
example a capture followed by a decay back to the parent) use the sparse LU.

After the exponential, two adjustments are made:

- A nuclide with no parent present in the step is set to its closed-form value
  $N_i(0)\,e^{A_{ii}t}$ instead of the CRAM value. Both describe the same
  equation, and the closed form is exact, so a stable nuclide that is only
  being burned does not accumulate round-off.
- Densities at or below $10^{-30}$ atoms/b-cm are dropped. This is the same
  floor used by the network bound described below.

## Building the matrix

The coefficients of $A$ come from two sources:

- **The transmutation network** gives decay constants, decay branching,
  reaction products and fission yields. Each of these can come from a different
  library through four independent settings. See
  [Nuclear data settings](usage.md#nuclear-data-settings).
- **The collapse** gives each $\sigma\phi$ (see [The collapse](#the-collapse)).

$A$ has one column per parent nuclide $j$:

- **Decay.** $\lambda_j = \ln 2 / T_{1/2}$ is added to the diagonal as a loss,
  and each decay mode adds $b\,\lambda_j$ to its daughter's row, where $b$ is
  the mode's branching ratio. Emitted light particles are also produced, so an
  alpha decay produces He4. A mode with no daughter in the chain, such as
  spontaneous fission, removes atoms without producing any.
- **Reactions.** Each reaction rate $R$ is added to the diagonal as a loss, and
  $b\,R$ is added to each product's row. The light ejectiles named by the
  reaction (H1, H2, H3, He3, He4) are also produced, so gas production is part
  of the inventory. A reaction whose product is the target itself cancels
  against its own loss term.
- **Fission.** The fission rate $R_f$ is a loss, and each fission product $p$
  gains $R_f\,Y(p)$, where $Y$ is the spectrum-weighted yield described in
  [Fission yields](#fission-yields).

Stable nuclides have no decay term and are removed only by reactions.

### The collapse

Each $\sigma\phi$ is the pointwise cross section folded against the spectrum:

$$
\sigma_{\text{eff}} = \frac{\sum_g \sigma_g \phi_g}{\sum_g \phi_g},
\qquad
R = 10^{-24}\,\sigma_{\text{eff}} \sum_g \phi_g = 10^{-24} \int \sigma(E)\,\psi(E)\,\mathrm{d}E
$$

where $\psi$ is the piecewise-constant flux density given by the group fluxes.
The total flux cancels, so the rate is the integral of the cross section over
the spectrum. The cross section is used at the energy resolution of the
evaluation, so the group structure of the spectrum is the only averaging
applied.

Each $\sigma_g$ is the integral of the cross section over the group divided by
the group width. The integral uses the trapezoid rule over the group edges and
every evaluated point inside the group. Cross sections are interpolated
linearly between points, so the trapezoid rule is exact.

At the ends of the evaluated energy range:

- Below the first energy, a threshold reaction is zero and any other reaction
  takes its first value.
- Above the last energy, the cross section is zero, while the group keeps its
  full width. This would make the rate too low, so a run raises an error if
  more than 0.1% of the flux lies above the top of a nuclide's evaluation. See
  [Energy range](libraries.md#energy-range).

Cross sections are taken at the material's temperature, which must be one of
the temperatures in the data. There is no interpolation between temperatures.
If the material has no temperature set, the first temperature in the data is
used.

Within each group the flux is assumed flat in energy. This assumption has an
error of its own. Compared with a pointwise reference for the FNS foil
reactions on VITAMIN-J-175, flat within-group flux gives a 3.7% mean error on
the hard FNS spectrum (21% with $1/E$ within each group). With a 10% $1/E$ tail
added to the spectrum, the error is 28% for flat and 3.2% for $1/E$. Since
neither shape is better in both cases, YANI uses the flat shape. Finer groups
reduce this error for both shapes.

### Fission yields

Fission yields are tabulated at a few incident energies, typically thermal,
500 keV and 14 MeV, and the yield depends on the energy of the neutron causing
the fission. YANI uses the independent yields (MT=454) and combines the
tabulated sets as

$$
Y(p) = \sum_k c_k\,Y_k(p), \qquad
c_k \propto \int \sigma_f(E)\,\psi(E)\,h_k(E)\,\mathrm{d}E
$$

where $h_k$ is a hat function equal to 1 at the $k$-th tabulated energy and
falling linearly to 0 at the neighbouring tabulated energies, held constant
beyond the first and last. Each set is weighted by the fraction of fissions
near its energy, and the weights are normalised to sum to one. The
interpolation between tabulated energies is always linear, regardless of the
interpolation law given in the evaluation.

The set of reachable fission products is the union over all tabulated sets. A
nuclide with yields and a nonzero fission rate but no weights raises an error.

### Which nuclides get loaded

YANI does not truncate the network at a fixed number of reaction or decay
steps. A fixed depth drops real nuclides when set too low and loads unneeded
data when set too high. Instead, YANI calculates an upper bound on the density
each candidate nuclide could reach, given the irradiation time and rates, and
keeps the nuclides whose bound reaches the $10^{-30}$ atoms/b-cm floor.

The bound is calculated over the whole reachable network in a single pass.
Setting the edges of unloaded nuclides to zero would not give a bound, because
a nuclide fed by many parents that are each below the floor can still exceed it
in total. Growing the loaded set in rounds and finishing with a bounding sweep
is correct but slower: on the ENDF/B-VIII.1 chain from Fe56, the sweep only
terminates once 1059 of 1060 nuclides are loaded, and returns the same result
as the single pass after thirteen rounds.

## Isomeric branching

When a reaction leaves part of its product in a metastable state, the
metastable state is a separate nuclide with its own half-life and decay chain.
The branching fraction is stored as a function of incident energy and folded
against the spectrum when rates are calculated, so runs with different spectra
on the same target can have different branching fractions.
`get_isomeric_branching()` returns the split used in each step. See
[Weighted, from a solve](usage.md#weighted-from-a-solve).

## Self-shielding

The collapse assumes the given spectrum is the flux inside the material. Often
the spectrum is the flux in the surrounding field instead. Inside a lump of
material, the flux is depressed across resonances where the total cross section
is large, so the true reaction rate is lower than the unshielded rate.

The correction changes the shape of the flux within each group and preserves
the group totals, since those come from a measurement or a transport
calculation. It is applied as a per-group, per-reaction weighting. A nuclide
with no resonances in a group is unchanged.

The flux depression and the escape probability both depend on how easily a
neutron leaves the lump, which depends on its geometry. A `Material` has no
geometry, so the user gives a shape or a mean chord length $4V/S$. YANI never
infers a shape. Without one, no shielding is applied and the result is
bit-identical to a run without self-shielding.

The flux inside the lump is found by solving

$$
\left(\Sigma_t(u) + \Sigma_e\right)\phi(u) =
\int_{u-\Delta u}^{u} \Sigma_s(u')\,\phi(u')\,\frac{e^{-(u-u')}}{1-\alpha}\,\mathrm{d}u' + \Sigma_e
$$

from high to low energy in lethargy, so the in-scattering source uses the flux
already calculated at higher energies. It makes no assumption that resonances
are narrow.

The narrow-resonance approximation, which uses the asymptotic $1/E$ form for
the in-scattering source, was implemented and tested but is not included. It
over-shields nuclides with strong elastic resonances, where in-scattering fills
in the capture dips. On a $1/E$ field at 50 µm it is 41% low on Co59, 63% low on
W186 and 16% low on Mn55, and within 1% on Rh103, Fe56, Eu151 and Nb93. Against
measurement, W186(n,γ) in FNG-tung is 1.29 b. The slowing-down solve gives C/E
0.80 and the narrow-resonance approximation gives 0.46, which is twice as far
from the measurement as no correction. Whether the approximation is accurate
for a given run depends on its spectrum and composition, which a user cannot
easily check in advance, so it is not offered. See
[Self-shielding](usage.md#self-shielding).

## Schedules

A schedule is a list of steps, each with a duration and a rate, and each step is
one matrix exponential. A `Cooldown` is a step with a rate of zero. Its matrix
contains only decay terms, and it uses the same solver as an irradiation step.
The inventory is reported at the start and at the end of every step, so the
output times are the cumulative sums of the step durations. To get a decay
curve, use many short cooldown steps, which are cheap; `cooldown_steps()`
generates them.

On `Material.transmute`, rates are calculated once for each distinct spectrum.
The collapse gives each reaction rate per unit flux from the shape of the
spectrum, and each pulse multiplies these by its own `rate`. Pulses that share
a `source` share one collapse. With self-shielding on, the flux depression is
calculated from the starting composition. Within one spectrum, rates do not
change as the composition changes.

### Coupled to transport

In yamc, `Model.simulate_transmutation` uses a transport calculation instead of
the collapse. Each material's reaction rates are tallied directly as
continuous-energy track-length estimates of $\sigma(E)\,\ell$, scored at the
energy of each track, so there is no group structure. The rate per target atom
is

$$
R = \frac{\langle \sigma \ell \rangle}{10^{24}\,V} \times S
$$

where $\langle \sigma \ell \rangle$ is the mean per source particle in b-cm,
$V$ is the material volume in cm³ and $S$ is the pulse's source rate in n/s.
For this reason, `rate` is a source rate in yamc and a total flux in
`Material.transmute`. Fission-yield weights are tallied in the same way, with
the hat functions applied on each track.

There are two methods:

- **independent** runs transport once, with the starting composition, and
  scales the per-source-particle rates by each step's source rate. It is the
  faster method and the only one that supports nuclear-data uncertainty.
- **coupled** runs transport at the start of every irradiation step with the
  current compositions, and updates the materials in the geometry after each
  step. Rates are held at their beginning-of-step values for the whole step,
  with no predictor-corrector, so split any step long enough for burnup to
  change the flux.

Both methods start with a short scouting run that bounds every reaction rate.
These bounds select which product nuclides are tallied, using the same bound as
[Which nuclides get loaded](#which-nuclides-get-loaded).

## Derived quantities

Each derived quantity is a sum over nuclides of atom density times a per-atom
value from the decay data. With $N_i$ in atoms/b-cm and $V$ in cm³, the number
of atoms is $10^{24} N_i V$.

**Activity** is $A_i = \lambda_i\,10^{24} N_i V$ in Bq, with
$\lambda_i = \ln 2 / T_{1/2}$ from the same chain used in the solve. Stable
nuclides are omitted.

**Decay heat** is $P_i = A_i\,\bar E_i$, where $\bar E_i$ is the mean energy
released per decay, the sum of three MT=457 average energies:

- light particles: beta, conversion and Auger electrons
- electromagnetic: gamma and X-rays
- heavy particles: alpha, protons, neutrons and fragments

Neutrino energy is excluded because it is not deposited. `component=` returns
the beta, gamma or alpha part on its own. If a nuclide that produces heat has
no component split in its data, an error is raised. Some decay records contain
$Q/3$ placeholder energies instead of evaluated ones; see
[Some decay records are placeholders](libraries.md#some-decay-records-are-placeholders).

**Specific values** replace $V$: `per="cm3"` sets it to 1 and `per="g"` sets it
to $1/\rho$, so neither needs the material volume.

**Decay photon lines** come from the MF=8 discrete spectra of the gamma and
X-ray radiation types. Each line's emission rate per atom is $\lambda_i$ times
its intensity per decay, and the line spectrum is that rate times the number of
atoms, summed over nuclides. Lines at the same energy are merged. The lines are
not binned, so the spectrum can be used directly as a photon source.

**Decay photon continua** are the parts of decay photon spectra given in the
evaluation as a density over energy instead of as lines, for example the
photons from spontaneous fission or the emission of nuclides far from
stability. Each continuum keeps its own energy grid and ENDF interpolation law
and is not resampled or merged. Its emission rate is the exact integral under
that law. These are evaluated decay spectra. Bremsstrahlung is not modelled.

### Clearance index

A clearance, exemption or disposal limit set gives a limit $L_i$ for each
radionuclide, in Bq/g, Ci/m³ or Bq depending on the regulation. The index is

$$
I = \sum_i \frac{a_i}{L_i}
$$

where $a_i$ is the nuclide's activity in the same units. The material meets the
set's limits when $I$ is below the set's threshold, normally 1. The activities
use the half-lives of the transmutation chain, the same ones as `activity()`.
Specific activities are divided by the mass of the whole material, so stable
nuclides must remain in the inventory.

The limit tables and the arithmetic come from the
[radiological-material-clearance-finder](https://github.com/fusion-energy/radiological_material_clearance_finder)
crate. Depending on the set, the limit used for a nuclide can be adjusted:

- a nuclide the table does not list takes the set's catch-all limit, if it has
  one, and is listed in `defaulted`;
- where a parent's limit already includes a daughter in secular equilibrium,
  the daughter's activity is left out (`excluded`), or the part the parent
  accounts for is credited and only the rest is assessed (`credited`);
- activity with no limit and no catch-all is not in the index and is reported
  in `uncovered` and `uncovered_fraction`.

A low index with a large `uncovered_fraction` does not show that the material
meets the limits. See [Clearance and disposal limits](usage.md#clearance-and-disposal-limits).

### Contact dose

The contact dose rate treats the material as a half-space that emits photons
uniformly. At the surface, the uncollided flux at energy $E$ from a uniform
isotropic source of $q$ photons/cm³/s is $q / 2\mu(E)$, where $\mu$ is the
material's linear attenuation coefficient. The size of the material cancels, so
the result needs no volume or distance. Summed over all lines of all nuclides:

$$
\dot D = \frac{B}{2} \sum_i 10^{24} N_i \sum_\ell S_{i\ell}\,
\frac{E_\ell\,(\mu_\text{en}/\rho)_\text{air}(E_\ell)}{\mu(E_\ell)}
$$

for absorbed dose in air, where $S_{i\ell}$ is the emission rate of line $\ell$
per atom and $\mu = \sum_e \rho_e\,(\mu/\rho)_e$ is calculated from each
element's partial density and its NIST XCOM mass attenuation coefficient.
$(\mu_\text{en}/\rho)_\text{air}$ is from NIST SRD 126. For effective dose,
$E\,(\mu_\text{en}/\rho)_\text{air}$ is replaced by the ICRP-116 photon
fluence-to-effective-dose coefficient for the AP geometry. Both tables are
interpolated log-log, and lines outside the energy range of both tables are
not counted. Continua are integrated exactly under their interpolation law,
using Gauss-Legendre moments of the response.

The build-up factor $B$ (default 2) accounts for photons that scatter and still
reach the surface. It is the largest source of error: compared with a photon
transport calculation of the same half-space, it gives a result 16 to 17% high
for Co60 in steel. The method follows FISPACT-II (UKAEA-CCFE-RE(21)02,
Appendix C.7.1).

Dose rates away from the material need a photon transport calculation. The
photon lines can be used as its source, and `dose_coefficients()` provides the
ICRP-116 and ICRP-74 coefficients, including H*(10), to fold with its flux
tally.

## Nuclear-data uncertainty

The solve is deterministic and every entry of the matrix is a rate, so
uncertainty is propagated by perturbing the inputs to those rates and repeating
the solve. This is exact to all orders in the matrix exponential: nothing is
linearised, the sandwich rule is not used, and the solver is unchanged.

### Folding the covariance

A reaction rate is linear in the cross section, and MF=33 gives a covariance
that is constant on each interval of the evaluation's energy grid. Together
these give

$$
\operatorname{Cov}(R_i, R_j) = \sum_{k,l} C_{ij}[k,l]\; r_i[k]\; r_j[l]
$$

where $r_i[k]$ is reaction $i$'s rate restricted to covariance interval $k$.
This is exact and does not project the covariance onto the flux group
structure, since the integration is done on the covariance grid. Each block is
folded on its own grid and the contributions are summed.

LB=8 blocks are the exception. An LB=8 block is a short-range variance in
barns squared, not relative to the cross section. ENDF-102 section 33.2.2.2
states that the average over a subinterval $\Delta E_j$ of its interval
$\Delta E_k$ has variance $F_k\,\Delta E_k/\Delta E_j$ and is uncorrelated with
any other subinterval. Its contribution to a rate therefore depends on how the
flux varies within $\Delta E_k$, which is the only place the flux groups enter.
The fold splits $\Delta E_k$ at the group boundaries, where the flux density
$\psi$ is constant, so the rule applies exactly to each piece and the variance
of the rate is $F_k\,\Delta E_k \sum_j \psi_j^2\,\Delta E_j$. A flux that is
flat over the whole interval gives the plain absolute diagonal, which is the
smallest this term can be for a given flux in the interval. The more the flux
is concentrated within an LB=8 interval, the larger the term: ENDF/B-VIII.1
Cr52 (n,p) is 17.7% for a flux flat over the tape's [14, 16] MeV interval and
22.5% for a flux in a single 0.2 MeV group at 14.1 MeV.

A covariance grid does not have to cover the whole flux range. The part of a
rate from outside the grid has no stated uncertainty, so it is included in the
denominator but not the numerator, and the relative uncertainty is smaller
than the covariance grid alone would suggest. `rate_fraction_covered` records
the fraction of each rate that has a stated uncertainty: the rate from energies
where the reaction's diagonal variance, summed over its blocks, is nonzero,
divided by the rate over the whole flux range. An interval with a variance of
zero counts as uncovered. The rate used is the rate in the fold, dilute on a
dilute run and shielded on a self-shielded run. On a transport run, the
tallied rate is different: the fraction there is of the dilute rate over the
tally spectrum, the covered fraction of the tallied rate is not calculated, and
the production-weighted `rate_fraction_covered_total` is `None`.

### Drawing a replica

For the cross sections, one replica is

$$
L = V\sqrt{\Lambda}, \qquad z \sim N(0, I), \qquad \delta = Lz
$$

from the eigendecomposition of the relative covariance. Each $\delta_i$ is
normal with standard deviation $\sigma_i = \sqrt{\sum_j L_{ij}^2}$ and carries
channel $i$'s correlations with the other channels. The rate is perturbed
through a lognormal with the same mean and variance:

$$
s_i^2 = \ln\left(1 + \sigma_i^2\right), \qquad
R_i' = R_i \exp\left(s_i\,\frac{\delta_i}{\sigma_i} - \frac{s_i^2}{2}\right)
$$

so the mean of $R_i'$ is $R_i$ and its variance is $\sigma_i^2 R_i^2$, and no
sampled rate is negative. The linear form $R_i(1 + \delta_i)$ can give negative
rates: on the FNS decay-heat benchmark it sent 8.3% of all sampled rates below
zero (13% on iron), and setting them to zero biases the mean upward. For small
$\sigma_i$ the two forms differ only at order $\sigma_i^2$, so well-known cross
sections sample almost the same way under either. The lognormal transform
preserves rank correlation between channels exactly. The Pearson correlation
changes by a factor that tends to one as $\sigma$ tends to zero.

The evaluation gives a covariance but no distribution, so the lognormal shape
is an assumption. For a channel with sigma near 1 or above, this assumption
determines the tails. Such channels are heavy-tailed and their sampled spread
converges slowly: at 1024 replicas, the maximum the driver adds automatically,
the median sample standard deviation is 0.98 of sigma at $\sigma = 1$, 0.92 at
2, 0.83 at 3 and 0.50 at 9. TENDL-2017 has channels at $10^4$% and above. The
report lists every sampled channel of a populated nuclide with an evaluated
relative sigma of at least 1 in `sigma_at_least_one` and at least 10 in
`sigma_at_least_ten`. Channels with sigma of 1 or more on nuclides outside the
populated bound (described below) are listed in
`sigma_at_least_one_outside_bound`, since a draw on such a channel can be
orders of magnitude above nominal and populate the nuclide.

The eigendecomposition uses cyclic Jacobi rotation. The matrices are one per
nuclide, over that nuclide's activation channels, and range from a few to a few
tens of rows. At that size Jacobi is fast, needs no dependency, is
bit-reproducible, and gives the eigenvectors needed for clipping. Cholesky
would require positive definite matrices, and MF=33 matrices are often not
positive semi-definite as evaluated, so negative eigenvalues are clipped to
zero. Clipping only adds variance, and can give a nonzero spread to a channel
whose evaluated variance is zero.

A matrix counts as repaired when any of the following holds:

- its correlation matrix $R = D^{-1/2} C D^{-1/2}$, over the channels with a
  positive variance, has an eigenvalue below $-n \cdot 10^{-12}$, where $n$ is
  the number of those channels;
- a channel has a negative variance;
- a channel has zero variance and a nonzero covariance with another channel.

$R$ is congruent to that block of $C$, so one is positive semi-definite exactly
when the other is. On $R$ the round-off of the decomposition is about $n$ times
machine epsilon regardless of the channel sigmas, so a positive semi-definite
matrix whose smallest eigenvalue is a few ulps below zero does not count as
repaired. The test does not compare $\lambda_\text{min}$ of $C$ with its
$\lambda_\text{max}$, because TENDL-2017 has channels with relative sigma up to
$5.6 \times 10^8$ (variance near $3 \times 10^{17}$), and one such channel
would set the threshold far above a real repair among the other channels.

The repair is reported in these fields:

- `covariance_repaired` lists the nuclides with a repaired channel that a draw
  can move (one with a positive rate on a spectrum used in the schedule). Any
  entry sets `has_gaps` to true.
- The report covers the nuclides the material can populate. The fold uses every
  chain nuclide with data, which from almost any composition is the whole
  reachable chain, so a nuclide is reported only when an upper bound on its
  density over the schedule, at nominal rates, reaches the solver floor of
  $10^{-30}$ atoms/b-cm. A nuclide outside the bound cannot change any nominal
  density by that much, but a replica's rates on a wide channel can be orders
  of magnitude above nominal. Repaired nuclides outside the bound with a
  channel a draw can move are listed in `covariance_repaired_outside_bound`,
  and any entry also sets `has_gaps` to true.
- `covariance_repairs` records, for each repaired populated nuclide and
  spectrum, $\lambda_\text{min}$, $\lambda_\text{max}$, the variance added
  relative to the stated trace, and each channel's evaluated variance (as
  stated, even when negative) alongside the sigma it is sampled at.
- `worst_sigma_inflation` is the largest ratio of sampled to evaluated sigma,
  minus one, over the repaired channels a draw can move. A small
  $|\lambda_\text{min}| / \lambda_\text{max}$ does not guarantee a small change
  to the channel that matters, so the sigmas themselves are the main measure.
- `rate_weighted_sigma_inflation` is the weighted mean of each channel's
  sampled over evaluated sigma, minus one. Each channel is weighted by its rate
  at unit flux, its spectrum's fluence in the schedule and its parent's initial
  density. Weighting the inflation instead of the sigma stops a wide channel
  with a small rate from dominating. Because of the initial density, this is a
  first-generation measure: produced nuclides have no weight, and their repairs
  appear in the other fields.

The sampled sigma is read from the factorization for every matrix, so matrices
below the repair threshold show their round-off there.

The other sources are sampled using their own stated sigma:

- **Flux.** Drawn once per replica and group, from the pulse's `flux_std_dev`
  or through the factor of its `flux_covariance`, and shared by every rate
  collapsed against that spectrum. A rate is linear in the flux, so the
  perturbed rate is the collapse's per-group terms reweighted exactly, without
  repeating the collapse.
- **Half-lives.** Drawn per nuclide from the sigma in the decay data.
- **Decay energies.** Drawn from the sigma on each beta, gamma and alpha
  component that has one, or on the total if no component has a sigma.
- **Tallied rates.** On a transport run, drawn jointly from their per-history
  covariance.

The decay data gives an expected value and a standard deviation for each value,
with no distribution or correlation (ENDF-102 section 29.1), and each nuclide is
sampled independently. A half-life or decay energy is its nominal value times a
lognormal factor with mean one and variance equal to the squared relative
sigma, so every draw is positive and the ensemble has the stated mean and sigma
exactly, with no floor. The independence between a nuclide's decay-energy
components and between different nuclides' half-lives is an assumption, since
the data gives no correlation. A sigma that cannot be sampled (one on a decay
energy of zero, or one that is not finite) is held at nominal and listed in
`half_life_uncertainty_not_carried` or `decay_energy_uncertainty_not_carried`,
both counted as gaps.

A decay branching ratio is sampled only where the data determines the joint
distribution of a parent's decay modes. MT=457 gives each mode a ratio and a
sigma with no covariance between modes, and the ratios sum to a fixed total.
The split of the error is therefore only determined for a parent with exactly
two modes and one sigma between them: both modes have the same sigma, or one
has a sigma and the other is its complement. In that case one normal draw moves
one mode up and the other down by the same amount, keeping the total. The
parent is sampled only when its smaller ratio is at least five sigmas from
zero, so the normal stays within the physical range. A draw clamped to the
pair's total is counted in `decay_branchings_floored`. Every other parent is
held at its evaluated ratios and listed by reason:
`no_decay_branching_uncertainty`, `decay_branchings_three_or_more_modes`,
`decay_branchings_unequal_sigmas` and `decay_branchings_too_wide`, each counted
as a gap. Only the inventory changes: a sampled parent's lines and decay energy
per decay use its nominal branching.

The flux and tallied-rate draws are normal. A flux bin or tallied rate drawn
below zero is set to zero and counted in `flux_bins_floored` or
`statistical_floored`. This biases the mean of that source upward, so a nonzero
count means the normal distribution is a poor description of the data. These
two sources stay normal because they carry correlations, which a lognormal
would not preserve.

Seeds depend only on their arguments. A cross-section, half-life,
decay-branching or decay-energy draw depends only on `(seed, replica, nuclide)`:
not on the number of replicas, the order they ran in, or the other nuclides in
the material. The flux draw depends on `(seed, replica, spectrum)`, where
spectrum is the spectrum's index among the schedule's spectra. The statistical
draw depends on `(seed, replica)` and is made jointly over the material's
tallied rates, so adding or removing a tallied rate changes the other draws.
A given seed always reproduces a run.

### Derived quantities under uncertainty

Activity, decay heat, contact dose and every photon line are calculated once
per replica, with that replica's half-lives, and the spread is taken over the
results. They are not combined from per-nuclide sigmas.

Adding in quadrature would be wrong. Every Mn56 atom in an irradiated iron foil
came from an Fe56 atom, so the two densities are anticorrelated and their
spreads partly cancel. Quadrature would count variance that is not there.
Calculating once from the mean inventory would also be wrong: activity and
decay heat are linear in $N$, so this gives the correct mean but a spread of
zero. Contact dose is not linear in the densities at all, since a replica that
produces more of an emitter also absorbs more of its photons.

The replica's half-lives must be used here as well as in the solve. A
saturated activity is $\lambda N = R$, which depends very little on its own
half-life. Using the nominal $\lambda$ would give it the full spread of
$N = R / \lambda$. A line's intensity per atom is its emission per decay times
$\lambda$, so it is also rescaled with the replica's $\lambda$, which keeps the
emission per decay at its evaluated value. Decay energies are only used here:
they are sampled where decay heat is calculated and affect nothing else.

### What is not propagated

Six sources are propagated: activation cross sections, the flux spectrum (on
`Material.transmute`), half-lives, two-mode decay branching ratios as described
above, decay energies, and the statistical error of tallies (on a transport
run). Everything listed below is held at its evaluated or nominal value in
every replica. Most of these have their own uncertainty or model error, which
is then missing from the sigma, so the sigma is underestimated, and for some
results this is the largest term. Two can go either way, because holding them
also removes a feedback that reduces the spread: self-shielding, and the
response of the flux to the cross sections of a material that shapes its own
flux. Their entries below say which way each goes. The covariance blocks that
are skipped because they only state a correlation (blocks whose `MAT1` names
another evaluation) can also go either way: dropping a covariance term lowers
the variance of a sum when the term is positive and raises it when the term is
negative.

- **Decay branching ratios not covered by the two-mode draw, and fission
  yields.** Both have published uncertainties, per decay mode and per yield. A
  parent with three or more modes, two unequal sigmas, a pair too wide to
  sample without truncation, or no sigma is held at its evaluated ratios.
  Fission yields are not propagated yet. The weights that combine a nuclide's
  yield sets by incident energy come from the nominal spectrum in every
  replica, so a flux draw does not change them.
- **Isomeric branching.** The split of a reaction product between the ground
  state and an isomer comes from MF=9 or MF=10 (as named in `not_perturbed`).
  Where an evaluation gives its uncertainty, it does so in MF=40, which is
  parsed but not used yet. With the branching overlay configured
  (`transmutation_branch_ratios`), the flux-weighted split is calculated once
  from the nominal spectrum, so on `Material.transmute` a flux draw changes the
  rates but not the split. The `(n,n')` channels added by the overlay to reach a
  metastable state, including In115 to In115m, have no group-averaged cross
  section. They have no cross-section covariance, and on `Material.transmute`
  no flux-spectrum uncertainty either.
- **Resonance-parameter covariance (MF=32).** ENDF-6 gives the cross-section
  covariance in the resonance range as an MF=32 part plus the MF=33 part, and
  many evaluations put the whole resonance-range uncertainty in MF=32 and leave
  MF=33 at zero there. The ENDF parser reads MF=32 but the fold does not use it
  yet. It folds MF=33 only, so a capture rate driven by resonance flux can have
  a sigma near zero. For capture in a $1/E$ field, NJOY ERRORR gives
  ENDF/B-VIII.1 W186 1.53% with MF=32 and 0.00% from MF=33 alone. The coverage
  report shows this: W186's capture block states zero variance from
  $10^{-5}$ eV to 10 keV, where nearly all the capture rate is, so on the FNS
  spectrum its `rate_fraction_covered` is about 0.07. W186 is still listed
  under `perturbed`, since the block's other intervals are used. The same check
  gives 6.32% against 0.01% on the JEFF-4.0 Ag109 tape and 4.71% against 0.00%
  on the TENDL-2025 Co59 tape. YANI's TENDL-2025 covariance is not published
  yet, so a run on it currently lists Co59 under `no_covariance_data`.
- **MF=33 blocks that are not used.** These are:
    - blocks whose `MAT1` names another evaluation, which give covariance with
      it (including links to the standards);
    - blocks whose partner is not a cross section (`XMF1` other than 0 or 3);
    - NC blocks that cannot be derived (LTY 1 to 4, and the LTY=0 blocks
      counted in `skipped_nc`);
    - lumped reactions (MT=851 to 870) with several components that no
      derivation names, which give the uncertainty of a sum of reactions;
    - blocks on partial levels (MT=600 to 849 and 875 to 891) where the chain
      uses the total and no LTY=0 NC block names them.

    A block naming the evaluation's own MAT is folded, as are an LTY=0 NC
    block's derivation from the reactions it names and a lump with a single
    component. `skipped_cross_material`, `skipped_other_file`, `skipped_nc` and
    `lumped_covariance_not_assignable` count the first four kinds, on reactions
    the fold reaches, and all set `has_gaps`. Partial levels are not counted,
    and the rates they and the lumps would cover count as uncovered in
    `rate_fraction_covered_total`. A nuclide whose blocks are all of these
    kinds, or all on reactions the chain does not use, is listed under
    `no_covariance_data`, which sets `has_gaps`. Tungsten's `(n,2n)` is lumped:
    ENDF/B-VIII.1, JEFF-4.0 and FENDL-3.2d give it only together with
    `(n,2np)`. JEFF-4.0 Be9 gives its `(n,2n)` only on the levels MT=875 to 890,
    and ENDF/B-VIII.1 Ca40 gives its `(n,p)` and `(n,a)` only on MT=600 and 800,
    so Ca40 is listed under `perturbed` through its capture alone.
- **Self-shielding.** With a shape or a chord, every replica uses the flux
  depression calculated from the evaluated cross sections. Holding it fixed
  drops two effects with opposite signs. A larger capture cross section would
  deepen its own dip, which narrows the spread, and this is not included. The
  elastic and total covariance does not reach the correction either, which
  would widen the spread where MF=33 gives a resonance-range uncertainty for
  elastic scattering. Which effect is larger depends on the evaluation. For a
  0.1 mm Au197 foil under $1/E$ on VITAMIN-J-175, ENDF/B-VIII.1 gives no
  resonance-range elastic uncertainty, and the held sigma is 1.8 times too large
  (1.70% held against 0.96% with the feedback). TENDL-2017 does give one, and
  there the held sigma is too small: 5.34% held against 6.07% with the feedback
  and the elastic term together (2.23% with the feedback alone). These figures
  fold the shielded partials, as the fold does.
- **Response of the flux to the cross sections.** In yamc's
  `Model.simulate_transmutation`, a replica's cross sections rescale the tallied
  rates and leave the tallied flux unchanged. For a trace activation product
  this is exact to first order in its own cross section. For a material that
  shapes its own flux it is not: a larger Li6(n,t) cross section in a breeder
  depresses its own flux, the same narrowing feedback as self-shielding, so
  holding the flux overstates that rate's sigma. The covariance is folded per
  nuclide, so the cross sections of the materials the neutrons passed through
  (a shield, a multiplier, a breeder) never change the flux on either path, and
  this understates the sigma of a product behind many mean free paths of steel.
  On `Material.transmute` the spectrum uncertainty is only what the pulse is
  given. The coupled method does not support `data_uncertainty` because its
  step-to-step tally noise is not propagated yet. It is also where the response
  of the flux to a perturbed cross section would be included.
- **Decay photon line intensities.** Each line's emission per decay is the
  evaluated value, so a line's uncertainty band is the band on the activity of
  the nuclides emitting it. The decay data gives a sigma on 99.6% of
  ENDF/B-VIII.1 gamma lines. The effect on contact dose is negligible for Co60
  (0.014%) but not for Mn56 (0.6 to 1.8%) or W187 (0.8 to 3.7%), with the range
  covering ENDF/B-VIII.1, JEFF-4.0 and JENDL-5.0 and both independent and fully
  correlated lines.
- **Dose constants and build-up.** Contact dose uses the same photon
  attenuation coefficients, the same response (air energy absorption, or the
  ICRP-116 coefficients for effective dose) and the same constant build-up
  factor in every replica. None of these tables gives a per-value uncertainty.
  The build-up factor is a modelling choice with a larger error: the default of
  2 is 16 to 17% high for Co60 in steel compared with a photon transport
  calculation of the same half-space.
- **Material composition and natural abundances.** Element and impurity
  fractions, density and natural isotopic abundances are the same in every
  replica. For activation driven by a trace impurity this is often the largest
  missing term: in a 316L-like steel with 0.1 wt% cobalt, the contact dose at
  10 years is 99.6% Co60 and changes by 0.69% per 1% change in the cobalt
  fraction. A material contains only the elements it is given, and the bundled
  PNNL compendium's `Steel, Stainless 316L` has no cobalt, niobium, tantalum or
  silver.

`not_perturbed` in `get_data_uncertainty_info` lists every input above on every
run: fission yields, isomeric branching (MF=9/MF=10), cross-material,
non-cross-section, underivable NC and unassignable lumped MF=33 blocks,
resonance-parameter covariance (MF=32), decay photon line energies and
intensities and the decay photon continuum, the photon attenuation,
energy-absorption and fluence-to-dose coefficients, the contact-dose build-up
factor, and the material composition, density, natural abundances and atomic
masses. It also adds an entry for each source a run turns off (half-life,
decay energy, decay branching, activation cross section), the per-branch decay
emission of a parent whose branching was sampled, the flux spectrum on
`Material.transmute` when that source is off or some or all spectra have no
sigma, the tallied-rate statistics when a transport run does not sample them,
the self-shielding correction when shielding is on, and the flux response to
perturbed cross sections on a transport run that perturbs the cross sections.

Some held inputs on this page have no entry of their own: MF=33 blocks on
partial levels (MT=600-849, 875-891), for which the chain has no rate, so they
are neither listed nor counted; the overlay's `(n,n')` channels; the isomeric
split and fission-yield weights held at the nominal spectrum under a flux draw;
and, on `Material.transmute`, the response of the flux to the cross sections of
the materials the neutrons passed through.

`has_gaps` only considers the sources the run perturbs. It is true when any of
these occurs:

- a nuclide with no usable MF=33 block;
- a skipped cross-material, non-cross-section or NC block;
- a mirrored pair whose copies disagree;
- an unassignable lump;
- a block with an unsupported or malformed layout;
- a channel whose partial rates add up to more or less than its rate
  (`partials_above_rate`, `partials_below_rate`);
- a derived channel whose opposing terms have no stated covariance
  (`derived_opposing_uncorrelated`);
- a covariance repaired beyond round-off on a channel a draw can move, inside
  or outside the populated bound;
- a spectrum with no flux sigma;
- a reachable unstable nuclide with no half-life sigma, or with a decay energy
  but no sigma on it;
- a half-life or decay-energy sigma that cannot be sampled;
- a multi-mode parent whose branching was held.

Of the inputs in the not-propagated list, the skipped and unassignable MF=33
blocks set `has_gaps`, and the partial-level blocks set it only through
`no_covariance_data`, when they are all a nuclide has. A reported sigma is the
spread from the six propagated sources, with everything in this list held
fixed. See [Nuclear-data uncertainty](usage.md#nuclear-data-uncertainty).

## Reproducibility

These three properties are checked by tests:

- **Thread count does not change the result.** A 1-thread and a 7-thread run
  agree to the last bit, including the per-replica ensemble, the sigmas and the
  truncation counters.
- **A seed reproduces a run.** See the seeding rules above.
- **Optimisations do not change the result.** Every performance change to the
  collapse is checked to be bit-identical to the previous implementation, by
  hex-float comparison of inventories and against a reference of the per-group
  terms, one-group rates and fission-yield weights.

Without `data_uncertainty`, no covariance is read from disk, no matrix is
folded or factorised, and the step loop runs once. The means are bit-identical
to a build without uncertainty support.

[pusa2010]: https://doi.org/10.13182/NSE09-14
[pusa2015]: https://doi.org/10.13182/NSE15-26
