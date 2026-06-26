<%* 
const currDate = tp.file.title;
const dateFormat = "YYYY-MM-DD";
const tag = tp.date.now("YYYY/MM/DD", 0, currDate, dateFormat)
-%>
<% "---" %>
tags:
- <% tag %>
- Daily
<% "---" %>


[[<% tp.date.now(dateFormat, -1, currDate, dateFormat) %>|◀ Yesterday]] | [[<% tp.date.now("YYYY-MM-DD", 1, currDate, dateFormat) %>|Tomorrow ▶]]
## Notes


## New open items


## ✅ This Week So Far


## 📓 Learnings & Follow-ups


## TODO

```dataview
TABLE t.text AS "Task", t.header AS "Section Header"
FROM -"zz-Templates"
FLATTEN file.tasks AS t
WHERE (t.status != "-" AND t.status != "x")
SORT choice(contains(t.text, "🔺"), 0, choice(contains(t.text, "⏫"), 1, choice(contains(t.text, "🔼"), 2, choice(contains(t.text, "🔽"), 3, choice(contains(t.text, "⏬"), 4, 2.5))))) ASC, file.cdate DESC
```

### Completed / Cancelled

```dataview
TABLE 
t.text AS "Task", t.header AS "Section Header"
FROM -"zz-Templates"
FLATTEN file.tasks AS t WHERE t.completion = date("<% currDate %>") SORT file.cdate DESC
```

### References
```dataview 
TABLE 
	link(item.link, item.text) AS "Line Content", 
	file.mtime AS "Modified",
	file.ctime AS "Created"
FROM -"zz-Templates"
FLATTEN file.lists AS item 
WHERE 
	contains(item.tags, "#<% tag %>") OR 
	contains(item.outlinks, [[]])
SORT file.mtime DESC
```