# Method

What YANI actually computes, in the order it computes it. The
[overview](index.md) states the equation; this page is the rest of it. Every
choice here has a reason, and where a cheaper option was measured and rejected
that is recorded rather than quietly omitted.

## From input to answer

A run goes through six stages, and each section below takes one of them:

1. **Network.** The transmutation chain gives every nuclide's decay modes,
   reaction products and fission yields. The nuclides the material can actually
   populate over the schedule are found from the starting composition, and the
   rest are never loaded ([Which nuclides get loaded](#which-nuclides-get-loaded)).
2. **Rates.** Each reaction's rate per atom comes from folding your spectrum
   against the pointwise cross section ([The collapse](#the-collapse)), with a
   flux depression applied first if you asked for self-shielding
   ([Self-shielding](#self-shielding)). Fission yields and isomeric splits are
   weighted by the same spectrum.
3. **Matrix.** Decay constants and rates go into the sparse matrix $A$
   ([Building the matrix](#building-the-matrix)).
4. **Solve.** Each step of the schedule is one matrix exponential
   ([The solve](#the-solve), [Schedules](#schedules)).
5. **Observables.** Activity, decay heat, photon emission and contact dose are
   computed from each step's inventory and the decay data
   ([From inventory to observables](#from-inventory-to-observables)).
6. **Uncertainty**, when asked for, repeats stages 2 to 5 with perturbed inputs
   ([Nuclear-data uncertainty](#nuclear-data-uncertainty)).

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

Most of a transmutation network has no cycles: a chain of decays only goes
downhill. The linear solve at each pole is therefore taken block by block over
the strongly connected components of the network, in order, and only a block
that does contain a cycle (a capture followed by a decay back to the parent, for
instance) goes to the sparse LU. The rest is substitution.

Two things happen after the exponential. A nuclide that nothing in the step
feeds, because none of its parents is present, is set to its closed form
$N_i(0)\,e^{A_{ii}t}$ rather than the CRAM value: the two solve the same
equation, the closed form is exact, and it keeps a stable nuclide that is only
being burned from picking up round-off. Then every density at or below
$10^{-30}$ atoms/b-cm is dropped, which is the floor the network bound below is
measured against.

## Building the matrix

The exponential is published coefficients. The work is in the coefficients of
$A$, which come from two places.

**The transmutation network** supplies decay constants, decay branching,
reaction products and fission yields. Which library supplies which of those is
four independent settings, so a network can mix sources by subsection. See
[Nuclear data settings](usage.md#nuclear-data-settings).

**The collapse** supplies each $\sigma\phi$, described next.

With both in hand, $A$ is filled column by column, one column per parent $j$:

- **Decay.** $\lambda_j = \ln 2 / T_{1/2}$ goes on the diagonal as a loss, and
  each mode adds $b\,\lambda_j$ to the row of its daughter, $b$ the mode's
  branching. The light particle a mode emits is produced too, so an alpha decay
  makes He4. A mode with no daughter in the chain, spontaneous fission among
  them, removes atoms and makes nothing.
- **Reactions.** Each reaction's rate $R$ goes on the diagonal as a loss and
  $b\,R$ into the row of each product, along with the light ejectiles the
  reaction names (H1, H2, H3, He3, He4), so gas production is part of the
  inventory rather than a separate tally. A reaction that leaves the target as
  it was cancels against its own loss.
- **Fission.** The fission rate is a loss, and each fission product $p$ gains
  $R_f\,Y(p)$, with $Y$ the spectrum-weighted yield described in
  [Fission yields](#fission-yields).

Stable nuclides are ordinary columns with no decay term: they are lost only to
reactions.

### The collapse

Each $\sigma\phi$ comes from folding your spectrum against the pointwise cross
section:

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

In practice each $\sigma_g$ is the integral of the cross section over the group
divided by the group width, taken by the trapezoid rule over the group's edges
and every evaluated point inside it. The cross section is read linear-linear
between its points, so the trapezoid rule is exact for it rather than an
approximation. Two edges need a rule:

- **Below the evaluation's first energy** a threshold reaction is zero and any
  other reaction holds its first value.
- **Above its last energy** the cross section is zero and the group keeps its
  full width. A spectrum reaching past a nuclide's evaluation would therefore
  read low without saying so, so a run with more than 0.1% of its flux above
  the top of a nuclide's evaluation raises instead. See
  [Energy range](libraries.md#energy-range).

Cross sections are taken at the material's temperature, which must be one the
data was prepared at: nothing is interpolated between temperatures. A material
with no temperature set takes the first one in the data.

The flux shape within a group is taken as flat in energy, and that is a choice
with an error of its own. Measured against a pointwise reference on the FNS
foil reactions with VITAMIN-J-175, flat is the best of the shapes tried on the
hard FNS spectrum (3.7% mean error, against 21% for $1/E$ within each group),
and the worst once a 10% $1/E$ tail is added (28%, against 3.2%). No fixed
shape wins on both, so the shape stays flat and the remedy is finer groups.

### Fission yields

Fission yields are tabulated at a few incident energies (thermal, 500 keV and
14 MeV is typical), and the yield a fission actually has depends on what
energy caused it. YANI uses the independent yields (MT=454) and mixes the
tabulated sets as

$$
Y(p) = \sum_k c_k\,Y_k(p), \qquad
c_k \propto \int \sigma_f(E)\,\psi(E)\,h_k(E)\,\mathrm{d}E
$$

where $h_k$ is a hat function that is 1 at the $k$-th tabulated energy and
falls linearly to 0 at its neighbours, flat beyond the first and last. So each
set is weighted by the share of fissions happening near its energy, and the
weights sum to one. The interpolation between tabulated energies is linear
whatever law the evaluation states. The fission products a material can reach
are the union over all tabulated sets, so none is missed because the spectrum
happens to weight its set lightly. A nuclide with yields and a nonzero fission
rate but no weights raises rather than losing its products.

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

## Schedules

A schedule is a list of steps, each with a duration and a rate, and each step is
one matrix exponential. A `Cooldown` is a step with a rate of zero: its matrix
holds decay terms only, and it goes through the same solver rather than a
separate decay path, so there is no seam between irradiation and cooling. The
inventory is reported at the start and at the end of every step, so the output
times are the cumulative sums of the durations and nothing is reported inside a
step. A decay curve wants many short cooldown steps, which cost almost nothing,
and `cooldown_steps()` spaces them.

On `Material.transmute` the rates are worked out once per distinct spectrum,
not once per step. The collapse gives each reaction's rate per unit flux, from
the spectrum's shape alone, and each pulse multiplies those by its own `rate`.
Ten pulses sharing one `source` collapse once, and a pulse with a different
`source` gets a collapse of its own. With self-shielding on, the flux
depression is solved from the starting composition. That is the second half of
the point under [The solve](#the-solve): within one spectrum the rates do not
follow the composition, because the spectrum is your input.

### Coupled to transport

In yamc, `Model.simulate_transmutation` replaces the collapse with a transport
run. Each material's rates are tallied directly as continuous-energy
track-length estimates of $\sigma(E)\,\ell$, scored at each track's own
energy, so there is no group structure and no within-group assumption. Per atom
of the target, the rate is

$$
R = \frac{\langle \sigma \ell \rangle}{10^{24}\,V} \times S
$$

with $\langle \sigma \ell \rangle$ the mean per source particle in b-cm, $V$
the material's volume in cm³ and $S$ the pulse's source rate in n/s. That is
why `rate` means a source rate there and a flux here. The fission-yield weights
are tallied the same way, with the hat functions applied on each track.

Two methods differ in how often transport runs:

- **independent** runs it once, at the starting composition, and scales the
  per-source-particle rates by each step's source rate. It is the cheap one, and
  the only one that propagates nuclear-data uncertainty.
- **coupled** runs it at the start of every irradiation step, with the
  compositions the previous step left, and writes the new compositions back to
  the geometry. Rates are held at those beginning-of-step values over the step,
  with no predictor-corrector, so a step long enough for its own burnup to move
  the flux should be split.

Before either, a short scouting run bounds every rate, and the bound picks
which product nuclides get scored, the same bound as
[Which nuclides get loaded](#which-nuclides-get-loaded) with the bounding
rates in place of the collapsed ones.

## From inventory to observables

Everything a step reports beyond the inventory itself is a sum over nuclides of
atom density times a per-atom quantity from the decay data. With $N_i$ in
atoms/b-cm and $V$ in cm³, $10^{24} N_i V$ atoms are present.

**Activity** is $A_i = \lambda_i\,10^{24} N_i V$ in Bq, with
$\lambda_i = \ln 2 / T_{1/2}$ from the same chain the solve used. Stable
nuclides contribute nothing and are left out.

**Decay heat** is $P_i = A_i\,\bar E_i$, with $\bar E_i$ the mean energy
released per decay, from the MT=457 average energies: the light-particle part
(beta, conversion and Auger electrons), the electromagnetic part (gamma and
X-rays) and the heavy-particle part (alpha, protons, neutrons and fragments).
Neutrino energy is not included, since it is not deposited. The `component=`
split returns each part on its own as beta, gamma and alpha, and a nuclide that
makes heat but carries no split raises rather than being left out of a
component. Some decay records state $Q/3$ placeholders instead of evaluated
energies; how those are found and filled is in
[Some decay records are placeholders](libraries.md#some-decay-records-are-placeholders).

**Specific values** replace $V$: `per="cm3"` sets it to 1 and `per="g"` to
$1/\rho$, which is why neither needs the material's volume.

**Decay photon lines** come from the MF=8 discrete spectra of the gamma and
X-ray radiation types. Each line carries its emission per atom per second,
$\lambda_i$ times the line's intensity per decay, and the step's line spectrum
is that times the number of atoms, summed over nuclides. Lines at the same
energy are merged and nothing is binned, so the spectrum is exactly the
evaluated one and goes straight into a photon source.

**Decay photon continua** are the part of a decay photon spectrum the
evaluation gives as a density over energy rather than as lines: the photons of
spontaneous fission, or the whole emission of a nuclide far from stability where
no lines are known. Each is kept on its own energy grid with its own ENDF
interpolation law and is neither resampled nor merged with others, and its
emission rate is its exact integral under that law. These are evaluated decay
spectra, not bremsstrahlung, which is not modelled anywhere.

### Contact dose

The contact dose rate treats the material as a half-space emitting photons
uniformly. At the surface, the uncollided photon flux of energy $E$ from a
uniform isotropic source of $q$ photons per cm³ per second is $q / 2\mu(E)$,
with $\mu$ the material's own linear attenuation coefficient: half the photons
head away from the surface, and the depth they arrive from is set by $\mu$. The
material's size drops out, which is why the answer needs no volume and no
distance. Summed over the lines of every nuclide:

$$
\dot D = \frac{B}{2} \sum_i 10^{24} N_i \sum_\ell S_{i\ell}\,
\frac{E_\ell\,(\mu_\text{en}/\rho)_\text{air}(E_\ell)}{\mu(E_\ell)}
$$

for absorbed dose in air, where $S_{i\ell}$ is line $\ell$'s emission per atom
per second, and $\mu = \sum_e \rho_e\,(\mu/\rho)_e$ is built from each
element's partial density and NIST XCOM mass attenuation coefficients.
$(\mu_\text{en}/\rho)_\text{air}$ is from NIST SRD 126. For effective dose the
factor $E\,(\mu_\text{en}/\rho)_\text{air}$ becomes the ICRP-116 photon
fluence-to-effective-dose coefficient for the AP geometry. Both tables are read
log-log, and a line outside the range both tables cover contributes nothing.
A continuum enters the same sum as an integral over its density, taken exactly
under its interpolation law against Gauss-Legendre moments of the response.

The build-up factor $B$, 2 by default, stands in for photons that scatter and
still arrive. It is the approximation that carries the error: against a photon
transport calculation of the same half-space it reads 16 to 17% high for Co60
in steel. This is the FISPACT-II method (UKAEA-CCFE-RE(21)02, Appendix C.7.1)
and agrees with OpenMC's `Material.get_photon_contact_dose_rate` for lines.

Dose anywhere other than in contact with the material is a photon transport
problem: the photon lines are a source for it, and `dose_coefficients()` gives
the ICRP-116 or ICRP-74 coefficients, H*(10) among them, to fold into its flux
tally.

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
uncertainty: the rate from energies where the reaction's own diagonal
variance, summed over its blocks, is nonzero, over the rate across the flux
range. An interval a grid spans with a variance of zero counts as uncovered,
since it states no uncertainty either. The rate is the one the fold divides by,
dilute on a dilute run and shielded on a self-shielded one. A tallied rate on a
transport run is not that rate: the share there is of the dilute rate over the
tally spectrum, the covered share of the tallied rate is not computed, and the
production-weighted `rate_fraction_covered_total` is reported as `None` on such
a run.

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

The decay data states an expected value and a standard deviation on each value
and no distribution or correlation (ENDF-102 section 29.1), and each nuclide is
drawn on its own. A half-life or decay energy is its nominal value times a
lognormal factor with mean one and variance equal to the squared relative sigma,
so every draw is positive and the ensemble has the stated mean and sigma
exactly, with no floor, however wide the sigma. The independence between a
nuclide's decay-energy components and between different nuclides' half-lives is
a choice, since the data states no correlation. A sigma no draw can carry, one
stated on a decay energy of zero or one that is not finite, is held at nominal
and named in `half_life_uncertainty_not_carried` or
`decay_energy_uncertainty_not_carried`, both counted as gaps.

A decay branching ratio is drawn only where the data fixes the joint
distribution of a parent's modes. MT=457 gives each mode a ratio and a sigma
and no covariance between modes, and the ratios sum to a fixed total, so the
split of the error is determined only for a parent with exactly two modes and
one sigma between them: both modes state the same sigma, or one states it and
the other is its complement. There one normal draw moves one mode up and the
other down by the same amount, so the pair's total is kept, and the parent is
sampled only when its smaller ratio is at least five sigmas from zero, so the
normal stays inside the physical range. A draw clamped to the pair's total is
counted in `decay_branchings_floored`. Every other parent is held at its
evaluated ratios and named by why: `no_decay_branching_uncertainty`,
`decay_branchings_three_or_more_modes`, `decay_branchings_unequal_sigmas` and
`decay_branchings_too_wide`, each counted as a gap. Only the inventory moves:
a drawn parent's lines and decay energy per decay follow its nominal
branching.

The flux and tallied-rate draws are normal, with a floor where a draw would
leave the physical range: a flux bin or a tallied rate below zero is set to zero
and counted in `flux_bins_floored` or `statistical_floored`. A floor biases that
source's mean upward, as it did for the linear cross-section form, so a nonzero
count says the normal is being used past where it describes the data. These two
stay normal because they carry correlations, which a lognormal would not keep.

Seeds are pure functions of their arguments. A cross-section, half-life,
decay-branching or decay-energy draw depends on `(seed, replica, nuclide)` and
on nothing else: not
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

Six sources are propagated: the activation cross sections, the flux spectrum
(on `Material.transmute`), the half-lives, the two-mode decay branching ratios
described above, the decay energies, and the tallies' statistical error (on a
transport run). Everything below is held at its
evaluated or nominal value in every replica. Most of these carry an uncertainty
or a model error of their own that is then missing from the sigma, so holding
them understates it, and for some results it is the largest term. Two can go
either way, because holding them also removes a feedback that narrows the
spread: self-shielding, and the flux's response to the cross sections of a
material that shapes its own flux. Their bullets say which way each goes, and
where. The covariance blocks that are skipped because they state only a
correlation (the blocks whose `MAT1` names another evaluation) can also go
either way: dropping a covariance term lowers the
variance of a sum when the term is positive and raises it when it is negative.

- **Decay branching ratios the two-mode draw does not cover, and fission
  yields.** Both have published uncertainties, per decay mode and per yield.
  A parent with three or more modes, two unequal sigmas, a pair too wide to
  sample untruncated, or no sigma is held at its evaluated ratios, and fission
  yields are not propagated yet. The weights that mix a nuclide's yield sets by incident energy come from the
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
  `perturbed`, since the block's other intervals are used. The
  same check gives 6.32% against 0.01% on the JEFF-4.0 Ag109 tape and 4.71%
  against 0.00% on the TENDL-2025 Co59 tape. yani's TENDL-2025 covariance is not
  published yet, so a run on it today lists Co59 under `no_covariance_data`
  instead.
- **MF=33 blocks that are not used.** Blocks whose `MAT1` names another
  evaluation, which state covariance with it (the links to the standards among
  them); blocks whose partner is not a cross section (`XMF1` other than 0 or
  3); NC blocks that cannot be derived (LTY 1 to 4, and the LTY=0 blocks
  counted in `skipped_nc`); lumped reactions (MT=851 to 870) with several
  components that no derivation names, which state the uncertainty of a sum of
  reactions; and blocks stated on partial levels (MT=600 to 849 and 875 to
  891) where the chain drives the total and no LTY=0 NC block names them. A
  block naming the evaluation's own MAT is folded, as are an LTY=0 NC block's
  derivation from the reactions it names and a lump with a single component.
  `skipped_cross_material`, `skipped_other_file`, `skipped_nc` and
  `lumped_covariance_not_assignable` count the first four, on reactions the
  fold reaches, and all set `has_gaps`. The partial levels are not counted,
  and the rates they and the lumps would cover count as uncovered in
  `rate_fraction_covered_total`. A nuclide whose blocks are all of these kinds,
  or all on reactions the chain does not drive, has no usable block and is
  listed under `no_covariance_data`, which sets `has_gaps`.
  Tungsten's `(n,2n)` is lumped: ENDF/B-VIII.1, JEFF-4.0 and FENDL-3.2d state it
  only together with `(n,2np)`. JEFF-4.0 Be9 states its `(n,2n)` only on the
  levels MT=875 to 890, and ENDF/B-VIII.1 Ca40 its `(n,p)` and `(n,a)` only on
  MT=600 and 800, so Ca40 is listed under `perturbed` through its capture alone.
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
  partials, as the fold does.
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
  tally noise is not propagated yet; it is also where the flux's response to a
  perturbed cross section would come in.
- **Decay photon line intensities.** Each line's emission per decay stays the
  evaluated one, so a line's band is the band on the activity of the nuclides
  emitting it. The decay data states a sigma on 99.6% of ENDF/B-VIII.1 gamma
  lines. On contact dose it is negligible for Co60 (0.014%) and not for Mn56
  (0.6 to 1.8%) or W187 (0.8 to 3.7%), the range running across ENDF/B-VIII.1,
  JEFF-4.0 and JENDL-5.0 and from independent lines to fully correlated ones.
- **Dose constants and build-up.** Contact dose uses the same photon attenuation
  coefficients, the same response (air energy absorption, or the ICRP-116
  coefficients for effective dose) and the same constant build-up factor in
  every replica. None of those tables publishes a per-value uncertainty, and the
  build-up factor is a model choice whose error is the larger term: the default
  of 2 reads 16 to 17% high for Co60 in steel against a photon transport
  calculation of the same half-space.
- **Material composition and natural abundances.** Element and impurity
  fractions, density and natural isotopic abundances are the same in every
  replica. For activation driven by a trace impurity this is often the largest
  omission: in a 316L-like steel with 0.1 wt% cobalt, the contact dose at 10
  years is 99.6% Co60 and moves 0.69% per 1% on the cobalt fraction. A material
  carries only the elements it is given, and the bundled PNNL compendium's
  `Steel, Stainless 316L` lists no cobalt, niobium, tantalum or silver.

`not_perturbed` in `get_data_uncertainty_info` names every input in this list
on every run: fission yields, isomeric branching (MF=9/MF=10), cross-material,
non-cross-section, underivable NC and unassignable lumped MF=33 blocks,
resonance-parameter covariance (MF=32), decay photon line energies and
intensities and the decay photon continuum, the photon attenuation,
energy-absorption and fluence-to-dose coefficients, the contact-dose build-up
factor, and the material composition, density, natural abundances and atomic
masses. It adds an entry for each source a run switches off (half-life, decay
energy, decay branching, activation cross section), the per-branch decay
emission of a parent whose branching was drawn, the flux spectrum on
`Material.transmute`
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
them met a nuclide with no usable MF=33 block, a skipped cross-material,
non-cross-section or NC block, a mirrored pair whose copies disagree, an
unassignable lump, a block whose layout is unsupported or malformed, a channel
whose partial rates add up to more, or less, than its rate
(`partials_above_rate`, `partials_below_rate`), a derived channel whose
opposing terms have no stated covariance (`derived_opposing_uncorrelated`), a
covariance repaired past round-off on a channel a draw can move (inside the
populated bound or outside it), a spectrum with no flux sigma, a reachable
unstable nuclide with no stated half-life sigma, or with a decay energy but no
stated sigma on it, a stated half-life or decay-energy sigma no draw can carry,
or a multi-mode parent whose branching was held. Of the inputs in this list,
the skipped and unassignable MF=33 blocks set it, and the partial-level blocks
set it only through `no_covariance_data`, when they are all a nuclide has. A
sigma is the spread from the six sources above with everything in this list
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
