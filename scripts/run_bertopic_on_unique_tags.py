#!/usr/bin/env python3
"""Run BERTopic on unique tags with in-code configuration."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LOGGER = logging.getLogger("bertopic_unique_tags")
GENERIC_LABEL_WORDS = {
    "aid",
    "aids",
    "assistance",
    "benefit",
    "benefits",
    "class",
    "development",
    "education",
    "facility",
    "financial",
    "general",
    "help",
    "level",
    "programme",
    "program",
    "purchase",
    "scheme",
    "schemes",
    "section",
    "service",
    "services",
    "student",
    "students",
    "support",
    "training",
    "welfare",
}


def to_jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "item") and callable(value.item):
        try:
            return value.item()
        except Exception:
            pass
    return value


def read_unique_tags(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    tags = payload.get("unique_tags", [])
    if not isinstance(tags, list):
        raise ValueError("Input JSON is missing 'unique_tags' as a list.")
    return [tag.strip() for tag in tags if isinstance(tag, str) and tag.strip()]


def load_json_file(path: Path | None) -> Any:
    if path is None:
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def build_model(
    *,
    language: str,
    embedding_model_name: str,
    top_n_words: int,
    ngram_range: tuple[int, int],
    min_topic_size: int,
    nr_topics: int | str | None,
    calculate_probabilities: bool,
    low_memory: bool,
    random_state: int,
    umap_n_neighbors: int,
    umap_n_components: int,
    umap_min_dist: float,
    umap_metric: str,
    hdbscan_min_cluster_size: int,
    hdbscan_min_samples: int | None,
    hdbscan_metric: str,
    cluster_selection_method: str,
    min_df: int,
    max_df: float,
    stop_words: str | None,
    representation_model_name: str | None,
    seed_topic_file: Path | None,
    zeroshot_topic_file: Path | None,
    zeroshot_min_similarity: float,
):
    try:
        from bertopic import BERTopic
        from bertopic.representation import KeyBERTInspired
        from hdbscan import HDBSCAN
        from sentence_transformers import SentenceTransformer
        from sklearn.feature_extraction.text import CountVectorizer
        from umap import UMAP
    except ImportError as exc:
        raise SystemExit(
            "Missing BERTopic dependencies. Install them first, for example:\n"
            "  uv add bertopic sentence-transformers hdbscan umap-learn scikit-learn\n"
            f"Original import error: {exc}"
        ) from exc

    embedding_model = SentenceTransformer(embedding_model_name)
    vectorizer_model = CountVectorizer(
        ngram_range=ngram_range,
        stop_words=stop_words,
        min_df=min_df,
        max_df=max_df,
    )
    umap_model = UMAP(
        n_neighbors=umap_n_neighbors,
        n_components=umap_n_components,
        min_dist=umap_min_dist,
        metric=umap_metric,
        low_memory=low_memory,
        random_state=random_state,
    )

    hdbscan_kwargs: dict[str, Any] = {
        "min_cluster_size": hdbscan_min_cluster_size,
        "metric": hdbscan_metric,
        "cluster_selection_method": cluster_selection_method,
        "prediction_data": True,
    }
    if hdbscan_min_samples is not None:
        hdbscan_kwargs["min_samples"] = hdbscan_min_samples
    hdbscan_model = HDBSCAN(**hdbscan_kwargs)

    representation_model = None
    if representation_model_name == "keybert":
        representation_model = KeyBERTInspired()

    return BERTopic(
        language=language,
        embedding_model=embedding_model,
        top_n_words=top_n_words,
        n_gram_range=ngram_range,
        min_topic_size=min_topic_size,
        nr_topics=nr_topics,
        low_memory=low_memory,
        calculate_probabilities=calculate_probabilities,
        seed_topic_list=load_json_file(seed_topic_file),
        zeroshot_topic_list=load_json_file(zeroshot_topic_file),
        zeroshot_min_similarity=zeroshot_min_similarity,
        vectorizer_model=vectorizer_model,
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        representation_model=representation_model,
        verbose=True,
    )


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(to_jsonable(payload), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def configure_logging(run_dir: Path) -> Path:
    logs_dir = run_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "run.log"

    LOGGER.handlers.clear()
    LOGGER.setLevel(logging.INFO)
    LOGGER.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    LOGGER.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    LOGGER.addHandler(stream_handler)

    return log_path


def slugify(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value.strip())
    parts = [part for part in cleaned.split("-") if part]
    return "-".join(parts) or "bertopic-run"


def create_run_dir(output_root: Path, run_name: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_root / f"{timestamp}_{slugify(run_name)}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def clean_label_candidate(term: str, max_words: int) -> str:
    words = [
        part
        for part in "".join(char.lower() if char.isalnum() or char.isspace() else " " for char in term).split()
        if part
    ]
    if not words:
        return ""

    filtered = [word for word in words if word not in GENERIC_LABEL_WORDS]
    chosen_words = filtered if filtered else words
    return " ".join(chosen_words[:max_words]).strip()


def normalize_text(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() or char.isspace() else " " for char in value)
    return " ".join(cleaned.split())


def prefix_key(term: str, width: int = 5) -> str:
    normalized = normalize_text(term)
    if not normalized:
        return ""
    first_word = normalized.split()[0]
    return first_word[:width]


def build_short_topic_labels(
    topic_model: Any,
    docs: list[str],
    topics: list[int],
    max_words: int,
    preferred_topic_keywords: list[str] | None,
) -> dict[int, str]:
    labels: dict[int, str] = {-1: "outlier"}
    topic_to_docs: dict[int, list[str]] = {}
    for document, topic_id in zip(docs, topics):
        topic_to_docs.setdefault(int(topic_id), []).append(document)

    preferred_keywords = [normalize_text(keyword) for keyword in (preferred_topic_keywords or []) if keyword.strip()]
    preferred_prefixes = {keyword: prefix_key(keyword) for keyword in preferred_keywords}

    for topic_id in topic_model.get_topics():
        if topic_id == -1:
            continue

        topic_documents = topic_to_docs.get(int(topic_id), [])
        normalized_documents = [normalize_text(document) for document in topic_documents]

        forced_label = ""
        for keyword in preferred_keywords:
            keyword_prefix = preferred_prefixes[keyword]
            if keyword_prefix and any(prefix_key(document) == keyword_prefix for document in normalized_documents):
                forced_label = keyword
                break

        if forced_label:
            labels[int(topic_id)] = forced_label
            continue

        topic_terms = topic_model.get_topic(topic_id) or []
        label = ""
        for item in topic_terms:
            raw_term = item[0] if isinstance(item, (list, tuple)) and item else str(item)
            candidate = clean_label_candidate(str(raw_term), max_words=max_words)
            if candidate:
                label = candidate
                break

        if not label:
            label = f"topic {topic_id}"
        labels[int(topic_id)] = label

    return labels


def write_html_figure(figure: Any, output_path: Path) -> None:
    figure.write_html(str(output_path), include_plotlyjs="cdn")


def save_visualizations(topic_model: Any, output_dir: Path) -> dict[str, str]:
    visualizations_dir = output_dir / "visualizations"
    visualizations_dir.mkdir(parents=True, exist_ok=True)

    saved_paths: dict[str, str] = {}
    visualization_builders = {
        "topics": topic_model.visualize_topics,
        "barchart": topic_model.visualize_barchart,
        "hierarchy": topic_model.visualize_hierarchy,
        "heatmap": topic_model.visualize_heatmap,
    }

    for name, builder in visualization_builders.items():
        output_path = visualizations_dir / f"{name}.html"
        LOGGER.info("Generating visualization: %s", name)
        try:
            figure = builder()
            write_html_figure(figure, output_path)
            saved_paths[name] = str(output_path.resolve())
            LOGGER.info("Saved visualization: %s", output_path.resolve())
        except Exception as exc:
            saved_paths[name] = f"failed: {exc}"
            LOGGER.exception("Failed to generate visualization %s", name)

    return saved_paths


def run(
    *,
    input_file: Path,
    output_root: Path,
    run_name: str,
    save_model: bool,
    language: str,
    embedding_model_name: str,
    top_n_words: int,
    ngram_range: tuple[int, int],
    min_topic_size: int,
    nr_topics: int | str | None,
    calculate_probabilities: bool,
    low_memory: bool,
    random_state: int,
    umap_n_neighbors: int,
    umap_n_components: int,
    umap_min_dist: float,
    umap_metric: str,
    hdbscan_min_cluster_size: int,
    hdbscan_min_samples: int | None,
    hdbscan_metric: str,
    cluster_selection_method: str,
    min_df: int,
    max_df: float,
    stop_words: str | None,
    representation_model_name: str | None,
    seed_topic_file: Path | None,
    zeroshot_topic_file: Path | None,
    zeroshot_min_similarity: float,
    max_topic_label_words: int,
    preferred_topic_keywords: list[str] | None,
) -> None:
    run_dir = create_run_dir(output_root, run_name)
    stats_dir = run_dir / "stats"
    model_dir = run_dir / "model"
    stats_dir.mkdir(parents=True, exist_ok=True)
    log_path = configure_logging(run_dir)
    LOGGER.info("Created run directory: %s", run_dir.resolve())
    LOGGER.info("Log file: %s", log_path.resolve())
    LOGGER.info("Input file: %s", input_file.resolve())
    LOGGER.info("Output root: %s", output_root.resolve())
    LOGGER.info("Run name: %s", run_name)

    docs = read_unique_tags(input_file)
    if not docs:
        raise SystemExit("No unique tags found in input file.")
    LOGGER.info("Loaded %d tag documents from input JSON.", len(docs))
    LOGGER.info(
        "Key model config: embedding=%s, min_topic_size=%d, nr_topics=%s, ngram_range=%s, random_state=%d",
        embedding_model_name,
        min_topic_size,
        nr_topics,
        ngram_range,
        random_state,
    )
    LOGGER.info(
        "Clustering config: umap_neighbors=%d, umap_components=%d, hdbscan_min_cluster_size=%d, hdbscan_min_samples=%s",
        umap_n_neighbors,
        umap_n_components,
        hdbscan_min_cluster_size,
        hdbscan_min_samples,
    )

    LOGGER.info("Building BERTopic model and embedding backend.")
    topic_model = build_model(
        language=language,
        embedding_model_name=embedding_model_name,
        top_n_words=top_n_words,
        ngram_range=ngram_range,
        min_topic_size=min_topic_size,
        nr_topics=nr_topics,
        calculate_probabilities=calculate_probabilities,
        low_memory=low_memory,
        random_state=random_state,
        umap_n_neighbors=umap_n_neighbors,
        umap_n_components=umap_n_components,
        umap_min_dist=umap_min_dist,
        umap_metric=umap_metric,
        hdbscan_min_cluster_size=hdbscan_min_cluster_size,
        hdbscan_min_samples=hdbscan_min_samples,
        hdbscan_metric=hdbscan_metric,
        cluster_selection_method=cluster_selection_method,
        min_df=min_df,
        max_df=max_df,
        stop_words=stop_words,
        representation_model_name=representation_model_name,
        seed_topic_file=seed_topic_file,
        zeroshot_topic_file=zeroshot_topic_file,
        zeroshot_min_similarity=zeroshot_min_similarity,
    )
    LOGGER.info("BERTopic model constructed successfully.")

    LOGGER.info("Starting fit_transform on %d tag documents.", len(docs))
    topics, probabilities = topic_model.fit_transform(docs)
    LOGGER.info("fit_transform completed.")

    LOGGER.info("Generating short topic labels with max %d words.", max_topic_label_words)
    topic_labels = build_short_topic_labels(
        topic_model,
        docs=docs,
        topics=topics,
        max_words=max_topic_label_words,
        preferred_topic_keywords=preferred_topic_keywords,
    )
    topic_model.set_topic_labels(topic_labels)
    LOGGER.info("Applied short topic labels to BERTopic model.")

    LOGGER.info("Collecting topic and document statistics.")
    topic_info = topic_model.get_topic_info()
    doc_info = topic_model.get_document_info(docs)
    topic_info["ShortLabel"] = topic_info["Topic"].map(topic_labels)
    doc_info["ShortLabel"] = doc_info["Topic"].map(topic_labels)
    outlier_count = int(sum(1 for topic in topics if topic == -1))
    topic_count = len(topic_info)
    LOGGER.info(
        "Derived %d topics (including outlier bucket). Outliers: %d of %d documents.",
        topic_count,
        outlier_count,
        len(docs),
    )

    topic_info_path = stats_dir / "topic_info.csv"
    doc_info_path = stats_dir / "document_info.csv"
    summary_path = stats_dir / "summary.json"
    config_path = stats_dir / "config.json"

    LOGGER.info("Writing CSV statistics.")
    topic_info.to_csv(topic_info_path, index=False)
    doc_info.to_csv(doc_info_path, index=False)

    topic_details: list[dict[str, Any]] = []
    for _, row in topic_info.iterrows():
        topic_id = int(row["Topic"])
        topic_details.append(
            {
                "topic_id": topic_id,
                "count": int(row["Count"]),
                "name": row.get("Name"),
                "short_label": topic_labels.get(topic_id),
                "representative_terms": topic_model.get_topic(topic_id),
            }
        )

    config = {
        "run_name": run_name,
        "language": language,
        "embedding_model_name": embedding_model_name,
        "top_n_words": top_n_words,
        "ngram_range": list(ngram_range),
        "min_topic_size": min_topic_size,
        "nr_topics": nr_topics,
        "calculate_probabilities": calculate_probabilities,
        "low_memory": low_memory,
        "random_state": random_state,
        "umap_n_neighbors": umap_n_neighbors,
        "umap_n_components": umap_n_components,
        "umap_min_dist": umap_min_dist,
        "umap_metric": umap_metric,
        "hdbscan_min_cluster_size": hdbscan_min_cluster_size,
        "hdbscan_min_samples": hdbscan_min_samples,
        "hdbscan_metric": hdbscan_metric,
        "cluster_selection_method": cluster_selection_method,
        "min_df": min_df,
        "max_df": max_df,
        "stop_words": stop_words,
        "representation_model_name": representation_model_name,
        "seed_topic_file": str(seed_topic_file.resolve()) if seed_topic_file else None,
        "zeroshot_topic_file": str(zeroshot_topic_file.resolve()) if zeroshot_topic_file else None,
        "zeroshot_min_similarity": zeroshot_min_similarity,
        "max_topic_label_words": max_topic_label_words,
        "preferred_topic_keywords": preferred_topic_keywords,
    }

    LOGGER.info("Writing config and summary JSON.")
    visualization_paths = save_visualizations(topic_model, run_dir)

    summary = {
        "input_file": str(input_file.resolve()),
        "run_dir": str(run_dir.resolve()),
        "document_count": len(docs),
        "topic_count_including_outliers": topic_count,
        "outlier_count": outlier_count,
        "config": config,
        "artifacts": {
            "config": str(config_path.resolve()),
            "topic_info_csv": str(topic_info_path.resolve()),
            "document_info_csv": str(doc_info_path.resolve()),
            "visualizations": visualization_paths,
            "log_file": str(log_path.resolve()),
            "model_dir": str(model_dir.resolve()) if save_model else None,
        },
        "topic_labels": topic_labels,
        "topics": topic_details,
    }
    write_json(config_path, config)
    write_json(summary_path, summary)

    if calculate_probabilities and probabilities is not None:
        LOGGER.info("Saving topic probabilities array.")
        try:
            import numpy as np
        except ImportError as exc:
            raise SystemExit(
                "NumPy is required to save topic probabilities when calculate_probabilities=True."
            ) from exc
        np.save(stats_dir / "topic_probabilities.npy", probabilities)

    if save_model:
        LOGGER.info("Saving BERTopic model to disk.")
        topic_model.save(model_dir)
        LOGGER.info("Saved model directory: %s", model_dir.resolve())

    LOGGER.info("Run complete.")
    print(f"Processed {len(docs)} tag documents.")
    print(f"Run directory: {run_dir.resolve()}")
    print(f"Topic info written to: {topic_info_path.resolve()}")
    print(f"Document assignments written to: {doc_info_path.resolve()}")
    print(f"Summary written to: {summary_path.resolve()}")


def main() -> None:
    input_file = Path("/Users/ratniel/JurisAI/unique_tags.json")
    output_root = Path("/Users/ratniel/JurisAI/bertopic_runs")
    run_name = "unique-tags-english-minilm-zeroshot-pass"
    save_model = True

    # First exploration pass:
    # - short tags only
    # - English model
    # - reproducible runs
    # - prefer broader topics with few outliers, not zero at all costs
    language = "english"
    embedding_model_name = "all-MiniLM-L6-v2"
    top_n_words = 10
    ngram_range = (1, 2)
    min_topic_size = 12
    nr_topics: int | str | None = 50
    calculate_probabilities = False
    low_memory = False
    random_state = 42

    umap_n_neighbors = 15
    umap_n_components = 5
    umap_min_dist = 0.0
    umap_metric = "cosine"

    hdbscan_min_cluster_size = 12
    hdbscan_min_samples: int | None = 2
    hdbscan_metric = "euclidean"
    cluster_selection_method = "eom"

    min_df = 1
    max_df = 1.0
    stop_words: str | None = "english"
    representation_model_name: str | None = "keybert"
    max_topic_label_words = 2
    preferred_topic_keywords = ["accident", "accommodation", "agriculture"]

    seed_topic_file: Path | None = None
    zeroshot_topic_file: Path | None = Path("/Users/ratniel/JurisAI/bertopic_zeroshot_topics.json")
    zeroshot_min_similarity = 0.7

    run(
        input_file=input_file,
        output_root=output_root,
        run_name=run_name,
        save_model=save_model,
        language=language,
        embedding_model_name=embedding_model_name,
        top_n_words=top_n_words,
        ngram_range=ngram_range,
        min_topic_size=min_topic_size,
        nr_topics=nr_topics,
        calculate_probabilities=calculate_probabilities,
        low_memory=low_memory,
        random_state=random_state,
        umap_n_neighbors=umap_n_neighbors,
        umap_n_components=umap_n_components,
        umap_min_dist=umap_min_dist,
        umap_metric=umap_metric,
        hdbscan_min_cluster_size=hdbscan_min_cluster_size,
        hdbscan_min_samples=hdbscan_min_samples,
        hdbscan_metric=hdbscan_metric,
        cluster_selection_method=cluster_selection_method,
        min_df=min_df,
        max_df=max_df,
        stop_words=stop_words,
        representation_model_name=representation_model_name,
        seed_topic_file=seed_topic_file,
        zeroshot_topic_file=zeroshot_topic_file,
        zeroshot_min_similarity=zeroshot_min_similarity,
        max_topic_label_words=max_topic_label_words,
        preferred_topic_keywords=preferred_topic_keywords,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
