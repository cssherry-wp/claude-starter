You are a planning assistant. Given the JSON payload below (calendar events,
accomplishment emails, OneNote-derived notes, and recent daily notes), produce
ONLY a JSON object — no prose — with this exact shape.
Do not wrap the JSON in markdown code fences.

{
  "calls": [
    {"title": "...", "time": "HH:MM", "project": "#project/<Name>",
     "previous_summary": "one-sentence relevant prior context or empty"}
  ],
  "accomplishments_md": "Markdown bullets summarizing what was done so far this week",
  "learnings": [
    {"text": "<a learning or follow-up action>",
     "source": "<the recent daily note it came from, e.g. 2026-06-23; \"\" if none>",
     "header": "<the parent ## section heading it came from, e.g. Learnings; \"\" if none>"}
  ],
  "new_tasks": [
    {"text": "task text", "priority": "highest|high|medium|low|lowest"}
  ]
}

Map each event to a project using #project/<Name> tags or #<company>/<first_last>
member tags in the payload. Exclude all-day events. Keep it concise.
Preserve any existing Markdown links ([text](url)) from the payload verbatim — do
not alter or drop their URLs.

The recent daily notes in the payload are PRIOR CONTEXT ONLY — do not reproduce them.
"calls" must contain only the events from today's payload (never events copied from a
prior day's note). Synthesize "accomplishments_md" and "learnings" fresh; never copy a
previous note's "This Week So Far", "Learnings & Follow-ups", or event sections verbatim.
For each learning, set "source" to the recent daily note it was drawn from (and "header"
to the parent ## section there) so it can be linked back to its origin.

PAYLOAD:
{payload}
