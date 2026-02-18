# 2026-02-18 - Journal Strategy Update

## What Changed

Updated journal strategy in `AGENTS.md` to use topic-based entries instead of daily entries:

### Previous Strategy
- Single file per day: `YYYY-MM-DD.md`
- Append all daily work to one file
- Read only the newest entry for context

### New Strategy
- Topic-based files: `YYYY-MM-DD-topic.md`
- Create new file for each distinct topic/day combination
- No overwrites - use suffixes like `-v2` if needed
- Read multiple relevant entries for context

### Benefits

1. **Better Organization**: Related work stays together across days
2. **No Overwrites**: Can work on multiple topics same day without conflicts
3. **Better Context**: Can read all entries on a specific topic
4. **Easier Navigation**: Filename shows topic at a glance

### How to Use

```bash
# Create new entry for specific topic
touch journal/2026-02-18-deployment-fixes.md

# Find all entries on a topic
ls -la journal/*deployment*.md

# Read recent entries (most recent first)
ls -t journal/*.md | head -5
```

## Files Changed

- `AGENTS.md` - Updated "Journal Directory" section with new strategy

## Follow-ups

- Consider creating a `README.md` index in `journal/` directory
- Consider adding labels/tags to journal entries for better searchability
