# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-19

### Added
- Data collection from multiple sources (RSS, HTML index, release notes, documentation)
- Support for 4 ingestion methods: `rss`, `html_index`, `release_index`, `docs_root`
- Smart deduplication by URL and SHA256 hash
- Content update detection
- Firecrawl integration for web scraping
- Dify integration for AI classification
- Content normalization to reduce false positives
- Automatic batching to optimize requests
- Content clamping (head + tail) for AI
- Automatic retry with exponential backoff
- JSON state persistence
- Support for Jupyter Notebook and Python script
- Complete documentation in README.md

### Fixed
- Refactored `sources_config.json` to remove unused attributes
- Reduced configuration file size

### Security
- Environment variables for API keys
- Basic URL filtering

## [Unreleased]

### Planned
- [ ] REST API to query items
- [ ] Web dashboard
- [ ] Slack/Discord integration
- [ ] Webhook support for real-time triggers
- [ ] Distributed cache
- [ ] Metrics and monitoring
- [ ] Multiple Dify workspaces support
- [ ] Unit tests
- [ ] CI/CD with GitHub Actions

