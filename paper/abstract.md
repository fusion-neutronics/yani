# YANI paper abstract

This paper introduces YANI (Yet Another Nuclide Inventory), a transmutation and
activation code that computes how a material's nuclide inventory evolves in a
neutron flux field, and the activity, decay heat, contact dose rate and decay
photon emission that follow from it.
The driving application is fusion reactor design and analysis, where activation
of structural, breeding and shielding materials sets maintenance access,
cooling requirements and waste classification, but the formulation is
flux-field general: any irradiation environment for which a neutron spectrum
and an irradiation history can be stated is in scope.
YANI carries no particle transport and no eigenvalue capability of its own,
taking the spectrum as given, which reduces export control concerns while
keeping the codebase and API minimal, maintainable, and fusion-focused.

YANI provides the core capabilities expected of a modern inventory code,
including solution of the Bateman equations with reaction terms as a matrix
exponential by the Chebyshev Rational Approximation Method at order 48 with a
sparse LU factorization whose symbolic factorization is reused across the
poles, coupled decay and neutron-reaction production and loss, fission yields,
isomeric branching, arbitrary irradiation and cooling schedules, and derived
quantities covering nuclide inventories, activities, decay heat, contact dose
rates and discrete decay photon line spectra.
Beyond these foundations, YANI targets end-to-end activation workflows by
integrating capabilities often external to traditional inventory codes,
including collapse of reaction rates against the user's own spectrum using
continuous-energy cross sections rather than a multigroup pre-collapse,
energy-dependent flux-weighted isomeric branching, automatic
transmutation-network reduction from a provable bound on the density each
candidate nuclide can reach, per-pulse spectra so that a campaign whose
spectrum changes shape between phases is expressed directly rather than
averaged, independently sourced network subsections that may be mixed by
library, a bundled citable material library, decay photon line spectra emitted
in the form a coupled photon transport run consumes directly, and high-level
analysis objects that minimise post-processing requirements.

A Python user interface with a Rust backend provides an accessible,
high-performance, and portable simulation environment.
The solver, its bindings and its data readers are developed in a single Rust
workspace shared with the YAMC Monte Carlo transport code, so a transport
spectrum and an inventory calculation meet across one set of nuclear data and
one set of material definitions rather than across a file format boundary.
Rapid adoption is supported through simple installation from a wheel that needs
no compiler, a fully permissive license stack, documentation, extensive
examples, user support, on-demand nuclear data retrieval, and a verification
and validation (V&V) suite run against open activation benchmarks.

YANI reads nuclear data in a binary columnar Apache Arrow IPC format, providing
a portable, cacheable representation of transport-ready cross sections and
transmutation networks that is read as typed columns rather than parsed as
fixed-width text.
Evaluated ENDF-6 files are converted once, through NJOY and a Rust ENDF parser,
into per-nuclide LZ4-compressed section objects that are published per library
and fetched and cached on demand, so a calculation downloads only the sections
it needs; ENDF/B-VIII.1, JEFF-4.0, TENDL-2025, TENDL-2017 and FENDL-3.2d are
available as keywords, and locally converted evaluations may be mixed with
them per nuclide.
The format reduces startup and repeat-calculation times while enabling
deployment across native platforms and WebAssembly (WASM) environments: the
same Rust solver that backs the installed wheel runs client-side in the
browser, against the same continuous-energy data, with no server component and
with nothing uploaded.
YANI supports the major operating systems (Windows, macOS, and Linux) and CPU
(x86 and ARM) architectures.

Verification against established inventory codes and open activation
benchmarks, together with performance evaluation, demonstrates that the
framework provides an efficient and portable platform for modern fusion
activation and inventory workflows.
