import { appendFileSync } from "node:fs";

const ID = "praxismembench-long-context";
const HISTORY = /<conversation_history source="(previous_sessions|current_session)">\n([\s\S]*?)\n<\/conversation_history>/g;
const estimate = (value) => Math.ceil(JSON.stringify(value).length / 3.5);

function limits(context_window_tokens, reserve_tokens) {
  if (!Number.isSafeInteger(context_window_tokens) || context_window_tokens <= 0 ||
      !Number.isSafeInteger(reserve_tokens) || reserve_tokens < 0 ||
      reserve_tokens >= context_window_tokens) {
    throw new TypeError("Invalid Long Context window/reserve configuration");
  }
  return context_window_tokens - reserve_tokens;
}

function historyBlocks(messages) {
  const blocks = [];
  for (let index = 0; index < messages.length; index++) {
    const message = messages[index];
    if (message.role !== "user") continue;
    const texts = typeof message.content === "string"
      ? [{ part: null, text: message.content }]
      : Array.isArray(message.content)
        ? message.content.flatMap((part, i) => part?.type === "text" && typeof part.text === "string"
          ? [{ part: i, text: part.text }] : [])
        : [];
    for (const { part, text } of texts) {
      for (const match of text.matchAll(HISTORY)) {
        let records;
        try { records = JSON.parse(match[2]); } catch { continue; }
        if (!Array.isArray(records) || !records.every((record) => record &&
            ["user", "assistant", "system"].includes(record.role) && typeof record.content === "string")) {
          continue;
        }
        blocks.push({ index, part, start: match.index, end: match.index + match[0].length,
          source: match[1], full: match[0], records, drop: 0, remove: false });
      }
    }
  }
  return blocks;
}

function retainedBlock(block) {
  if (block.remove || (block.drop > 0 && block.drop >= block.records.length)) return "";
  if (block.drop === 0) return block.full;
  return `<conversation_history source="${block.source}">\n${JSON.stringify(block.records.slice(block.drop))}\n</conversation_history>`;
}

function render(messages, blocks) {
  let result = messages;
  const groups = new Map();
  for (const block of blocks) {
    if (!block.remove && block.drop === 0) continue;
    const key = `${block.index}:${block.part}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(block);
  }
  for (const group of groups.values()) {
    const { index, part } = group[0];
    const message = result[index];
    let text = part === null ? message.content : message.content[part].text;
    for (const block of group.toReversed()) {
      text = text.slice(0, block.start) + retainedBlock(block) + text.slice(block.end);
    }
    const content = part === null ? text : message.content.map((value, i) => i === part ? { ...value, text } : value);
    if (result === messages) result = [...messages];
    result[index] = { ...message, content };
  }
  return result;
}

/** Pure context view: only valid, explicitly tagged user history blocks may shrink.
 * Input messages and their real dialogue/tool/system content are never mutated.
 * Budget uses the shared chars/3.5 estimate.
 */
export function assembleContext({ messages, systemPrompt, tools, context_window_tokens = 128000,
  reserve_tokens = 16000 }) {
  const budget = limits(context_window_tokens, reserve_tokens);
  const known = typeof systemPrompt === "string";
  const blocks = historyBlocks(messages);
  let view = messages;
  const total = () => estimate({ systemPrompt: known ? systemPrompt : "", messages: view, tools });
  if (known) {
    // Each previous_sessions block is a complete archive snapshot. Keep only the latest.
    const snapshots = blocks.filter((block) => block.source === "previous_sessions");
    for (const block of snapshots.slice(0, -1)) block.remove = true;
    view = render(messages, blocks);
    const order = [...blocks.filter((block) => block.source === "previous_sessions"),
      ...blocks.filter((block) => block.source === "current_session")];
    for (const block of order) {
      if (total() <= budget) break;
      if (block.remove) continue;
      if (block.records.length === 0) {
        block.remove = true;
        view = render(messages, blocks);
        continue;
      }
      block.drop = block.records.length;
      view = render(messages, blocks);
      if (total() > budget) continue;
      // Find the smallest oldest-prefix removal that fits the complete serialized view.
      let low = 1;
      let high = block.records.length;
      while (low < high) {
        const mid = Math.floor((low + high) / 2);
        block.drop = mid;
        view = render(messages, blocks);
        if (total() <= budget) high = mid;
        else low = mid + 1;
      }
      block.drop = low;
      view = render(messages, blocks);
    }
  }
  const contextTokens = total();
  const retained = blocks.map((block) => {
    if (!known) return block.full;
    return retainedBlock(block);
  }).filter(Boolean);
  return {
    messages: view,
    estimatedTokens: contextTokens,
    audit: {
      stage: "model",
      context_tokens: contextTokens,
      system_tokens: known ? estimate(systemPrompt) : 0,
      message_tokens: estimate(view),
      tool_tokens: tools === undefined ? 0 : estimate(tools),
      retained_history_tokens: retained.length ? Math.ceil(retained.reduce((sum, text) => sum + JSON.stringify(text).length, 0) / 3.5) : 0,
      dropped_history_messages: blocks.reduce((sum, block) => sum + (block.remove ? block.records.length : block.drop), 0),
      overbudget_tokens: Math.max(0, contextTokens - budget),
      within_budget: known && contextTokens <= budget,
      system_known: known,
      context_window_tokens,
      reserve_tokens,
    },
  };
}

export default {
  id: ID,
  name: "PraxisMemBench Long Context",
  configSchema: {
    jsonSchema: {
      type: "object",
      additionalProperties: false,
      properties: {
        context_window_tokens: { type: "integer", minimum: 1, default: 128000 },
        reserve_tokens: { type: "integer", minimum: 0, default: 16000 },
        audit_path: { type: "string" },
      },
    },
  },
  register(api) {
    const config = api.pluginConfig ?? {};
    const context_window_tokens = config.context_window_tokens ?? 128000;
    const reserve_tokens = config.reserve_tokens ?? 16000;
    limits(context_window_tokens, reserve_tokens);
    api.registerContextEngine(ID, () => ({
      info: { id: ID, name: "Long Context", ownsCompaction: true },
      async ingest() { return { ingested: false }; },
      async compact() { return { ok: true, compacted: false, reason: "Long Context does not summarize" }; },
      async assemble(params) {
        return { messages: params.messages, estimatedTokens: estimate(params.messages) };
      },
    }));
    api.registerProvider({
      id: "praxismembench",
      label: "Benchmark Task Model",
      auth: [],
      wrapStreamFn({ streamFn }) {
        if (typeof streamFn !== "function") throw new Error("StreamFunctionUnavailable");
        return (model, context, options) => {
          const result = assembleContext({ messages: context.messages,
            systemPrompt: context.systemPrompt, tools: context.tools,
            context_window_tokens, reserve_tokens });
          if (config.audit_path) {
            try { appendFileSync(config.audit_path, JSON.stringify(result.audit) + "\n", { mode: 0o600 }); }
            catch { api.logger?.warn?.("Long Context metadata audit write failed"); }
          }
          if (!result.audit.within_budget) throw new Error("ContextBudgetExceeded");
          return streamFn(model, { ...context, messages: result.messages }, options);
        };
      },
    });
  },
};
