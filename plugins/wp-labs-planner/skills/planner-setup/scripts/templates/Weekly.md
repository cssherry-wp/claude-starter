<%* 
const currDate = tp.file.title;
const dateFormat = "YYYY-MM-DD";
const tag = tp.date.now("YYYY/MM", 0, currDate, dateFormat)
-%>
<% "---" %>
tags:
- <% tag %>
- Weekly
<% "---" %>

# Week overview — {{week}}

## Highlights


## Open tasks by project


## Open tasks (current)
```dataview
TASK
FROM -"zz-Templates"
WHERE !completed AND status != "-"
SORT choice(contains(text, "🔺"), 0, choice(contains(text, "⏫"), 1, choice(contains(text, "🔼"), 2, choice(contains(text, "🔽"), 3, choice(contains(text, "⏬"), 4, 5)))))
GROUP BY filter(tags, (t) => startswith(t, "#project/"))[0] AS Project
```

## In progress this week
```dataview
TASK
FROM -"zz-Templates"
WHERE status = "/" OR status = "\\"
SORT choice(contains(text, "🔺"), 0, choice(contains(text, "⏫"), 1, choice(contains(text, "🔼"), 2, choice(contains(text, "🔽"), 3, choice(contains(text, "⏬"), 4, 5)))))
GROUP BY filter(tags, (t) => startswith(t, "#project/"))[0] AS Project
```

## Learnings & Follow-ups


## References
```dataview
TABLE file.ctime AS "Created", file.mtime AS "Edited"
FROM -"zz-Templates"
WHERE file.cday >= date("{{week_start}}") AND file.cday <= date("{{week_end}}")
SORT file.ctime DESC
```

## Completed this week
```dataview
TASK
FROM -"zz-Templates"
WHERE completed AND completion >= date("{{week_start}}") AND completion <= date("{{week_end}}")
SORT choice(contains(text, "🔺"), 0, choice(contains(text, "⏫"), 1, choice(contains(text, "🔼"), 2, choice(contains(text, "🔽"), 3, choice(contains(text, "⏬"), 4, 5)))))
GROUP BY filter(tags, (t) => startswith(t, "#project/"))[0] AS Project
```

## Cancelled this week
```dataview
TASK
FROM -"zz-Templates"
WHERE status = "-" AND file.day >= date("{{week_start}}") AND file.day <= date("{{week_end}}")
SORT choice(contains(text, "🔺"), 0, choice(contains(text, "⏫"), 1, choice(contains(text, "🔼"), 2, choice(contains(text, "🔽"), 3, choice(contains(text, "⏬"), 4, 5)))))
GROUP BY filter(tags, (t) => startswith(t, "#project/"))[0] AS Project
```
