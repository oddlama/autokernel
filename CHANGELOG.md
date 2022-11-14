# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html) with [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

## [unreleased]

### Bug Fixes

- Remove wildcard dependency on libc

## [2.0.0] – 2022-11-14

### Documentation

- Add commented example config file
- Add lua tutorial
- Add hardening example

### Features

- Reimplement autokernel in rust
- Add native C bridge to the kernel KConfig interface
- Add makefile interceptor that runs the bridge with the correct environment
- Dynamically inject bridge as shared library
- Add config file to allow specifying build process internals
- Add lua configuration API
- Add traditional kconfig configuration file parser
- Add symbol set function with checks
- Add tristate and int/hex symbol range checks
- Add expression conversion to rust
- Add autokernel-index tool to extract kernel information to sqlite database
- Implement symbol dependency satisfier
- Add symbol value tracking to keep a "transaction history"
- Print assignment errors and duplicate assignment warnings

[unreleased]: https://github.com/oddlama/autokernel/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/oddlama/autokernel/compare/v0.1.0...v2.0.0
[0.1.0]: https://github.com/oddlama/autokernel/releases/tag/v0.1.0
