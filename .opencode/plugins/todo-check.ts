import type { Plugin } from "@opencode-ai/plugin"

// Session interruption handling:
// When user presses Escape or aborts, the flow is:
// 1. session.error event fires with MessageAbortedError
// 2. session.status idle event fires (with NO reason field)
// 3. session.idle event fires (deprecated)
//
// We track sessions with errors via erroredSessions Set.
// When session goes idle and had an error, we skip todo-check.

type TodoItem = {
  content: string
  status: string
  priority: string
}

const log = async (client: any, message: string, extra?: Record<string, unknown>) => {
  await client.app.log({
    body: {
      service: "todo-check",
      level: "info",
      message,
      extra,
    },
  })
}

export const TodoCheckPlugin: Plugin = async ({ client }) => {
  // Group todos by session ID to avoid cross-session pollution
  // This ensures todos from session A don't trigger checks in session B
  const todosBySession: Map<string, TodoItem[]> = new Map()
  
  // Track sessions that had errors (e.g., user interruption via abort)
  // When session goes idle after an error, we skip todo-check
  const erroredSessions: Set<string> = new Set()
  
  // Track prompt counts per session to prevent duplicate prompts
  // Increments when prompt is sent, clears when todos are updated or session becomes busy
  const promptCounter: Map<string, number> = new Map()
  
  // Track event counts for debugging
  let eventCount = 0

  await log(client, "plugin initialized", {
    todosBySessionSize: 0,
    erroredSessionsSize: 0,
    promptCounterSize: 0,
  })

  return {
    event: async ({ event }) => {
      // Filter: Ignore deprecated session.idle events (session.status already covers idle state)
      // See: https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/session/status.ts#L41-L45
      if (event.type === "session.idle") {
        return
      }

      eventCount++
      const timestamp = Date.now()
      
      // Log EVERY event received with full context
      await log(client, `[EVENT #${eventCount}] ${event.type} received`, {
        timestamp,
        eventType: event.type,
        sessionID: event.properties?.sessionID,
        properties: event.properties,
      })

      // Track todo list updates per session
      // Source: todo.updated event from opencode session module
      // https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/session/todo.ts#L18
      if (event.type === "todo.updated") {
        const sessionId = event.properties?.sessionID as string | undefined
        const todos = event.properties?.todos as TodoItem[] | undefined
        
        await log(client, `[TODO.UPDATED] Processing for session ${sessionId}`, {
          sessionId,
          todoCount: todos?.length ?? 0,
          todos: todos?.map((t) => ({ content: t.content, status: t.status })),
        })
        
        if (sessionId && todos) {
          todosBySession.set(sessionId, todos)
          
          // Clear prompt counter when todos are updated (new work started)
          const hadPrompts = promptCounter.get(sessionId) ?? 0
          promptCounter.delete(sessionId)
          
          await log(client, `[TODO.UPDATED] Cleared for session ${sessionId}`, {
            sessionId,
            hadPrompts,
            promptCounterSize: promptCounter.size,
          })
          
          await log(client, `[TODOS.STORED] ${todos.length} items for session ${sessionId}`, {
            sessionId,
            todoCount: todos.length,
            unresolvedCount: todos.filter((t) => t.status !== "completed" && t.status !== "cancelled").length,
            todosBySessionSize: todosBySession.size,
          })
        }
      }

      // Clear error tracking when session becomes busy (errors don't persist across work sessions)
      if (event.type === "session.status" && event.properties?.status?.type === "busy") {
        const sessionId = event.properties?.sessionID as string | undefined
        
        if (sessionId) {
          const hadError = erroredSessions.has(sessionId)
          erroredSessions.delete(sessionId)
          
          await log(client, `[BUSY.CLEAR] Session ${sessionId} became busy`, {
            sessionId,
            hadError,
            promptCount: promptCounter.get(sessionId) ?? 0,
            erroredSessionsSize: erroredSessions.size,
            promptCounterSize: promptCounter.size,
          })
        }
      }

      // Track session errors (e.g., user interruption via abort/Escape)
      // Source: session.error event structure
      // https://github.com/anomalyco/opencode/blob/dev/packages/sdk/js/src/gen/types.gen.ts
      // When user presses Escape or session is aborted, a MessageAbortedError is emitted
      if (event.type === "session.error") {
        const sessionId = event.properties?.sessionID as string | undefined
        const error = event.properties?.error as { name: string; data?: { message: string } } | undefined
        
        await log(client, `[SESSION.ERROR] Received error event`, {
          sessionId,
          errorName: error?.name,
          errorData: error?.data,
          eventProperties: event.properties,
        })
        
        if (sessionId && error?.name === "MessageAbortedError") {
          erroredSessions.add(sessionId)
          await log(client, `[ERRORED.SESSIONS.ADD] Session ${sessionId} marked as errored (aborted)`, {
            sessionId,
            errorMessage: error.data?.message,
            erroredSessionsSize: erroredSessions.size,
            erroredSessionsList: Array.from(erroredSessions),
          })
        }
      }

      // Handle session idle events
      // Source: session.status event structure
      // https://github.com/anomalyco/opencode/blob/dev/packages/opencode/src/session/status.ts#L28-L35
      if (event.type === "session.status" && event.properties?.status?.type === "idle") {
        const sessionId = event.properties?.sessionID as string | undefined
        
        await log(client, `[IDLE.START] Processing idle event`, {
          sessionId,
          eventProperties: event.properties,
          erroredSessionsSize: erroredSessions.size,
          erroredSessionsList: Array.from(erroredSessions),
          promptCount: promptCounter.get(sessionId) ?? 0,
          promptCounterSize: promptCounter.size,
        })
        
        if (!sessionId) {
          await log(client, `[IDLE.SKIP] No sessionId in event`, { eventProperties: event.properties })
          return
        }

        // Skip if session had an error (e.g., user interrupted via abort/Escape)
        if (erroredSessions.has(sessionId)) {
          await log(client, `[IDLE.SKIP.ERROR] Session ${sessionId} had error before idle`, {
            sessionId,
            errorType: "MessageAbortedError",
            erroredSessionsSize: erroredSessions.size,
          })
          return
        }

        const todos = todosBySession.get(sessionId) ?? []
        const status = event.properties?.status
        
        // Filter unresolved todos
        const unresolved = todos.filter(
          (t) => t.status !== "completed" && t.status !== "cancelled",
        )
        
        await log(client, `[IDLE.STATE] Session ${sessionId}`, {
          sessionId,
          status,
          todoCount: todos.length,
          unresolvedCount: unresolved.length,
          promptCount: promptCounter.get(sessionId) ?? 0,
          promptCounterSize: promptCounter.size,
        })

        if (unresolved.length === 0) {
          await log(client, `[IDLE.SKIP.RESOLVED] Session ${sessionId} all todos resolved`, {
            sessionId,
            todoCount: todos.length,
            completedCount: todos.filter((t) => t.status === "completed").length,
            cancelledCount: todos.filter((t) => t.status === "cancelled").length,
          })
          return
        }

        // Skip if prompt already sent 3 times for this session (prevents spam)
        // Counter increments on send, clears on todo update
        const promptCount = promptCounter.get(sessionId) ?? 0
        if (promptCount >= 3) {
          await log(client, `[IDLE.SKIP.PROMPTED] Session ${sessionId} already prompted ${promptCount} times (max 3)`, {
            sessionId,
            promptCount,
            promptCounterSize: promptCounter.size,
          })
          return
        }

        const items = unresolved
          .map((t, i) => `${i + 1}. [${t.status}] ${t.content}`)
          .join("\n")

        const body = [
          "<todo-check>",
          "<attribution>This message is from the todo-check plugin.</attribution>",
          "",
          "You have unfinished todo items:",
          "",
          items,
          "",
          "Review each item. If all are addressed, reply TODO_CHECKED to dismiss.",
          "If any item is genuinely incomplete, continue working on it.",
          "</todo-check>",
        ].join("\n")

        await log(client, `[PROMPT.SEND] Sending todo-check for ${sessionId}`, {
          sessionId,
          unresolvedCount: unresolved.length,
          promptLength: body.length,
        })

        try {
          await client.session.prompt({
            path: { id: sessionId },
            body: {
              parts: [{ type: "text", text: body }],
            },
          })
          // Increment prompt counter on successful send
          const newCount = (promptCounter.get(sessionId) ?? 0) + 1
          promptCounter.set(sessionId, newCount)
          
          await log(client, `[PROMPT.SUCCESS] Todo-check sent for ${sessionId}`, {
            sessionId,
            unresolvedCount: unresolved.length,
            promptCount: newCount,
            promptCounterSize: promptCounter.size,
          })
        } catch (err: any) {
          await log(client, `[PROMPT.ERROR] Failed for ${sessionId}`, {
            sessionId,
            error: err.message,
            stack: err.stack,
          })
          // Prompt counter stays unchanged on error - will retry on next idle
          await log(client, `[PROMPT.RETRY] Will retry ${sessionId} on next idle`, {
            sessionId,
            promptCounterSize: promptCounter.size,
          })
        }
      }
    },
  }
}
