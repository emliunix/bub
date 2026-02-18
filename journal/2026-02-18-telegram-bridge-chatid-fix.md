# 2026-02-18 - Telegram Bridge chat_id Fix

## Problem

The telegram-bridge was failing to send replies back to Telegram. Logs showed:
```
telegram.bridge.outbound topic=tg:436026689 chat_id= len=2
telegram.bridge.send_error chat_id=
```

The `chat_id` was empty, causing `ValueError: invalid literal for int() with base 10: ''`.

## Root Cause

In `src/bub/cli/bus.py`, the `handle_outbound()` function extracts `chat_id` from the payload:
```python
chat_id = payload.get("chat_id", "")
```

However, the `create_tg_reply_payload()` function in `src/bub/message/messages.py` was not including `chat_id` in the payload it returned. The agent was sending responses to the correct topic (`tg:{chat_id}`) but the payload itself was missing the `chat_id` field that the bridge expected.

## Fix

Updated `create_tg_reply_payload()` to accept and include `chat_id` in the payload:

### 1. Updated `create_tg_reply_payload()` signature
**File:** `src/bub/message/messages.py:209`
```python
def create_tg_reply_payload(
    message_id: str,
    from_addr: str,
    timestamp: str,
    text: str,
    channel: str,
    chat_id: str,  # Added
) -> dict[str, object]:
```

### 2. Updated payload to include chat_id
**File:** `src/bub/message/messages.py:220`
```python
return {
    "messageId": message_id,
    "type": "tg_reply",
    "from": from_addr,
    "timestamp": timestamp,
    "chat_id": chat_id,  # Added
    "content": {
        "text": text,
        "channel": channel,
    },
}
```

### 3. Updated callers to pass chat_id
**File:** `src/bub/cli/app.py:285`
```python
reply_payload = create_tg_reply_payload(
    message_id=f"msg_{client_id}_{datetime.now(UTC).timestamp()}",
    from_addr=client_id,
    timestamp=datetime.now(UTC).isoformat(),
    text=content,
    channel=reply_type,
    chat_id=message.chat_id,  # Added
)
```

**File:** `src/bub/channels/websocket.py:97`
```python
payload = create_tg_reply_payload(
    message_id=f"msg_ws_{datetime.now(UTC).timestamp()}",
    from_addr="websocket:client",
    timestamp=datetime.now(UTC).isoformat(),
    text=message.content,
    channel=message.channel,
    chat_id=message.chat_id,  # Added
)
```

## Files Changed

| File | Lines | Description |
|------|-------|-------------|
| `src/bub/message/messages.py` | 209-226 | Added `chat_id` parameter and payload field |
| `src/bub/cli/app.py` | 291 | Pass `chat_id=message.chat_id` to payload creator |
| `src/bub/channels/websocket.py` | 103 | Pass `chat_id=message.chat_id` to payload creator |

## Status

✅ Fix applied and deployed
✅ Services restarted successfully
✅ All components running (bus, system-agent, tape, telegram-bridge)

## Follow-up

- Monitor logs for successful message delivery
- Consider adding validation to ensure chat_id is never empty before sending to Telegram API
