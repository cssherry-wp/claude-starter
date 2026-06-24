---
tags:
- Weekly
---
# Week overview — {{week}}

## Highlights


## Open tasks by project
```dataview
TASK
FROM -"zz-Templates"
WHERE !completed AND contains(string(tags), "#project/")
GROUP BY filter(tags, (t) => startswith(t, "#project/"))[0] AS Project
```

## Snapshot (frozen)

## From the weekly planner
```dataview
TASK
FROM -"zz-Templates"
WHERE contains(string(tags), "#weekly-planner")
SORT file.cdate DESC
```

## Project statuses

## Learnings & Follow-ups


## References
```dataview
TABLE link(item.link, item.text) AS "Line", file.mtime AS "Modified"
FROM -"zz-Templates"
FLATTEN file.lists AS item
WHERE contains(item.tags, "#Weekly")
SORT file.mtime DESC
```
