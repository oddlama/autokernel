# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) with [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

## [2.0.2] - 2023-03-03

### Bug Fixes

- Use universal shebang for interceptor
- Name unused parameters to support GCC<=10 ([#5](https://github.com/orhun/git-cliff/issues/5))
- Interpret unnamed .config script files as kconfig files ([#6](https://github.com/orhun/git-cliff/issues/6))

### Documentation

- Add autokernel crates.io badge

### Features

- Add lua function to access kernel env

### Miscellaneous Tasks

- Make uuid an optional dependency
- Update dependencies
- Run formatter
- Update cargo-release to use git-cliff

## [2.0.1] - 2022-11-14

### Bug Fixes

- Remove wildcard dependency on libc

### Miscellaneous Tasks

- Update CHANGELOG.md for 2.0.1

## [2.0.0] - 2022-11-14

### Bug Fixes

- Tests had missing import
- Repecting defconfig output before parsing symbols
- Feat: snafu -> anhow (thiserror if we want more detail)
- Quickfix to make test run, please either fix the envs or leave it hardcoded like this
- Tests running again :D
- RC and 'static to make symbol vtable access possible
- Cleanup and tests - BUT setvalue not working
- Remove access of internal default state
- Removed vtable together with RC workaround
- Option.unwrap to option.context for better error handling
- Stripping CONFIG_ for kconfig compatibility
- Missing imports on newly split tests module
- Symbol routing of bool, tristate
- Inconsistencies in symbol assignment and wrong C return type
- Don't fail test if teardown not necessary
- Drastically simplify symbol set errors for now
- Also display symbols with unknown type
- Get tests to run again
- Don't include assignments to unassignable symbols in solver output
- Removing logging from tests and moving test-deps to dev-dependencies
- Generalize input .c finding algorithm
- Suppress defconfig output

### Documentation

- Add draft for new readme
- Finish README draft
- Add changelog

### Features

- Add makefile interceptor that runs the bridge with the correct environment
- Roadmap and user stories
- Config loading and a few more (random) cli flags
- Wip: refactor bridge exporter
- Recompile bridge when source changes
- Finalize new bridge
- Remove base64.h; add temporary timing benchmark
- Type printing and cargo fmt
- Very raw very first version of validating a config
- Dynamically inject bridge as shared library
- Bridge to snafu, weird though
- Add bridge to get symbols
- Improve bridge to aquire symbols (returns a vec now)
- Extend CSymbol to reflect most native files
- Sub commands
- Un-expose internals of CSymbol
- Isolate environment for each bridge
- Add better bridge debug output
- Set string value; get symbols by name; build work started (e.g. clean)
- Start on config validation
- Colored output
- Build bundled flag and cleanup, wip: setting symbols for bug discovery
- Clean library initialization
- Proper symbol setting, including rebuilding of all symbols
- Implement basic symbol setting from toml
- Ordered config loading of simple kconfig like config.txt
- Lua support (medium), set function
- Support for ordered loading through loading a txt file with lua
- Writing config
- Bridge types and properties
- Genericized config
- Silence messages from C kconfig
- Add SymbolValue and lua globals
- Only define real symbols (type != Unknown)
- Kconfig load, proper test setup wip
- Add symbol set function with checks
- Resing kernel between tests, just rebuilding bridges now
- Unchecked config loading and kconfig exposed to lua
- Add tristate and int/hex symbol range checks
- Implement lua api to access values
- Add lua api to inspect values
- Add second executable to implement the analyzer later
- Add expression conversion to rust
- Add explicit comparison in lua
- Principal about ambiguity
- Lua test macro and setup
- Bad tests for lua
- Add better expressions and expression display
- Add colored expr print
- Wip: implement error type for symbol assignment
- Satisfier setup, unused wip
- Wip: prepare symbols for transaction history
- Add value tracking
- Print assignment errors and duplicate assignment warnings
- Re-add error messages
- Print unmet dependencies
- Add complex cases for solver; add error type for solver
- Always emit solved symbols in order of dependency
- Operate solver on extended visibility expr instead of just direct dependencies
- Added proper reporting of ambiguous requirements
- Add lua api to call satisfier, and properly add rev_dep to expression when there is no prompt
- Pretty print errors in satisfy calls just like in regular set calls
- Add satisfy command
- Pretty-print status
- Implement symbol to csv dump
- Index to sqlite db; have indexer optional feature
- Add version struct to lua and make the kernel
- Add config file to allow specifying build process internals
- Begin implementation of script to index many kernels and configs
- Add arch config downloader
- Add debian and arch to autoindexer
- Both regular and two-stage build finished
- Implement missing error types
- Better shared indexing format
- Implement bridge support down to kernel version 4.2
- Improve indexing database format
- Add defconfig indexing by default
- Add explicit init-db command
- Better clap help messages and cleanup todos
- Add commented example config file
- Add lua tutorial
- Add context to some errors
- Add hardening example

### Miscellaneous Tasks

- Format bridge.c
- Remove old bridge executor
- Remove uses of old bridge
- Just some formatting
- Add important todo
- Experiment with lua syntax
- Simplify number match arms
- Remove debug tests from config
- Print all deps to debug
- Print all deps
- Remove dummy Expr::None
- Return correct expr default
- Validate transactions regardless of config impl
- Improve dependency print
- Track file and line separately in history
- Improve location print formatting
- Enforce minimum num_col_width in location prints
- Update dependencies
- Added stage messages
- Remove indexing script (will be a separate project)
- Clippy fix
- Remove old test files
- Move config.toml to example
- Prepare version 2.0.0

### Refactor

- Only construct symbol wrapper when needed
- Restructuring bridge into own folder
- Split into lib and binary; remove prints for now (prepare for unified printing)
- Remove old files
- SymbolValue::Auto as separate function
- Simplify value assignment match
- Prepare renaming config->script

### Styling

- Apply fmt

### Wip

- Mini thoughts on build
- Explore possibilites to modify env just in shared lib
- Added some todos for C->Rust conversionx
- Add bridge symbol wrapper
- Reorder lifetimes of new symbol wrapper
- Scoped lua functions
- Experiment with boolean expressions
- Detect unchangeable options

