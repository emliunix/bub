so record some of the patterns I came up:

- traces: a separate topics tracking tape (context) lives alongside the main tape, after each turn it summarizes the topic and development, and keep in it's own context.
- recall: analyze user intention, and topics from history and tracked topics. detect topic switch, and pull enough information to inject into the prompt
- ask_parent: on fork, the parent tape is passed down to subagent, and when the subagent needs more information, it can spawn a special ask tool (which is a nested subagent with parent's tape snapshot), so it should be restricted to chat only, no tool calls. And those asks will be passed back to parent on finish.
- ask_child: the same, but in the other direction. the subagent may return not only the result, but also it's tape (not the merge back behavior, but just a pointer to it's finalized state). so the parent can push to ask more information or resume with another task.
- saved_child: continue of ask_child, so we can make the child explore first and return when it has enough context. and the parent decides to keep a snapshot of it. and resume it later maybe in parallel for different kinds of tasks.
- supervised: an accompany agent can not only summarize and inject context, but also supervise with more topic focused mind. so when it's detected it gets distracted or fall into a repeated error hell, we can inject a forced phase change to rethink/reorganize the work
- setup_constriants: to not be distracted, we can set say folder list r/w permissions, tool call allow list, with the reasons explained to start real tool calls.
