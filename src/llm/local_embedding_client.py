from __future__ import annotations

from src.llm.embedding_text_formatter import (
    format_texts_for_embedding,
    sentence_transformer_load_kwargs,
)


class LocalSentenceTransformerEmbeddingClient:
    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer

        self.default_model = model_name
        self._model = SentenceTransformer(
            model_name,
            **sentence_transformer_load_kwargs(model_name),
        )

    def embed_text(
        self,
        text: str,
        *,
        model: str | None = None,
        task_type: str = "RETRIEVAL_DOCUMENT",
        output_dimensionality: int | None = None,
    ) -> list[float]:
        return self.embed_texts(
            [text],
            model=model,
            task_type=task_type,
            output_dimensionality=output_dimensionality,
        )[0]

    def embed_texts(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        task_type: str = "RETRIEVAL_DOCUMENT",
        output_dimensionality: int | None = None,
    ) -> list[list[float]]:
        if model and model != self.default_model:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                model,
                **sentence_transformer_load_kwargs(model),
            )
            self.default_model = model

        resolved_model = model or self.default_model
        formatted_texts = format_texts_for_embedding(
            texts,
            model_name=resolved_model,
            task_type=task_type,
        )
        vectors = self._model.encode(
            formatted_texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()
