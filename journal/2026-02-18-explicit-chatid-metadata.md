# 2026-02-18 - Explicit chat_id and Telegram Metadata Architecture

## Motivation

The previous architecture had implicit chat_id handling which caused issues:
- `chat_id` was derived from `senderId` assuming private chats only
- In group chats, `chat_id` (group ID) differs from `senderId` (user ID)
- No Telegram-specific metadata for reply threading or group detection
- Reply creation relied on "quirky parsing" of senderId

## Solution: Explicit Metadata + Factory Pattern

### 1. Explicit chat_id Field

**Before (implicit):**
```python
# chat_id derived from senderId - breaks in groups
chat_id = str(content.get("senderId", ""))
```

**After (explicit):**
```python
# chat_id is explicitly set in tg_message
chat_id = str(content.get("chat_id", content.get("senderId", "")))
```

### 2. Telegram-Specific Metadata

Added to `TgMessageContent`:
- `chat_id: str` - Explicit conversation ID
- `telegram_message_id: int` - Original Telegram message ID
- `telegram_chat_id: int` - Original Telegram chat ID  
- `is_group: bool` - Whether this is a group chat
- `reply_to_telegram_message_id: int | None` - Message being replied to

### 3. Factory Pattern for Reply Creation

**New functions in `messages.py`:**

```python
def make_reply(request: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """Factory: dispatch to appropriate reply maker by message type."""
    msg_type = request.get("type", "")
    if msg_type == "tg_message":
        return make_telegram_reply(request, data)
    raise ValueError(f"Unknown message type: {msg_type}")

def make_telegram_reply(request: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """Create tg_reply with proper metadata binding."""
    content = request.get("content", {})
    chat_id = str(content.get("chat_id", content.get("senderId", "")))
    
    return {
        "messageId": f"msg_{uuid.uuid4().hex}",
        "type": "tg_reply",
        "reply_to_message_id": request.get("messageId", ""),
        "chat_id": chat_id,
        "content": {
            "text": data.get("text", ""),
            "telegram_reply_to_message_id": content.get("telegram_message_id"),
        },
    }
```

## Architecture Benefits

### Clear Separation of Concerns
```
tg_message:
  - chat_id: "-1001234567890"  # Group ID (conversation context)
  - senderId: "987654321"      # User ID (who sent it)
  - telegram_message_id: 12345 # For reply threading
  - is_group: true             # Behavior changes
```

### Request-Response Binding
```
User sends message (telegram_message_id=12345)
    ↓
tg_message with telegram_message_id=12345
    ↓
Agent processes and creates reply
    ↓
tg_reply with telegram_reply_to_message_id=12345
    ↓
Telegram API sends with reply_to_message_id=12345
    ↓
Message appears as reply thread in Telegram UI
```

## Files Changed

| File | Changes |
|------|---------|
| `src/bub/message/messages.py` | Added chat_id and Telegram metadata fields, factory functions |
| `src/bub/cli/bus.py` | Extract and populate all metadata when creating tg_message |

## Usage

### Creating a reply (simplified):
```python
from bub.message.messages import make_reply

# In agent handler
reply_payload = make_reply(
    request=incoming_payload,
    data={"text": "Hello!", "from": client_id}
)
```

### Accessing metadata:
```python
content = payload.get("content", {})
chat_id = content.get("chat_id")  # Always available
is_group = content.get("is_group", False)  # For group-specific behavior
original_tg_msg_id = content.get("telegram_message_id")  # For reply threading
```

## Future Work

1. **Update telegram-bridge** to use `telegram_reply_to_message_id` when calling Telegram API
2. **Update agent handler** in `app.py` to use `make_reply()` factory
3. **Group chat support** - differentiate behavior based on `is_group`
4. **Rate limiting** - per-chat limits based on `chat_id`

## Status

✅ Explicit chat_id field added
✅ Telegram metadata extracted and populated
✅ Factory pattern implemented
✅ Backwards compatibility maintained (fallback to senderId)
✅ Changes committed: `e05dafd`

