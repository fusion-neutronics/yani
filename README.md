# yani

**Y**et **A**nother **N**uclide **I**nventory: transmutation and activation
without transport. A material, an irradiation schedule and a neutron spectrum
in; inventories, activities, decay heat and decay photon spectra out. No
geometry, no transport, no Monte Carlo.

[Documentation](https://fusion-neutronics.github.io/yani/) |
[PyPI](https://pypi.org/project/yani/)

```bash
pip install yani
```

```python
import yani

yani.cross_section_data = "endf-b8.1"
chain = "transmutation-endf-b8.1-sfr.arrow"
yani.transmutation_decay_data = chain
yani.transmutation_reactions = chain
yani.transmutation_fission_yields = chain

steel = yani.materials.pnnl.material("Steel, Stainless 316", volume=1000.0)
spectrum = yani.NeutronSource(
    energy=yani.sources.Histogram([1e-5, 1e5, 1e6, 1.5e7], [1e12, 1e13, 1e14])
)
schedule = yani.PulseSchedule([
    yani.Pulse(rate=1.11e14, duration=(1, "a"), source=spectrum),
    yani.Cooldown(duration=(1, "d")),
])

final = steel.transmute(schedule=schedule)[-1]
print(final.activity(), "Bq")
print(final.decay_heat(), "W")
```

## What it solves

The nuclide inventory under irradiation is the Bateman equations with reaction
terms, `dN/dt = A N`, solved as a matrix exponential `N(t) = exp(A t) N(0)` by
CRAM at order 48. The solver is Rust; the wheel needs no compiler and no
external toolchain.

## What this repository contains

Documentation, packaging and release automation. The code lives in the
`yani-core` wheel this package depends on, which provides the `yani` module
itself, its type stubs and its docstrings. `pip install yani` pulls it in.

That arrangement is why there is no Python here: one source of truth for the
API, and no re-export layer that can drift from it.

## Relationship to yamc

[yamc](https://github.com/fusion-neutronics/yamc) is a superset: everything here
plus neutron and photon transport, geometry, tallies and transport-coupled
transmutation. The two are **alternatives, not companions**. Installing both
puts two extension modules in one process, so `yamc.Material` and
`yani.Material` are distinct types and the nuclear-data configuration exists
twice.

Pick yani when you already have a spectrum. Pick yamc when the spectrum should
come from a transport solve.

## License

MIT.
