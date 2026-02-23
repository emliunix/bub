# Architecture

Comprehensive documentation of Bub architecture.

## Overview

For a high-level overview, see the [Architecture Overview](../architecture.md).

## Visual Diagrams

Detailed Mermaid diagrams illustrating the system architecture:

### Core Components
- [Class Hierarchy](01-class-hierarchy.md) - UML class diagram showing all components
- [Component Interaction](05-detailed-component-interaction.md) - System-wide interaction flow
- [Channel Initialization](08-channel-initialization-flow.md) - How channels are set up
- [Tape Architecture](09-tape-architecture.md) - TapeService, Store, and LLM integration
- [Session Forking Pattern](10-session-forking-pattern.md) - Context manager pattern for subagents

### Session Management
- [Session Lifecycle](06-session-lifecycle.md) - Session state machine and forking
- [Session Forking Pattern](10-session-forking-pattern.md) - Context manager workflow

### Data Flow
- [Message Flow Sequence](02-message-flow-sequence.md) - Step-by-step message processing
- [Data Flow](07-data-flow-with-type-mapping.md) - Type transformation through the system
- [Session Lifecycle](06-session-lifecycle.md) - Session state machine
- [Tape Architecture](09-tape-architecture.md) - How data persists in tapes

### Architecture Comparison
- [NEW Architecture](03-new-architecture-direct-coupling.md) - Current upstream design
- [Comparison](04-old-vs-new-architecture-comparison.md) - OLD (MessageBus) vs NEW (Direct)

## Design Patterns

Advanced patterns for multi-agent workflows:

- [Session Forking Pattern](10-session-forking-pattern.md) - Delegating work to subagents

## Additional Documentation

- [Agent Federation](../agent-federation.md) - Multi-agent deployment
- [Agent Protocol](../agent-protocol.md) - JSON-RPC protocol specification
- [Distributed Architecture](../distributed-architecture.md) - Scaling considerations
- [Implementation Plan](../implementation-plan.md) - Development roadmap
