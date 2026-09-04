"""The first run: five steps, the examples, and the Start here card. Part 1."""

from __future__ import annotations

from pathlib import Path


def walk(ui, org="Example Studio", you="Alex", kinds=("apps",), examples=False) -> None:
    ui.run(f"S.org={org!r};S.you={you!r};obGo(2);")
    picks = "".join(f"S.setupWork.{k}=true;" for k in kinds)
    ui.run(f"obGo(3);{picks}render();")
    ui.run(f"obGo(4);S.obExamples={'true' if examples else 'false'};render();")
    ui.run("obGo(5);")
    ui.run("obFinish();", settle=500)


# ------------------------------------------------------------------ the steps


def test_a_fresh_machine_opens_on_the_first_step(ui) -> None:
    assert ui.js("S.view") == "setup"
    assert ui.js("S.obStep") == 1
    assert ui.count(".ob .dots i") == 5
    assert ui.count(".ob .dots i.on") == 1
    body = ui.html()
    assert "Dig keeps every project you're working on in one place." in body
    assert "no outbound internet requests of any kind" in body
    assert "no accounts and no cloud" in body
    assert "Sync is off by default" in body


def test_it_only_appears_once(ui) -> None:
    walk(ui)
    assert ui.js("S.view") == "home"
    ui.restart()
    assert ui.js("S.view") == "home", "a second launch goes straight in"


def test_back_and_continue_walk_the_steps(ui) -> None:
    for step in range(1, 6):
        ui.run(f"obGo({step});")
        assert ui.js("S.obStep") == step
        assert ui.count(".ob .dots i.on") == 1
        assert ui.count(".ob .dots i.done") == step - 1
    assert "Back" in ui.html()
    assert "Open Dig" in ui.html()


def test_the_name_fields_are_optional(ui) -> None:
    ui.run("obGo(2);")
    assert "optional" in ui.html().lower()
    ui.run("obGo(5);obFinish();", settle=500)
    assert ui.js("S.setupDone") is True
    assert ui.text(".hd h1").startswith("Good")
    assert "," not in ui.text(".hd h1"), "with no name it simply says good morning"


def test_the_preview_says_what_will_be_created(ui) -> None:
    ui.run("obGo(3);S.setupWork.apps=true;render();")
    preview = ui.text(".ob .preview")
    assert "Apps" in preview and "App" in preview
    assert "Idea" in preview and "Keep up" in preview

    ui.run("S.setupWork.apps=false;render();")
    assert "Projects" in ui.text(".ob .preview")
    assert "Task" in ui.text(".ob .preview")


def test_skip_jumps_to_the_end_and_still_applies_defaults(ui) -> None:
    ui.run("obGo(3);S.setupWork.personal=true;render();obSkip();")
    assert ui.js("S.obStep") == 5
    ui.run("obFinish();", settle=500)
    assert [g["id"] for g in ui.js("S.groups")] == ["personal"]
    assert ui.js("S.setupDone") is True


def test_each_work_kind_creates_exactly_its_documented_defaults(ui) -> None:
    walk(ui, kinds=("apps", "clients", "content", "personal", "programs"))
    assert [g["id"] for g in ui.js("S.groups")] == [
        "apps", "clients", "content", "personal", "programs"
    ]
    assert [t["id"] for t in ui.js("S.types")] == [
        "app", "eng", "content", "task", "program"
    ]
    groups = {g["id"]: g for g in ui.js("S.groups")}
    assert groups["clients"]["priv"] is True and groups["clients"]["color"] == "#D14A7A"
    assert groups["personal"]["priv"] is True and groups["personal"]["color"] == "#6B8F71"
    assert groups["apps"]["color"] == "#0BA39E"
    assert groups["content"]["color"] == "#2457F5"
    assert groups["programs"]["color"] == "#D9890B"


# -------------------------------------------------------------- the examples


def test_starting_empty_creates_nothing(ui) -> None:
    walk(ui, examples=False)
    assert ui.js("S.projects") == []
    assert ui.js("S.ideas") == []
    assert ui.js("S.inbox") == []
    assert ui.js("S.library") == []
    assert ui.js("S.activity") == []
    assert "Nothing lined up" in ui.html()


def test_the_examples_are_generic_and_complete(ui) -> None:
    walk(ui, kinds=("apps", "personal"), examples=True)
    names = [p["name"] for p in ui.js("S.projects")]
    assert sorted(names) == [
        "Kitchen renovation", "New client onboarding", "Quarterly report", "Website refresh"
    ]
    assert all(p["example"] for p in ui.js("S.projects"))
    assert len(ui.js("S.ideas")) == 4
    assert len(ui.js("S.inbox")) == 1
    assert any(p["wait"] for p in ui.js("S.projects")), "one thing waiting"
    assert sum(len(p["decisions"]) for p in ui.js("S.projects")) == 2
    assert sum(len(p["logs"]) for p in ui.js("S.projects")) == 1
    assert ui.js("S.resurfId"), "there is an old idea to bring back"


def test_the_examples_carry_none_of_anyones_real_work(ui) -> None:
    walk(ui, examples=True)
    everything = " ".join(
        [p["name"] + p["notes"] for p in ui.js("S.projects")]
        + [i["text"] + i["desc"] for i in ui.js("S.ideas")]
        + [l["title"] + l["meta"] for l in ui.js("S.library")]
    )
    for private in ("Kamsiob", "Wellbeing", "Marchmont", "C9", "Riverbank Care", "@"):
        assert private not in everything


def test_the_examples_come_out_in_one_click(ui) -> None:
    walk(ui, examples=True)
    ui.run("S.view='settings';render();")
    assert "Remove the examples" in ui.html()

    ui.run("removeExamples();", settle=500)
    assert ui.js("S.projects") == []
    assert ui.js("S.ideas") == []
    assert ui.js("S.library") == []
    assert any("example records" in t for t in ui.toasts())

    ui.run("S.view='settings';render();")
    assert "Remove the examples" not in ui.html(), "the button goes once there are none"


def test_removing_the_examples_leaves_your_own_work_alone(ui) -> None:
    walk(ui, examples=True)
    ui.run("openNew(S.groups[0].id);document.getElementById('np-n').value='Mine';createP(null);")
    ui.run("removeExamples();", settle=500)
    assert [p["name"] for p in ui.js("S.projects")] == ["Mine"]


# ------------------------------------------------------------- run it again


def test_setup_can_be_run_again_without_touching_anything(ui) -> None:
    walk(ui, kinds=("apps",))
    ui.run("openNew('apps');document.getElementById('np-n').value='Keep me';createP(null);")
    ui.run("G('apps').name='My apps';")

    ui.run("S.view='settings';render();")
    assert "Run setup again" in ui.html()
    ui.run("S.obStep=1;go('setup');")
    assert ui.js("S.view") == "setup" and ui.js("S.obStep") == 1
    ui.run("obGo(3);S.setupWork.programs=true;render();obGo(5);obFinish();", settle=500)

    assert [p["name"] for p in ui.js("S.projects")] == ["Keep me"]
    groups = {g["id"]: g["name"] for g in ui.js("S.groups")}
    assert groups["apps"] == "My apps", "the edited group is left alone"
    assert "programs" in groups, "the missing default is added"


# --------------------------------------------------------------- start here


def test_start_here_shows_and_ticks_itself(ui) -> None:
    walk(ui, kinds=("apps",))
    assert ui.count(".starthere") == 1
    assert ui.count(".starthere .step.ok") == 0

    ui.run("openNew('apps');document.getElementById('np-n').value='First one';createP(null);")
    ui.run("go('home');")
    assert ui.count(".starthere .step.ok") == 1

    ui.run("openCap();document.getElementById('cap-in').value='Something to remember';doCapture();")
    ui.run("go('home');")
    assert ui.count(".starthere .step.ok") == 2

    pid = ui.js("S.projects[0].id")
    ui.run(f"tickStartHere('nextStep');go('home');")
    assert ui.count(".starthere") == 0, "all three done, so it goes"


def test_start_here_can_be_dismissed_and_never_comes_back(ui) -> None:
    walk(ui, kinds=("apps",))
    assert ui.count(".starthere") == 1
    ui.click(".starthere .x")
    assert ui.count(".starthere") == 0
    ui.restart()
    assert ui.count(".starthere") == 0


def test_start_here_survives_a_restart_until_it_is_finished(ui) -> None:
    walk(ui, kinds=("apps",))
    ui.run("openNew('apps');document.getElementById('np-n').value='First one';createP(null);go('home');")
    ui.restart()
    assert ui.count(".starthere") == 1
    assert ui.count(".starthere .step.ok") == 1
