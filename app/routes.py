from flask import Blueprint, current_app, jsonify, render_template, request

from ml.predict import Artifacts, predict
from pg import dashboard_data as dd
from pg import monitoring
from pg.features import FEATURE_COLUMNS

bp = Blueprint("main", __name__)

FEATURE_HELP = {
    "files_changed": "Files changed in the commit", "lines_added": "Lines added", "lines_deleted": "Lines deleted",
    "python_files_changed": "Python files modified", "test_files_changed": "Test files modified",
    "dependency_changes": "Changed lines in dependency files", "known_test_count": "Tests known before the run",
    "previous_build_failed": "Previous build failed (1/0)", "previous_3_build_failures": "Failures in last 3 builds (0-3)",
    "historical_avg_duration": "Historical avg build duration (s)", "historical_failure_rate": "Historical failure rate (0-1)",
}


def _storage():
    return current_app.storage()


def _metrics():
    return _storage().read_json_or_none("reports/model_metrics.json")


@bp.get("/health")
def health():
    return jsonify(status="ok")


@bp.get("/")
def overview():
    df = dd.load_df(_storage())
    ov = dd.overview(df)
    chart = None
    if not ov["empty"]:
        chart = {"labels": ["success", "failure"], "counts": [ov["successful"], ov["failed"]]}
    return render_template("overview.html", ov=ov, chart=chart, page="overview")


@bp.route("/predict", methods=["GET", "POST"])
def predict_page():
    result = error = None
    values = {}
    if request.method == "POST":
        values = {c: request.form.get(c, "").strip() for c in FEATURE_COLUMNS}
        try:
            arts = Artifacts.from_storage(_storage())
            s = current_app.config["PG_SETTINGS"]
            result = predict(values, arts, request.form.get("model") or None, s.risk_low, s.risk_high)
        except FileNotFoundError:
            error = "No trained model exists yet. Collect real executions, aggregate, and run ml/train.py first."
        except ValueError as exc:
            error = str(exc)
    return render_template("predict.html", features=FEATURE_COLUMNS, help=FEATURE_HELP, values=values,
                           result=result, error=error, page="predict")


@bp.post("/api/predict")
def api_predict():
    try:
        arts = Artifacts.from_storage(_storage())
        s = current_app.config["PG_SETTINGS"]
        body = request.get_json(force=True, silent=True) or {}
        return jsonify(predict(body.get("features", {}), arts, body.get("model"), s.risk_low, s.risk_high))
    except FileNotFoundError:
        return jsonify(error="no trained model available"), 404
    except ValueError as exc:
        return jsonify(error=str(exc)), 400


@bp.get("/history")
def history():
    rows = dd.history(dd.load_df(_storage()))
    return render_template("history.html", rows=rows, page="history")


@bp.get("/models")
def models():
    return render_template("models.html", m=_metrics(), page="models")


@bp.get("/experiments")
def experiments():
    return render_template("experiments.html", exps=dd.experiments(_storage()), page="experiments")


@bp.get("/monitoring")
def monitoring_page():
    snap = monitoring.snapshot(current_app.config["PG_SETTINGS"])
    return render_template("monitoring.html", snap=snap, page="monitoring")


@bp.get("/api/overview")
def api_overview():
    return jsonify(dd.overview(dd.load_df(_storage())))


@bp.get("/api/history")
def api_history():
    return jsonify(dd.history(dd.load_df(_storage())))


@bp.get("/api/metrics")
def api_metrics():
    m = _metrics()
    return (jsonify(m), 200) if m else (jsonify(error="no evaluation available"), 404)


@bp.get("/api/experiments")
def api_experiments():
    return jsonify(dd.experiments(_storage()))
