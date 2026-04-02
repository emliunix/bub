import type { Plugin } from "@opencode-ai/plugin"

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
  let todos: TodoItem[] = []
  let sessionId: string | null = null

  await log(client, "plugin initialized")

  return {
    event: async ({ event }) => {
      if (event.type === "todo.updated") {
        sessionId = event.properties?.sessionID ?? sessionId
        todos = event.properties?.todos ?? todos
        await log(client, `todo.updated: ${todos.length} items`, {
          sessionId,
          todos: todos.map((t) => ({ content: t.content, status: t.status })),
        })
      }

      if (event.type === "session.status" && event.properties?.status?.type === "idle") {
        sessionId = event.properties?.sessionID ?? sessionId
        await log(client, "session.status idle", {
          sessionId,
          todoCount: todos.length,
          unresolved: todos.filter(
            (t) => t.status !== "completed" && t.status !== "cancelled",
          ).length,
        })

        if (!sessionId) {
          await log(client, "idle skipped: no sessionId")
          return
        }

        const unresolved = todos.filter(
          (t) => t.status !== "completed" && t.status !== "cancelled",
        )

        if (unresolved.length === 0) {
          await log(client, "idle: all resolved, skipping")
          return
        }

        const items = unresolved
          .map((t, i) => `${i + 1}. [${t.status}] ${t.content}`)
          .join("\n")

        const body = [
          "<todo-check>",
          "You have unfinished todo items:",
          "",
          items,
          "",
          "Review each item. If all are addressed, reply TODO_CHECKED to dismiss.",
          "If any item is genuinely incomplete, continue working on it.",
          "</todo-check>",
        ].join("\n")

        await log(client, `sending prompt: ${unresolved.length} unresolved`)

        try {
          await client.session.prompt({
            path: { id: sessionId },
            body: {
              parts: [{ type: "text", text: body }],
            },
          })
          await log(client, "prompt sent ok")
        } catch (err: any) {
          await log(client, `prompt failed: ${err.message}`)
        }
      }
    },
  }
}
