# What's actually inside a 2026 ChatGPT export, and what it quietly breaks

*Brian Harris, MD · November 2026 · Also published at [brianharris.org](https://brianharris.org/essays/whats-inside-a-chatgpt-export/)*

Exporting three and a half years of ChatGPT conversations ought to involve a settings menu and an email; for me it took the better part of six months. In October 2025 I merged my personal account into a ChatGPT Business workspace for my practice, which OpenAI makes easy and does not make reversible: the personal workspace is deleted, and the help pages now say plainly that data export is not available in a Business workspace, that members cannot export their own history, and that in rare cases long-running or historical chats may not survive a merge at all. I learned the first part in May 2026, when support directed me to an export button that did not exist in my workspace, and the rest over months of tickets that ended in October with confirmation that the merge could not be undone and that leaving the workspace would take the merged history with it. What eventually worked was an owner-level export command tucked into the workspace's member administration page, which the documentation describes as available when it is available; nothing about it is guaranteed, and in my case the first two exports it produced did not contain my conversations, while the third, for reasons nobody explained, did. If you are considering merging a personal account into a Business workspace, export the personal account first; OpenAI's own documentation now gives the same advice.

The export I finally had was, for practical purposes, the only copy of three and a half years I could count on, and I set out to build a private, local, searchable archive from it. Most people assume an export like this is a transcript: a faithful record of what they asked and what the model answered, in order. That is partly true; but it is better understood as a snapshot of the system's internal state, including the conversation you had, the drafts you rejected, the copies an account migration made on your behalf, and the timestamps of that migration, stored side by side and none of it labeled as such. Most tools treat it as a transcript, when it is closer to a raw copy of the system's own records, branching history included, and that mismatch produces silent distortion: everything imports, the counts look plausible, and the archive is wrong in ways that surface only when you depend on it. Clinicians will recognize the pattern from the electronic health record, where the same note copied forward nine times still describes a single visit. What follows is what I measured in my own export (11,294 conversation records, November 2026), for anyone who builds or maintains an importer; the examples and test fixtures in this repository are synthetic, and only aggregate counts come from my data.

The first thing an older tool will miss is the file it expects. There is no longer a single `conversations.json`; my export split it across 113 shards, `conversations-000.json` onward, about a hundred conversations each. The export does describe itself: an `export_manifest.json` declares `conversations.json` as a sharded logical file and gives the shard count, so an importer can ask the manifest rather than guess at a naming convention that has already changed once.

The more consequential change is inside each conversation. A ChatGPT conversation is stored less like a scroll than like a family tree: each message records only its parent, the message it was replying to, and when you regenerate an answer or edit a question nothing is overwritten; the new version is added as a sibling, and a bookmark called `current_node` marks the branch you were last looking at. Older exports also listed each message's replies (its children), so a parser could start at the first message and read downward. In my export, not one of 240,291 messages had that list. You can still climb from the bookmark up to the first message, since every message knows its parent, but you can no longer walk down from the top, and a parser built to read downward finds nothing. The traversal that works is the climb: begin at `current_node`, follow parents to the root, and reverse the path. Every conversation in my export had a valid bookmark, so a fallback is purely defensive, though a guard against a corrupted loop of parent pointers costs almost nothing.

The family tree matters because of the relatives it keeps. Every regenerated answer and every edited message adds a sibling branch, and only one path is the exchange that actually happened. About one conversation in ten carried text off that path, roughly 2,600 abandoned messages in all. An importer that iterates every node and sorts by time interleaves those drafts with the real conversation, so search returns answers that were rejected and summaries summarize them. There is a quieter version of the same error: if a thread's identity is derived from its first message, and the user edited their opening question, the identity rests on text the user threw away.

The merge was the largest distortion and the least visible one. Grouping records that share any message id (message ids survive cloning even though conversation ids do not), my 11,277 records with a message tree collapsed to 2,775 real conversations. Of those, 1,696 had never been cloned; 1,060 existed in exactly nine copies. Most copies were identical, but 15 groups were strict subsets of a longer copy, which is what a conversation looks like when it continued after the merge and left earlier snapshots behind, and 14 were genuine forks that shared a prefix and then diverged. Identical copies are aliases of one conversation, subsets are aliases of the copy that continued, and forks should keep their shared prefix once with each divergent tail as its own branch. An importer that keys on the export's own id holds roughly four copies of everything for a merged account, and vector search, being thorough, returns all nine.

Dates followed the clones. For every one of the 1,060 cloned conversations, all nine copies carried a conversation-level creation time in October 2025, the month of the merge, regardless of when the conversation took place; no copy kept the original date. Message-level timestamps survived, and among conversations that were never cloned, only 10 of 1,696 showed a conversation date more than a day after their first message. The fix is simple once the mechanism is clear: date a conversation by its earliest message. Otherwise 38% of my real conversations would be dated to a single month, an error that would skew any timeline and any search that asks when something was first discussed.

The text itself carries markup most readers never see. Assistant messages contain spans delimited by Unicode private-use characters, a kind, then a payload; I counted at least 26 kinds, dominated by citations (42,020 of them). Left in place, they enter search indexes and embeddings as noise, and a marker in the middle of a phrase can split exactly the words a keyword search needed. Citation spans can be removed; entity spans carry a small JSON array whose second element is the display name, which can replace the span so the sentence still reads. If an importer also strips mathematical notation, a naive pattern between dollar signs will cheerfully delete everything between two prices in ordinary prose.

Attachments and model reasoning follow the same theme: the information is present, but not where a transcript-minded parser looks. Recovering an attachment means joining message parts, which use two different pointer schemes, with two separate sidecar files; reasoning is exported as separate nodes whose text sits outside the field most parsers read, and dropping it is defensible as long as someone chose to.

None of this makes the export unusable, and some of it may change with the next format revision. But the details matter less than the model behind them: an export records how the system stored what you said, including its revisions, its copies and its housekeeping, and an importer that reconstructs the conversation from that record (one path through the tree, one identity per conversation, one date drawn from its messages) ends up with an archive that answers questions accurately, which was the reason for building it.

The fixtures in this repository reproduce every case above, the reference section below has the full counts, and I have reported the traversal problem to one open-source importer as [mychatarchive#21](https://github.com/1ch1n/mychatarchive/issues/21). If you maintain an importer and want the fixtures adapted to your test suite, open an issue here.

---

## Reference for importer authors

The essay above in checklist form, with the numbers from my export.

- **Find shards via the manifest.** `export_manifest.json` → `logical_files["conversations.json"]` gives `sharded: true`, `shard_count`, and the file list (113 shards, about 100 conversations each).
- **Traverse upward only.** `children` is absent from every node (0 of 240,291); walk `parent` from `current_node` and reverse. Fallback when `current_node` is missing: newest leaf (a node that is no other node's parent). Guard against cycles.
- **Expect abandoned branches** in about 10% of conversations (roughly 2,600 off-path user/assistant messages).
- **Collapse workspace-merge clones** with union-find over shared message ids, then classify each group: identical → aliases; strict subset → alias of the continued superset; divergent → fork that keeps its shared prefix once.
- **Date from messages.** Conversation `create_time` is the clone date for every cloned conversation; use the earliest message `create_time`.
- **Clean private-use markup** `\ue200<kind>\ue202<payload>\ue201`: drop citation kinds; replace `entity`/`product_entity` with JSON element 1; drop malformed spans. Avoid naive `$...$` LaTeX stripping.
- **Join three sources for attachments:** `asset_pointer` in message parts, `conversation_asset_file_names.json`, `library_files.json`.
- **Decide about reasoning:** `thoughts` and `reasoning_recap` nodes keep their text outside `parts`.
- **Skip records without a tree** (`mapping` absent, or defensively, `null`) without aborting the import.

### Export layout (November 2026)

| File | Contents |
|---|---|
| `conversations-000.json` … `conversations-112.json` | 113 shards; JSON arrays of conversation objects |
| `export_manifest.json` | Every file with size; declares the sharded logical `conversations.json` |
| `file-<id>.dat` | 2,646 attachment blobs, no extension |
| `conversation_asset_file_names.json` | File id → original filename (2,189 entries) |
| `library_files.json` | 1,595 file records incl. `origination_thread_id`, `origination_message_id`, `mime_type`, `file_name`, `content_backing_kind` |
| `shared_conversations.json`, `user.json`, `user_settings.json`, `sectioned_conversations.json` (empty), `index.html` | Metadata and a viewer |

Conversation object keys observed: `conversation_id`, `id`, `title`, `create_time`, `update_time`, `current_node`, `mapping`, `default_model_slug`, `is_archived`, `is_starred`, `is_read_only`, `is_study_mode`, `is_do_not_remember`, `memory_scope`, `pinned_time`, `plugin_ids`, `conversation_template_id`, `voice`.

### Workspace-merge clone groups

| Group size | Groups | Notes |
|---|---|---|
| 1 | 1,696 | never cloned; 10 had a conversation date >1 day after first message |
| 9 | 1,060 | all nine copies dated October 2025 (the merge) |
| 2-4 | 19 | |
| **Total** | **2,775** | from 11,277 records with a `mapping` |

Within multi-record groups: 1,050 identical, 15 strict subsets, 14 divergent forks.

### Private-use markup kinds (top)

| Kind | Count | | Kind | Count |
|---|---|---|---|---|
| `cite` | 42,020 | | `url` | 445 |
| `filecite` | 3,733 | | `i` | 383 |
| `product_entity` | 1,353 | | `navlist` | 279 |
| `entity` | 985 | | `video` | 275 |
| `products` | 502 | | `product` | 240 |

Also seen: `link`, `finance`, `genui`, `image_group`, `summary`, `link_title`, `entity_metadata`, `businesses_map`, `tlwm`, `product_query`, `filenavlist`, `time`, `gmail`, `forecast`, `visualize`, `message_reaction`.

### Other counts

`asset_pointer` schemes: `sediment://` 6,530, `file-service://` 1,690. Content types: `text` 184,328; `thoughts` 20,180; `multimodal_text` 15,098; `reasoning_recap` 9,406. Records with no `mapping` key: 17; with `mapping: null`: 0.

## Files

- `make_chatgpt_fixture.py`: writes a small synthetic export covering a regenerated answer, an edited question, an edited first question, a missing `current_node`, absent and `null` mappings, a parent-pointer cycle, and a workspace clone.
- `probe_mychatarchive.py`: runs one existing importer's parser against the fixture.

## License

Scripts: MIT. Text: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). See `LICENSE` and `LICENSE-docs`.
