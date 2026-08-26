# YANI

**Y**et **A**nother **N**uclide **I**nventory. A material, an irradiation
schedule and a neutron spectrum in; inventories, activities, decay heat,
contact dose and decay photon spectra out.

[Try it online](https://fusion-neutronics.github.io/yani-online/) 🌐 |
[Documentation](https://fusion-neutronics.github.io/yani/) 📝 |
[PyPI](https://pypi.org/project/yani/) 🐍

The browser version needs no install and no account. It is the same Rust solver
compiled to WebAssembly, against the same continuous-energy data, so it answers
what the wheel answers rather than a reduced version of it. The solve runs on
your machine; nothing is uploaded.

```bash
pip install yani
```

```python
import yani

yani.cross_section_data = "tendl-2025"
yani.transmutation_reactions = "tendl-2025"
yani.transmutation_branch_ratios = "tendl-2025"
yani.transmutation_decay_data = "endf-b8.1"      # TENDL has no decay data
yani.transmutation_fission_yields = "endf-b8.1"  # nor fission yields

steel = yani.materials.pnnl.material("Steel, Stainless 316", volume=1000.0)
spectrum = yani.NeutronSource(
    energy=yani.sources.Histogram([1e-5, 1e5, 1e6, 1.5e7], [1e12, 1e13, 1e14])
)
schedule = yani.PulseSchedule([
    yani.Pulse(rate=1.11e14, duration=(1, "a"), source=spectrum),
    yani.Cooldown(duration=(1, "d")),
])

results = steel.transmute(schedule=schedule)
final = results.step_materials(material_id=steel.id or 0)[-1]
print(final.activity(), "Bq")
print(final.decay_heat(), "W")
print(final.contact_dose(), "Gy/h")
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

