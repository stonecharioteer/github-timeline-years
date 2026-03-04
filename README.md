# GitHub Contribution Timeline

Fetch and visualize GitHub contribution data across multiple years, including private repository contributions.

## Prerequisites

- [GitHub CLI (`gh`)](https://cli.github.com/) authenticated
- [uv](https://docs.astral.sh/uv/) for running Python scripts
- [just](https://github.com/casey/just) command runner

## Usage

```bash
just              # Show available recipes
just all          # Fetch data and generate infographic
just fetch        # Fetch contribution data only
just generate     # Generate matplotlib infographic only
just site         # Generate interactive HTML site
just serve        # Start local server to preview the site
```

All recipes accept `--from` and `--to` year parameters (defaults: 10 years ago to current year):

```bash
just all --from 2014 --to 2026
```

## Output

- `data/*.json` - Raw contribution data per year from GitHub GraphQL API
- `contribution_timeline.png` - Static infographic (matplotlib)
- `index.html` - Interactive web visualization
