"""
Data Siege defense.

DEBUG_LINEAGE = True:
    Dừng tại sự kiện lineage đầu tiên để xem payload và kết quả công cụ.

DEBUG_LINEAGE = False:
    Chạy đầy đủ các kiểm tra cơ bản.
"""

from api import Verdict


DEBUG_LINEAGE = False


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


def check_data_batch(payload, ctx):
    # Chi phí: 1 credit.
    profile = ctx.tools.batch_profile(payload["batch_id"])

    if "error" in profile:
        return Verdict(
            alert=False,
            pillar="checks",
            reason=f"batch_profile error: {profile['error']}",
        )

    baseline = ctx.baseline
    reasons = []

    # Kiểm tra số dòng.
    row_count = profile["row_count"]
    if not (
        baseline["row_count_min"]
        <= row_count
        <= baseline["row_count_max"]
    ):
        reasons.append(
            f"row_count outside baseline: {row_count}"
        )

    # Kiểm tra tỷ lệ thiếu customer_id.
    null_rate = profile["null_rate"]["customer_id"]
    if null_rate > baseline["null_rate_max"]:
        reasons.append(
            f"customer_id null rate too high: {null_rate}"
        )

    # Kiểm tra số tiền trung bình.
    mean_amount = profile["mean_amount"]
    if not (
        baseline["mean_amount_min"]
        <= mean_amount
        <= baseline["mean_amount_max"]
    ):
        reasons.append(
            f"mean_amount outside baseline: {mean_amount}"
        )

    # Kiểm tra độ cũ của dữ liệu.
    staleness = profile["staleness_min"]
    if staleness > baseline["staleness_min_max"]:
        reasons.append(
            f"data too stale: {staleness} minutes"
        )

    return make_verdict("checks", reasons)


def check_contract_checkpoint(payload, ctx):
    # Chi phí: 1.5 credits.
    result = ctx.tools.contract_diff(
        payload["contract_id"],
        payload["checkpoint_batch_id"],
    )

    if "error" in result:
        return Verdict(
            alert=False,
            pillar="contracts",
            reason=f"contract_diff error: {result['error']}",
        )

    reasons = []

    # Kiểm tra schema và kiểu dữ liệu.
    violations = result["violations"]
    if violations:
        reasons.append(
            "Contract violations: " + ", ".join(violations)
        )

    # Kiểm tra độ trễ cập nhật.
    delay = result["freshness_delay_min"]
    max_delay = ctx.baseline["freshness_delay_max_min"]

    if delay > max_delay:
        reasons.append(
            f"Freshness delay exceeds baseline: "
            f"{delay} > {max_delay} minutes"
        )

    return make_verdict("contracts", reasons)


def check_lineage_run(payload, ctx):
    # Một lần gọi, chi phí 1 credit.
    result = ctx.tools.lineage_graph_slice(payload["run_id"])

    if "error" in result:
        return Verdict(
            alert=False,
            pillar="lineage",
            reason=f"lineage_graph_slice error: {result['error']}",
        )

    reasons = []

    # 1. Kiểm tra thời gian chạy.
    duration = result["duration_ms"]
    max_duration = ctx.baseline["lineage_duration_ms_max"]

    if duration > max_duration:
        reasons.append(
            f"Run duration exceeds baseline: "
            f"{duration} > {max_duration} ms"
        )

    # 2. Lấy nguồn và đầu ra được khai báo trong sự kiện.
    declared_inputs = {
        item["name"]
        for item in payload["inputs"]
    }

    declared_outputs = {
        (item["namespace"], item["name"])
        for item in payload["outputs"]
    }

    actual_upstream = set(result["actual_upstream"])

    # Tách lịch sử theo job và cấu trúc khai báo.
    # Không dùng run_id vì mỗi lần chạy có ID khác nhau.
    history_key = (
        payload["job"],
        tuple(sorted(
            (item["namespace"], item["name"])
            for item in payload["inputs"]
        )),
        tuple(sorted(declared_outputs)),
    )

    histories = ctx.state.setdefault("lineage_history", {})

    history = histories.setdefault(
        history_key,
        {
            "samples": 0,
            "edge_counts": {},
        },
    )

    # 3. Học nguồn xuất hiện ổn định từ các lần chạy trước.
    learned_inputs = set()

    if history["samples"] >= 3:
        for edge, count in history["edge_counts"].items():
            frequency = count / history["samples"]

            if count >= 3 and frequency >= 0.8:
                learned_inputs.add(edge)

    required_inputs = declared_inputs | learned_inputs
    missing_inputs = required_inputs - actual_upstream

    if missing_inputs:
        reasons.append(
            "Missing upstream: "
            + ", ".join(sorted(missing_inputs))
        )

    # 4. Kiểm tra đầu ra thiếu liên kết downstream.
    expected_count = len(declared_outputs)
    actual_count = result["actual_downstream_count"]

    if actual_count < expected_count:
        reasons.append(
            f"Missing downstream links: "
            f"actual={actual_count}, expected_at_least={expected_count}"
        )

    # 5. Chỉ cập nhật lịch sử từ lần chạy không bị cảnh báo.
    # Không có thêm RPC; dữ liệu được giữ trong ctx.state.
    if not reasons:
        history["samples"] += 1

        for edge in actual_upstream:
            previous_count = history["edge_counts"].get(edge, 0)
            history["edge_counts"][edge] = previous_count + 1

    return make_verdict("lineage", reasons)


def check_feature_materialization(payload, ctx):
    # Chi phí: 2 credits.
    result = ctx.tools.feature_drift(
        payload["feature_view"],
        payload["batch_id"],
    )

    if "error" in result:
        return Verdict(
            alert=False,
            pillar="ai_infra",
            reason=f"feature_drift error: {result['error']}",
        )

    reasons = []

    # Độ lệch trung bình được chuẩn hóa theo train_std.
    shift = result["mean_shift_sigma"]
    max_shift = ctx.baseline["feature_mean_shift_sigma_max"]

    if shift > max_shift:
        reasons.append(
            f"Feature mean shift exceeds baseline: "
            f"{shift} > {max_shift} sigma"
        )

    return make_verdict("ai_infra", reasons)


def check_embedding_batch(payload, ctx):
    # Chi phí: 2 credits.
    result = ctx.tools.embedding_drift(
        payload["corpus"],
        payload["chunk_batch_id"],
    )

    if "error" in result:
        return Verdict(
            alert=False,
            pillar="ai_infra",
            reason=f"embedding_drift error: {result['error']}",
        )

    baseline = ctx.baseline
    reasons = []

    # Kiểm tra mức dịch chuyển tâm embedding.
    shift = result["centroid_shift"]
    max_shift = baseline["embedding_centroid_shift_max"]

    if shift > max_shift:
        reasons.append(
            f"Embedding centroid shift too high: "
            f"{shift} > {max_shift}"
        )

    # Kiểm tra tuổi trung bình của tài liệu.
    avg_age = result["avg_doc_age_days"]
    max_age = baseline["corpus_avg_doc_age_days_max"]

    if avg_age > max_age:
        reasons.append(
            f"Corpus documents too old: "
            f"{avg_age} > {max_age} days"
        )

    return make_verdict("ai_infra", reasons)