---
name: github-pr-review
description: Handle GitHub PR review comments using gh CLI and GraphQL API. Use when responding to inline PR comments, resolving review threads, or managing PR feedback.
---

# GitHub PR Review Comment Handler

## When to Use

- Responding to inline PR review comments
- Resolving review threads
- Managing PR feedback programmatically

## Prerequisites

- `gh` CLI installed and authenticated
- Repository access
- PR number

## Quick Start

### 1. Get Review Thread IDs

```bash
gh api graphql -f query='
query {
  repository(owner: "OWNER", name: "REPO") {
    pullRequest(number: PR_NUMBER) {
      reviewThreads(first: 50) {
        nodes {
          id
          isResolved
          comments(first: 1) {
            nodes {
              path
              body
              line
            }
          }
        }
      }
    }
  }
}'
```

Extract thread IDs:
```bash
gh api graphql -f query='...' | jq -r '.data.repository.pullRequest.reviewThreads.nodes[] | "\(.id)|\(.comments.nodes[0].path):\(.comments.nodes[0].line)|\(.comments.nodes[0].body)"'
```

### 2. Reply to Thread

```bash
gh api graphql -f query='
mutation {
  addPullRequestReviewThreadReply(input: {
    pullRequestReviewThreadId: "THREAD_ID"
    body: "Fixed - [explanation]"
  }) {
    comment { id }
  }
}'
```

### 3. Resolve Thread

```bash
gh api graphql -f query='
mutation {
  resolveReviewThread(input: {
    threadId: "THREAD_ID"
  }) {
    thread {
      id
      isResolved
    }
  }
}'
```

## Batch Operations

Reply and resolve multiple threads:

```bash
# Save thread IDs
gh api graphql -f query='...' | jq -r '.data.repository.pullRequest.reviewThreads.nodes[].id' > threads.txt

# Reply to each
while read thread_id; do
  gh api graphql -f query="
mutation {
  addPullRequestReviewThreadReply(input: {
    pullRequestReviewThreadId: \"$thread_id\"
    body: \"Fixed - [explanation]\"
  }) {
    comment { id }
  }
}"
done < threads.txt

# Resolve all
while read thread_id; do
  gh api graphql -f query="
mutation {
  resolveReviewThread(input: {
    threadId: \"$thread_id\"
  }) {
    thread { id isResolved }
  }
}"
done < threads.txt
```

## Complete Example

```bash
OWNER="Sense"
REPO="cursor-starter-kit"
PR_NUMBER=30

# Get threads
gh api graphql -f query="
query {
  repository(owner: \"$OWNER\", name: \"$REPO\") {
    pullRequest(number: $PR_NUMBER) {
      reviewThreads(first: 50) {
        nodes {
          id
          comments(first: 1) {
            nodes {
              path
              line
              body
            }
          }
        }
      }
    }
  }
}" | jq -r '.data.repository.pullRequest.reviewThreads.nodes[] | "\(.id)|\(.comments.nodes[0].path):\(.comments.nodes[0].line // "N/A")|\(.comments.nodes[0].body)"'

# Reply to specific thread
gh api graphql -f query='
mutation {
  addPullRequestReviewThreadReply(input: {
    pullRequestReviewThreadId: "THREAD_ID_HERE"
    body: "Fixed in commit abc1234"
  }) {
    comment { id }
  }
}'

# Resolve thread
gh api graphql -f query='
mutation {
  resolveReviewThread(input: {
    threadId: "THREAD_ID_HERE"
  }) {
    thread { id isResolved }
  }
}'
```

## Troubleshooting

**404 Not Found**
- Check `gh auth status`
- Verify repo access: `gh repo view OWNER/REPO`
- Confirm PR exists: `gh pr view PR_NUMBER`

**Permission denied**
- Need write access to repository
- Check: `gh api repos/OWNER/REPO | jq .permissions`

**Wrong ID type**
- Thread IDs start with: `MDIzOlB1bGxSZXF1ZXN0UmV2aWV3VGhyZWFk`
- Comment IDs start with: `MDI0OlB1bGxSZXF1ZXN0UmV2aWV3Q29tbWVudA==`
- Use thread ID, not comment ID

## Notes

- GraphQL API required for inline comment threading
- REST API (`gh pr comment`) cannot reply to specific threads
- Thread IDs are stable and won't change
- Works with GitHub Enterprise
- Resolving threads is optional but recommended

## See Also

- GitHub GraphQL API: https://docs.github.com/graphql
- `gh api` documentation: `gh api --help`
