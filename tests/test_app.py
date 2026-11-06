from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def by_label(elements, label):
    return next(e for e in elements if e.label == label)


@pytest.mark.parametrize("repeat", range(3))
@pytest.mark.parametrize("experiment", ["A", "B"])
def test_full_ui_flow(repeat, experiment, tmp_path, monkeypatch):
    monkeypatch.setenv("BOTSHELF_DB", str(tmp_path / "test.sqlite"))
    app = AppTest.from_file(str(ROOT / "legacy_app.py"), default_timeout=30).run()
    assert not app.exception
    by_label(app.radio, "Experiment").set_value(experiment).run()
    # Known recalled real product for the first preset.
    by_label(app.radio, "Workspace").set_value("Shopping Simulation").run()
    by_label(app.button, "Run baseline").click().run()
    assert not app.exception

    assert app.session_state["before_run"].status == "ok"
    by_label(app.radio, "Workspace").set_value("Improve & Compare").run()
    approve = [c for c in app.checkbox if "→" in c.label]
    assert approve
    approve[0].check().run()
    by_label(app.button, "Apply approved revisions").click().run()
    assert not app.exception
    assert not by_label(app.button, "Run paired comparison").disabled
    by_label(app.button, "Run paired comparison").click().run()
    assert app.session_state["after_run"].status == "ok"
    by_label(app.radio, "Workspace").set_value("Evaluation & Export").run()
    assert not app.exception
    assert len(app.get("download_button")) >= 3
    # Switching targets invalidates previous run/revision state.
    target = by_label(app.selectbox, "Target product")
    target.set_value("350").run()
    assert "revised" not in app.session_state
    assert "before_run" not in app.session_state
    assert not app.exception


def test_custom_and_review_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("BOTSHELF_DB", str(tmp_path / "test.sqlite"))
    app = AppTest.from_file(str(ROOT / "legacy_app.py"), default_timeout=30).run()
    by_label(app.radio, "Workspace").set_value("Evaluation & Export").run()
    assert by_label(app.button, "Run batch evaluation").disabled
    by_label(app.checkbox, "Allow unreviewed exploratory evaluation (clearly labelled)").check().run()
    by_label(app.button, "Run batch evaluation").click().run()
    assert not app.exception
    assert not app.session_state["batch"]["manifest"]["formal_evaluation"]

