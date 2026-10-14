#!/bin/bash
#
# Print the body of the GitHub release for a tag, taken from that version's
# section of the changelog.
#
#   release-notes.sh CHANGELOG TAG REPOSITORY
#
# The section is the one headed "## TAG". A pre-release tag such as
# v2.0.0-rc.1 with no section of its own uses its final version's, v2.0.0. A tag
# with no section at all gets a link to the changelog, and the script exits 2 so
# the workflow can warn about it without failing the release.
#
# The changelog is written to be read in the docs, so two things change on the
# way to a release page:
#
#   - Relative links resolve against docs/ in the repository at that tag.
#     A release page has no base path, so they would otherwise all be broken.
#   - Hard-wrapped lines are joined back into whole paragraphs and list items.
#     GitHub shows every line break in a release body as written.

set -euo pipefail

changelog=$1
tag=$2
repo=$3

section() {
  awk -v heading="## $1" '
    $0 == heading { found = 1; next }
    found && /^## / { exit }
    found
  ' "$changelog"
}

body=$(section "$tag")
if [ -z "$body" ] && [ "${tag#*-}" != "$tag" ]; then
  body=$(section "${tag%%-*}")
fi

if [ -z "$body" ]; then
  echo "See the [Changelog](https://github.com/$repo/blob/$tag/docs/CHANGELOG.md) for the changes in this release."
  exit 2
fi

printf '%s\n' "$body" |
  sed -E "s#\]\(([^)h#][^)]*)\)#](https://github.com/$repo/blob/$tag/docs/\1)#g" |
  awk '
    # A line that is not blank, not a heading, not the start of a list item
    # and not in a code block continues the line before it. An indented
    # bullet starts a nested item, so it keeps its indentation. An indented
    # number does not: a wrapped line can begin with one, as in "port other
    # than\n  5432.", and nothing here nests a numbered list.
    function flush() { if (line != "") print line; line = "" }

    /^[[:space:]]*```/ { flush(); print; fenced = !fenced; next }
    fenced { print; next }
    /^[[:space:]]*$/ { flush(); print ""; next }
    /^(#|[-*+] |[0-9]+\. |\||>)/ || /^[[:space:]]+[-*+] / {
      flush(); line = $0; next
    }
    {
      sub(/^[[:space:]]+/, "")
      line = (line == "") ? $0 : line " " $0
    }
    END { flush() }
  ' |
  sed -e '/./,$!d'
