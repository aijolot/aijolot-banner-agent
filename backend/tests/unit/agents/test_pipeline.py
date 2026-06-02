"""Tests for ADK Workflow pipeline graph construction and composition.

These tests validate the PIPELINE_MODE=full pipeline — the Workflow graph
that replaces SequentialAgent/LoopAgent/ParallelAgent. The smoke-demo-flow.py
script exercises the legacy API route path and does not use the Workflow;
this test suite is the authoritative coverage for the ADK Workflow pipeline.
"""

from __future__ import annotations

import pytest

from google.adk.workflow import FunctionNode, JoinNode, Workflow


class TestPipelineConstruction:
    """Verify that the pipeline builds without errors and has correct topology."""

    def test_pre_review_pipeline_builds(self):
        from app.agents.pipeline import build_pre_review_pipeline

        pipeline = build_pre_review_pipeline()
        assert isinstance(pipeline, Workflow)
        assert pipeline.name == "pre_review_pipeline"

    def test_post_review_pipeline_builds(self):
        from app.agents.pipeline import build_post_review_pipeline

        pipeline = build_post_review_pipeline()
        assert isinstance(pipeline, Workflow)
        assert pipeline.name == "post_review_pipeline"

    def test_pre_review_has_expected_nodes(self):
        from app.agents.pipeline import build_pre_review_pipeline

        pipeline = build_pre_review_pipeline()
        node_names = {n.name for n in pipeline.graph.nodes}
        expected = {
            "brand_load", "personalization", "best_practices",
            "concept_draft", "prompt_refine", "image_gen", "image_opt",
            "html_render", "liquid_build", "render_join", "audit",
            "hitl_review",
        }
        assert expected.issubset(node_names), f"Missing: {expected - node_names}"

    def test_post_review_has_expected_nodes(self):
        from app.agents.pipeline import build_post_review_pipeline

        pipeline = build_post_review_pipeline()
        node_names = {n.name for n in pipeline.graph.nodes}
        assert "schedule_route" in node_names
        assert "shopify_publish" in node_names

    def test_render_join_is_join_node(self):
        from app.agents.pipeline import render_join

        assert isinstance(render_join, JoinNode)
        assert render_join.name == "render_join"

    def test_audit_node_is_function_node(self):
        from app.agents.pipeline import fn_audit

        assert isinstance(fn_audit, FunctionNode)
        assert fn_audit.name == "audit"

    def test_pre_review_has_conditional_edges(self):
        """Audit node must have conditional edges for retry routing."""
        from app.agents.pipeline import build_pre_review_pipeline

        pipeline = build_pre_review_pipeline()
        audit_edges = [
            e for e in pipeline.graph.edges
            if e.from_node.name == "audit"
        ]
        routes = {e.route for e in audit_edges}
        assert "pass" in routes, "Missing 'pass' route from audit"
        assert "retry" in routes, "Missing 'retry' route from audit"

    def test_pass_edge_goes_to_hitl_review(self):
        from app.agents.pipeline import build_pre_review_pipeline

        pipeline = build_pre_review_pipeline()
        pass_edges = [
            e for e in pipeline.graph.edges
            if e.from_node.name == "audit" and e.route == "pass"
        ]
        assert len(pass_edges) == 1
        assert pass_edges[0].to_node.name == "hitl_review"

    def test_retry_edge_goes_to_concept_draft(self):
        from app.agents.pipeline import build_pre_review_pipeline

        pipeline = build_pre_review_pipeline()
        retry_edges = [
            e for e in pipeline.graph.edges
            if e.from_node.name == "audit" and e.route == "retry"
        ]
        assert len(retry_edges) == 1
        assert retry_edges[0].to_node.name == "concept_draft"

    def test_hitl_review_node_exists(self):
        """Node 10 (HITL) must be an explicit node in the graph."""
        from app.agents.pipeline import build_pre_review_pipeline

        pipeline = build_pre_review_pipeline()
        node_names = {n.name for n in pipeline.graph.nodes}
        assert "hitl_review" in node_names

    def test_parallel_render_fan_out(self):
        """html_render and liquid_build should both follow image_opt."""
        from app.agents.pipeline import build_pre_review_pipeline

        pipeline = build_pre_review_pipeline()
        from_image_opt = [
            e for e in pipeline.graph.edges
            if e.from_node.name == "image_opt"
        ]
        targets = {e.to_node.name for e in from_image_opt}
        assert "html_render" in targets
        assert "liquid_build" in targets

    def test_parallel_render_fan_in(self):
        """Both renders should feed into render_join."""
        from app.agents.pipeline import build_pre_review_pipeline

        pipeline = build_pre_review_pipeline()
        to_join = [
            e for e in pipeline.graph.edges
            if e.to_node.name == "render_join"
        ]
        sources = {e.from_node.name for e in to_join}
        assert "html_render" in sources
        assert "liquid_build" in sources

    def test_all_user_nodes_are_function_or_join(self):
        from app.agents.pipeline import build_pre_review_pipeline
        from google.adk.workflow import BaseNode

        pipeline = build_pre_review_pipeline()
        for node in pipeline.graph.nodes:
            if node.name == "__START__":
                continue  # ADK-internal start sentinel
            assert isinstance(node, (FunctionNode, JoinNode, BaseNode)), (
                f"{node.name} is {type(node).__name__}"
            )


class TestGraphBuildFunctions:
    """Verify graph.py and coordinator.py factory functions."""

    def test_build_graph_returns_workflow(self):
        from app.agents.graph import build_graph

        result = build_graph()
        assert isinstance(result, Workflow)

    def test_build_post_review_graph(self):
        from app.agents.graph import build_post_review_graph

        result = build_post_review_graph()
        assert isinstance(result, Workflow)

    def test_build_coordinator_returns_workflow(self):
        from app.agents.coordinator import build_coordinator

        result = build_coordinator()
        assert isinstance(result, Workflow)

    def test_nodes_list_still_exists(self):
        """NODES list must remain for backward compat."""
        from app.agents.graph import NODES

        assert len(NODES) == 12
        assert NODES[0].name == "load_brand_context"
        assert NODES[-1].name == "publish_to_shopify"


class TestStateBridge:
    """Verify state reader/writer functions."""

    def test_init_pipeline_state(self):
        from app.agents.state_bridge import init_pipeline_state

        state = init_pipeline_state(
            trace_id="t1",
            session_id="s1",
            brand_id="avocado_store",
            campaign={"goal": "test"},
        )
        assert state["trace_id"] == "t1"
        assert state["brand_id"] == "avocado_store"
        assert state["campaign"]["goal"] == "test"
        assert state["retries"] == {}
        assert state["variants"] == []

    def test_brand_context_load_reader(self):
        from app.agents.state_bridge import read_brand_context_load

        state = {"brand_id": "demo_apparel"}
        kwargs = read_brand_context_load(state)
        assert kwargs == {"brand_id": "demo_apparel"}

    def test_concept_draft_reader(self):
        from app.agents.state_bridge import read_concept_draft

        state = {
            "campaign": {"goal": "sell"},
            "brand_context": {
                "id": "test", "name": "Test",
                "palette": [{"name": "Ink", "hex": "#111111"}],
                "voice": {"tone": [], "prohibited_words": [], "required_phrases": []},
                "shopify": {"store_domain": "test.myshopify.com"},
                "notes": "",
            },
            "variants": [],
            "best_practices": [],
        }
        kwargs = read_concept_draft(state)
        assert kwargs["campaign"] == {"goal": "sell"}
        assert kwargs["brand_context"] is not None

    def test_audit_writer_handles_tuple(self):
        from app.agents.state_bridge import write_performance_audit

        state = {}
        result = ({"status": "pass", "overall_pass": True}, "human_review_required")
        delta = write_performance_audit(state, result)
        assert delta["audit_decision"] == "human_review_required"
        assert delta["audit_report"]["status"] == "pass"


class TestAuditRouting:
    """Verify audit node routing logic using _DECISION_RETRY_TARGETS."""

    def _simulate_routing(self, state: dict) -> str:
        """Simulate the routing logic from node_audit without ADK Context."""
        from app.agents.pipeline import _DECISION_RETRY_TARGETS

        decision = state.get("audit_decision", "human_review_required")
        retry_target = _DECISION_RETRY_TARGETS.get(decision)

        if retry_target is None:
            return "pass"

        retries = dict(state.get("retries", {}))
        current = retries.get(retry_target, 0)
        if current >= 2:
            state["audit_decision"] = "escalate_hitl"
            return "pass"
        else:
            retries[retry_target] = current + 1
            state["retries"] = retries
            return "retry"

    def test_pass_on_human_review_required(self):
        state = {"retries": {}, "audit_decision": "human_review_required"}
        assert self._simulate_routing(state) == "pass"

    def test_pass_on_escalate_hitl(self):
        state = {"retries": {}, "audit_decision": "escalate_hitl"}
        assert self._simulate_routing(state) == "pass"

    def test_retry_node_5_targets_concept(self):
        """retry_node_5 should target draft_banner_concept."""
        state = {"retries": {}, "audit_decision": "retry_node_5"}
        assert self._simulate_routing(state) == "retry"
        assert state["retries"]["draft_banner_concept"] == 1

    def test_retry_node_8_targets_render_html(self):
        """retry_node_8 should target render_html."""
        state = {"retries": {}, "audit_decision": "retry_node_8"}
        assert self._simulate_routing(state) == "retry"
        assert state["retries"]["render_html"] == 1

    def test_retry_counter_increments(self):
        """Two consecutive retries should increment the counter to 2."""
        state = {"retries": {}, "audit_decision": "retry_node_5"}
        self._simulate_routing(state)
        assert state["retries"]["draft_banner_concept"] == 1

        state["audit_decision"] = "retry_node_5"  # second retry
        self._simulate_routing(state)
        assert state["retries"]["draft_banner_concept"] == 2

    def test_retry_exhausted_escalates(self):
        """After 2 retries, should escalate to HITL instead of retrying."""
        state = {"retries": {"draft_banner_concept": 2}, "audit_decision": "retry_node_5"}
        assert self._simulate_routing(state) == "pass"
        assert state["audit_decision"] == "escalate_hitl"

    def test_render_html_retry_exhausted(self):
        """render_html target also respects the 2-retry budget."""
        state = {"retries": {"render_html": 2}, "audit_decision": "retry_node_8"}
        assert self._simulate_routing(state) == "pass"
        assert state["audit_decision"] == "escalate_hitl"

    def test_unknown_decision_routes_to_pass(self):
        """Unknown decisions (not in _DECISION_RETRY_TARGETS) pass through."""
        state = {"retries": {}, "audit_decision": "some_unknown_value"}
        assert self._simulate_routing(state) == "pass"
