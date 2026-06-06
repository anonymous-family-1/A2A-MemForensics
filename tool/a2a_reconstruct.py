#!/usr/bin/env python3

import argparse
import json
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

@dataclass
class AgentCard:
    name: str
    url: str
    description: str
    protocol_version: str
    capabilities: dict
    skills: list[dict]
    provider: dict
    raw: dict

    @property
    def skill_names(self) -> list[str]:
        return [s.get("name", s.get("id", "?")) for s in self.skills]

    @property
    def port(self) -> Optional[str]:
        m = re.search(r':(\d+)', self.url)
        return m.group(1) if m else None

@dataclass
class RpcRequest:
    rpc_id: str
    message_id: str
    role: str
    text: str
    blocking: bool
    execution_mode: Optional[str]
    target_agent: Optional[str]
    user_goal: Optional[str]
    memory_offset: Optional[int]
    raw: dict

@dataclass
class RpcResponse:
    rpc_id: str
    task_id: str
    context_id: str
    state: str
    response_message_id: str
    response_text: str
    history: list[dict]
    artifacts: list[dict]
    embedded_plan: Optional[dict]
    memory_offset: Optional[int]
    raw: dict

@dataclass
class Interaction:
    index: int
    user_goal: str
    agent_card: Optional[AgentCard]
    request: Optional[RpcRequest]
    response: Optional[RpcResponse]
    interaction_type: str

_STRINGS_OFFSET_RE = re.compile(r'^\s*([0-9a-fA-F]+) (.+)$')

def extract_strings(image_path: str, min_len: int = 6,
                    strings_bin: str = "strings") -> list[tuple[int, str]]:
    print(f"[*] Extracting strings from {image_path} ...")
    try:
        result = subprocess.run(
            [strings_bin, "-a", "-t", "x", "-n", str(min_len), image_path],
            capture_output=True, text=True, errors="replace"
        )
        pairs: list[tuple[int, str]] = []
        for raw_line in result.stdout.splitlines():
            m = _STRINGS_OFFSET_RE.match(raw_line)
            if m:
                pairs.append((int(m.group(1), 16), m.group(2)))
        print(f"[*] Extracted {len(pairs):,} raw strings.")
        return pairs
    except FileNotFoundError:
        print(f"[!] '{strings_bin}' not found. Install binutils or pass --strings-bin.")
        sys.exit(1)

_TEMP_TAIL = re.compile(r'\d$')
_TEMP_HEAD = re.compile(r'^C[^a-zA-Z]')

def stitch_degree_splits(
    pairs: list[tuple[int, str]]
) -> list[tuple[int, Optional[int], str]]:
    out: list[tuple[int, Optional[int], str]] = []
    i = 0
    while i < len(pairs):
        start_offset, line = pairs[i]
        end_offset: Optional[int] = None
        while (i + 1 < len(pairs)
               and _TEMP_TAIL.search(line)
               and _TEMP_HEAD.match(pairs[i + 1][1])):
            i += 1
            end_offset = pairs[i][0]
            line = line + '°' + pairs[i][1]
        out.append((start_offset, end_offset, line))
        i += 1
    stitched = len(pairs) - len(out)
    if stitched:
        print(f"[*] Degree-symbol stitching joined {stitched} fragment pair(s).")
    return out

_CONTENT_STOP = re.compile(
    r'^(?:\[[\?0-9]|]0;|\x1b|app\.|node |{"|\{"jsonrpc|"kind"|#!|/home/|import |require\()'
)

def extract_agent_outputs(lines: list[str]) -> list[str]:
    AO_PAT = re.compile(r'"agent_output"\s*:\s*"((?:[^"\\]|\\.){10,})')
    seen: set[str] = set()
    results: list[str] = []
    for line in lines:
        m = AO_PAT.search(line)
        if not m:
            continue
        raw = m.group(1)
        text = (raw.replace('\\n', '\n')
                   .replace('\\"', '"')
                   .replace('\\\\', '\\')
                   .rstrip('"'))
        if text not in seen:
            seen.add(text)
            results.append(text)
    results.sort(key=len, reverse=True)
    return results

def reconstruct_multiline_content(lines: list[str],
                                   header_pattern: re.Pattern) -> Optional[str]:
    header_idx = -1
    for i, line in enumerate(lines):
        if header_pattern.search(line):
            header_idx = i
            break
    if header_idx == -1:
        return None

    parts: list[str] = []
    for idx, line in enumerate(lines[header_idx: header_idx + 100]):
        stripped = line.strip()
        if not stripped:
            continue
        if _CONTENT_STOP.match(stripped):
            break
        if idx == 0:
            m = header_pattern.search(stripped)
            if m:
                stripped = stripped[m.start():].rstrip('"')
        if idx > 0 and parts:
            prev = parts[-1]
            if (prev.endswith(', ') or prev.endswith('- ')) and stripped and stripped[0].islower():
                stripped = '[…]' + stripped
        parts.append(stripped)

    return '\n'.join(parts) if parts else None

def carve_json_objects(lines: list[str],
                       offsets: Optional[list[int]] = None,
                       end_offsets: Optional[list[Optional[int]]] = None) -> list[dict]:
    seen: set[str] = set()
    objects: list[dict] = []

    for line_idx, line in enumerate(lines):
        if '{' not in line:
            continue
        line_offset = offsets[line_idx] if offsets else None
        line_end_offset = end_offsets[line_idx] if end_offsets else None
        for fragment in _balanced_fragments(line):
            try:
                obj = json.loads(fragment)
                if not isinstance(obj, dict):
                    continue
                key = json.dumps(obj, sort_keys=True)
                if key in seen:
                    continue
                seen.add(key)
                if line_offset is not None:
                    obj["_memory_offset"] = line_offset
                if line_end_offset is not None:
                    obj["_memory_offset_end"] = line_end_offset
                objects.append(obj)
            except json.JSONDecodeError:
                pass

    print(f"[*] Carved {len(objects)} unique JSON objects from memory.")
    return objects

def _balanced_fragments(line: str) -> list[str]:
    fragments = []
    depth = 0
    start = -1
    in_string = False
    escape = False

    for i, ch in enumerate(line):
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            if depth > 0:
                depth -= 1
                if depth == 0 and start != -1:
                    fragments.append(line[start:i + 1])
                    start = -1
    return fragments

def classify_objects(objects: list[dict]) -> dict[str, list[dict]]:
    agent_cards: list[dict] = []
    rpc_requests: list[dict] = []
    rpc_responses: list[dict] = []
    artifact_updates: list[dict] = []
    other: list[dict] = []

    for obj in objects:
        if _is_agent_card(obj):
            obj["_a2a_type"] = "agent_card"
            agent_cards.append(obj)
        elif _is_rpc_request(obj):
            obj["_a2a_type"] = "rpc_request"
            rpc_requests.append(obj)
        elif _is_rpc_response(obj):
            obj["_a2a_type"] = "rpc_response"
            rpc_responses.append(obj)
        elif _is_artifact_update(obj):
            obj["_a2a_type"] = "artifact_update"
            artifact_updates.append(obj)
        else:
            other.append(obj)

    print(f"[*] Classified: {len(agent_cards)} agent cards | "
          f"{len(rpc_requests)} RPC requests | "
          f"{len(rpc_responses)} RPC responses | "
          f"{len(artifact_updates)} artifact updates")
    return {
        "agent_cards": agent_cards,
        "rpc_requests": rpc_requests,
        "rpc_responses": rpc_responses,
        "artifact_updates": artifact_updates,
        "other": other,
    }

def _is_agent_card(obj: dict) -> bool:
    return (
        "protocolVersion" in obj
        and "skills" in obj
        and "capabilities" in obj
        and "url" in obj
        and "name" in obj
    )

def _is_rpc_request(obj: dict) -> bool:
    return (
        obj.get("jsonrpc") == "2.0"
        and obj.get("method") == "message/send"
        and "params" in obj
    )

def _is_rpc_response(obj: dict) -> bool:
    result = obj.get("result", {})
    return (
        obj.get("jsonrpc") == "2.0"
        and "result" in obj
        and isinstance(result, dict)
        and (result.get("kind") == "task" or "contextId" in result)
    )

def _is_artifact_update(obj: dict) -> bool:
    return (
        obj.get("kind") == "artifact-update"
        and isinstance(obj.get("artifact"), dict)
        and "taskId" in obj
    )

def parse_agent_card(raw: dict) -> AgentCard:
    return AgentCard(
        name=raw.get("name", "Unknown"),
        url=raw.get("url", ""),
        description=raw.get("description", ""),
        protocol_version=raw.get("protocolVersion", ""),
        capabilities=raw.get("capabilities", {}),
        skills=raw.get("skills", []),
        provider=raw.get("provider", {}),
        raw=raw,
    )

def parse_rpc_request(raw: dict) -> RpcRequest:
    params = raw.get("params", {})
    msg = params.get("message", {})
    config = params.get("configuration", {})

    parts = msg.get("parts", [])
    full_text = " ".join(
        p.get("text", "") for p in parts if p.get("kind") == "text"
    )

    exec_mode = None
    target_agent = None
    user_goal = None
    if "Execution mode:" in full_text:
        m = re.search(r'Execution mode:\s*([\w-]+)', full_text)
        if m:
            exec_mode = m.group(1)
        m = re.search(r'Target agent:\s*([\w-]+)', full_text)
        if m:
            target_agent = m.group(1)
        m = re.search(r'User goal:\s*"?([^"\n]+)"?', full_text)
        if m:
            user_goal = m.group(1).strip().strip('"')
    else:
        user_goal = full_text.strip().strip('"')

    return RpcRequest(
        rpc_id=str(raw.get("id", "")),
        message_id=msg.get("messageId", ""),
        role=msg.get("role", "user"),
        text=full_text,
        blocking=config.get("blocking", False),
        execution_mode=exec_mode,
        target_agent=target_agent,
        user_goal=user_goal,
        memory_offset=raw.get("_memory_offset"),
        raw=raw,
    )

def parse_rpc_response(raw: dict) -> RpcResponse:
    result = raw.get("result", {})
    status = result.get("status", {})
    status_msg = status.get("message", {})

    resp_parts = status_msg.get("parts", [])
    resp_text = " ".join(
        p.get("text", "") for p in resp_parts if p.get("kind") == "text"
    )

    embedded_plan = _extract_embedded_plan(resp_text)
    if embedded_plan is None:
        embedded_plan = _extract_plan_from_artifacts(result.get("artifacts", []))

    return RpcResponse(
        rpc_id=str(raw.get("id", "")),
        task_id=result.get("id", ""),
        context_id=result.get("contextId", ""),
        state=status.get("state", "unknown"),
        response_message_id=status_msg.get("messageId", ""),
        response_text=resp_text,
        history=result.get("history", []),
        artifacts=result.get("artifacts", []),
        embedded_plan=embedded_plan,
        memory_offset=raw.get("_memory_offset"),
        raw=raw,
    )

def _extract_embedded_plan(text: str) -> Optional[dict]:
    t = text.strip()
    if not t.startswith('{'):
        return None

    for frag in _balanced_fragments(t):
        try:
            obj = json.loads(frag)
            if isinstance(obj, dict) and ("plan" in obj or "user_request" in obj):
                return obj
        except json.JSONDecodeError:
            pass

    _is_plan = ('"plan"' in t and '"execution_mode"' in t)
    _is_discovery = '"discovery_type"' in t or '"discovered_agent"' in t
    if _is_plan or _is_discovery:
        partial: dict = {"_partial": True}
        for key, pat in [
            ("user_request",    r'"user_request"\s*:\s*"((?:[^"\\]|\\.)+)"'),
            ("execution_mode",  r'"execution_mode"\s*:\s*"([^"]+)"'),
            ("target_agent",    r'"target_agent"\s*:\s*"([^"]+)"'),
            ("selected_agent",  r'"selected_agent"\s*:\s*"([^"]+)"'),
            ("discovery_type",  r'"discovery_type"\s*:\s*"([^"]+)"'),
        ]:
            m = re.search(pat, t)
            if m:
                partial[key] = m.group(1).replace('\\"', '"').replace('\\\\', '\\')

        steps_text = re.search(r'"plan_steps"\s*:\s*(\[.*?\])', t, re.DOTALL)
        if steps_text:
            try:
                partial["plan_steps"] = json.loads(steps_text.group(1))
            except json.JSONDecodeError:
                pass

        partial["agent_output"] = ""
        return partial if len(partial) > 2 else None

    return None

def _extract_plan_from_artifacts(artifacts: list[dict]) -> Optional[dict]:
    for art in artifacts:
        for part in art.get("parts", []):
            if part.get("kind") == "data":
                data = part.get("data", {})
                if isinstance(data, dict) and (
                    "plan" in data
                    or "user_request" in data
                    or "discovery_type" in data
                    or "execution_mode" in data
                ):
                    return data
    return None

_PR_TASK_ID    = re.compile(r'"kind"\s*:\s*"task"[^}]*?"id"\s*:\s*"([0-9a-f-]{36})"')
_PR_CTX_ID     = re.compile(r'"contextId"\s*:\s*"([0-9a-f-]{36})"')
_PR_STATE      = re.compile(r'"state"\s*:\s*"(completed|working|failed|submitted|input-required)"')
_PR_RESP_MSGID = re.compile(r'"role"\s*:\s*"agent"[^}]*?"messageId"\s*:\s*"([0-9a-f-]{36})"')
_PR_RPC_ID     = re.compile(r'"jsonrpc"\s*:\s*"2\.0"\s*,\s*"id"\s*:\s*"?(\w+)"?')
_PR_TEXT       = re.compile(r'"text"\s*:\s*"((?:[^"\\]|\\.){20,})')

def extract_partial_responses(lines: list[str]) -> list[RpcResponse]:
    results: list[RpcResponse] = []

    for line in lines:
        if '"kind":"task"' not in line and '"kind": "task"' not in line:
            continue
        if '"jsonrpc"' not in line:
            continue

        m_task = _PR_TASK_ID.search(line)
        m_ctx  = _PR_CTX_ID.search(line)
        m_state = _PR_STATE.search(line)
        if not (m_task and m_ctx and m_state):
            continue

        task_id    = m_task.group(1)
        context_id = m_ctx.group(1)
        state      = m_state.group(1)

        m_rpc  = _PR_RPC_ID.search(line)
        rpc_id = m_rpc.group(1) if m_rpc else "1"

        m_rmid = _PR_RESP_MSGID.search(line)
        response_message_id = m_rmid.group(1) if m_rmid else ""

        text_matches = _PR_TEXT.findall(line)
        resp_text = max(text_matches, key=len) if text_matches else ""
        resp_text = (resp_text
                     .replace('\\n', '\n')
                     .replace('\\"', '"')
                     .replace('\\\\', '\\'))

        embedded_plan = _extract_embedded_plan(resp_text)

        history = _extract_history_from_line(line)

        results.append(RpcResponse(
            rpc_id=rpc_id,
            task_id=task_id,
            context_id=context_id,
            state=state,
            response_message_id=response_message_id,
            response_text=resp_text,
            history=history,
            artifacts=[],
            embedded_plan=embedded_plan,
            memory_offset=None,
            raw={"_source": "partial_regex", "_preview": line[:120]},
        ))

    by_task: dict[str, RpcResponse] = {}
    for r in results:
        if r.task_id not in by_task or r.resp_text_len() > by_task[r.task_id].resp_text_len():
            by_task[r.task_id] = r

    unique = list(by_task.values())
    if unique:
        print(f"[*] Partial-response regex fallback recovered {len(unique)} response(s).")
    return unique

def _extract_history_from_line(line: str) -> list[dict]:
    history: list[dict] = []
    for m in re.finditer(
        r'"role"\s*:\s*"(user|agent)"[^}]*?'
        r'"kind"\s*:\s*"text"\s*,\s*"text"\s*:\s*"([^"]{5,200})"',
        line
    ):
        history.append({"role": m.group(1), "text": m.group(2)})
    return history

def _resp_text_len(self) -> int:
    return len(self.response_text)

RpcResponse.resp_text_len = _resp_text_len

def _get_history_user_text(resp: RpcResponse) -> Optional[str]:
    for entry in resp.history:
        if entry.get("role") != "user":
            continue
        if "parts" in entry:
            for p in entry.get("parts", []):
                if p.get("kind") == "text":
                    return p.get("text", "")
        if "text" in entry:
            return entry["text"]
    return None

def _pick_best_response(req: RpcRequest, candidates: list[RpcResponse],
                        used: set[str]) -> Optional[RpcResponse]:
    available = [r for r in candidates if r.task_id not in used]
    if not available:
        return None
    if len(available) == 1:
        return available[0]

    req_prefix = req.text.strip()[:60].lower()

    if req_prefix:
        for r in available:
            hist_text = _get_history_user_text(r)
            if hist_text and hist_text.strip()[:60].lower() == req_prefix:
                return r

    def _has_conflicting_history(r: RpcResponse) -> bool:
        hist_text = _get_history_user_text(r)
        if not hist_text:
            return False
        return hist_text.strip()[:60].lower() != req_prefix

    filtered = [r for r in available if not _has_conflicting_history(r)]
    pool = filtered if filtered else available

    def _looks_like_plan(r: RpcResponse) -> bool:
        if r.embedded_plan:
            return True
        t = r.response_text.strip()
        return t.startswith('{') and any(k in t for k in (
            '"plan"', '"execution_mode"', '"user_request"',
            '"discovery_type"', '"discovered_agent"'
        ))

    if req.execution_mode:
        with_plan = [r for r in pool if _looks_like_plan(r)]
        return with_plan[0] if with_plan else pool[0]
    else:
        without_plan = [r for r in pool if not _looks_like_plan(r)]
        return without_plan[0] if without_plan else pool[0]

def reconstruct_interactions(
    agent_cards: list[AgentCard],
    requests: list[RpcRequest],
    responses: list[RpcResponse],
) -> list[Interaction]:
    interactions: list[Interaction] = []

    resp_by_id: dict[str, list[RpcResponse]] = {}
    for r in responses:
        resp_by_id.setdefault(r.rpc_id, []).append(r)

    used_task_ids: set[str] = set()

    for req in requests:
        candidates = resp_by_id.get(req.rpc_id, [])
        resp = _pick_best_response(req, candidates, used_task_ids)

        if resp:
            used_task_ids.add(resp.task_id)

        goal = req.user_goal or req.text

        card = _match_agent_card(req, resp, agent_cards)

        itype = "planner-orchestrated" if req.execution_mode else "direct"

        interactions.append(Interaction(
            index=len(interactions) + 1,
            user_goal=goal,
            agent_card=card,
            request=req,
            response=resp,
            interaction_type=itype,
        ))

    matched_resp_ids = {i.response.rpc_id for i in interactions if i.response}
    for resp in responses:
        if resp.rpc_id not in matched_resp_ids:
            goal = _goal_from_response(resp)
            card = _match_agent_card_from_response(resp, agent_cards)
            interactions.append(Interaction(
                index=len(interactions) + 1,
                user_goal=goal or "(goal not recovered)",
                agent_card=card,
                request=None,
                response=resp,
                interaction_type="partial (request not recovered)",
            ))

    return interactions

def _match_agent_card(req: RpcRequest, resp: Optional[RpcResponse],
                      cards: list[AgentCard]) -> Optional[AgentCard]:
    if req.target_agent:
        slug = req.target_agent.lower().replace("-", " ").replace("_", " ")
        for card in cards:
            if slug in card.name.lower():
                return card

    if resp and resp.embedded_plan:
        da = resp.embedded_plan.get("discovered_agent", {})
        da_name = da.get("name", "")
        if da_name:
            for card in cards:
                if da_name.lower() in card.name.lower():
                    return card

    for card in cards:
        if card.name.lower() in req.text.lower():
            return card

    if len(cards) == 1:
        return cards[0]

    return None

def _match_agent_card_from_response(resp: RpcResponse,
                                     cards: list[AgentCard]) -> Optional[AgentCard]:
    if resp.embedded_plan:
        name = resp.embedded_plan.get("discovered_agent", {}).get("name", "")
        for card in cards:
            if name and name.lower() in card.name.lower():
                return card
    return None

def _goal_from_response(resp: RpcResponse) -> Optional[str]:
    if resp.embedded_plan:
        plan = resp.embedded_plan.get("plan", {})
        return plan.get("user_goal") or resp.embedded_plan.get("user_request")
    return None

W = 72

def _bar(char: str = "─") -> str:
    return char * W

def _header(title: str, char: str = "═") -> str:
    pad = max(0, W - len(title) - 4)
    return f"╔══ {title} {'═' * pad}╗"

def _step(n: int, label: str, status: str = "") -> str:
    tag = f"[STEP {n}]"
    s = f"{status}  " if status else ""
    return f"\n  {tag} {label}  {s}"

def _indent(text: str, prefix: str = "      ") -> str:
    return textwrap.indent(text, prefix)

def print_interaction(ix: Interaction) -> None:
    status_icon = "✓" if (ix.response and ix.response.state == "completed") else "?"
    print()
    print(_bar("═"))
    print(f"  INTERACTION #{ix.index}  [{ix.interaction_type.upper()}]  {status_icon}")
    print(_bar("═"))
    print(f"  USER GOAL: {ix.user_goal}")
    print()

    print(_bar("─"))
    print("  STEP 1 — AGENT DISCOVERY (/.well-known/agent-card.json)")
    print(_bar("─"))
    card = ix.agent_card
    if card:
        print(f"    Name        : {card.name}")
        print(f"    URL         : {card.url}")
        print(f"    Protocol    : A2A {card.protocol_version}")
        print(f"    Description : {card.description}")
        cap = card.capabilities
        print(f"    Capabilities:")
        print(f"      streaming              = {cap.get('streaming')}")
        print(f"      pushNotifications      = {cap.get('pushNotifications')}")
        print(f"      stateTransitionHistory = {cap.get('stateTransitionHistory')}")
        print(f"    Skills ({len(card.skills)}):")
        for sk in card.skills:
            tags = ", ".join(sk.get("tags", []))
            print(f"      [{sk.get('id')}]  {sk.get('name')}")
            print(f"        {sk.get('description', '')}")
            if tags:
                print(f"        tags: {tags}")
            examples = sk.get("examples", [])
            if examples:
                print(f"        example: \"{examples[0]}\"")
        if card.provider:
            print(f"    Provider    : {card.provider.get('organization', '')} "
                  f"<{card.provider.get('url', '')}>")
    else:
        print("    (agent card not recovered for this interaction)")

    print()
    print(_bar("─"))
    print("  STEP 2 — TASK SUBMISSION  (JSON-RPC message/send)")
    print(_bar("─"))
    req = ix.request
    if req:
        print(f"    JSON-RPC id : {req.rpc_id}")
        print(f"    Message ID  : {req.message_id or '(not recovered)'}")
        if req.memory_offset is not None:
            print(f"    Memory Offset: 0x{req.memory_offset:08x}  ({req.memory_offset} bytes)")
        print(f"    Role        : {req.role}")
        print(f"    Blocking    : {req.blocking}")
        if req.execution_mode:
            print(f"    Exec Mode   : {req.execution_mode}")
        if req.target_agent:
            print(f"    Target Agent: {req.target_agent}")
        print(f"    Payload:")
        clean_req = {
            "jsonrpc": "2.0",
            "id": req.rpc_id,
            "method": "message/send",
            "params": req.raw.get("params", {}),
        }
        req_json = json.dumps(clean_req, indent=6)
        if len(req_json) > 1200:
            req_json = req_json[:1200] + "\n      ... (truncated)"
        print(_indent(req_json, "      "))
    else:
        print("    (request not recovered for this interaction)")

    print()
    print(_bar("─"))
    print("  STEP 3 — TASK EXECUTION")
    print(_bar("─"))
    resp = ix.response
    if resp:
        print(f"    Task ID     : {resp.task_id}")
        print(f"    Context ID  : {resp.context_id}")
        if resp.memory_offset is not None:
            print(f"    Memory Offset: 0x{resp.memory_offset:08x}  ({resp.memory_offset} bytes)")
        print(f"    Final State : {resp.state.upper()}")

        if resp.history:
            print(f"    History ({len(resp.history)} entries):")
            for entry in resp.history:
                role = entry.get("role", "?")
                parts = entry.get("parts", [])
                if parts:
                    for p in parts:
                        if p.get("kind") == "text":
                            snippet = p["text"][:120].replace("\n", " ")
                            print(f"      [{role}] \"{snippet}\"")
                elif "text" in entry:
                    snippet = entry["text"][:120].replace("\n", " ")
                    print(f"      [{role}] \"{snippet}\"")
        else:
            print("    History     : (not recovered)")

        plan_data = resp.embedded_plan
        if plan_data:
            plan = plan_data.get("plan", {})
            if plan:
                print()
                print(f"    Planner Execution Plan:")
                print(f"      execution_mode : {plan.get('execution_mode', '?')}")
                print(f"      target_agent   : {plan.get('target_agent', '?')}")
                steps = plan.get("plan_steps", [])
                if steps:
                    print(f"      plan_steps ({len(steps)}):")
                    for step in steps:
                        print(f"        step {step.get('step')}: agent={step.get('agent')} "
                              f"skill={step.get('skill')}")
                        print(f"          input: \"{step.get('input', '')}\"")
                        print(f"          expected_output: {step.get('expected_output', '')}")
    else:
        print("    (task not recovered for this interaction)")

    print()
    print(_bar("─"))
    print("  STEP 4 — RESULT")
    print(_bar("─"))
    if resp:
        print(f"    Response Message ID: {resp.response_message_id or '(not recovered)'}")

        plan_data = resp.embedded_plan

        if plan_data:
            if plan_data.get("_partial"):
                print(f"    [Note: plan JSON was truncated in memory — key fields recovered by regex]")
            exec_mode = plan_data.get("execution_mode") or (
                plan_data.get("plan", {}).get("execution_mode") if isinstance(plan_data.get("plan"), dict) else None
            )
            tgt = plan_data.get("target_agent") or (
                plan_data.get("plan", {}).get("target_agent") if isinstance(plan_data.get("plan"), dict) else None
            )
            sel = plan_data.get("selected_agent") or plan_data.get("plan", {}).get("target_agent", "")
            disc = plan_data.get("discovery_type", "")
            if exec_mode:
                print(f"    Execution mode : {exec_mode}")
            if disc:
                print(f"    Discovery type : {disc}")
            if tgt:
                print(f"    Target agent   : {tgt}")
            if sel:
                print(f"    Selected agent : {sel}")

            output = plan_data.get("agent_output", "")
            if output:
                print(f"    Agent Output (via planner):")
                if isinstance(output, dict):
                    out_lines = json.dumps(output, indent=6).splitlines()
                else:
                    out_lines = str(output).splitlines()
                for line in out_lines[:40]:
                    print(f"      {line}")
                if len(out_lines) > 40:
                    print(f"      ... ({len(out_lines) - 40} more lines)")
            elif resp.response_text and not resp.response_text.strip().startswith('{'):
                print(f"    Agent Output (via planner):")
                for line in resp.response_text.splitlines()[:40]:
                    print(f"      {line}")

        elif resp.response_text:
            print(f"    Response Content:")
            for line in resp.response_text[:1500].splitlines()[:40]:
                print(f"      {line}")

        if resp.artifacts:
            print(f"    Artifacts ({len(resp.artifacts)}):")
            for art in resp.artifacts:
                print(f"      [{art.get('artifactId', '?')}] {art.get('name', '?')}")
    else:
        print("    (result not recovered for this interaction)")

    print()

def print_summary(interactions: list[Interaction],
                  agent_cards: list[AgentCard],
                  requests: list[RpcRequest],
                  responses: list[RpcResponse]) -> None:
    print()
    print(_bar("═"))
    print("  RECONSTRUCTION SUMMARY")
    print(_bar("═"))
    print(f"  Agent cards recovered  : {len(agent_cards)}")
    print(f"  RPC requests recovered : {len(requests)}")
    print(f"  RPC responses recovered: {len(responses)}")
    print(f"  Interactions linked    : {len(interactions)}")
    print()
    print("  Agent cards found:")
    for card in agent_cards:
        print(f"    • {card.name}  ({card.url})  protocol={card.protocol_version}")
    print()
    print("  Interaction index:")
    for ix in interactions:
        state = ix.response.state.upper() if ix.response else "NO RESPONSE"
        goal_preview = ix.user_goal[:60] + "..." if len(ix.user_goal) > 60 else ix.user_goal
        print(f"    #{ix.index}  [{state}]  [{ix.interaction_type}]")
        print(f"         Goal: \"{goal_preview}\"")
        if ix.agent_card:
            print(f"         Agent: {ix.agent_card.name}  ({ix.agent_card.url})")
        if ix.response:
            print(f"         Task ID: {ix.response.task_id}")
            print(f"         Context ID: {ix.response.context_id}")
    print(_bar("═"))

def _strip_internal(obj: dict) -> dict:
    return {k: v for k, v in obj.items() if not k.startswith("_")}

def _fmt_offset(offset: Optional[int],
                end_offset: Optional[int] = None) -> str:
    if offset is None:
        return "(not recovered — partial regex match)"
    s = f"0x{offset:08x}  ({offset:,} bytes)"
    if end_offset is not None:
        s += f"  →  0x{end_offset:08x}  ({end_offset:,} bytes)"
    return s

def print_raw_objects(classified: dict,
                      partial_responses: list[RpcResponse]) -> None:
    sections = [
        ("AGENT CARDS",      classified["agent_cards"]),
        ("RPC REQUESTS",     classified["rpc_requests"]),
        ("RPC RESPONSES",    classified["rpc_responses"]),
        ("ARTIFACT UPDATES", classified["artifact_updates"]),
    ]

    for title, objects in sections:
        print()
        print(_bar("─"))
        print(f"  {title}  ({len(objects)})")
        print(_bar("─"))
        if not objects:
            print("  (none found)")
            continue
        for i, raw in enumerate(objects, 1):
            offset = raw.get("_memory_offset")
            end_offset = raw.get("_memory_offset_end")
            clean = _strip_internal(raw)
            print(f"\n  [{i}]  Memory Offset: {_fmt_offset(offset, end_offset)}")
            print(json.dumps(clean, indent=4))

    if partial_responses:
        print()
        print(_bar("─"))
        print(f"  PARTIAL RESPONSES  ({len(partial_responses)})")
        print("  NOTE: not recovered as complete JSON — fields extracted via")
        print("        regex from page-boundary-truncated strings.")
        print(_bar("─"))
        for i, resp in enumerate(partial_responses, 1):
            print(f"\n  [{i}]  Memory Offset: {_fmt_offset(None)}")
            partial_obj: dict = {
                "task_id":      resp.task_id,
                "context_id":   resp.context_id,
                "state":        resp.state,
                "response_text": resp.response_text,
            }
            if resp.history:
                partial_obj["history"] = resp.history
            print(json.dumps(partial_obj, indent=4))

def build_json_report(classified: dict,
                      partial_responses: list[RpcResponse]) -> dict:
    def _annotate(raw: dict) -> dict:
        offset = raw.get("_memory_offset")
        end_offset = raw.get("_memory_offset_end")
        entry: dict = {
            "type": raw.get("_a2a_type", "unknown"),
            "memory_offset": offset,
            "memory_offset_hex": f"0x{offset:08x}" if offset is not None else None,
        }
        if end_offset is not None:
            entry["memory_offset_end"] = end_offset
            entry["memory_offset_end_hex"] = f"0x{end_offset:08x}"
        entry["object"] = _strip_internal(raw)
        return entry

    partial_list = []
    for resp in partial_responses:
        entry: dict = {
            "type": "rpc_response_partial",
            "memory_offset": None,
            "memory_offset_hex": None,
            "note": "partial regex extraction — full JSON not recovered",
            "object": {
                "task_id":      resp.task_id,
                "context_id":   resp.context_id,
                "state":        resp.state,
                "response_text": resp.response_text,
                "history":      resp.history,
            },
        }
        partial_list.append(entry)

    return {
        "agent_cards":      [_annotate(o) for o in classified["agent_cards"]],
        "rpc_requests":     [_annotate(o) for o in classified["rpc_requests"]],
        "rpc_responses":    [_annotate(o) for o in classified["rpc_responses"]],
        "artifact_updates": [_annotate(o) for o in classified["artifact_updates"]],
        "partial_responses": partial_list,
    }

class _Tee:
    def __init__(self, real_stdout, file_obj) -> None:
        self._real = real_stdout
        self._file = file_obj

    def write(self, s: str) -> int:
        self._real.write(s)
        self._file.write(s)
        return len(s)

    def flush(self) -> None:
        self._real.flush()
        self._file.flush()

    def isatty(self) -> bool:
        return False

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reconstruct A2A protocol interactions from a memory image."
    )
    parser.add_argument("image", help="Path to the memory image file")
    parser.add_argument("--output", "-o", default=None,
                        help="Write JSON report to this file")
    parser.add_argument("--text-output", "-t", default=None,
                        help="Write full text reconstruction report to this file")
    parser.add_argument("--dump", "-d", default=None,
                        help="Write all carved JSON objects (with memory offsets) "
                             "as a flat JSON array to this file")
    parser.add_argument("--strings-bin", default="strings",
                        help="Path to the strings(1) binary")
    parser.add_argument("--min-len", type=int, default=6,
                        help="Minimum string length (default: 6)")
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"[!] File not found: {image_path}")
        sys.exit(1)

    _text_file = None
    _real_stdout = sys.stdout
    if args.text_output:
        _text_file = open(args.text_output, "w", encoding="utf-8")
        sys.stdout = _Tee(_real_stdout, _text_file)

    try:
        _main_body(image_path, args)
    finally:
        if _text_file:
            sys.stdout = _real_stdout
            _text_file.close()
            print(f"[*] Text report written to: {args.text_output}")

def _main_body(image_path: Path, args) -> None:
    pairs = extract_strings(str(image_path), args.min_len, args.strings_bin)

    triples = stitch_degree_splits(pairs)

    lines       = [l   for _, _, l in triples]
    offsets     = [o   for o, _, _ in triples]
    end_offsets = [e   for _, e, _ in triples]

    agent_outputs = extract_agent_outputs(lines)
    if agent_outputs:
        print(f"[*] Extracted {len(agent_outputs)} agent_output candidate(s), "
              f"longest: {len(agent_outputs[0])} chars.")

    multiline_content: Optional[str] = None
    if agent_outputs:
        multiline_content = agent_outputs[0]
        best = multiline_content.strip().rstrip('"')
        if len(best) < 200:
            prefix = re.escape(best[:30]) if best else None
            if prefix:
                derived_pat = re.compile(prefix, re.IGNORECASE)
                longer = reconstruct_multiline_content(lines, derived_pat)
                _json_spill = re.compile(
                    r'"(?:taskId|contextId|messageId|jsonrpc|method|role|kind)"\s*:')
                if longer and len(longer) > len(multiline_content) and not _json_spill.search(longer):
                    multiline_content = longer
        if multiline_content:
            print(f"[*] Best agent_output candidate: {len(multiline_content)} chars.")

    objects = carve_json_objects(lines, offsets, end_offsets)

    classified = classify_objects(objects)

    agent_cards = [parse_agent_card(o) for o in classified["agent_cards"]]
    requests    = [parse_rpc_request(o)  for o in classified["rpc_requests"]]
    responses   = [parse_rpc_response(o) for o in classified["rpc_responses"]]

    artifact_updates_raw = classified.get("artifact_updates", [])
    artifact_by_task: dict[str, list[dict]] = {}
    for au in artifact_updates_raw:
        tid = au.get("taskId", "")
        if tid:
            artifact_by_task.setdefault(tid, []).append(au.get("artifact", {}))
    if artifact_by_task:
        print(f"[*] Indexed {len(artifact_by_task)} task(s) with artifact-update event(s).")

    if not responses:
        print("[*] No complete RPC responses parsed — running partial-response fallback ...")
        responses = extract_partial_responses(lines)
    else:
        known_ids = {r.task_id for r in responses}
        extras = [r for r in extract_partial_responses(lines)
                  if r.task_id not in known_ids]
        responses.extend(extras)

    if args.dump:
        partial_only = [r for r in responses if r.raw.get("_source") == "partial_regex"]
        a2a_buckets = (
            classified["agent_cards"]
            + classified["rpc_requests"]
            + classified["rpc_responses"]
            + classified["artifact_updates"]
        )
        def _dump_entry(o: dict) -> dict:
            offset = o.get("_memory_offset")
            end_offset = o.get("_memory_offset_end")
            entry: dict = {
                "type": o.get("_a2a_type", "unknown"),
                "memory_offset": offset,
                "memory_offset_hex": f"0x{offset:08x}" if offset is not None else None,
            }
            if end_offset is not None:
                entry["memory_offset_end"] = end_offset
                entry["memory_offset_end_hex"] = f"0x{end_offset:08x}"
            entry["object"] = _strip_internal(o)
            return entry

        dump_array = [_dump_entry(o) for o in a2a_buckets]
        for resp in partial_only:
            dump_array.append({
                "type": "rpc_response_partial",
                "memory_offset": None,
                "memory_offset_hex": None,
                "note": "partial — page-boundary truncation, fields recovered via regex",
                "object": {
                    "task_id":       resp.task_id,
                    "context_id":    resp.context_id,
                    "state":         resp.state,
                    "response_text": resp.response_text,
                    "history":       resp.history,
                },
            })
        Path(args.dump).write_text(json.dumps(dump_array, indent=2))
        print(f"[*] Dumped {len(dump_array)} A2A objects to: {args.dump} "
              f"({len(partial_only)} partial)")

    print("[*] Reconstructing interactions ...")
    interactions = reconstruct_interactions(agent_cards, requests, responses)
    print(f"[*] Reconstructed {len(interactions)} interaction(s).")

    for ix in interactions:
        if not ix.response:
            continue
        resp = ix.response
        if resp.embedded_plan is None and resp.task_id in artifact_by_task:
            extracted = _extract_plan_from_artifacts(artifact_by_task[resp.task_id])
            if extracted is not None:
                resp.embedded_plan = extracted

    def _best_content_for(truncated: str) -> Optional[str]:
        trunc = truncated.strip()

        if not trunc or len(trunc) < 50:
            if multiline_content:
                return multiline_content
            return agent_outputs[0] if agent_outputs else None

        if multiline_content:
            mc = multiline_content.strip()
            if mc.startswith(trunc[:20]) or trunc[:20] in mc[:80]:
                return multiline_content

        for ao in agent_outputs:
            if ao.startswith(trunc[:20]) or trunc[:20] in ao[:80]:
                return ao

        if agent_outputs and len(trunc) < 200:
            return agent_outputs[0]

        return None

    for ix in interactions:
        if not ix.response:
            continue
        resp = ix.response

        if resp.response_text and len(resp.response_text.strip()) < 200:
            better = _best_content_for(resp.response_text)
            if better:
                resp.response_text = better

        if resp.embedded_plan and isinstance(resp.embedded_plan.get("agent_output"), str):
            ao = resp.embedded_plan["agent_output"]
            if len(ao.strip()) < 200:
                better = _best_content_for(ao)
                if better:
                    resp.embedded_plan["agent_output"] = better

    partial_only = [r for r in responses
                    if r.raw.get("_source") == "partial_regex"]

    print()
    print("=" * W)
    print("  A2A MEMORY FORENSICS — RAW JSON OBJECTS")
    print(f"  Image : {image_path.name}")
    counts = (f"{len(classified['agent_cards'])} agent cards | "
              f"{len(classified['rpc_requests'])} RPC requests | "
              f"{len(classified['rpc_responses'])} RPC responses | "
              f"{len(classified['artifact_updates'])} artifact updates")
    if partial_only:
        counts += f" | {len(partial_only)} partial (regex)"
    print(f"  Found : {counts}")
    print("=" * W)

    print_raw_objects(classified, partial_only)

    print()
    print("=" * W)

    if args.output:
        report = build_json_report(classified, partial_only)
        Path(args.output).write_text(json.dumps(report, indent=2))
        print(f"[*] JSON report written to: {args.output}")

if __name__ == "__main__":
    main()
