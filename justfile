# GitHub contribution timeline

default:
    @just --list

current_year := `date +%Y`
default_from := `echo $(( $(date +%Y) - 10 ))`

# Fetch contribution data for the given year range
fetch from=default_from to=current_year:
    bash fetch_contributions.sh {{from}} {{to}}

# Generate the contribution timeline infographic
generate from=default_from to=current_year:
    uv run generate_infographic.py --from {{from}} --to {{to}}

# Generate the interactive HTML site
site:
    uv run generate_site.py

# Start a local server to preview the site
serve: site
    python3 -m http.server 8765

# Fetch data and generate all outputs
all from=default_from to=current_year: (fetch from to) (generate from to) site
