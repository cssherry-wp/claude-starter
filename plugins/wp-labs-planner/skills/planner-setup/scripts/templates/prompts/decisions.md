You are maintaining a decision log for the project "{project}". From the MATERIALS
below (each item has note/header/text), extract only HIGH-LEVEL decisions that were
made — not tasks, notes, or status. Output ONLY a JSON object:

{
  "decisions": [
    {"decision": "<one-sentence decision>", "note": "<source note path>",
     "header": "<the item's header, verbatim, or empty>"}
  ]
}

Use the note/header from the source item the decision came from. No prose, no fences.

MATERIALS:
{materials}
