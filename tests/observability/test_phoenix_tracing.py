"""Exercise real instrumentors with fake provider responses, without network calls."""
from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import Mock, patch
from typing import ClassVar, cast

import litellm
from google.genai import types
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from openinference.instrumentation import suppress_tracing, using_attributes

# Import clients before tracing starts: captured function aliases must not bypass it.
from src.agentic.workflow import BasicAgenticWorkflow
from src.llm.contracts import TextGenerationClient
from src.llm.gemini_client import GeminiClient
from src.llm.llamaindex_google_client import LlamaIndexGoogleGenAIClient
from src.llm.local_openai_client import LocalOpenAICompatibleClient
from src.llm.openrouter_client import OpenRouterClient
from src.observability import phoenix_tracing


class PhoenixTracingTests(unittest.TestCase):
    discovery: ClassVar[bool] = False

    @classmethod
    def setUpClass(cls):
        from google.genai.models import AsyncModels, Models
        cls.google_originals = {
            (owner, method): getattr(owner, method)
            for owner in (Models, AsyncModels)
            for method in ('generate_content', 'generate_content_stream')
        }
        cls.exporter = InMemorySpanExporter()
        cls.provider = TracerProvider()
        cls.provider.add_span_processor(SimpleSpanProcessor(cls.exporter))
        trace.set_tracer_provider(cls.provider)
        # Patch the transport before instrumentation; the real instrumentor wraps it.
        def fake_completion(**kwargs):
            if kwargs['messages'][-1]['content'] == 'fail':
                raise PermissionError('provider rejected request')
            content = 'Answer'
            if kwargs.get('response_format'):
                if cls.discovery and '"tool_calls":' in kwargs['messages'][-1]['content']:
                    content = json.dumps({'tool_calls': [{'tool_name':'semantic_search','query':'farmer support'}]})
                else:
                    content = json.dumps({'primary_intent': 'scheme_discovery' if cls.discovery else 'out_of_scope', 'reasoning':'test', 'confidence':1, 'user_goal':'farmer support'})
            return litellm.ModelResponse(
                model='resolved-model',
                choices=[{'message': {'role': 'assistant', 'content': content}, 'finish_reason': 'stop'}],
                usage={'prompt_tokens': 2, 'completion_tokens': 1, 'total_tokens': 3},
            )
        cls.transport_patch = patch('litellm.completion', fake_completion)
        cls.transport_patch.start()
        with patch.object(phoenix_tracing, 'register', return_value=cls.provider):
            status = phoenix_tracing.configure_phoenix_tracing(endpoint='http://127.0.0.1:6006/v1/traces')
        assert status.enabled

    @classmethod
    def tearDownClass(cls):
        # Restore SDK hooks so other tests do not inherit instrumentation.
        from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor
        from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
        from openinference.instrumentation.litellm import LiteLLMInstrumentor
        GoogleGenAIInstrumentor().uninstrument()
        LlamaIndexInstrumentor().uninstrument()
        LiteLLMInstrumentor().uninstrument()
        cls.transport_patch.stop()
        for (owner, method), original in cls.google_originals.items():
            setattr(owner, method, original)
        phoenix_tracing._TRACING_CONFIGURED = False
        cls.provider.shutdown()

    def setUp(self):
        self.exporter.clear()
        type(self).discovery = False

    def llm_spans(self):
        return [s for s in self.exporter.get_finished_spans() if (s.attributes or {}).get('openinference.span.kind') == 'LLM']

    @staticmethod
    def google_response(text='Answer', model='resolved-gemini'):
        return types.GenerateContentResponse(
            model_version=model,
            candidates=[types.Candidate(content=types.Content(role='model', parts=[types.Part(text=text)]), finish_reason=types.FinishReason.STOP)],
            usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=2, candidates_token_count=1, total_token_count=3),
        )

    def test_local_and_openrouter_identity_usage_parent_and_errors(self):
        for client in (LocalOpenAICompatibleClient(model='requested-model'), OpenRouterClient(api_key='test', model='requested-model')):
            self.exporter.clear()
            with using_attributes(session_id='chat-test'):
                with trace.get_tracer(__name__).start_as_current_span('turn') as parent:
                    self.assertEqual(client.generate_text('hello'), 'Answer')
            spans = self.llm_spans()
            self.assertEqual(len(spans), 1)
            span = spans[0]
            assert span.parent is not None
            self.assertEqual(span.parent.span_id, parent.get_span_context().span_id)
            self.assertEqual((span.attributes or {})['session.id'], 'chat-test')
            self.assertEqual((span.attributes or {})['llm.provider'], client.provider_name)
            self.assertEqual((span.attributes or {})['llm.model_name'], 'resolved-model')
            self.assertEqual((span.attributes or {})['llm.request.model_name'], 'requested-model')
            self.assertEqual((span.attributes or {})['llm.token_count.total'], 3)
            self.assertEqual(span.status.status_code.name, 'OK')
            self.exporter.clear()
            with self.assertRaises(PermissionError):
                client.generate_text('fail')
            span = self.llm_spans()[0]
            self.assertEqual(span.status.status_code.name, 'ERROR')
            self.assertEqual((span.attributes or {})['llm.provider'], client.provider_name)
            self.assertEqual((span.attributes or {})['llm.model_name'], 'requested-model')

    def test_gemini_sync_and_async_model_fallback(self):
        client = GeminiClient(api_key='test', model='requested-gemini')
        with patch('google.genai.models.Models._generate_content', return_value=self.google_response()):
            self.assertEqual(client.generate_text('hello'), 'Answer')
        span = self.llm_spans()[0]
        self.assertEqual((span.attributes or {})['llm.model_name'], 'resolved-gemini')
        self.assertEqual((span.attributes or {})['llm.provider'], 'google')
        self.assertEqual((span.attributes or {})['llm.request.model_name'], 'requested-gemini')
        self.assertEqual((span.attributes or {})['llm.token_count.total'], 3)
        assert client.last_invocation_metadata is not None
        self.assertEqual(client.last_invocation_metadata.model, 'resolved-gemini')
        self.exporter.clear()
        async def run():
            with patch('google.genai.models.AsyncModels._generate_content', return_value=self.google_response(model=None)):
                self.assertEqual(await client.agenerate_text('hello'), 'Answer')
        asyncio.run(run())
        span = self.llm_spans()[0]
        self.assertEqual((span.attributes or {})['llm.model_name'], 'requested-gemini')
        self.assertEqual((span.attributes or {})['llm.provider'], 'google')

    def test_gemini_streams_finish_after_consumption(self):
        client = GeminiClient(api_key='test', model='requested-gemini')
        with using_attributes(session_id='stream-chat'):
            with patch('google.genai.models.Models._generate_content_stream', return_value=iter([self.google_response()])):
                stream = client.stream_text('hello')
                self.assertEqual(list(stream), ['Answer'])
        self.assertEqual(len(self.llm_spans()), 1)
        self.assertEqual((self.llm_spans()[0].attributes or {})['session.id'], 'stream-chat')
        self.exporter.clear()
        async def chunks():
            yield self.google_response('First')
            self.assertEqual(len(self.llm_spans()), 0)
            yield self.google_response('Second')
        async def run():
            with patch('google.genai.models.AsyncModels._generate_content_stream', return_value=chunks()):
                return [chunk async for chunk in client.astream_text('hello')]
        self.assertEqual(asyncio.run(run()), ['First', 'Second'])
        self.assertEqual(len(self.llm_spans()), 1)
        span = self.llm_spans()[0]
        self.assertEqual((span.attributes or {})['llm.provider'], 'google')
        self.assertEqual((span.attributes or {})['llm.model_name'], 'resolved-gemini')
        self.assertEqual((span.attributes or {})['llm.token_count.total'], 3)

    def test_workflow_keeps_llm_children_and_session_in_one_trace(self):
        async def run():
            workflow = BasicAgenticWorkflow(
                llm=cast(TextGenerationClient, LocalOpenAICompatibleClient(model='requested-model')),
                retriever=Mock(), mongo_client=Mock(),
            )
            return await workflow.run(user_message='hello', session_snapshot={'chat_session_id':'workflow-chat'})
        result = asyncio.run(run())
        spans = self.exporter.get_finished_spans()
        self.assertEqual(len({s.context.trace_id for s in spans}), 1)
        llms = self.llm_spans()
        self.assertEqual(len(llms), 2)
        parents = {s.context.span_id: s.name for s in spans}
        self.assertEqual({parents[s.parent.span_id] for s in llms}, {'BasicAgenticWorkflow.classify_intent', 'BasicAgenticWorkflow.generate_reply'})
        self.assertTrue(all((s.attributes or {})['session.id'] == 'workflow-chat' for s in spans))
        self.assertEqual(result['session_snapshot']['chat_session_id'], 'workflow-chat')

    def test_retrieval_planner_and_manual_retrieval_share_the_workflow_trace(self):
        type(self).discovery = True
        def search(**kwargs):
            with trace.get_tracer(__name__).start_as_current_span('synthetic.retrieval'):
                return {'results':[], 'raw_hit_count':0, 'retrieval_filters_enabled':True, 'retrieval_filter_mode':'state_only', 'candidate_filters':{}, 'applied_filters':{}, 'ignored_filters':{}}
        async def run():
            workflow = BasicAgenticWorkflow(
                llm=cast(TextGenerationClient, LocalOpenAICompatibleClient(model='requested-model')),
                retriever=Mock(search=search), mongo_client=Mock(),
            )
            return await workflow.run(user_message='farmer support', session_snapshot={'chat_session_id':'discovery-chat'})
        asyncio.run(run())
        spans = self.exporter.get_finished_spans()
        self.assertEqual(len({s.context.trace_id for s in spans}), 1)
        parents = {s.context.span_id:s.name for s in spans}
        self.assertEqual(len(self.llm_spans()), 3)
        self.assertEqual({parents[s.parent.span_id] for s in self.llm_spans()}, {'BasicAgenticWorkflow.classify_intent','BasicAgenticWorkflow.plan_retrieval_tools','BasicAgenticWorkflow.generate_reply'})
        retrieval = next(s for s in spans if s.name == 'synthetic.retrieval')
        self.assertEqual(parents[retrieval.parent.span_id], 'BasicAgenticWorkflow.retrieve_schemes')

    def test_concurrent_sessions_do_not_share_trace_context(self):
        async def turn(session_id):
            workflow = BasicAgenticWorkflow(
                llm=cast(TextGenerationClient, LocalOpenAICompatibleClient(model='requested-model')),
                retriever=Mock(), mongo_client=Mock(),
            )
            return await workflow.run(user_message='hello', session_snapshot={'chat_session_id': session_id})
        async def run():
            return await asyncio.gather(turn('chat-a'), turn('chat-b'))
        asyncio.run(run())
        traces = {}
        for span in self.exporter.get_finished_spans():
            traces.setdefault(span.context.trace_id, set()).add((span.attributes or {}).get('session.id'))
        self.assertEqual(len(traces), 2)
        self.assertEqual({frozenset(ids) for ids in traces.values()}, {frozenset({'chat-a'}), frozenset({'chat-b'})})

    def test_suppressed_calls_do_not_relabel_the_parent(self):
        client = LocalOpenAICompatibleClient(model='requested-model')
        with trace.get_tracer(__name__).start_as_current_span('caller'):
            with suppress_tracing():
                client.generate_text('hello')
        self.assertEqual(len(self.llm_spans()), 0)
        self.assertNotIn('llm.model_name', self.exporter.get_finished_spans()[0].attributes or {})

    def test_stream_error_keeps_identity_and_error_status(self):
        client = GeminiClient(api_key='test', model='requested-gemini')
        async def chunks():
            yield self.google_response('First')
            raise RuntimeError('stream interrupted')
        async def run():
            with patch('google.genai.models.AsyncModels._generate_content_stream', return_value=chunks()):
                return [chunk async for chunk in client.astream_text('hello')]
        with self.assertRaises(RuntimeError):
            asyncio.run(run())
        spans = self.llm_spans()
        self.assertEqual(len(spans), 1)
        self.assertEqual(spans[0].status.status_code.name, 'ERROR')
        self.assertEqual((spans[0].attributes or {})['llm.provider'], 'google')
        self.assertEqual((spans[0].attributes or {})['llm.request.model_name'], 'requested-gemini')

    def test_llamaindex_google_provider_path(self):
        with patch('google.genai.models.Models.get', return_value=types.Model(name='gemini-test', input_token_limit=1000, output_token_limit=100)):
            client = LlamaIndexGoogleGenAIClient(api_key='test', model='gemini-test')
        with patch('google.genai.models.Models.get', return_value=types.Model(name='gemini-test', input_token_limit=1000, output_token_limit=100)), patch('google.genai.models.Models._generate_content', return_value=self.google_response()):
            self.assertEqual(client.generate_text('hello'), 'Answer')
        spans = self.llm_spans()
        self.assertEqual(len(spans), 1)
        self.assertEqual((spans[0].attributes or {})['llm.provider'], 'google')
        self.assertEqual((spans[0].attributes or {})['llm.model_name'], 'resolved-gemini')
        self.assertEqual((spans[0].attributes or {})['llm.token_count.total'], 3)
        self.exporter.clear()
        with suppress_tracing(), patch('google.genai.models.Models.get', return_value=types.Model(name='gemini-test', input_token_limit=1000, output_token_limit=100)), patch('google.genai.models.Models._generate_content', return_value=self.google_response()):
            client.generate_text('hello')
        self.assertEqual(len(self.llm_spans()), 0)


if __name__ == '__main__':
    unittest.main()
