<%* const gen = tp.date.now("YYYY-MM-DD") -%>
---
tags:
- Weekly
---
# Week overview — <% gen %>

```dataview
TASK
FROM -"zz-Templates"
WHERE !completed AND contains(string(tags), "#project/")
GROUP BY filter(tags, (t) => startswith(t, "#project/"))[0] AS Project
```
