# Retrieval strategy experiment

Dense retrieval remains the default. The default filter mode remains `state_only`.

Set `WORKFLOW_RETRIEVAL_STRATEGY` to `dense`, `sparse`, or `hybrid`.
Both eval CLIs also accept `--retrieval-strategy`.
The dashboard sends its strategy selection to the shared eval runner.

Sparse and hybrid search require the configured sparse vector slot.
Hybrid search combines dense and sparse results with Qdrant RRF.
The current keyword vector uses hashed term counts. It is not BM25.
If the lexical query is empty, the search uses dense retrieval.
The debug payload and eval summary record the strategy.

Use the same corpus, classifier, model, and filters for comparisons.
Keep run artifacts under the canonical `evals/` run directories.
These changes do not establish that hybrid retrieval improves quality.
