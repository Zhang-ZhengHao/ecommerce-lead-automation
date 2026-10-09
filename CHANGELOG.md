# Changelog

All notable public changes to this project are recorded here. Published tags
are treated as immutable; corrections use a new patch release.

## [0.1.0] - 2026-10-09

### Added

- A single semantic application version displayed with the process-captured
  build SHA.
- Weekly Dependabot checks for Python and GitHub Actions dependencies.
- Public engineering evidence, release design, and implementation-plan records.
- Regression checks that keep the synthetic workbook's product and export names
  aligned with the interface.

### Changed

- The development test constraint now excludes vulnerable pytest releases and
  requires pytest 9.0.3 or newer within the 9.x series.
- Session upload deduplication now uses SHA-256 instead of SHA-1.
- Configured model endpoints must be credential-free HTTP(S) URLs without a
  query or fragment. HTTP remains available for controlled local deployments.
- The synthetic golden workbook now uses the current product and export names.

### Verified

- The release suite contains 128 tests and runs on Python 3.10 and 3.12.
- Python source compilation and installed-dependency consistency are checked in
  GitHub Actions.
- The release gate includes dependency vulnerability and static security scans.

### Boundaries

This is an offline-first workflow-automation case study, not a production
messaging platform. It does not add accounts, a customer database, durable
audit logs, background jobs, or automatic message sending. The included data
is synthetic, and every sendable export still requires human confirmation.

[0.1.0]: https://github.com/Zhang-ZhengHao/ecommerce-lead-automation/releases/tag/v0.1.0
