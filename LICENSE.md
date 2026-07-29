# License and ownership

This repository is **internal developer productivity tooling**. It is not
open-source and is not intended for external distribution.

## What this code does
Every tool in this repo is a thin CLI wrapper around a REST API of an
enterprise system your organisation already operates (GitLab, Jira,
Confluence today; more later). No third-party services are contacted.

## What this code does *not* do
It never bundles, embeds, transmits, or logs credentials. Personal access
tokens are read at runtime from files stored outside the repo (see
`docs/ARCHITECTURE.md`).

## Contributing
Bug reports and pull requests from teammates are welcome. Please:
* keep new verbs in the existing pattern (see `docs/ADDING_A_TOOL.md`);
* do not add third-party dependencies without discussion;
* never commit a token or secret -- the `.gitignore` protects most shapes
  but a review is still your responsibility.

## Redistribution
Do not redistribute externally without approval from the owner. Fork
internally as needed.

