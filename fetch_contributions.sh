#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="$SCRIPT_DIR/data"

FROM_YEAR="${1:?Usage: $0 <from_year> <to_year>}"
# Account was created in 2015, so don't fetch before that
if [ "$FROM_YEAR" -lt 2015 ]; then FROM_YEAR=2015; fi
TO_YEAR="${2:?Usage: $0 <from_year> <to_year>}"
USERNAME="${3:-stonecharioteer}"

mkdir -p "$DATA_DIR"

for year in $(seq "$FROM_YEAR" "$TO_YEAR"); do
    echo "Fetching contributions for $year..."
    gh api graphql -f query="
    query {
        user(login: \"$USERNAME\") {
            contributionsCollection(from: \"${year}-01-01T00:00:00Z\", to: \"${year}-12-31T23:59:59Z\") {
                contributionCalendar {
                    totalContributions
                    weeks {
                        contributionDays {
                            date
                            contributionCount
                            color
                        }
                    }
                }
                commitContributionsByRepository(maxRepositories: 100) {
                    repository { nameWithOwner }
                    contributions(first: 100) {
                        nodes { occurredAt commitCount }
                    }
                }
                issueContributionsByRepository(maxRepositories: 100) {
                    repository { nameWithOwner }
                    contributions(first: 100) {
                        nodes { occurredAt }
                    }
                }
                pullRequestContributionsByRepository(maxRepositories: 100) {
                    repository { nameWithOwner }
                    contributions(first: 100) {
                        nodes { occurredAt }
                    }
                }
                pullRequestReviewContributionsByRepository(maxRepositories: 100) {
                    repository { nameWithOwner }
                    contributions(first: 100) {
                        nodes { occurredAt }
                    }
                }
            }
        }
    }" > "$DATA_DIR/${year}.json"
    echo "  Saved to data/${year}.json"
done

echo "Done! Fetched contribution data for ${FROM_YEAR}-${TO_YEAR}."
