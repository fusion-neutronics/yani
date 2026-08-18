# YANI paper abstract

This paper introduces YANI (Yet Another Nuclide Inventory), a transmutation and
activation code designed to address the inventory, activation and shutdown dose
challenges inherent in fusion reactor design and analysis.
YANI is intentionally focused on spectrum-driven inventory evolution and carries
no particle transport or eigenvalue capability of its own, reducing export
control concerns while maintaining a minimal, maintainable, and fusion-focused
codebase and API.

YANI provides the core capabilities expected of a modern inventory code,
including solution of the Bateman equations with reaction terms as a matrix
exponential by the Chebyshev Rational Approximation Method at order 48, coupled
decay and neutron-reaction production and loss, fission yields, isomeric
branching, arbitrary irradiation and cooling schedules, and derived quantities
covering nuclide inventories, activities, decay heat, contact dose rates and
decay photon line spectra.
Beyond these foundations, YANI targets end-to-end fusion activation workflows by
integrating capabilities often external to traditional inventory codes,
including continuous-energy collapse of reaction rates against the user's own
spectrum rather than a multigroup pre-collapse, energy-dependent flux-weighted
isomeric branching, automatic transmutation-network reduction from a provable
bound on reachable nuclide densities, per-pulse spectra so that a campaign whose
spectrum changes shape between phases is expressed directly, independently
sourced network subsections that may be mixed by library, a bundled citable
material library, and high-level analysis objects that minimise post-processing
requirements.

A Python user interface with a Rust backend provides an accessible,
high-performance, and portable simulation environment.
Rapid adoption is supported through simple installation from a wheel that needs
no compiler and no transport stack, a fully permissive license stack,
documentation, extensive examples, user support, on-demand nuclear data
retrieval, and verification and validation (V&V) against open activation
benchmarks.

YANI stores nuclear data in a binary columnar Apache Arrow format, providing a
portable, cacheable representation of transport-ready cross sections and
transmutation networks that is read as typed columns rather than parsed as text.
Combined with a process-wide in-memory cache that is topped up rather than
rebuilt, this reduces startup and repeat-calculation times while enabling
deployment across native platforms and WebAssembly (WASM) environments: the same
Rust solver that backs the installed wheel also runs client-side in the browser,
against the same continuous-energy data, with no server component.
YANI supports the major operating systems (Windows, macOS, and Linux) and CPU
(x86 and ARM) architectures.

Verification against established inventory codes and open benchmarks, together
with performance evaluation, demonstrates that the framework provides an
efficient and portable platform for modern fusion activation workflows.
