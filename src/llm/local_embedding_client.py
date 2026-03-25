from __future__ import annotations

from sentence_transformers import SentenceTransformer


class LocalSentenceTransformerEmbeddingClient:
    def __init__(self, model_name: str) -> None:
        self.default_model = model_name
        self._model = SentenceTransformer(model_name)

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
            self._model = SentenceTransformer(model)
            self.default_model = model

        vectors = self._model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vectors.tolist()
