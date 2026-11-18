from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from src.config.settings import OpenRouterSettings, Settings, WorkflowSettings


class SettingsEnvOverrideTests(unittest.TestCase):
    def test_nomic_defaults_and_embedding_overrides(self) -> None:
        with patch.dict(Settings.model_config, {"env_file": None}), patch.dict(os.environ, {}, clear=True):
            settings = Settings()
            self.assertEqual(settings.embedding_model(), "nomic-ai/nomic-embed-text-v1.5")
            self.assertEqual(settings.qdrant.default_collection, "schemes_vectors_v3_nomic_embed_text_v1_5")
            self.assertEqual(settings.qdrant.production_collection, settings.qdrant.default_collection)
        with patch.dict(Settings.model_config, {"env_file": None}), patch.dict(os.environ, {"EMBEDDING_MODEL": "all-MiniLM-L6-v2", "QDRANT_COLLECTION": "custom_vectors"}, clear=True):
            settings = Settings()
            self.assertEqual(settings.embedding_model(), "all-MiniLM-L6-v2")
            self.assertEqual(settings.qdrant.default_collection, "custom_vectors")

    def test_agentic_workflow_defaults_to_openrouter_free_router(self) -> None:
        workflow = WorkflowSettings()
        openrouter = OpenRouterSettings()

        self.assertEqual(workflow.generation_provider, "openrouter")
        self.assertEqual(workflow.generation_model, "openrouter/free")
        self.assertEqual(workflow.intent_provider, "openrouter")
        self.assertEqual(workflow.intent_model, "openrouter/free")
        self.assertEqual(openrouter.model, "openrouter/free")

    def test_workflow_provider_legacy_env_overrides_apply(self) -> None:
        original_generation = os.environ.get("WORKFLOW_GENERATION_PROVIDER")
        original_intent = os.environ.get("WORKFLOW_INTENT_PROVIDER")
        try:
            os.environ["WORKFLOW_GENERATION_PROVIDER"] = "local_openai"
            os.environ["WORKFLOW_INTENT_PROVIDER"] = "local_openai"
            settings = Settings()
        finally:
            if original_generation is None:
                os.environ.pop("WORKFLOW_GENERATION_PROVIDER", None)
            else:
                os.environ["WORKFLOW_GENERATION_PROVIDER"] = original_generation
            if original_intent is None:
                os.environ.pop("WORKFLOW_INTENT_PROVIDER", None)
            else:
                os.environ["WORKFLOW_INTENT_PROVIDER"] = original_intent

        self.assertEqual(settings.workflow.generation_provider, "local_openai")
        self.assertEqual(settings.workflow.intent_provider, "local_openai")

    def test_openrouter_api_key_env_is_loaded(self) -> None:
        original_api_key = os.environ.get("OPENROUTER_API_KEY")
        try:
            os.environ["OPENROUTER_API_KEY"] = "test-openrouter-key"
            settings = Settings()
        finally:
            if original_api_key is None:
                os.environ.pop("OPENROUTER_API_KEY", None)
            else:
                os.environ["OPENROUTER_API_KEY"] = original_api_key

        self.assertEqual(settings.openrouter.api_key, "test-openrouter-key")


if __name__ == "__main__":
    unittest.main()
