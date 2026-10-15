"""Local experiment: bound-normalized interpretation of the supplied teaching guidance.

All cutoffs were fixed before evaluation; no event IDs or phase keys are used.
"""

from math import sqrt

from api import Verdict


COMPOSITE_BOUND_UNITS = True
COMPOSITE_MAX = 1.30
FEATURE_SHIFT_MAX = 0.65
EMBEDDING_SHIFT_MAX = 0.040
CORPUS_AGE_MAX_DAYS = 44.5


def register(ctx):
    ctx.on("data_batch", check_data_batch)
    ctx.on("contract_checkpoint", check_contract_checkpoint)
    ctx.on("lineage_run", check_lineage_run)
    ctx.on("feature_materialization", check_feature_materialization)
    ctx.on("embedding_batch", check_embedding_batch)


def make_verdict(pillar, reasons):
    return Verdict(
        alert=bool(reasons),
        pillar=pillar,
        reason="; ".join(reasons) if reasons else "Checks passed",
    )


def tool_error(pillar, result):
    return Verdict(
        alert=False,
        pillar=pillar,
        reason=f"Tool error: {result['error']}",
    )


def check_data_batch(payload, ctx):
    profile = ctx.tools.batch_profile(payload["batch_id"])
    if "error" in profile:
        return tool_error("checks", profile)

    b = ctx.baseline
    reasons = []
    rows = profile["row_count"]
    amount = profile["mean_amount"]
    null_rate = profile["null_rate"]["customer_id"]
    stale = profile["staleness_min"]

    if not b["row_count_min"] <= rows <= b["row_count_max"]:
        reasons.append(f"row_count outside baseline: {rows}")
    if not b["mean_amount_min"] <= amount <= b["mean_amount_max"]:
        reasons.append(f"mean_amount outside baseline: {amount}")
    if null_rate > b["null_rate_max"]:
        reasons.append(f"null rate too high: {null_rate}")
    if stale > b["staleness_min_max"]:
        reasons.append(f"data too stale: {stale}")

    # Baseline arithmetic is cached in memory, with no additional tool call.
    if "batch_composite_scales" not in ctx.state:
        divisor = 2.0 if COMPOSITE_BOUND_UNITS else 6.0
        ctx.state["batch_composite_scales"] = (
            (b["row_count_min"] + b["row_count_max"]) / 2.0,
            (b["row_count_max"] - b["row_count_min"]) / divisor,
            (b["mean_amount_min"] + b["mean_amount_max"]) / 2.0,
            (b["mean_amount_max"] - b["mean_amount_min"]) / divisor,
        )

    row_center, row_scale, amount_center, amount_scale = ctx.state[
        "batch_composite_scales"
    ]
    distance = sqrt(
        ((rows - row_center) / row_scale) ** 2
        + ((amount - amount_center) / amount_scale) ** 2
        + (null_rate / b["null_rate_max"]) ** 2
        + (stale / b["staleness_min_max"]) ** 2
    )
    if distance > COMPOSITE_MAX:
        reasons.append(f"Composite distance too high: {distance:.4f}")

    return make_verdict("checks", reasons)


def check_contract_checkpoint(payload, ctx):
    result = ctx.tools.contract_diff(
        payload["contract_id"], payload["checkpoint_batch_id"]
    )
    if "error" in result:
        return tool_error("contracts", result)

    reasons = list(result["violations"])
    delay = result["freshness_delay_min"]
    if delay > ctx.baseline["freshness_delay_max_min"]:
        reasons.append(f"Freshness delay exceeds baseline: {delay}")

    sla = payload.get("declared_sla", {}).get("freshness_min")
    if isinstance(sla, (int, float)) and delay > sla:
        reasons.append(f"Declared freshness SLA exceeded: {delay} > {sla}")

    return make_verdict("contracts", reasons)


def check_lineage_run(payload, ctx):
    result = ctx.tools.lineage_graph_slice(payload["run_id"])
    if "error" in result:
        return tool_error("lineage", result)

    reasons = []
    required = {item["name"] for item in payload["inputs"]}
    # A domain invariant supplied explicitly by the course, not a run answer.
    if payload["job"] == "dbt:stg_orders":
        required.update(("raw.orders", "raw.customers"))

    missing = required - set(result["actual_upstream"])
    if missing:
        reasons.append("Missing upstream: " + ", ".join(sorted(missing)))

    downstream = result["actual_downstream_count"]
    if downstream == 0:
        reasons.append("Orphan output: no downstream consumers")
    elif downstream < len(payload["outputs"]):
        reasons.append("Fewer downstream consumers than declared outputs")

    if result["duration_ms"] > ctx.baseline["lineage_duration_ms_max"]:
        reasons.append(f"Runtime exceeds baseline: {result['duration_ms']}")

    return make_verdict("lineage", reasons)


def check_feature_materialization(payload, ctx):
    result = ctx.tools.feature_drift(payload["feature_view"], payload["batch_id"])
    if "error" in result:
        return tool_error("ai_infra", result)

    reasons = []
    if result["mean_shift_sigma"] > FEATURE_SHIFT_MAX:
        reasons.append(f"Feature skew: {result['mean_shift_sigma']}")
    return make_verdict("ai_infra", reasons)


def check_embedding_batch(payload, ctx):
    result = ctx.tools.embedding_drift(payload["corpus"], payload["chunk_batch_id"])
    if "error" in result:
        return tool_error("ai_infra", result)

    reasons = []
    if result["centroid_shift"] > EMBEDDING_SHIFT_MAX:
        reasons.append(f"Embedding drift: {result['centroid_shift']}")
    if result["avg_doc_age_days"] > CORPUS_AGE_MAX_DAYS:
        reasons.append(f"Corpus too old: {result['avg_doc_age_days']}")
    return make_verdict("ai_infra", reasons)
