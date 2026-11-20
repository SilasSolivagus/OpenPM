#!/usr/bin/env python3
"""Static preflight gate for walkthrough.html and spec.json (spec-v2) deliverables."""

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


INTERACTIVE_CLASSES = {"pwx-track", "pwx-modal"}
INTERACTIVE_TAGS_IN_PAGE = {"button", "input", "select", "textarea"}


def _parse_points(points_str: str) -> List[Tuple[str, str]]:
    """Parse SVG polygon points string into coordinate pairs."""
    tokens = re.findall(r"-?\d+(?:\.\d+)?", points_str or "")
    return [(tokens[i], tokens[i + 1]) for i in range(0, len(tokens) - 1, 2)]


class WalkthroughParser(HTMLParser):
    """HTML parser that collects DOM topology, anchors, and script blocks."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: List[Tuple[str, Dict[str, str], int]] = []
        self.polylines: List[Tuple[int, Dict[str, str]]] = []
        self.polygons: List[Tuple[int, Dict[str, str], List[Tuple[str, Dict[str, str], int]]]] = []
        self.interactive_elements: List[Tuple[int, str, Dict[str, str]]] = []
        self.comp_ids: Dict[str, List[int]] = {}
        self.dom_page_ids: Set[str] = set()
        self.scripts: List[Tuple[int, str]] = []
        self._in_script = False
        self._script_start_line = 0
        self._script_chunks: List[str] = []

    def _current_page_id(self) -> Optional[str]:
        for _, attrs, _ in reversed(self.stack):
            classes = set((attrs.get("class") or "").split())
            if "data-page" in attrs or "proto-page" in classes or "page" in classes:
                return attrs.get("data-page") or attrs.get("id") or "<unknown-page>"
        return None

    def _in_proto_page(self) -> bool:
        return self._current_page_id() is not None

    def _in_defs_or_marker(self) -> bool:
        return any(tag in {"defs", "marker"} for tag, _, _ in self.stack)

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        line, _ = self.getpos()
        attr_dict = {k: (v if v is not None else "") for k, v in attrs}
        classes = set(attr_dict.get("class", "").split())

        if "data-page" in attr_dict and attr_dict["data-page"].strip():
            self.dom_page_ids.add(attr_dict["data-page"].strip())
        if "id" in attr_dict and attr_dict["id"].strip():
            self.dom_page_ids.add(attr_dict["id"].strip())

        if "data-comp-id" in attr_dict and attr_dict["data-comp-id"].strip():
            cid = attr_dict["data-comp-id"].strip()
            page_scope = self._current_page_id() or "<global>"
            self.comp_ids.setdefault(f"{page_scope}::{cid}", []).append(line)

        if tag == "polyline":
            self.polylines.append((line, attr_dict))

        if tag == "polygon" and not self._in_defs_or_marker():
            self.polygons.append((line, attr_dict, list(self.stack)))

        in_page = self._in_proto_page()
        is_target_class = bool(classes & INTERACTIVE_CLASSES)
        is_primary_btn = in_page and tag == "button" and "primary" in classes
        is_page_interactive = in_page and (
            tag in INTERACTIVE_TAGS_IN_PAGE or attr_dict.get("role") == "button"
        )
        if is_target_class or is_primary_btn or is_page_interactive:
            self.interactive_elements.append((line, tag, attr_dict))

        if tag == "script":
            self._in_script = True
            self._script_start_line = line
            self._script_chunks = []

        self.stack.append((tag, attr_dict, line))

    def handle_startendtag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1][0] == tag:
            self.stack.pop()

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_script:
            self.scripts.append((self._script_start_line, "".join(self._script_chunks)))
            self._in_script = False
            self._script_chunks = []

        for idx in range(len(self.stack) - 1, -1, -1):
            if self.stack[idx][0] == tag:
                del self.stack[idx:]
                break

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self._script_chunks.append(data)


def _extract_nodes_pages(scripts: List[Tuple[int, str]]) -> Tuple[bool, List[Tuple[str, str]]]:
    """Extract (node_id, page_id) references from NODES object in <script> blocks."""
    found_nodes = False
    refs: List[Tuple[str, str]] = []

    for _, script in scripts:
        match = re.search(r"\bNODES\s*=\s*\{", script)
        if not match:
            continue
        found_nodes = True
        start = match.end() - 1
        depth = 0
        end = start
        in_str: Optional[str] = None
        escaped = False
        for i in range(start, len(script)):
            ch = script[i]
            if in_str:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == in_str:
                    in_str = None
                continue
            if ch in {"'", '"', "`"}:
                in_str = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        nodes_block = script[start:end]
        for node_match in re.finditer(r"""['"]?([A-Za-z0-9_-]+)['"]?\s*:\s*\{""", nodes_block):
            node_id = node_match.group(1)
            sub_start = node_match.end() - 1
            sub_depth = 0
            sub_end = sub_start
            for j in range(sub_start, len(nodes_block)):
                if nodes_block[j] == "{":
                    sub_depth += 1
                elif nodes_block[j] == "}":
                    sub_depth -= 1
                    if sub_depth == 0:
                        sub_end = j + 1
                        break
            node_body = nodes_block[sub_start:sub_end]
            page_match = re.search(r"""\b['"]?page['"]?\s*:\s*['"]([^'"]+)['"]""", node_body)
            if page_match:
                refs.append((node_id, page_match.group(1).strip()))

    return found_nodes, refs


def run_preflight(html_path: Path) -> List[str]:
    """Run all static preflight checks and return a list of error messages."""
    content = html_path.read_text(encoding="utf-8")
    parser = WalkthroughParser()
    parser.feed(content)
    parser.close()

    errors: List[str] = []

    # (a) All <polyline> must have data-from and data-to
    for line, attrs in parser.polylines:
        missing = [k for k in ("data-from", "data-to") if not attrs.get(k, "").strip()]
        if missing:
            errors.append(
                f"[Check A - Polyline] Line {line}: <polyline> missing {', '.join(missing)}"
            )

    # (b) All diamond <polygon> enclosing <g> must have data-node and data-node-type="decision"
    for line, attrs, ancestors in parser.polygons:
        points = _parse_points(attrs.get("points", ""))
        if len(points) != 4:
            continue
        g_ancestors = [(t, a, ln) for t, a, ln in ancestors if t == "g"]
        if not g_ancestors:
            errors.append(
                f"[Check B - Decision] Line {line}: diamond <polygon> is not wrapped in a <g> element"
            )
            continue
        has_valid_g = any(
            a.get("data-node", "").strip() and a.get("data-node-type", "").strip() == "decision"
            for _, a, _ in g_ancestors
        )
        if not has_valid_g:
            nearest_g_line = g_ancestors[-1][2]
            errors.append(
                f"[Check B - Decision] Line {line} (in <g> at line {nearest_g_line}): "
                "diamond <polygon> ancestor <g> must have non-empty data-node and data-node-type=\"decision\""
            )

    # (c) Interactive elements must have data-comp-id and data-comp-name
    for line, tag, attrs in parser.interactive_elements:
        missing = [k for k in ("data-comp-id", "data-comp-name") if not attrs.get(k, "").strip()]
        if missing:
            cls = attrs.get("class", "")
            desc = f"<{tag} class=\"{cls}\">" if cls else f"<{tag}>"
            errors.append(
                f"[Check C - Anchor] Line {line}: {desc} missing {', '.join(missing)}"
            )

    for cid, lines in parser.comp_ids.items():
        if len(lines) > 1:
            errors.append(
                f"[Check C - Anchor] Duplicate data-comp-id=\"{cid}\" at lines {', '.join(map(str, lines))}"
            )

    # (d) NODES referenced pages must exist in DOM
    found_nodes, page_refs = _extract_nodes_pages(parser.scripts)
    if not found_nodes:
        errors.append("[Check D - NODES] Could not find NODES definition in <script> blocks")
    else:
        for node_id, page_id in page_refs:
            if page_id not in parser.dom_page_ids:
                errors.append(
                    f"[Check D - NODES] Node \"{node_id}\" references page=\"{page_id}\", "
                    "which does not exist in DOM (data-page or id)"
                )

    return errors


def run_spec_preflight(spec_path: Path) -> List[str]:
    """Run static preflight checks on a spec-v2 JSON file and return error messages."""
    try:
        raw = spec_path.read_text(encoding="utf-8")
        data: Any = json.loads(raw)
    except Exception as exc:
        return [f"[Spec - JSON] Failed to parse JSON: {exc}"]

    if not isinstance(data, dict):
        return ["[Spec - Root] Top-level value must be a JSON object"]

    errors: List[str] = []

    # 1. Required top-level fields & types
    if data.get("version") != "spec-v2":
        errors.append(f"[Spec - Version] version must be \"spec-v2\", got {data.get('version')!r}")

    required_types: Dict[str, type] = {
        "meta": dict,
        "vars": list,
        "nodes": dict,
        "pages": dict,
    }
    for key, expected_type in required_types.items():
        if key not in data:
            errors.append(f"[Spec - Required] Missing required top-level field \"{key}\"")
        elif not isinstance(data[key], expected_type):
            errors.append(
                f"[Spec - Type] Field \"{key}\" must be {expected_type.__name__}, got {type(data[key]).__name__}"
            )

    if errors:
        return errors

    nodes: Dict[str, Any] = data["nodes"]
    pages: Dict[str, Any] = data["pages"]
    vars_list: List[Any] = data["vars"]

    var_ids: Set[str] = set()
    for idx, v in enumerate(vars_list):
        if isinstance(v, dict) and isinstance(v.get("id"), str) and v["id"].strip():
            var_ids.add(v["id"].strip())
        else:
            errors.append(f"[Spec - Vars] vars[{idx}] must be an object with non-empty \"id\"")

    # 2. Validate pages[].variant_of points to an existing base page without cycles
    for page_id, page_def in pages.items():
        if not isinstance(page_def, dict):
            errors.append(f"[Spec - Pages] Page \"{page_id}\" must be an object")
            continue
        base_id = page_def.get("variant_of")
        if base_id is not None:
            if not isinstance(base_id, str) or not base_id.strip():
                errors.append(f"[Spec - Variant] Page \"{page_id}\" has invalid variant_of={base_id!r}")
            elif base_id not in pages:
                errors.append(
                    f"[Spec - Variant] Page \"{page_id}\" variant_of=\"{base_id}\" does not exist in pages"
                )
            else:
                seen: Set[str] = {page_id}
                cur: Optional[str] = base_id
                while cur is not None:
                    if cur in seen:
                        errors.append(f"[Spec - Variant] Cycle detected in variant_of chain starting at \"{page_id}\"")
                        break
                    seen.add(cur)
                    cur_def = pages.get(cur)
                    cur = cur_def.get("variant_of") if isinstance(cur_def, dict) else None

    # 3. Validate nodes[].page exists in pages (and decision nodes reference a valid branchVar)
    for node_id, node_def in nodes.items():
        if not isinstance(node_def, dict):
            errors.append(f"[Spec - Nodes] Node \"{node_id}\" must be an object")
            continue
        page_ref = node_def.get("page")
        if not isinstance(page_ref, str) or not page_ref.strip():
            errors.append(f"[Spec - Nodes] Node \"{node_id}\" missing non-empty \"page\"")
        elif page_ref not in pages:
            errors.append(
                f"[Spec - Nodes] Node \"{node_id}\" references page=\"{page_ref}\", which does not exist in pages"
            )
        if node_def.get("isDecision") is True:
            bvar = node_def.get("branchVar")
            if not isinstance(bvar, str) or bvar not in var_ids:
                errors.append(
                    f"[Spec - Nodes] Decision node \"{node_id}\" references branchVar={bvar!r}, which is not in vars"
                )

    # 4. Validate vars[].diamond and vars[].options[].target
    for idx, v in enumerate(vars_list):
        if not isinstance(v, dict):
            continue
        vid = v.get("id", f"vars[{idx}]")
        kind = v.get("kind")

        if kind == "branch":
            diamond = v.get("diamond")
            if not isinstance(diamond, str) or not diamond.strip():
                errors.append(f"[Spec - Vars] Branch var \"{vid}\" missing non-empty \"diamond\"")
            elif diamond not in nodes:
                errors.append(
                    f"[Spec - Vars] Branch var \"{vid}\" diamond=\"{diamond}\" does not exist in nodes"
                )
            elif not (isinstance(nodes[diamond], dict) and nodes[diamond].get("isDecision") is True):
                errors.append(
                    f"[Spec - Vars] Branch var \"{vid}\" diamond=\"{diamond}\" is not a decision node (isDecision: true)"
                )

        if kind == "local" and isinstance(v.get("pages"), list):
            for p in v["pages"]:
                if p not in pages:
                    errors.append(
                        f"[Spec - Vars] Local var \"{vid}\" references page=\"{p}\", which does not exist in pages"
                    )

        options = v.get("options")
        if not isinstance(options, list) or not options:
            errors.append(f"[Spec - Vars] Var \"{vid}\" must have a non-empty \"options\" array")
        else:
            for opt_idx, opt in enumerate(options):
                if not isinstance(opt, dict):
                    errors.append(f"[Spec - Vars] Var \"{vid}\" options[{opt_idx}] must be an object")
                    continue
                target = opt.get("target")
                if kind == "branch" and (not isinstance(target, str) or not target.strip()):
                    errors.append(
                        f"[Spec - Vars] Branch var \"{vid}\" option \"{opt.get('id', opt_idx)}\" missing \"target\""
                    )
                elif isinstance(target, str) and target not in nodes:
                    errors.append(
                        f"[Spec - Vars] Var \"{vid}\" option \"{opt.get('id', opt_idx)}\" "
                        f"target=\"{target}\" does not exist in nodes"
                    )

    # 5. Validate optional state_groups and spec_cards page references
    state_groups = data.get("state_groups")
    if isinstance(state_groups, dict):
        for gid, gdef in state_groups.items():
            if isinstance(gdef, dict) and isinstance(gdef.get("states"), list):
                for st in gdef["states"]:
                    if isinstance(st, dict) and st.get("page") not in pages:
                        errors.append(
                            f"[Spec - StateGroups] State \"{gid}/{st.get('id')}\" references "
                            f"unknown page=\"{st.get('page')}\""
                        )

    spec_cards = data.get("spec_cards")
    if isinstance(spec_cards, list):
        for card in spec_cards:
            if isinstance(card, dict) and card.get("page") not in pages:
                errors.append(
                    f"[Spec - SpecCards] Card \"{card.get('id')}\" references unknown page=\"{card.get('page')}\""
                )

    return errors


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="preflight_check.py",
        description=(
            "Static preflight gate for walkthrough.html or spec.json (spec-v2).\n"
            "HTML checks: (a) <polyline> data-from/data-to, "
            "(b) diamond <polygon> <g> data-node & data-node-type=\"decision\", "
            "(c) interactive elements data-comp-id/data-comp-name, "
            "(d) NODES page references exist in DOM.\n"
            "JSON checks: spec-v2 top-level fields, nodes->pages, vars->diamond/target, pages->variant_of."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "target_file",
        type=Path,
        help="Path to the walkthrough.html or spec.json file to validate.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    arg_parser = build_arg_parser()
    args = arg_parser.parse_args(argv)

    target_path: Path = args.target_file
    if not target_path.is_file():
        print(f"ERROR: File not found: {target_path}", file=sys.stderr)
        return 2

    if target_path.suffix.lower() == ".json":
        errors = run_spec_preflight(target_path)
    else:
        errors = run_preflight(target_path)

    if errors:
        print(f"PREFLIGHT FAILED ({len(errors)} issue(s)) for {target_path}:", file=sys.stderr)
        for idx, err in enumerate(errors, start=1):
            print(f"  {idx}. {err}", file=sys.stderr)
        return 1

    print(f"PREFLIGHT PASSED: {target_path} (all checks passed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
