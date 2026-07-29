# `toolbelt` configuration

All configuration is **optional**. If you never create a config file, every
tool falls back to a set of built-in defaults baked into `src/<tool>/api.py`
and nothing breaks.

The mechanism exists so that:

* teammates whose GitLab / Jira / Confluence instances live at different
  hosts can point the tools at their own URLs without editing code, and
* the same clone can be reused across projects by flipping a default
  project id or space key.

## Where the config file lives

Resolution order:

1. `$TOOLBELT_CONFIG` -- explicit path (any filename, any location).
2. `<SECRETS_DIR>/config.toml` -- next to your token files. This is the
   normal case. With the default `SECRETS_DIR`, that is
   `%USERPROFILE%\.toolbelt\config.toml` on Windows.

If the file does not exist, everything just uses defaults. There is no
error, no warning.

## Format

Plain TOML (Python 3.11 stdlib `tomllib`). Comments start with `#`. See
[`config.toml.example`](../config.toml.example) at the repo root for a
copy-and-edit starter.

```toml
[gitlab]
base_url            = "https://gitlab.example.com/api/v4"
default_project_id  = 12345

[jira]
base_url             = "https://jira.example.com/rest/api/2"
browse_url           = "https://jira.example.com/browse"
default_project_key  = "ABC"

[conf]
host                = "https://confluence.example.com"
default_space_key   = "MYSPACE"
```

Any section, key, or value you leave out silently falls back to the
built-in default.

## Precedence per value

For every configurable value the tool checks three sources in order:

1. **Tool-specific environment variable** (highest priority).
2. **The TOML config file.**
3. **Built-in default constant.**

That means:

* CI or scripts can override one value at a time without editing the file.
* A shared config file can define the baseline, and individual overrides
  are still possible.
* A pristine clone with no env vars and no config file still works out of
  the box against the built-in defaults.

## Full reference

### `[gitlab]`

| Key                   | Env override                    | Built-in default                                |
|-----------------------|---------------------------------|-------------------------------------------------|
| `base_url`            | `TOOLBELT_GITLAB_URL`           | `https://gitlab.example.com/api/v4`         |
| `default_project_id`  | `TOOLBELT_GITLAB_PROJECT_ID`    | `1`  (int)                                   |

### `[jira]`

| Key                    | Env override                       | Built-in default                                |
|------------------------|------------------------------------|-------------------------------------------------|
| `base_url`             | `TOOLBELT_JIRA_URL`                | `https://jira.example.com/rest/api/2`           |
| `browse_url`           | `TOOLBELT_JIRA_BROWSE_URL`         | `https://jira.example.com/browse`               |
| `default_project_key`  | `TOOLBELT_JIRA_PROJECT_KEY`        | `MYPROJ`                                           |

### `[conf]`

| Key                  | Env override                    | Built-in default                                |
|----------------------|---------------------------------|-------------------------------------------------|
| `host`               | `TOOLBELT_CONF_HOST`            | `https://confluence.example.com`                |
| `base_url`           | `TOOLBELT_CONF_URL`             | derived from `host`  (`<host>/rest/api`)        |
| `default_space_key`  | `TOOLBELT_CONF_SPACE_KEY`       | `MYSPACE`                                          |

## Things NOT in the config file

These stay as environment variables by design:

| Setting                 | Env var             | Why not in config                                              |
|-------------------------|---------------------|----------------------------------------------------------------|
| Secrets directory       | `TOOLBELT_SECRETS`  | The config file lives inside this directory. Chicken-and-egg.  |
| Python interpreter      | `TOOLBELT_PYTHON`   | The `.cmd` shim picks it before Python is even launched.       |
| Location of config file | `TOOLBELT_CONFIG`   | Same reason -- the loader needs to know where to look.         |

## Rotating / editing the config

The file is read once per Python-process launch, so any change takes
effect on the next `gl` / `jira` / `conf` invocation. There is nothing to
restart.

## Troubleshooting

| Symptom                                | Cause                          | Fix                                                      |
|----------------------------------------|--------------------------------|----------------------------------------------------------|
| `[config] failed to parse ...`         | Malformed TOML                 | Check for stray quotes, missing brackets                 |
| `[config] section [X] must be a table` | Wrote `X = "y"` at top level   | Wrap in a `[X]` section header                           |
| Tool still hits the old URL            | Env var still set              | `set TOOLBELT_<TOOL>_URL=` to clear, or start a fresh shell |
| Config not being read                  | `TOOLBELT_CONFIG` points elsewhere | `echo %TOOLBELT_CONFIG%`, or unset it                    |

