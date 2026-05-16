from __future__ import annotations

from collections import defaultdict
from html import escape
from typing import Any

import gradio as gr
import pandas as pd
from pymongo import MongoClient
from qdrant_client import QdrantClient

from src.config.settings import settings
from src.eval.agentic_workflow_eval import iter_agentic_workflow_eval
from src.eval.retrieval_eval import iter_retrieval_eval

STATUS_GREEN = "#d1fae5"
STATUS_RED = "#fee2e2"
STATUS_AMBER = "#fef3c7"
STATUS_GRAY = "#f3f4f6"
APP_CSS = """
<style>
body, .gradio-container {
  background: #0f1115;
}
.gradio-container {
  max-width: 1720px !important;
}
.jurisai-hero {
  padding: 8px 0 18px 0;
}
.jurisai-hero h1 {
  font-size: 2.2rem;
  line-height: 1.1;
  margin: 0 0 10px 0;
}
.jurisai-hero p {
  color: #b3bcc9;
  font-size: 1rem;
  margin: 0;
  max-width: 920px;
}
.jurisai-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin: 10px 0 18px 0;
}
.jurisai-card {
  border: 1px solid #262b33;
  border-radius: 16px;
  padding: 14px 16px;
  background: linear-gradient(180deg, #171a21 0%, #12151b 100%);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.02);
  position: relative;
  overflow: hidden;
}
.jurisai-card::after {
  content: "";
  position: absolute;
  inset: auto 0 0 0;
  height: 3px;
  background: rgba(148,163,184,0.16);
}
.jurisai-card-good {
  border-color: rgba(34,197,94,0.38);
}
.jurisai-card-good::after {
  background: linear-gradient(90deg, #22c55e 0%, #86efac 100%);
}
.jurisai-card-warn {
  border-color: rgba(245,158,11,0.4);
}
.jurisai-card-warn::after {
  background: linear-gradient(90deg, #f59e0b 0%, #fcd34d 100%);
}
.jurisai-card-bad {
  border-color: rgba(239,68,68,0.38);
}
.jurisai-card-bad::after {
  background: linear-gradient(90deg, #ef4444 0%, #fca5a5 100%);
}
.jurisai-card-neutral {
  border-color: rgba(100,116,139,0.32);
}
.jurisai-card-neutral::after {
  background: linear-gradient(90deg, #475569 0%, #94a3b8 100%);
}
.jurisai-card-label {
  color: #9aa3af;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 8px;
}
.jurisai-card-status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.jurisai-card-badge {
  display: inline-block;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}
.jurisai-card-badge-good {
  background: rgba(34,197,94,0.14);
  color: #86efac;
}
.jurisai-card-badge-warn {
  background: rgba(245,158,11,0.16);
  color: #fcd34d;
}
.jurisai-card-badge-bad {
  background: rgba(239,68,68,0.16);
  color: #fca5a5;
}
.jurisai-card-badge-neutral {
  background: rgba(148,163,184,0.16);
  color: #cbd5e1;
}
.jurisai-card-value {
  font-size: 1.55rem;
  font-weight: 700;
  color: #f7fafc;
}
.jurisai-card-subvalue {
  margin-top: 4px;
  color: #94a3b8;
  font-size: 0.84rem;
}
.jurisai-card-note {
  font-size: 0.88rem;
  color: #c7d0db;
  margin-top: 10px;
}
.jurisai-meter {
  margin-top: 12px;
  height: 8px;
  border-radius: 999px;
  background: rgba(30,41,59,0.95);
  overflow: hidden;
}
.jurisai-meter-fill {
  height: 100%;
  border-radius: 999px;
}
.jurisai-meter-fill-good {
  background: linear-gradient(90deg, #16a34a 0%, #4ade80 100%);
}
.jurisai-meter-fill-warn {
  background: linear-gradient(90deg, #d97706 0%, #fbbf24 100%);
}
.jurisai-meter-fill-bad {
  background: linear-gradient(90deg, #dc2626 0%, #f87171 100%);
}
.jurisai-meter-fill-neutral {
  background: linear-gradient(90deg, #475569 0%, #94a3b8 100%);
}
.jurisai-panel {
  border: 1px solid #262b33;
  border-radius: 16px;
  background: #13161d;
  padding: 16px 18px;
}
.jurisai-panel h3 {
  margin: 0 0 10px 0;
  font-size: 1rem;
}
.jurisai-kv {
  display: grid;
  grid-template-columns: 160px 1fr;
  gap: 10px 14px;
  font-size: 0.96rem;
}
.jurisai-kv-label {
  color: #9aa3af;
}
.jurisai-kv-value {
  color: #edf2f7;
  word-break: break-word;
}
.jurisai-progress {
  margin-top: 14px;
  height: 10px;
  border-radius: 999px;
  background: rgba(30,41,59,0.95);
  overflow: hidden;
}
.jurisai-progress-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #f97316 0%, #fb7185 100%);
}
.jurisai-chip {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 0.82rem;
  font-weight: 600;
  margin-right: 6px;
  margin-bottom: 6px;
}
.jurisai-chip-green {
  background: rgba(34,197,94,0.16);
  color: #86efac;
}
.jurisai-chip-red {
  background: rgba(239,68,68,0.16);
  color: #fca5a5;
}
.jurisai-chip-amber {
  background: rgba(245,158,11,0.16);
  color: #fcd34d;
}
.jurisai-chip-gray {
  background: rgba(148,163,184,0.14);
  color: #cbd5e1;
}
.jurisai-table-wrap {
  border: 1px solid #262b33;
  border-radius: 16px;
  overflow: auto;
  background: #12151b;
}
.jurisai-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 980px;
  font-size: 0.94rem;
}
.jurisai-table th {
  position: sticky;
  top: 0;
  background: #171a21;
  color: #cbd5e1;
  text-align: left;
  padding: 12px 14px;
  border-bottom: 1px solid #313744;
  font-size: 0.82rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.jurisai-table td {
  padding: 12px 14px;
  border-bottom: 1px solid #1f2430;
  vertical-align: top;
  color: #eef2f7;
}
.jurisai-table tr:hover td {
  background: rgba(255,255,255,0.02);
}
.jurisai-muted {
  color: #9aa3af;
}
.jurisai-sidebar-note {
  color: #b9c2ce;
  font-size: 0.93rem;
  line-height: 1.55;
}
.jurisai-chat {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.jurisai-chat-message {
  border: 1px solid #262b33;
  border-radius: 16px;
  padding: 14px 16px;
  background: #13161d;
}
.jurisai-chat-details {
  border: 1px solid #262b33;
  border-radius: 16px;
  background: #13161d;
  overflow: hidden;
}
.jurisai-chat-details summary {
  list-style: none;
  cursor: pointer;
  padding: 14px 16px;
}
.jurisai-chat-details summary::-webkit-details-marker {
  display: none;
}
.jurisai-chat-details[open] summary {
  border-bottom: 1px solid #1f2430;
}
.jurisai-chat-content {
  padding: 14px 16px 16px 16px;
}
.jurisai-chat-message-user {
  border-color: rgba(59,130,246,0.32);
  background: linear-gradient(180deg, rgba(29,78,216,0.16) 0%, rgba(19,22,29,1) 100%);
}
.jurisai-chat-message-assistant {
  border-color: rgba(34,197,94,0.28);
}
.jurisai-chat-message-tool {
  border-color: rgba(245,158,11,0.28);
  background: linear-gradient(180deg, rgba(120,53,15,0.18) 0%, rgba(19,22,29,1) 100%);
}
.jurisai-chat-message-system {
  border-color: rgba(148,163,184,0.24);
  background: linear-gradient(180deg, rgba(51,65,85,0.20) 0%, rgba(19,22,29,1) 100%);
}
.jurisai-chat-role {
  color: #9aa3af;
  font-size: 0.77rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 8px;
}
.jurisai-chat-title {
  color: #f8fafc;
  font-size: 0.98rem;
  font-weight: 700;
  margin-bottom: 8px;
}
.jurisai-chat-body {
  color: #e2e8f0;
  line-height: 1.6;
}
.jurisai-chat-body p {
  margin: 0 0 8px 0;
}
.jurisai-chat-body ul {
  margin: 8px 0 0 18px;
}
.jurisai-chat-body li {
  margin-bottom: 6px;
}
.jurisai-chat-pre {
  margin-top: 10px;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.84rem;
  color: #dbe4ee;
  background: rgba(2,6,23,0.55);
  border: 1px solid #1f2937;
  border-radius: 12px;
  padding: 12px;
}
</style>
"""
def _mongo_database():
    client = MongoClient(settings.mongodb_uri)
    return client, client[settings.database_name]


def _load_eval_scheme_catalog() -> dict[str, dict[str, Any]]:
    client, database = _mongo_database()
    try:
        documents = list(database[settings.eval.enriched_subset_collection].find({}))
    finally:
        client.close()

    scheme_catalog: dict[str, dict[str, Any]] = {}
    for document in documents:
        scheme_id = str(document.get("_id"))
        scheme_catalog[scheme_id] = {
            "scheme_id": scheme_id,
            "name": document.get("name") or scheme_id,
            "state": document.get("state"),
            "level": document.get("level"),
            "provider": document.get("provider"),
            "provider_type": document.get("provider_type"),
            "topics": list(document.get("topics") or []),
            "tags": list(document.get("tags") or []),
            "url": document.get("url"),
        }
    return scheme_catalog


def _load_vdb_coverage(collection_name: str) -> tuple[dict[str, dict[str, Any]], str | None]:
    client = QdrantClient(url=settings.qdrant.url, api_key=settings.qdrant.api_key)
    offset = None
    coverage: dict[str, dict[str, Any]] = {}
    try:
        while True:
            points, offset = client.scroll(
                collection_name=collection_name,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                payload = point.payload or {}
                scheme_id = str(
                    payload.get("scheme_id")
                    or (payload.get("mongo_ref") or {}).get("document_id")
                    or point.id
                )
                scheme_entry = coverage.setdefault(
                    scheme_id,
                    {
                        "vector_count": 0,
                        "profiles": set(),
                        "name": payload.get("name"),
                        "state": payload.get("state"),
                        "level": payload.get("level"),
                    },
                )
                scheme_entry["vector_count"] += 1
                profile_name = payload.get("embedding_profile")
                if profile_name:
                    scheme_entry["profiles"].add(profile_name)
            if offset is None:
                break
    except Exception as exc:  # noqa: BLE001
        return {}, str(exc)
    finally:
        client.close()

    for entry in coverage.values():
        entry["profiles"] = sorted(entry["profiles"])
    return coverage, None


def _build_collection_sidebar(
    *,
    collection_name: str,
) -> tuple[str, pd.DataFrame]:
    scheme_catalog = _load_eval_scheme_catalog()
    coverage, coverage_error = _load_vdb_coverage(collection_name)

    rows: list[dict[str, Any]] = []
    for scheme_id, scheme in sorted(
        scheme_catalog.items(),
        key=lambda item: ((item[1].get("name") or "").lower(), item[0]),
    ):
        vdb_entry = coverage.get(scheme_id) or {}
        rows.append(
            {
                "scheme_name": scheme.get("name"),
                "scheme_id": scheme_id,
                "level": scheme.get("level") or "",
                "state": scheme.get("state") or "",
                "topics": ", ".join(scheme.get("topics") or []),
                "in_vdb": "yes" if scheme_id in coverage else "no",
                "vector_count": vdb_entry.get("vector_count", 0),
                "profiles": ", ".join(vdb_entry.get("profiles") or []),
            }
        )

    present_count = len([row for row in rows if row["in_vdb"] == "yes"])
    coverage_rate = (present_count / len(rows)) if rows else 0.0
    error_suffix = f"\n\nVDB coverage check error: `{coverage_error}`" if coverage_error else ""
    markdown = (
        f"**Eval collection coverage**\n\n"
        f"- Enriched eval schemes: `{len(rows)}`\n"
        f"- Schemes present in VDB: `{present_count}`\n"
        f"- Coverage rate: `{coverage_rate:.1%}`"
        f"{error_suffix}"
    )
    return markdown, pd.DataFrame(rows)


def _safe_json(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(exclude_none=True)
    if isinstance(value, dict):
        return {key: _safe_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_json(item) for item in value]
    return value


def _scheme_name(scheme_id: str, scheme_catalog: dict[str, dict[str, Any]]) -> str:
    scheme = scheme_catalog.get(scheme_id) or {}
    return str(scheme.get("name") or scheme_id)


def _json_block(value: Any) -> str:
    import json

    normalized = _safe_json(value)
    text = json.dumps(normalized, indent=2, ensure_ascii=False)
    return f"<pre class='jurisai-chat-pre'>{escape(text)}</pre>"


def _render_chat_message(*, role: str, tone: str, title: str, body_html: str) -> str:
    return (
        f"<details class='jurisai-chat-details jurisai-chat-message-{tone}' open>"
        "<summary>"
        f"<div class='jurisai-chat-role'>{escape(role)}</div>"
        f"<div class='jurisai-chat-title'>{escape(title)}</div>"
        "</summary>"
        f"<div class='jurisai-chat-content'><div class='jurisai-chat-body'>{body_html}</div></div>"
        "</details>"
    )


def _render_record_trace_chat(
    record: dict[str, Any],
    scheme_catalog: dict[str, dict[str, Any]],
) -> str:
    messages: list[str] = []
    positives = set(record["must_retrieve_scheme_ids"])
    distractors = set(record["must_not_retrieve_scheme_ids"])

    messages.append(
        _render_chat_message(
            role="User",
            tone="user",
            title="Golden query",
            body_html=f"<p>{escape(record['user_query'])}</p>",
        )
    )

    if record.get("classification"):
        messages.append(
            _render_chat_message(
                role="Assistant",
                tone="assistant",
                title="LLM analysis",
                body_html=(
                    f"<p>Retriever query: <code>{escape(record.get('retrieval_query') or 'n/a')}</code></p>"
                    "<p>Captured classifier output for this record. This shows structured model output, not hidden chain-of-thought.</p>"
                    f"{_json_block(record['classification'])}"
                ),
            )
        )
    elif record.get("classifier_error"):
        messages.append(
            _render_chat_message(
                role="System",
                tone="system",
                title="Classifier fallback",
                body_html=(
                    "<p>The classifier failed for this record, so retrieval ran with fallback normalization.</p>"
                    f"{_json_block({'classifier_error': record['classifier_error']})}"
                ),
            )
        )

    profile_names = [
        profile.get("embedding_profile")
        for profile in (record.get("debug") or {}).get("profiles", [])
        if profile.get("embedding_profile")
    ]
    messages.append(
        _render_chat_message(
            role="Tool",
            tone="tool",
            title="Retrieval call",
            body_html=(
                "<p>Qdrant retrieval executed for this eval record.</p>"
                f"{_json_block({'normalized_query': record.get('normalized_query'), 'embed_query': record.get('embed_query'), 'actual_filters': record.get('actual_filters'), 'applied_filters': record.get('applied_filters'), 'ignored_filters': record.get('ignored_filters'), 'raw_hit_count': record.get('raw_hit_count'), 'embedding_profiles': profile_names})}"
            ),
        )
    )

    result_items: list[str] = []
    for index, item in enumerate(record.get("results") or [], start=1):
        scheme_id = item["scheme_id"]
        if scheme_id in positives:
            marker = "gold hit"
        elif scheme_id in distractors:
            marker = "distractor leaked"
        else:
            marker = "non-gold"
        scheme_name = item.get("name") or _scheme_name(scheme_id, scheme_catalog)
        score = float(item.get("adjusted_score") or item.get("match_score") or 0.0)
        reasons = ", ".join(item.get("match_reasons") or [])
        details = f"{escape(marker)} | score {score:.3f}"
        if reasons:
            details += f" | {escape(reasons)}"
        result_items.append(
            f"<li><strong>#{index} {escape(scheme_name)}</strong><br>{details}</li>"
        )
    if not result_items:
        result_items.append("<li>No schemes returned.</li>")
    messages.append(
        _render_chat_message(
            role="Tool",
            tone="tool",
            title="Retrieval results",
            body_html="<ul>" + "".join(result_items) + "</ul>",
        )
    )

    workflow_trace = record.get("workflow_trace") or record.get("trace_steps") or []
    if workflow_trace:
        messages.append(
            _render_chat_message(
                role="Assistant",
                tone="assistant",
                title="Workflow trace",
                body_html=(
                    "<p>Additional workflow steps were captured for this record.</p>"
                    f"{_json_block(workflow_trace)}"
                ),
            )
        )

    final_answer = record.get("final_answer") or record.get("generation")
    if final_answer:
        final_body = (
            f"<p>{escape(final_answer)}</p>"
            if isinstance(final_answer, str)
            else _json_block(final_answer)
        )
        messages.append(
            _render_chat_message(
                role="Assistant",
                tone="assistant",
                title="Final answer",
                body_html=final_body,
            )
        )
    else:
        messages.append(
            _render_chat_message(
                role="System",
                tone="system",
                title="Final answer not captured",
                body_html=(
                    "<p>This retrieval eval run stops after classifier, filter, and retrieval scoring. "
                    "No final answer generation was executed, so Phoenix will usually only show retrieval-eval spans.</p>"
                ),
            )
        )

    return "<div class='jurisai-chat'>" + "".join(messages) + "</div>"


def _status_color(status: str) -> str:
    if status in {"gold_hit", "present"}:
        return STATUS_GREEN
    if status in {"missed_gold", "distractor_retrieved"}:
        return STATUS_RED
    if status == "retrieved_non_gold":
        return STATUS_AMBER
    return STATUS_GRAY


def _html_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    if not rows:
        return (
            "<div class='jurisai-panel'>"
            "<div class='jurisai-muted'>No rows.</div>"
            "</div>"
        )

    header = "".join(
        f"<th>{escape(label)}</th>"
        for _, label in columns
    )
    body_rows: list[str] = []
    for row in rows:
        background = row.get("_row_color", "white")
        cells = []
        for key, _ in columns:
            value = row.get(key, "")
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            cells.append(
                f"<td>{escape(str(value))}</td>"
            )
        body_rows.append(
            f"<tr style='background:{background};'>{''.join(cells)}</tr>"
        )
    return (
        "<div class='jurisai-table-wrap'>"
        "<table class='jurisai-table'>"
        f"<thead><tr>{header}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody></table>"
        "</div>"
    )


def _summary_markdown(run_data: dict[str, Any]) -> str:
    trace_status = run_data["trace_status"]
    eval_mode = str(run_data.get("eval_mode") or "retrieval_core")
    return (
        f"**Run context**\n\n"
        f"- Started: `{run_data['started_at']}`\n"
        f"- Completed: `{run_data.get('completed_at') or 'in progress'}`\n"
        f"- Collection: `{run_data['collection_name']}`\n"
        f"- Evaluation mode: `{eval_mode}`\n"
        f"- Intent provider/model: `{run_data.get('intent_provider', 'n/a')}` / `{run_data.get('intent_model', 'n/a')}`\n"
        f"- Generation provider/model: `{run_data.get('generation_provider', 'n/a')}` / `{run_data.get('generation_model', 'n/a')}`\n"
        f"- Top-k: `{run_data['limit']}`\n"
        f"- Artifact path: `{run_data.get('output_path') or 'n/a'}`\n"
        f"- Trace project: `{run_data['trace_project']}`\n"
        f"- Run trace id: `{run_data['run_trace_id'] or 'n/a'}`\n"
        f"- Tracing enabled: `{trace_status['enabled']}`\n"
        f"- Tracing detail: `{trace_status['detail']}`"
    )


def _live_status_html(
    run_data: dict[str, Any] | None,
    *,
    current_record_id: str | None,
    processed_count: int,
    total_count: int,
    is_running: bool,
) -> str:
    if not run_data:
        return (
            "<div class='jurisai-panel'>"
            "<h3>Live Progress</h3>"
            "<div class='jurisai-muted'>Run the evaluation to watch records stream in here.</div>"
            "</div>"
        )

    status_label = "Running" if is_running else "Completed"
    current_record = _record_lookup(run_data, current_record_id) if current_record_id else None
    record_line = (
        f"{escape(current_record_id)} for {escape(current_record['persona_id'])}"
        if current_record
        else "waiting"
    )
    progress_ratio = (processed_count / total_count) if total_count else 0.0
    return (
        "<div class='jurisai-panel'>"
        "<h3>Live Progress</h3>"
        "<div class='jurisai-kv'>"
        f"<div class='jurisai-kv-label'>Status</div><div class='jurisai-kv-value'>{escape(status_label)}</div>"
        f"<div class='jurisai-kv-label'>Processed</div><div class='jurisai-kv-value'>{processed_count}/{total_count}</div>"
        f"<div class='jurisai-kv-label'>Current record</div><div class='jurisai-kv-value'>{record_line}</div>"
        f"<div class='jurisai-kv-label'>Recall@5</div><div class='jurisai-kv-value'>{_format_percent(run_data['avg_recall_at_5'])} <span class='jurisai-muted'>(raw {_format_decimal(run_data['avg_recall_at_5'])})</span></div>"
        f"<div class='jurisai-kv-label'>Distractor pass</div><div class='jurisai-kv-value'>{_format_percent(run_data['distractor_pass_rate'])} <span class='jurisai-muted'>(raw {_format_decimal(run_data['distractor_pass_rate'])})</span></div>"
        f"<div class='jurisai-kv-label'>Filter match</div><div class='jurisai-kv-value'>{_format_percent(run_data['expected_filter_match_rate'])} <span class='jurisai-muted'>(raw {_format_decimal(run_data['expected_filter_match_rate'])})</span></div>"
        "</div>"
        "<div class='jurisai-progress'>"
        f"<div class='jurisai-progress-fill' style='width:{_clamp_ratio(progress_ratio) * 100:.0f}%;'></div>"
        "</div>"
        "</div>"
    )


def _build_live_record_payloads(
    run_data: dict[str, Any] | None,
    current_record_id: str | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not run_data or not current_record_id:
        return {}, {}

    record = _record_lookup(run_data, current_record_id)
    if record is None:
        return {}, {}

    input_payload = {
        "record_id": record["record_id"],
        "persona_id": record["persona_id"],
        "user_query": record["user_query"],
        "expected_filters": record["expected_filters"],
        "required_query_terms": record["required_query_terms"],
        "classifier_filters": (
            (record["classification"] or {}).get("retrieval_filters")
            if record["classification"]
            else []
        ),
        "retrieval_query_generated": record["retrieval_query"],
        "embed_query_generated": record["embed_query"],
        "query_topics": record["query_topics"],
        "query_tags": record["query_tags"],
        "query_terms_generated": record["query_terms"],
        "actual_filters": record["actual_filters"],
        "effective_eval_filters": record["effective_eval_filters"],
        "applied_filters": record["applied_filters"],
        "ignored_filters": record["ignored_filters"],
    }
    output_payload = {
        "trace_id": record["trace_id"],
        "used_classifier": record["used_classifier"],
        "classifier_error": record["classifier_error"],
        "raw_hit_count": record["raw_hit_count"],
        "recall_at_3": record["recall_at_3"],
        "recall_at_5": record["recall_at_5"],
        "mrr_at_5": record["mrr_at_5"],
        "distractor_pass": record["distractor_pass"],
        "expected_filter_match": record["expected_filter_match"],
        "must_retrieve_scheme_ids": record["must_retrieve_scheme_ids"],
        "must_not_retrieve_scheme_ids": record["must_not_retrieve_scheme_ids"],
        "retrieved_schemes": [
            {
                "rank": index,
                "scheme_id": item["scheme_id"],
                "name": item.get("name"),
                "state": item.get("state"),
                "level": item.get("level"),
                "match_profile": item.get("match_profile"),
                "adjusted_score": item.get("adjusted_score"),
                "match_reasons": item.get("match_reasons"),
            }
            for index, item in enumerate(record["results"], start=1)
        ],
    }
    return input_payload, output_payload


def _clamp_ratio(value: float) -> float:
    return max(0.0, min(float(value), 1.0))


def _metric_tone(
    value: float,
    *,
    good_threshold: float,
    warn_threshold: float,
    higher_is_better: bool = True,
) -> str:
    if higher_is_better:
        if value >= good_threshold:
            return "good"
        if value >= warn_threshold:
            return "warn"
        return "bad"
    if value <= good_threshold:
        return "good"
    if value <= warn_threshold:
        return "warn"
    return "bad"


def _metric_label(tone: str) -> str:
    return {
        "good": "Strong",
        "warn": "Mixed",
        "bad": "Needs Work",
        "neutral": "Context",
    }.get(tone, "Context")


def _format_percent(value: float) -> str:
    return f"{_clamp_ratio(value):.0%}"


def _format_decimal(value: float) -> str:
    return f"{value:.3f}"


def _metric_card_html(
    *,
    label: str,
    value: str,
    note: str,
    tone: str = "neutral",
    badge: str | None = None,
    meter_ratio: float | None = None,
    subvalue: str | None = None,
) -> str:
    badge_html = (
        "<div class='jurisai-card-status'>"
        f"<span class='jurisai-card-badge jurisai-card-badge-{tone}'>{escape(badge)}</span>"
        "</div>"
        if badge
        else ""
    )
    subvalue_html = (
        f"<div class='jurisai-card-subvalue'>{escape(subvalue)}</div>" if subvalue else ""
    )
    meter_html = ""
    if meter_ratio is not None:
        meter_html = (
            "<div class='jurisai-meter'>"
            f"<div class='jurisai-meter-fill jurisai-meter-fill-{tone}' "
            f"style='width:{_clamp_ratio(meter_ratio) * 100:.0f}%;'></div>"
            "</div>"
        )
    return (
        f"<div class='jurisai-card jurisai-card-{tone}'>"
        f"<div class='jurisai-card-label'>{escape(label)}</div>"
        f"{badge_html}"
        f"<div class='jurisai-card-value'>{escape(value)}</div>"
        f"{subvalue_html}"
        f"<div class='jurisai-card-note'>{escape(note)}</div>"
        f"{meter_html}"
        "</div>"
    )


def _summary_cards_html(run_data: dict[str, Any] | None) -> str:
    if not run_data:
        return (
            "<div class='jurisai-card-grid'>"
            "<div class='jurisai-card'><div class='jurisai-card-label'>Status</div>"
            "<div class='jurisai-card-note'>Run the evaluation to populate metrics.</div></div>"
            "</div>"
        )

    record_count = max(int(run_data["record_count"] or 0), 1)
    classifier_error_rate = run_data["classifier_error_count"] / record_count

    recall3_tone = _metric_tone(
        run_data["avg_recall_at_3"],
        good_threshold=0.45,
        warn_threshold=0.25,
    )
    recall5_tone = _metric_tone(
        run_data["avg_recall_at_5"],
        good_threshold=0.7,
        warn_threshold=0.45,
    )
    mrr_tone = _metric_tone(
        run_data["avg_mrr_at_5"],
        good_threshold=0.45,
        warn_threshold=0.25,
    )
    distractor_tone = _metric_tone(
        run_data["distractor_pass_rate"],
        good_threshold=0.9,
        warn_threshold=0.75,
    )
    filter_tone = _metric_tone(
        run_data["expected_filter_match_rate"],
        good_threshold=0.8,
        warn_threshold=0.5,
    )
    classifier_error_tone = _metric_tone(
        classifier_error_rate,
        good_threshold=0.0,
        warn_threshold=0.1,
        higher_is_better=False,
    )

    cards = [
        _metric_card_html(
            label="Records",
            value=str(run_data["record_count"]),
            subvalue="Golden records scored",
            note="Eval set size for this run.",
            tone="neutral",
            badge="Context",
        ),
        _metric_card_html(
            label="Recall@3",
            value=_format_percent(run_data["avg_recall_at_3"]),
            subvalue=f"raw {_format_decimal(run_data['avg_recall_at_3'])}",
            note="How much required gold coverage shows up in the top 3.",
            tone=recall3_tone,
            badge=_metric_label(recall3_tone),
            meter_ratio=run_data["avg_recall_at_3"],
        ),
        _metric_card_html(
            label="Recall@5",
            value=_format_percent(run_data["avg_recall_at_5"]),
            subvalue=f"raw {_format_decimal(run_data['avg_recall_at_5'])}",
            note="Top 5 gold coverage. This is the main retrieval success signal.",
            tone=recall5_tone,
            badge=_metric_label(recall5_tone),
            meter_ratio=run_data["avg_recall_at_5"],
        ),
        _metric_card_html(
            label="MRR@5",
            value=_format_percent(run_data["avg_mrr_at_5"]),
            subvalue=f"raw {_format_decimal(run_data['avg_mrr_at_5'])}",
            note="Ranking quality. Higher means the first correct scheme appears earlier.",
            tone=mrr_tone,
            badge=_metric_label(mrr_tone),
            meter_ratio=run_data["avg_mrr_at_5"],
        ),
        _metric_card_html(
            label="Distractor Pass",
            value=_format_percent(run_data["distractor_pass_rate"]),
            subvalue=f"raw {_format_decimal(run_data['distractor_pass_rate'])}",
            note="Top 5 results stayed free of must-not schemes.",
            tone=distractor_tone,
            badge=_metric_label(distractor_tone),
            meter_ratio=run_data["distractor_pass_rate"],
        ),
        _metric_card_html(
            label="Filter Match",
            value=_format_percent(run_data["expected_filter_match_rate"]),
            subvalue=f"raw {_format_decimal(run_data['expected_filter_match_rate'])}",
            note="Whether the run recovered the expected intent filters per record.",
            tone=filter_tone,
            badge=_metric_label(filter_tone),
            meter_ratio=run_data["expected_filter_match_rate"],
        ),
        _metric_card_html(
            label="Classifier Errors",
            value=str(run_data["classifier_error_count"]),
            subvalue=f"{_format_percent(classifier_error_rate)} of records",
            note="Classifier calls that failed before retrieval.",
            tone=classifier_error_tone,
            badge="Clean" if run_data["classifier_error_count"] == 0 else _metric_label(classifier_error_tone),
            meter_ratio=classifier_error_rate,
        ),
        _metric_card_html(
            label="Trace Project",
            value=run_data["trace_project"],
            subvalue="Phoenix span grouping",
            note="Use this label to correlate dashboard runs with traces.",
            tone="neutral",
            badge="Context",
        ),
    ]
    return f"<div class='jurisai-card-grid'>{''.join(cards)}</div>"


def _record_summary_html(run_data: dict[str, Any] | None) -> str:
    if not run_data:
        return (
            "<div class='jurisai-panel'>"
            "<div class='jurisai-muted'>Per-record metrics will appear here after a run.</div>"
            "</div>"
        )

    rows = []
    for row in run_data["records"]:
        if (
            row["recall_at_5"] >= 0.66
            and row["distractor_pass"]
            and row["expected_filter_match"]
        ):
            outcome = "strong"
        elif row["recall_at_5"] > 0.0:
            outcome = "mixed"
        else:
            outcome = "needs work"
        rows.append(
            {
                "record": row["record_id"],
                "persona": row["persona_id"],
                "outcome": outcome,
                "mode": "classifier" if row["used_classifier"] else "fallback",
                "raw_nodes": row["raw_hit_count"],
                "returned": len(row["results"]),
                "recall@3": _format_percent(row["recall_at_3"]),
                "recall@5": _format_percent(row["recall_at_5"]),
                "mrr@5": _format_percent(row["mrr_at_5"]),
                "distractors": "pass" if row["distractor_pass"] else "leaked",
                "filters": "match" if row["expected_filter_match"] else "miss",
                "_row_color": "#12151b",
            }
        )

    return _html_table(
        rows,
        [
            ("record", "Record"),
            ("persona", "Persona"),
            ("outcome", "Outcome"),
            ("mode", "Mode"),
            ("raw_nodes", "Raw Nodes"),
            ("returned", "Returned"),
            ("recall@3", "Recall@3"),
            ("recall@5", "Recall@5"),
            ("mrr@5", "MRR@5"),
            ("distractors", "Distractors"),
            ("filters", "Filter Match"),
        ],
    )


def _record_lookup(run_data: dict[str, Any], record_id: str) -> dict[str, Any] | None:
    for row in run_data.get("records", []):
        if row["record_id"] == record_id:
            return row
    return None


def _render_record_outputs(
    run_data: dict[str, Any] | None,
    record_id: str | None,
) -> tuple[str, Any, Any, Any, str, str, str, str]:
    if not run_data or not record_id:
        empty_message = "Run the evaluation and select a record to inspect details."
        return (
            empty_message,
            {},
            {},
            {},
            "<div>No results yet.</div>",
            "<div>No gold comparison yet.</div>",
            "<div>No raw nodes yet.</div>",
            "<div class='jurisai-panel'>No trace chat yet.</div>",
        )

    record = _record_lookup(run_data, record_id)
    if record is None:
        return (
            "Selected record was not found in the current run.",
            {},
            {},
            {},
            "<div>No results.</div>",
            "<div>No gold comparison.</div>",
            "<div>No raw nodes.</div>",
            "<div class='jurisai-panel'>No trace chat.</div>",
        )

    scheme_catalog = record["scheme_catalog"]
    positives = set(record["must_retrieve_scheme_ids"])
    distractors = set(record["must_not_retrieve_scheme_ids"])
    result_ids = [item["scheme_id"] for item in record["results"]]

    classifier_tone = "jurisai-chip-green" if record["used_classifier"] else "jurisai-chip-amber"
    distractor_tone = "jurisai-chip-green" if record["distractor_pass"] else "jurisai-chip-red"
    filter_tone = "jurisai-chip-green" if record["expected_filter_match"] else "jurisai-chip-red"
    overview = (
        "<div class='jurisai-panel'>"
        f"<h3>{escape(record['record_id'])} <span class='jurisai-muted'>for {escape(record['persona_id'])}</span></h3>"
        "<div style='margin-bottom:10px;'>"
        f"<span class='jurisai-chip {classifier_tone}'>"
        f"{'Classifier used' if record['used_classifier'] else 'Classifier fallback'}"
        "</span>"
        f"<span class='jurisai-chip {distractor_tone}'>"
        f"{'Distractors blocked' if record['distractor_pass'] else 'Distractor leakage'}"
        "</span>"
        f"<span class='jurisai-chip {filter_tone}'>"
        f"{'Filters matched' if record['expected_filter_match'] else 'Filters mismatched'}"
        "</span>"
        "</div>"
        "<div class='jurisai-kv'>"
        f"<div class='jurisai-kv-label'>Trace id</div><div class='jurisai-kv-value'>{escape(record['trace_id'] or 'n/a')}</div>"
        f"<div class='jurisai-kv-label'>User query</div><div class='jurisai-kv-value'>{escape(record['user_query'])}</div>"
        f"<div class='jurisai-kv-label'>Raw nodes fetched</div><div class='jurisai-kv-value'>{record['raw_hit_count']}</div>"
        f"<div class='jurisai-kv-label'>Final schemes returned</div><div class='jurisai-kv-value'>{len(record['results'])}</div>"
        f"<div class='jurisai-kv-label'>Recall@3</div><div class='jurisai-kv-value'>{_format_percent(record['recall_at_3'])} <span class='jurisai-muted'>(raw {_format_decimal(record['recall_at_3'])})</span></div>"
        f"<div class='jurisai-kv-label'>Recall@5</div><div class='jurisai-kv-value'>{_format_percent(record['recall_at_5'])} <span class='jurisai-muted'>(raw {_format_decimal(record['recall_at_5'])})</span></div>"
        f"<div class='jurisai-kv-label'>MRR@5</div><div class='jurisai-kv-value'>{_format_percent(record['mrr_at_5'])} <span class='jurisai-muted'>(raw {_format_decimal(record['mrr_at_5'])})</span></div>"
        f"<div class='jurisai-kv-label'>Classifier error</div><div class='jurisai-kv-value'>{escape(record['classifier_error'] or 'none')}</div>"
        "</div>"
        "</div>"
    )

    query_payload = {
        "user_query": record["user_query"],
        "retrieval_query_generated": record["retrieval_query"],
        "embed_query_generated": record["embed_query"],
        "query_topics": record["query_topics"],
        "query_tags": record["query_tags"],
        "required_query_terms": record["required_query_terms"],
        "query_terms_generated": record["query_terms"],
    }
    filter_payload = {
        "expected_filters": record["expected_filters"],
        "classifier_filters": (
            (record["classification"] or {}).get("retrieval_filters") if record["classification"] else []
        ),
        "actual_filters": record["actual_filters"],
        "effective_eval_filters": record["effective_eval_filters"],
        "applied_filters": record["applied_filters"],
        "ignored_filters": record["ignored_filters"],
    }
    classifier_payload = record["classification"] or {
        "used_classifier": record["used_classifier"],
        "classifier_error": record["classifier_error"],
    }

    result_rows = []
    for index, item in enumerate(record["results"], start=1):
        scheme_id = item["scheme_id"]
        if scheme_id in positives:
            status = "gold_hit"
        elif scheme_id in distractors:
            status = "distractor_retrieved"
        else:
            status = "retrieved_non_gold"
        result_rows.append(
            {
                "rank": index,
                "status": status,
                "scheme_name": item.get("name") or _scheme_name(scheme_id, scheme_catalog),
                "scheme_id": scheme_id,
                "state": item.get("state") or "",
                "level": item.get("level") or "",
                "match_profile": item.get("match_profile") or "",
                "match_score": f"{float(item.get('match_score') or 0.0):.3f}",
                "adjusted_score": f"{float(item.get('adjusted_score') or 0.0):.3f}",
                "reasons": ", ".join(item.get("match_reasons") or []),
                "_row_color": _status_color(status),
            }
        )

    gold_rows = []
    for scheme_id in record["must_retrieve_scheme_ids"]:
        present = scheme_id in result_ids
        gold_rows.append(
            {
                "status": "present" if present else "missed_gold",
                "scheme_name": _scheme_name(scheme_id, scheme_catalog),
                "scheme_id": scheme_id,
                "_row_color": _status_color("present" if present else "missed_gold"),
            }
        )
    for scheme_id in record["must_not_retrieve_scheme_ids"]:
        retrieved = scheme_id in result_ids
        gold_rows.append(
            {
                "status": "distractor_retrieved" if retrieved else "distractor_blocked",
                "scheme_name": _scheme_name(scheme_id, scheme_catalog),
                "scheme_id": scheme_id,
                "_row_color": _status_color(
                    "distractor_retrieved" if retrieved else "distractor_blocked"
                ),
            }
        )

    raw_node_rows = []
    for profile in (record["debug"] or {}).get("profiles", []):
        for index, hit in enumerate(profile.get("raw_hits") or [], start=1):
            raw_node_rows.append(
                {
                    "profile": profile.get("embedding_profile"),
                    "profile_rank": index,
                    "scheme_name": hit.get("name") or _scheme_name(hit["scheme_id"], scheme_catalog),
                    "scheme_id": hit.get("scheme_id"),
                    "state": hit.get("state") or "",
                    "level": hit.get("level") or "",
                    "score": f"{float(hit.get('score') or 0.0):.3f}",
                    "topics": ", ".join(hit.get("topics") or []),
                    "tags": ", ".join(hit.get("tags") or []),
                }
            )

    results_html = _html_table(
        result_rows,
        [
            ("rank", "Rank"),
            ("status", "Status"),
            ("scheme_name", "Scheme"),
            ("scheme_id", "Scheme ID"),
            ("state", "State"),
            ("level", "Level"),
            ("match_profile", "Winning Profile"),
            ("match_score", "Match Score"),
            ("adjusted_score", "Adjusted Score"),
            ("reasons", "Reasons"),
        ],
    )
    gold_html = _html_table(
        gold_rows,
        [
            ("status", "Gold Status"),
            ("scheme_name", "Scheme"),
            ("scheme_id", "Scheme ID"),
        ],
    )
    raw_nodes_html = _html_table(
        raw_node_rows,
        [
            ("profile", "Embedding Profile"),
            ("profile_rank", "Profile Rank"),
            ("scheme_name", "Scheme"),
            ("scheme_id", "Scheme ID"),
            ("state", "State"),
            ("level", "Level"),
            ("score", "Raw Score"),
            ("topics", "Topics"),
            ("tags", "Tags"),
        ],
    )
    trace_chat_html = _render_record_trace_chat(record, scheme_catalog)
    return (
        overview,
        _safe_json(query_payload),
        _safe_json(filter_payload),
        _safe_json(classifier_payload),
        results_html,
        gold_html,
        raw_nodes_html,
        trace_chat_html,
    )


def _render_run_snapshot(
    *,
    run_data: dict[str, Any] | None,
    sidebar_md: str,
    sidebar_df: pd.DataFrame,
    current_record_id: str | None,
    processed_count: int,
    total_count: int,
    is_running: bool,
):
    record_choices = [row["record_id"] for row in (run_data or {}).get("records", [])]
    labeled_choices = [
        (
            f"{row['record_id']} · {row['persona_id']} · R@5 {row['recall_at_5']:.2f}",
            row["record_id"],
        )
        for row in (run_data or {}).get("records", [])
    ]
    should_autoselect_record = bool(record_choices) and processed_count <= 1
    selected_record = (
        current_record_id
        if should_autoselect_record and current_record_id in record_choices
        else record_choices[0]
        if should_autoselect_record and record_choices
        else None
    )
    if selected_record is not None:
        (
            overview,
            query_payload,
            filter_payload,
            classifier_payload,
            result_table,
            gold_table,
            raw_node_table,
            trace_chat_html,
        ) = _render_record_outputs(run_data, selected_record)
    else:
        overview = gr.skip()
        query_payload = gr.skip()
        filter_payload = gr.skip()
        classifier_payload = gr.skip()
        result_table = gr.skip()
        gold_table = gr.skip()
        raw_node_table = gr.skip()
        trace_chat_html = gr.skip()
    live_inputs, live_outputs = _build_live_record_payloads(run_data, current_record_id)
    summary_md = (
        _summary_markdown(run_data)
        if run_data
        else "Run the evaluation to populate metrics."
    )
    return (
        run_data,
        summary_md,
        sidebar_md,
        _summary_cards_html(run_data),
        _record_summary_html(run_data),
        sidebar_df,
        (
            gr.update(choices=labeled_choices, value=selected_record)
            if selected_record is not None
            else gr.update(choices=labeled_choices)
        ),
        overview,
        query_payload,
        filter_payload,
        classifier_payload,
        result_table,
        gold_table,
        raw_node_table,
        trace_chat_html,
        _live_status_html(
            run_data,
            current_record_id=current_record_id,
            processed_count=processed_count,
            total_count=total_count,
            is_running=is_running,
        ),
        _safe_json(live_inputs),
        _safe_json(live_outputs),
    )


def create_dashboard(
    *,
    default_collection_name: str = settings.eval.qdrant_collection,
    default_trace_project: str = settings.phoenix.project_name,
    default_phoenix_endpoint: str | None = settings.phoenix.collector_endpoint,
) -> gr.Blocks:
    sidebar_markdown, sidebar_df = _build_collection_sidebar(
        collection_name=default_collection_name
    )

    with gr.Blocks(title="JurisAI Retrieval Eval Dashboard") as demo:
        run_state = gr.State(value=None)
        auto_refresh_timer = gr.Timer(value=10, active=True, render=False)

        gr.HTML(APP_CSS)
        gr.HTML(
            """
            <div class="jurisai-hero">
              <h1>JurisAI Retrieval Eval Dashboard</h1>
              <p>
                Inspect every golden record, compare expected versus actual retrieval behavior,
                review generated queries and filters, and correlate runs with Phoenix trace IDs.
              </p>
            </div>
            """
        )

        with gr.Row():
            with gr.Column(scale=1, elem_classes=["jurisai-sidebar"], min_width=340):
                with gr.Group():
                    gr.Markdown("### Run Controls")
                    eval_mode = gr.Dropdown(
                        label="Eval mode",
                        choices=[
                            ("Retrieval core", "retrieval_core"),
                            ("Agentic workflow", "agentic_workflow"),
                        ],
                        value="retrieval_core",
                    )
                    intent_provider = gr.Dropdown(
                        label="Intent provider",
                        choices=["gemini", "llamaindex_google", "local_openai", "openrouter"],
                        value=settings.workflow.intent_provider,
                    )
                    intent_model = gr.Textbox(
                        label="Intent model",
                        value=settings.workflow.intent_model,
                        info="For local or OpenRouter runs, set this to the model id you want to route to.",
                    )
                    generation_provider = gr.Dropdown(
                        label="Generation provider",
                        choices=["gemini", "llamaindex_google", "local_openai", "openrouter"],
                        value=settings.workflow.generation_provider,
                    )
                    generation_model = gr.Textbox(
                        label="Generation model",
                        value=settings.workflow.generation_model,
                        info="Used by agentic workflow mode for planning and final answer generation.",
                    )
                    limit = gr.Number(label="Top-k", value=5, precision=0)
                    collection_name = gr.Textbox(
                        label="Qdrant collection",
                        value=default_collection_name,
                    )
                    trace_project = gr.Textbox(
                        label="Phoenix project",
                        value=default_trace_project,
                    )
                    phoenix_endpoint = gr.Textbox(
                        label="Phoenix collector endpoint",
                        value=default_phoenix_endpoint or "",
                    )
                    with gr.Row():
                        run_button = gr.Button("Run evaluation", variant="primary", size="lg")
                        stop_button = gr.Button("Stop run", variant="secondary", size="lg")

                with gr.Accordion("How to start this dashboard", open=False):
                    gr.Markdown(
                        """
                        Start it from the repo root with:

                        ```bash
                        uv run python scripts/run_retrieval_eval_dashboard.py --host 127.0.0.1 --port 7860 --trace-project jurisai-retrieval-eval-dashboard
                        ```

                        Then open [http://127.0.0.1:7860](http://127.0.0.1:7860).

                        If Phoenix traces should appear, make sure `PHOENIX_COLLECTOR_ENDPOINT`
                        is set, and add `PHOENIX_API_KEY` too for Arize cloud.
                        """
                    )

                summary_md = gr.Markdown("Run the evaluation to populate metrics.")

                with gr.Accordion("Eval collection coverage", open=False):
                    sidebar_md = gr.Markdown(sidebar_markdown)

            with gr.Column(scale=3, elem_classes=["jurisai-main"]):
                summary_cards = gr.HTML(_summary_cards_html(None))
                live_status = gr.HTML(_live_status_html(None, current_record_id=None, processed_count=0, total_count=0, is_running=False))
                with gr.Tabs():
                    with gr.Tab("Live Progress"):
                        with gr.Row():
                            live_inputs_json = gr.JSON(label="Current record inputs")
                            live_outputs_json = gr.JSON(label="Current record outputs")
                    with gr.Tab("Run Overview"):
                        gr.Markdown("### Per-record summary")
                        summary_table = gr.HTML(_record_summary_html(None))
                    with gr.Tab("Collection Coverage"):
                        gr.Markdown(
                            "### Eval schemes indexed for retrieval\n"
                            "This full-width table shows every scheme in the eval subset and whether it is present in the vector DB."
                        )
                        coverage_table = gr.Dataframe(
                            value=sidebar_df,
                            label="Eval schemes and VDB coverage",
                            interactive=False,
                            wrap=True,
                            max_height=720,
                        )
                    with gr.Tab("Record Inspector"):
                        record_selector = gr.Dropdown(
                            label="Inspect golden record",
                            choices=[],
                            value=None,
                            info="Choose a scored record to inspect generated queries, filters, and fetched schemes.",
                        )
                        record_overview = gr.HTML(
                            "<div class='jurisai-panel'><div class='jurisai-muted'>"
                            "Select a record after running the evaluation."
                            "</div></div>"
                        )
                        with gr.Tabs():
                            with gr.Tab("Query & Filters"):
                                with gr.Row():
                                    query_json = gr.JSON(label="Query details")
                                    filter_json = gr.JSON(label="Filter details")
                            with gr.Tab("Classifier"):
                                classifier_json = gr.JSON(label="Classifier output")
                            with gr.Tab("Retrieved vs Gold"):
                                gr.Markdown("#### Retrieved schemes")
                                results_html = gr.HTML("<div class='jurisai-panel'>No results yet.</div>")
                                gr.Markdown("#### Gold expectations")
                                gold_html = gr.HTML("<div class='jurisai-panel'>No gold comparison yet.</div>")
                            with gr.Tab("Raw Nodes"):
                                raw_nodes_html = gr.HTML("<div class='jurisai-panel'>No raw nodes yet.</div>")
                            with gr.Tab("Trace Chat"):
                                trace_chat = gr.HTML("<div class='jurisai-panel'>No trace chat yet.</div>")

        def _run_and_render(
            eval_mode_value: str,
            intent_provider_value: str,
            intent_model_value: str,
            generation_provider_value: str,
            generation_model_value: str,
            limit_value: float,
            collection_name_value: str,
            trace_project_value: str,
            phoenix_endpoint_value: str,
        ):
            resolved_limit = int(limit_value or 5)
            resolved_collection_name = (
                collection_name_value.strip() or default_collection_name
            )
            resolved_intent_provider = intent_provider_value.strip() or settings.workflow.intent_provider
            resolved_intent_model = intent_model_value.strip() or settings.workflow.intent_model
            resolved_generation_provider = (
                generation_provider_value.strip() or settings.workflow.generation_provider
            )
            resolved_generation_model = (
                generation_model_value.strip() or settings.workflow.generation_model
            )
            resolved_trace_project = (
                trace_project_value.strip() or default_trace_project
            )
            resolved_phoenix_endpoint = phoenix_endpoint_value.strip() or None
            local_sidebar_md, local_sidebar_df = _build_collection_sidebar(
                collection_name=resolved_collection_name
            )
            scheme_catalog = _load_eval_scheme_catalog()
            yield _render_run_snapshot(
                run_data=None,
                sidebar_md=local_sidebar_md,
                sidebar_df=local_sidebar_df,
                current_record_id=None,
                processed_count=0,
                total_count=0,
                is_running=True,
            )
            iterator = (
                iter_agentic_workflow_eval
                if eval_mode_value == "agentic_workflow"
                else iter_retrieval_eval
            )
            for run_data, record_result, processed_count, total_count in iterator(
                limit=resolved_limit,
                collection_name=resolved_collection_name,
                include_debug=True,
                intent_provider=resolved_intent_provider,
                intent_model=resolved_intent_model,
                generation_provider=resolved_generation_provider,
                generation_model=resolved_generation_model,
                trace_project=resolved_trace_project,
                phoenix_endpoint=resolved_phoenix_endpoint,
                persist_artifact=True,
            ):
                for row in run_data.get("records", []):
                    row["scheme_catalog"] = scheme_catalog
                yield _render_run_snapshot(
                    run_data=run_data,
                    sidebar_md=local_sidebar_md,
                    sidebar_df=local_sidebar_df,
                    current_record_id=record_result["record_id"],
                    processed_count=processed_count,
                    total_count=total_count,
                    is_running=processed_count < total_count,
                )

        def _select_record(run_data: dict[str, Any] | None, record_id: str | None):
            return _render_record_outputs(run_data, record_id)

        def _refresh_coverage(collection_name_value: str):
            return _build_collection_sidebar(
                collection_name=collection_name_value.strip() or default_collection_name
            )

        run_event = run_button.click(
            _run_and_render,
            inputs=[
                eval_mode,
                intent_provider,
                intent_model,
                generation_provider,
                generation_model,
                limit,
                collection_name,
                trace_project,
                phoenix_endpoint,
            ],
            outputs=[
                run_state,
                summary_md,
                sidebar_md,
                summary_cards,
                summary_table,
                coverage_table,
                record_selector,
                record_overview,
                query_json,
                filter_json,
                classifier_json,
                results_html,
                gold_html,
                raw_nodes_html,
                trace_chat,
                live_status,
                live_inputs_json,
                live_outputs_json,
            ],
        )

        stop_button.click(
            lambda: None,
            inputs=[],
            outputs=[],
            cancels=[run_event],
        )

        record_selector.change(
            _select_record,
            inputs=[run_state, record_selector],
            outputs=[
                record_overview,
                query_json,
                filter_json,
                classifier_json,
                results_html,
                gold_html,
                raw_nodes_html,
                trace_chat,
            ],
        )

        auto_refresh_timer.tick(
            _refresh_coverage,
            inputs=[collection_name],
            outputs=[sidebar_md, coverage_table],
        )

    return demo
