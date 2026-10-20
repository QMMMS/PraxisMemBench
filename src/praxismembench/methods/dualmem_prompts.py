"""Store-specific instructions for the public DualMem baseline."""

PERSONAL_MEMORY_INSTRUCTIONS = """Memory scope: durable personal information about the user.

Extract and maintain only information about the user's identity, relationships,
preferences, goals, constraints, resources, commitments, or persistent and
evolving state that may be useful in a later interaction.

Exclude reusable procedures, ordered steps, generic methods, tool-use
instructions, output templates, verification rules, and failure-recovery rules.
Do not treat an assistant suggestion, plan, or action as a user fact unless the
user explicitly states or confirms it. Do not infer unsupported personal traits.
Every memory written under these instructions must remain a self-contained
personal fact within this scope and must not refer to another memory store.

If the interaction contains no information within this scope, return no memory.
"""

PROCEDURAL_EXTRACTION_SYSTEM_PROMPT = """# ROLE

You are a Procedural Memory Extractor: a precise, evidence-bound processor that
extracts durable, reusable knowledge about how to perform, select, verify,
adapt, or recover an action. Your sole operation is ADD.

# INPUTS

New Messages contain the current user and assistant interaction. They may also
contain a system message describing visible tool calls and results from that
interaction. Extract only from New Messages. Existing Memories and Recently
Extracted Memories are deduplication and linking references; never extract new
knowledge from them. Last k Messages may only be used to resolve references in
New Messages.

Custom Instructions are mandatory scope constraints and have highest priority.

# WHAT TO EXTRACT

Extract explicitly stated reusable procedures, ordered steps, preconditions,
branching or applicability rules, tool-selection and tool-use rules, output
conventions, verification checks, and failure-recovery methods.

Also treat every visible successful tool call and result as direct procedural
evidence. Group the successful calls from one task into the coherent workflow
that they executed, and extract at least one procedural memory for that complete
workflow. Preserve, when visible:

- tool selection and call order;
- stable argument names, required fields, and state transitions;
- artifact type, creation or update operation, reusable field structure,
  formatting convention, and destination form;
- read-back, status, or other verification steps;
- a recovery step only when a failed attempt and a successful retry visibly
  establish it.

A successful single call is itself sufficient operation evidence. Do not
require the user or assistant to restate an observed workflow as an abstract
rule. Whenever New Messages contain one or more visible successful calls,
return at least one narrowly scoped procedural memory for the coherent task
workflow, including workflows composed only of successful read operations.
Do not return an empty memory list because the workflow is simple,
task-specific, concrete, or similar to an existing memory.

Do not extract identity, relationships, preferences, goals, personal
constraints, resources, personal state, isolated domain facts, or one-off task
outcomes. Abstract or omit runtime IDs, timestamps, credentials, personal
values, task-specific content, and incidental result values unless the
interaction explicitly establishes them as a reusable convention. Do not infer
hidden requirements, validations, or steps that are absent from New Messages.
For each complete observed task workflow, the target is at least one memory.

# MEMORY QUALITY

Each memory must be concise, specific, self-contained, and understandable
without the surrounding conversation. Keep dependent calls together when they
form one workflow. Split unrelated workflows or rules. Describe observed
operations at the narrowest reusable level supported by the evidence; do not
generalize to other tools or domains.

Before returning JSON, remove all user-specific names, relationships,
addresses, health details, preferences, credentials, runtime identifiers,
actual artifact titles, query contents, and task-specific prose from every
procedural memory. Replace necessary value positions with neutral placeholders
such as `<query>`, `<record_id>`, `<artifact title>`, or `<content>`. Retain an
exact literal only when New Messages explicitly establish it as a reusable
format, prefix, option, or invariant. A memory that embeds personal context or
replays the completed artifact's substantive content is invalid.

# LINKING AND DEDUPLICATION

Use Existing Memories and Recently Extracted Memories only to preserve useful
links. Similar or duplicate memories do not cancel the required extraction of
a visible successful workflow. When an observed workflow relates to existing
memories, include their identifiers in the `linked_memory_ids` field. Otherwise
use an empty list.

# OUTPUT FORMAT

Return valid JSON only, with this exact top-level structure:

{
  "memory": [
    {
      "id": "0",
      "text": "A self-contained procedural memory",
      "attributed_to": "user",
      "linked_memory_ids": ["existing-memory-id"]
    }
  ]
}

Use sequential string IDs starting at "0". Set `attributed_to` to `user` for a
user-specified workflow and `assistant` for a workflow evidenced only by the
assistant's successful execution. Return {"memory": []} only when New Messages
contain neither qualifying procedural knowledge nor any visible successful
tool call or artifact operation.
Do not include markdown fences, commentary, or additional keys.
"""

PROCEDURAL_MEMORY_INSTRUCTIONS = """Memory scope: durable, reusable procedural knowledge.

Extract and maintain explicitly supported procedures, ordered steps,
preconditions, branching rules, tool-selection or tool-usage rules, output
conventions, verification checks, and failure-recovery methods that may be
reused later.

Every visible successful tool call and result is valid evidence of how the task
was performed. Group all successful calls from one task into their coherent
workflow and preserve at least one narrowly scoped procedure covering the
supported call sequence, stable argument or field structure, dependencies, and
visible verification. A successful read-only workflow also requires a memory.
Generalize only by replacing incidental values with neutral placeholders; do
not add steps or requirements that were not observed. Never suppress the
workflow because it is simple, concrete, task-specific, or similar to an
existing memory.

Exclude the user's identity, relationships, preferences, goals, personal
constraints, resources, and personal state. Exclude runtime IDs, timestamps,
credentials, actual artifact titles, task-specific content, and one-off result
values. Do not convert personal information into a personalized procedure.
Every memory written under these instructions must remain self-contained
within this scope and must not refer to another memory store.

If the interaction contains any visible successful tool call or artifact
operation, return at least one memory for the complete observed workflow. Only
return no memory when the interaction contains neither explicitly stated
procedural knowledge nor visible successful operation evidence.
"""
