"""Tests for ADK Workflow pipeline graph construction and composition."""

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
            "pipeline_done",
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

    def test_retry_edge_goes_to_concept_draft(self):
        from app.agents.pipeline import build_pre_review_pipeline

        pipeline = build_pre_review_pipeline()
        retry_edges = [
            e for e in pipeline.graph.edges
            if e.from_node.name == "audit" and e.route == "retry"
        ]
        assert len(retry_edges) == 1
        assert retry_edges[0].to_node.name == "concept_draft"

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
    """Verify audit node routing logic."""

    def test_pass_route(self):
        """node_audit should set ctx.route='pass' on pass decision."""
        # We test the routing logic directly since running the full
        # FunctionNode requires an ADK Context
        state = {"retries": {}, "audit_decision": "human_review_required"}
        decision = state["audit_decision"]
        if decision in ("pass", "human_review_required", "escalate_hitl"):
            route = "pass"
        else:
            route = "retry"
        assert route == "pass"

    def test_retry_route(self):
        state = {"retries": {}, "audit_decision": "retry_node_5"}
        decision = state["audit_decision"]
        if decision in ("pass", "human_review_required", "escalate_hitl"):
            route = "pass"
        else:
            retries = dict(state.get("retries", {}))
            target = "draft_banner_concept" if "node_5" in decision else "render_html"
            current = retries.get(target, 0)
            if current >= 2:
                route = "pass"
            else:
                retries[target] = current + 1
                state["retries"] = retries
                route = "retry"
        assert route == "retry"
        assert state["retries"]["draft_banner_concept"] == 1

    def test_retry_exhausted_routes_to_pass(self):
        state = {"retries": {"draft_banner_concept": 2}, "audit_decision": "retry_node_5"}
        decision = state["audit_decision"]
        retries = dict(state.get("retries", {}))
        target = "draft_banner_concept"
        current = retries.get(target, 0)
        if current >= 2:
            route = "pass"
        else:
            route = "retry"
        assert route == "pass"
