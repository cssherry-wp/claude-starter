# Transform change-review-findings.json into a GitHub "create review" request body.
# Args: --arg commit_id <reviewed head sha>   --arg marker "<!-- claude-autofix -->"
# Output: { commit_id, event:"COMMENT", comments:[...], body } for
#   gh api -X POST /repos/{owner}/{repo}/pulls/{n}/reviews --input -
# Only findings[] (line-anchored) become inline comments; unanchored[] + an
# auto-fixed digest go into the review body. Fixed findings carry the marker.

def confidence_line: "\n\n_(confidence \(.confidence))_";

def comment_body:
  .body + confidence_line
  + (if .status == "fixed"
     then "\n\n_Auto-fixed in the `[autofix]` commit._\n\n" + $marker
     else "" end);

def inline_comment:
  { path: .path, line: .line, side: (.side // "RIGHT"), body: comment_body }
  + (if .start_line != null
     then { start_line: .start_line, start_side: (.side // "RIGHT") }
     else {} end);

def fixed_list:
  [ (.findings // [])[] | select(.status == "fixed")
    | "- `\(.path):\(.line)` — \(.body | split("\n")[0])" ];

def unanchored_list:
  [ (.unanchored // [])[]
    | "- \(.body) _(confidence \(.confidence))_"
      + (if (.hint // "") != "" then " — _\(.hint)_" else "" end) ];

{
  commit_id: $commit_id,
  event: "COMMENT",
  comments: [ (.findings // [])[] | inline_comment ],
  body: (
    (.summary // "")
    + (if (fixed_list | length) > 0
       then "\n\n## Auto-fixed (\(fixed_list | length))\n" + (fixed_list | join("\n"))
       else "" end)
    + (if (unanchored_list | length) > 0
       then "\n\n## Other findings (not line-anchored)\n" + (unanchored_list | join("\n"))
       else "" end)
    + "\n\n" + $marker
  )
}
