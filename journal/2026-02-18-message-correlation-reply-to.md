# 2026-02-18 - Message Correlation with reply_to_message_id

## Problem

The `tg_reply` messages lacked a reference to the original `tg_message` they were responding to. This created a weak binding between request and response, making it difficult to:
- Trace message flows for debugging
- Handle out-of-order responses
- Support Telegram reply threading
- Correlate logs across distributed components

## Solution

Added `reply_to_message_id` field to create strong correspondence between messages.

## Changes

### 1. Updated `TgReplyPayload` TypedDict
**File:** `src/bub/message/messages.py:93`
```python
class TgReplyPayload(TypedDict):
    messageId: str
    type: Literal["tg_reply"]
    from_: str
    reply_to_message_id: str  # Added - references original tg_message.messageId
    timestamp: str
    content: TgReplyContent
```

### 2. Updated `TgReply` dataclass
**File:** `src/bub/message/messages.py:167`
```python
@dataclass
class TgReply:
    message_id: str
    from_addr: str
    reply_to_message_id: str  # Added
    timestamp: str
    text: str
    channel: str
```

### 3. Updated `create_tg_reply_payload()` function
**File:** `src/bub/message/messages.py:214-228`
```python
def create_tg_reply_payload(
    message_id: str,
    from_addr: str,
    reply_to_message_id: str,  # Added parameter
    timestamp: str,
    text: str,
    channel: str,
    chat_id: str,
) -> dict[str, object]:
    return {
        "messageId": message_id,
        "type": "tg_reply",
        "from": from_addr,
        "reply_to_message_id": reply_to_message_id,  # Added to payload
        "timestamp": timestamp,
        "chat_id": chat_id,
        "content": {
            "text": text,
            "channel": channel,
        },
    }
```

### 4. Updated agent handler
**File:** `src/bub/cli/app.py:285-293`
```python
original_message_id = payload.get("messageId", "")
reply_payload = create_tg_reply_payload(
    message_id=f"msg_{client_id}_{datetime.now(UTC).timestamp()}",
    from_addr=client_id,
    reply_to_message_id=original_message_id,  # Pass original message ID
    timestamp=datetime.now(UTC).isoformat(),
    text=content,
    channel=reply_type,
    chat_id=message.chat_id,
)
```

### 5. Updated WebSocket channel
**File:** `src/bub/channels/websocket.py:97-104`
```python
original_message_id = message.metadata.get("original_message_id", "")
payload = create_tg_reply_payload(
    message_id=f"msg_ws_{datetime.now(UTC).timestamp()}",
    from_addr="websocket:client",
    reply_to_message_id=original_message_id,
    ...
)
```

## Message Flow with Correlation

```
1. Telegram User sends: "Hello"

2. telegram-bridge creates:
   {
     "messageId": "msg_bridge_abc123",
     "type": "tg_message",
     "content": {"text": "Hello", ...}
   }

3. Agent receives and processes...

4. Agent creates reply:
   {
     "messageId": "msg_agent_xyz789",
     "type": "tg_reply",
     "reply_to_message_id": "msg_bridge_abc123",  # ← Strong binding
     "chat_id": "123456789",
     "content": {"text": "Hi there!"}
   }

5. telegram-bridge can now:
   - Extract chat_id and send to Telegram
   - Log which incoming message triggered the response
   - Support reply threading using reply_to_message_id
```

## Benefits

1. **Debugging**: Can trace full message lifecycle from user → bridge → agent → bridge → user
2. **Ordering**: Can detect and handle out-of-order responses
3. **Observability**: Distributed tracing across components
4. **Future Features**: 
   - Telegram reply threading (reply_to_message_id API parameter)
   - Message deduplication
   - Request timeout tracking

## Files Changed

| File | Lines | Description |
|------|-------|-------------|
| `src/bub/message/messages.py` | 93, 167, 214-228 | Added reply_to_message_id to type defs and payload creator |
| `src/bub/cli/app.py` | 285, 289 | Extract and pass original messageId |
| `src/bub/channels/websocket.py` | 97, 101 | Extract from metadata and pass |

## Status

✅ Type definitions updated
✅ Payload creator updated with new parameter
✅ All callers updated to pass reply_to_message_id
✅ Strong binding established between tg_message and tg_reply
✅ Changes committed: `5b2c77e`

## Follow-up

- Update telegram-bridge to use reply_to_message_id for Telegram reply threading
- Consider adding correlation IDs at the bus level for distributed tracing
