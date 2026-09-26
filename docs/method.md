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

The solve is deterministic and every expensive input is a reaction rate, so the
uncertainty is propagated by perturbing the rates and running the same solve
again. That is exact to all orders in the matrix exponential: nothing is
linearised, the sandwich rule is not used, and the solver is not touched at all,
only its input.

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
`rate_fraction_covered` records the share of each rate the grid actually
covered. Only relative blocks count toward it for now. An absolute (LB=0) or
short-range (LB=8) block still folds into the sigma but does not raise the
fraction, so a channel whose covariance is stated only in those blocks carries
a variance yet reads as uncovered.

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

The eigendecomposition is a cyclic Jacobi rotation rather than a library call:
the matrices are one per nuclide over that nuclide's activation channels, single
digits to low tens on a side, where Jacobi is fast, needs no dependency, is
bit-reproducible because it is pure arithmetic in a fixed order, and gives the
eigenvectors the clipping needs anyway. A Cholesky would be the obvious choice
if the matrices were positive definite, and the point is that they are not:
MF=33 matrices are frequently not PSD as evaluated, so negative eigenvalues are
clipped to zero. That repair only ever adds variance, and it can give a spread
to a channel whose evaluated variance is zero. `matrices_clipped` counts the
matrices that needed it and `worst_relative_clip` reports the largest
$|\lambda_\text{min}| / \lambda_\text{max}$, which is not the change in any one
sigma: a ratio under $10^{-3}$ can sit beside a dominant channel whose sigma
grew by more than 10%. A matrix that needed a large repair is one whose sampled
spread no longer means what the evaluation said.

Seeds are pure functions of their arguments: a rate depends on
`(seed, replica, nuclide)` and on nothing else. Not on how many replicas were
run, not on the order they ran in, and not on which other nuclides were in the
material.

### Derived quantities

Activity, decay heat, contact dose and every photon line are evaluated once per
replica and the spread taken over the results, rather than combined from
per-nuclide sigmas.

Quadrature would be wrong: every Mn56 atom in an irradiated iron foil came out
of an Fe56 atom, so the two densities move against each other and their spreads
partly cancel, and adding in quadrature double-counts a variance that is not
there. Evaluating once from the mean inventory would also be wrong: activity and
decay heat are linear in $N$, so that gives the right mean and a spread of
exactly zero, which reads as a confident result rather than a missing one. And
contact dose is not linear in the densities at all, since a replica that makes
more of an emitter also absorbs more of it.

### What is not propagated

Half-lives, decay branching ratios, fission yields and the isomeric-branching
overlay are held at their evaluated values. They carry their own uncertainties
and are out of scope for now. `data_uncertainty_info` says so per run rather
than leaving it to be inferred from a small sigma. See
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
