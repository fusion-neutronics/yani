# yani: transmutation without transport

**yani** (Yet Another Nuclide Inventory) is the standalone transmutation and
activation wheel built from this repository. A material, an irradiation schedule
and a neutron spectrum go in; inventories, activities, decay heat and decay
photon spectra come out. There is no geometry, no transport and no Monte Carlo.

```bash
pip install yani
```

## What it solves

The nuclide inventory of a material under irradiation is a system of coupled
linear ODEs, the Bateman equations with reaction terms:

```text
dN_i/dt = sum_j (lambda_j->i + sigma_j->i * phi) * N_j - (lambda_i + sigma_i * phi) * N_i
```

The first term is production of nuclide `i`, by decay of every parent `j` and by
neutron reactions on every parent `j`. The second is its loss, again by both
routes. Assembled over every nuclide in the network this is a matrix `A`, and one
timestep is a matrix exponential:

```text
N(t) = exp(A*t) * N(0)
```

which yani evaluates with CRAM (the Chebyshev Rational Approximation Method) at
order 48, following Pusa 2010 and 2015, using a sparse LU factorization whose
symbolic factorization is reused across the poles. Reaction rates are held at
their beginning-of-step values, so a schedule of `n` steps is `n` matrix
exponentials per material.

What takes the work is not the exponential, which is published coefficients: it
is the coefficients of `A`. Those come from a transmutation network (decay
constants, branching, reaction products, fission yields) and from folding your
spectrum against continuous-energy cross sections to get each `sigma * phi`.

## Relationship to yamc

[yamc](https://fusion-neutronics.github.io/yamc/) is a superset: it ships everything yani has, plus neutron and
photon transport, geometry, tallies and transport-coupled transmutation. The two
are **alternatives, not companions**. Installing both puts two extension modules
in one process, so `yamc.Material` and `yani.Material` are distinct types, and
the nuclear-data configuration exists twice, once per package.

Pick **yani** when you already have a spectrum, from a measurement or from an
earlier transport run, and want none of the transport stack. Pick **yamc** when
the spectrum should come from a transport solve, or when you want the coupled
[`Model.simulate_transmutation()`](https://fusion-neutronics.github.io/yamc/simulate_transmutation/) workflow or
shutdown dose rates.

The API is the same either way, so a script written against one is a rename away
from the other:

<!-- doctest: skip -->
```python
import yani as y     # or: import yamc as y
material = y.Material({"Fe56": 1.0}, density=7.87)
```

## What it does not do

- One stepper (beginning-of-step reaction rates). No predictor-corrector.
- No pathway analysis, no sensitivity or uncertainty propagation, no clearance
  indices, no ingestion or inhalation dose.
- Cross sections are read from the continuous-energy library and collapsed
  against your spectrum, so it reads transport-format data files even though it
  runs no transport. Only the sections activation needs are read, which is a
  small fraction of a library.
- No pre-collapsed multigroup libraries. The spectrum you supply does the
  collapsing, at the resolution you supply it.
