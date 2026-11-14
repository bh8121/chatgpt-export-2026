"""Build a small, fully synthetic ChatGPT 2026-style export for parser tests.

No real conversation data.
Usage:  python make_chatgpt_fixture.py OUT_DIR [--with-children]

By default nodes carry no "children" list, as in real 2026 exports (0 of 240,291
nodes had one). --with-children adds the lists back, to mimic older exports.

Layout mirrors the 2026 export:
  conversations-000.json, conversations-001.json   sharded conversation arrays
  conversation_asset_file_names.json               file id -> original name
  library_files.json                               file id -> conversation/message
  file_<id>.dat                                    attachment bytes

Conversations:
  conv-regen     regenerated answer + edited user turn + multimodal turn + markers
  conv-edit1     the FIRST user turn was edited (old version is earlier in time)
  conv-nocur     no current_node: parser must pick the newest leaf
  conv-nomap     "mapping" absent        conv-nullmap   "mapping": null
  conv-cycle     corrupt parent pointers forming a loop (must not hang)
  conv-regen-clone  workspace-merge clone of conv-regen (new id, clone-date create_time)
  conv-edit-long    first question edited after a long exchange: the live branch
                    (2 messages) is shorter and newer than the abandoned one (12)
"""
import json
import sys
from pathlib import Path

T0 = 1735689600.0  # 2025-01-01T00:00:00Z
FILE_ID = "file_000000000000000000000001"
CITE = "\ue200cite\ue202turn0search1\ue201"
ENT = '\ue200entity\ue202["city","Lisbon",null]\ue201'
WITH_CHILDREN = "--with-children" in sys.argv[2:]


def node(nid, parent, children, role=None, text=None, t=None, parts=None, ctype="text"):
    msg = None
    if role:
        msg = {
            "id": nid,
            "author": {"role": role},
            "create_time": t,
            "content": {"content_type": ctype,
                        "parts": parts if parts is not None else [text]},
        }
    n = {"id": nid, "message": msg, "parent": parent}
    if WITH_CHILDREN:
        n["children"] = children
    return n


def conv(cid, title, mapping, current, t=T0):
    c = {"id": cid, "conversation_id": cid, "title": title,
         "create_time": t, "update_time": t + 100, "mapping": mapping}
    if current is not None:
        c["current_node"] = current
    return c


regen = {
    "root": node("root", None, ["u1"]),
    "u1": node("u1", "root", ["a1_old", "a1_new"], "user", "Plan a two-day trip.", T0),
    "a1_old": node("a1_old", "u1", [], "assistant", "ABANDONED regenerated answer.", T0 + 10),
    "a1_new": node("a1_new", "u1", ["u2_old", "u2_new"], "assistant",
                   f"Start in {ENT} near the river.{CITE} Budget $40 to $60 per day.", T0 + 20),
    "u2_old": node("u2_old", "a1_new", ["a2_old"], "user", "ABANDONED edited question.", T0 + 30),
    "a2_old": node("a2_old", "u2_old", [], "assistant", "ABANDONED reply.", T0 + 40),
    "u2_new": node("u2_new", "a1_new", ["a2_new"], "user", None, T0 + 50,
                   ctype="multimodal_text",
                   parts=[{"content_type": "image_asset_pointer",
                           "asset_pointer": f"sediment://{FILE_ID}"},
                          "What is in this photo?"]),
    "a2_new": node("a2_new", "u2_new", [], "assistant", "A tram on a hill.", T0 + 60),
}

edit_first = {
    "root": node("root", None, ["u1_old", "u1_new"]),
    "u1_old": node("u1_old", "root", ["a1_old"], "user", "ABANDONED first question.", T0),
    "a1_old": node("a1_old", "u1_old", [], "assistant", "ABANDONED first answer.", T0 + 5),
    "u1_new": node("u1_new", "root", ["a1_new"], "user", "Rewritten first question.", T0 + 60),
    "a1_new": node("a1_new", "u1_new", [], "assistant", "Answer to rewrite.", T0 + 70),
}

no_current = {
    "root": node("root", None, ["u1"]),
    # children[] deliberately stale: lists only the older branch
    "u1": node("u1", "root", ["a_old"], "user", "Question.", T0),
    "a_old": node("a_old", "u1", [], "assistant", "ABANDONED older answer.", T0 + 10),
    "a_new": node("a_new", "u1", [], "assistant", "Newest answer.", T0 + 20),
}

cycle = {
    "x": node("x", "y", ["y"], "user", "Loop A.", T0),
    "y": node("y", "x", ["x"], "assistant", "Loop B.", T0 + 1),
}

# Six abandoned exchanges, then the first question is edited and answered once.
# The live branch is newer but shallower, so "deepest recent leaf" heuristics
# pick the abandoned branch; current_node points at the live one.
edit_long = {"root": node("root", None, ["old_u0", "new_u0"])}
_prev = "root"
for k in range(6):
    u, a = f"old_u{k}", f"old_a{k}"
    nxt = [f"old_u{k + 1}"] if k < 5 else []
    edit_long[u] = node(u, _prev, [a], "user", f"ABANDONED question {k}.", T0 + 10 * k)
    edit_long[a] = node(a, u, nxt, "assistant", f"ABANDONED answer {k}.", T0 + 10 * k + 5)
    _prev = a
edit_long["new_u0"] = node("new_u0", "root", ["new_a0"], "user",
                           "Rewritten opening question.", T0 + 1000)
edit_long["new_a0"] = node("new_a0", "new_u0", [], "assistant",
                           "Answer on the live branch.", T0 + 1005)

shard0 = [
    conv("conv-regen", "Trip plan", regen, "a2_new"),
    conv("conv-edit1", "Edited opener", edit_first, "a1_new"),
    conv("conv-nocur", "No current node", no_current, None),
    {"id": "conv-nomap", "title": "No mapping", "create_time": T0},
    {"id": "conv-nullmap", "title": "Null mapping", "create_time": T0, "mapping": None},
]
shard1 = [
    conv("conv-cycle", "Corrupt", cycle, "x"),
    conv("conv-regen-clone", "Trip plan", regen, "a2_new", t=T0 + 9e6),
    conv("conv-edit-long", "Edited after a long exchange", edit_long, "new_a0"),
]


def main(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "conversations-000.json").write_text(json.dumps(shard0, indent=1))
    (out / "conversations-001.json").write_text(json.dumps(shard1, indent=1))
    (out / "conversation_asset_file_names.json").write_text(json.dumps({FILE_ID: "photo.jpg"}))
    (out / "library_files.json").write_text(json.dumps(
        [{"file_id": FILE_ID, "conversation_id": "conv-regen", "message_id": "u2_new"}]))
    (out / f"{FILE_ID}.dat").write_bytes(b"\xff\xd8synthetic-not-a-real-jpeg")
    print("wrote", ", ".join(sorted(p.name for p in out.iterdir())))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
