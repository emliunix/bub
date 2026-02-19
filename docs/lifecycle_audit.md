# Component Lifecycle Audit

## Overview

This document audits the lifecycle management patterns across the Bub codebase, identifying inconsistencies and proposing a unified pattern.

## Current Lifecycle Patterns

### Pattern A: Simple Flag (Problematic)
**Used by:** `AgentLoop`, `TelegramChannel`, `DiscordChannel`, `WebSocketChannel`, `BaseChannel`, `SystemAgent`

```python
class Component:
    def __init__(self):
        self._running = False
    
    async def start(self) -> None:
        self._running = True
        # ... setup
    
    async def stop(self) -> None:
        self._running = False
        # ... cleanup
```

**Issues:**
- No task management for async operations
- Cannot wait for completion
- Race conditions possible

### Pattern B: Task Management (Partial)
**Used by:** `AgentBusClient`

```python
class AgentBusClient:
    def __init__(self):
        self._run_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
    
    async def run(self) -> None:
        self._run_task = asyncio.create_task(self._api._framework.run())
        try:
            await self._run_task
        except asyncio.CancelledError:
            pass
    
    async def disconnect(self) -> None:
        self._stop_event.set()
        if self._run_task:
            try:
                await self._run_task
            except asyncio.CancelledError:
                pass
            await self._transport.close()
```

**Issues:**
- `run()` is separate from `start()` - unclear which to call
- `disconnect()` vs `stop()` naming inconsistency
- No parent-child relationship tracking

### Pattern C: Server Pattern (Better)
**Used by:** `AgentBusServer`, `WebSocketListener`

```python
class AgentBusServer:
    async def start_server(self) -> None:
        await self._activity_log.start()
        await self._listener.start(self._handle_transport)
    
    async def stop_server(self) -> None:
        await self._listener.stop()
        await self._activity_log.stop()
```

**Issues:**
- Naming inconsistency (`start_server` vs `start`)
- No graceful shutdown of active connections

## Component Hierarchy

```
Application
├── ChannelManager
│   ├── TelegramChannel
│   ├── DiscordChannel
│   └── WebSocketChannel
├── AgentRuntime
│   └── SessionRuntime
│       └── AgentLoop
├── SystemAgent
└── AgentBusServer
    └── AgentConnection
        └── AgentBusClient (external peers)
```

## Proposed Unified Pattern

### Lifecycle State Machine

```
[CREATED] --start()--> [STARTING] --> [RUNNING] --stop()--> [STOPPING] --> [STOPPED]
                              |
                              +-- error --> [FAILED]
```

### Base Class Design

```python
class LifecycleComponent(ABC):
    """Base class for components with managed lifecycle."""
    
    def __init__(self) -> None:
        self._state = LifecycleState.CREATED
        self._stop_event = asyncio.Event()
        self._run_task: asyncio.Task | None = None
        self._children: list[LifecycleComponent] = []
        self._lock = asyncio.Lock()
    
    async def start(self) -> None:
        """Start the component and all children."""
        async with self._lock:
            if self._state != LifecycleState.CREATED:
                raise RuntimeError(f"Cannot start from {self._state}")
            self._state = LifecycleState.STARTING
            
            # Start children first
            for child in self._children:
                await child.start()
            
            # Start self
            await self._do_start()
            self._run_task = asyncio.create_task(self._run())
            self._state = LifecycleState.RUNNING
    
    async def stop(self) -> None:
        """Stop the component and all children gracefully."""
        async with self._lock:
            if self._state not in (LifecycleState.RUNNING, LifecycleState.STARTING):
                return
            self._state = LifecycleState.STOPPING
            
            # Signal stop
            self._stop_event.set()
            
            # Stop children in reverse order
            for child in reversed(self._children):
                await child.stop()
            
            # Wait for self to complete
            if self._run_task:
                try:
                    await self._run_task
                except asyncio.CancelledError:
                    pass
            
            await self._do_stop()
            self._state = LifecycleState.STOPPED
    
    @abstractmethod
    async def _do_start(self) -> None:
        """Component-specific start logic."""
        pass
    
    @abstractmethod
    async def _run(self) -> None:
        """Main run loop. Should respect self._stop_event."""
        pass
    
    @abstractmethod
    async def _do_stop(self) -> None:
        """Component-specific cleanup."""
        pass
    
    def add_child(self, child: LifecycleComponent) -> None:
        """Add a child component."""
        self._children.append(child)
```

## Specific Component Issues

### 1. AgentBusClient
**Current:**
- `run()` separate from initialization
- `disconnect()` vs `stop()` naming
- No way to wait for startup completion

**Fix:**
```python
class AgentBusClient(LifecycleComponent):
    async def _do_start(self) -> None:
        await self.initialize(self._client_id)
    
    async def _run(self) -> None:
        await self._api._framework.run()  # Should check stop_event
    
    async def _do_stop(self) -> None:
        await self._transport.close()
```

### 2. AgentBusServer
**Current:**
- `start_server()` / `stop_server()` naming
- No graceful connection shutdown
- Connections handle themselves

**Fix:**
```python
class AgentBusServer(LifecycleComponent):
    async def _do_start(self) -> None:
        await self._activity_log.start()
        await self._listener.start(self._handle_connection)
    
    async def _handle_connection(self, transport) -> None:
        # Create child connection component
        conn = AgentConnection(transport, self)
        self.add_child(conn)
        await conn.start()
    
    async def _run(self) -> None:
        await self._stop_event.wait()
    
    async def _do_stop(self) -> None:
        # Children stopped by base class
        await self._listener.stop()
        await self._activity_log.stop()
```

### 3. TelegramChannel / DiscordChannel / WebSocketChannel
**Current:**
- Simple `_running` flag
- No async task management
- Cannot wait for completion

**Fix:**
```python
class TelegramChannel(BaseChannel, LifecycleComponent):
    async def _do_start(self) -> None:
        self._app = await self._build_app()
        await self._app.initialize()
        await self._app.start()
    
    async def _run(self) -> None:
        # Run until stop signal
        while not self._stop_event.is_set():
            await asyncio.sleep(0.1)
    
    async def _do_stop(self) -> None:
        await self._app.stop()
        await self._app.shutdown()
```

### 4. AgentLoop
**Current:**
- TODO comment about API changes
- No proper bus integration

**Fix:**
```python
class AgentLoop(LifecycleComponent):
    async def _do_start(self) -> None:
        # Subscribe to bus messages
        pass
    
    async def _run(self) -> None:
        # Process messages until stopped
        await self._stop_event.wait()
    
    async def _do_stop(self) -> None:
        # Unsubscribe from bus
        pass
```

### 5. SystemAgent
**Current:**
- Mix of dispatch and processing logic
- Uses `self._running` flag with sleep loop

**Fix:**
```python
class SystemAgent(AgentBusClientCallbacks, LifecycleComponent):
    async def _do_start(self) -> None:
        self.client = await AgentBusClient.connect(self.bus_url, self)
        await self.client.initialize("agent:system")
        await self.client.subscribe("system:*")
    
    async def _run(self) -> None:
        # Use client.run() which respects stop_event
        if self.client:
            await self.client.run()
    
    async def _do_stop(self) -> None:
        if self.client:
            await self.client.disconnect()
```

## Migration Strategy

1. **Phase 1:** Create `LifecycleComponent` base class
2. **Phase 2:** Migrate leaf components (channels, loops)
3. **Phase 3:** Migrate parent components (managers, runtime)
4. **Phase 4:** Add proper error handling and restart policies

## Stop Event Propagation

The stop event should flow from parent to child:

```
App.stop() --> ChannelManager.stop() --> TelegramChannel.stop()
                                    --> DiscordChannel.stop()
                                    --> WebSocketChannel.stop()
```

Each component:
1. Sets its own stop event
2. Stops all children (parallel or sequential)
3. Waits for its run task to complete
4. Performs cleanup

## Benefits

1. **Consistent API:** All components use `start()` / `stop()`
2. **Graceful shutdown:** Proper cleanup order guaranteed
3. **Error handling:** Centralized state management
4. **Testability:** Easy to start/stop components in tests
5. **Observability:** Clear state transitions
