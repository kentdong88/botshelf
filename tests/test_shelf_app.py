import pytest
from streamlit.testing.v1 import AppTest
from botshelf.catalog import ROOT


def label(elements,name): return next(e for e in elements if e.label==name)


def test_four_stage_flow_and_isolation(tmp_path,monkeypatch):
    monkeypatch.setenv("BOTSHELF_DB",str(tmp_path/"ui.sqlite"))
    app=AppTest.from_file(str(ROOT/"app.py"),default_timeout=60).run()
    assert not app.exception
    label(app.button,"Run original shelf").click().run()
    assert not app.exception
    work=app.session_state["amazon_work"]
    assert work["baseline"]["metrics"]["successful_trials"]==15
    label(app.button,"Draft evidence-locked rewrite").click().run()
    assert not app.exception
    label(app.checkbox,"I checked the source passages and approve this version.").check().run()
    label(app.button,"Save approved rewrite").click().run()
    label(app.button,"Retest rewritten shelf").click().run()
    assert not app.exception
    assert app.session_state["amazon_work"]["rewritten_run"]["metrics"]["successful_trials"]==15
    label(app.text_input,"Verified value").set_value("Test fixture only: 24 months limited warranty")
    label(app.text_input,"Source document / reference").set_value("Test-only fixture record")
    label(app.text_input,"Confirmed by").set_value("Test fixture")
    label(app.checkbox,"I confirm this is accurate for this exact SKU and supported by the cited record.").check()
    label(app.button,"Save merchant-confirmed fact").click().run()
    assert not app.exception
    label(app.button,"Retest completed shelf").click().run()
    assert not app.exception
    assert app.session_state["amazon_work"]["completed_run"]["metrics"]["successful_trials"]==15
    assert len(app.get("download_button"))>=7
    label(app.slider,"Repeats per buyer request").set_value(2).run()
    assert "baseline" not in app.session_state["amazon_work"]
    assert "completed" not in app.session_state["amazon_work"]
    assert not app.exception


def test_legacy_workspace_remains_available(tmp_path,monkeypatch):
    monkeypatch.setenv("BOTSHELF_DB",str(tmp_path/"ui.sqlite"))
    app=AppTest.from_file(str(ROOT/"app.py"),default_timeout=60).run()
    label(app.selectbox,"Product workspace").set_value("WANDS research lab").run()
    assert not app.exception
    assert label(app.radio,"Workspace") is not None
