"""The welcome screen, and the defaults it creates. SPEC section 3.1."""

from __future__ import annotations


def finish_with(ui, org: str, *kinds: str) -> None:
    picks = "".join(f"S.setupWork.{k}=true;" for k in kinds)
    ui.run(f"S.org={org!r};{picks}render();finishSetup();")


def test_a_fresh_machine_opens_on_setup(ui) -> None:
    assert ui.js("S.view") == "setup"
    assert ui.js("S.setupDone") is False
    assert ui.js("S.groups.length") == 0
    assert ui.js("S.types.length") == 0


def test_nothing_is_pre_checked_and_the_name_is_empty(ui) -> None:
    assert ui.js("S.setupWork") == {
        "apps": False, "clients": False, "content": False,
        "personal": False, "programs": False,
    }
    assert ui.js("S.org") == ""
    assert ui.count(".pk.on") == 0


def test_the_theme_starts_on_follow_system(ui) -> None:
    assert ui.js("S.theme") == "system"


def test_apps_creates_the_apps_group_and_the_app_type(ui) -> None:
    finish_with(ui, "Kamsiob", "apps")
    assert ui.js("S.groups") == [
        {"id": "apps", "name": "Apps", "color": "#0BA39E", "priv": False}
    ]
    app_type = ui.js("S.types[0]")
    assert app_type["id"] == "app" and app_type["name"] == "App"
    assert app_type["stages"] == [
        "Idea", "Plan", "Design", "Build", "Test", "Release", "Keep up"
    ]
    assert app_type["check"] == {
        "Plan": ["Write the spec"],
        "Design": ["Approve the mockup", "Write DESIGN.md"],
        "Build": ["Make the repo public", "Keep HANDOFF.md current"],
        "Test": ["Test on a real device"],
        "Release": ["Store listing live", "Publish the release post"],
        "Keep up": ["Review the bug list"],
    }


def test_client_work_is_rose_and_private_by_default(ui) -> None:
    finish_with(ui, "Kamsiob", "clients")
    assert ui.js("S.groups[0]") == {
        "id": "clients", "name": "Clients", "color": "#D14A7A", "priv": True
    }
    client_type = ui.js("S.types[0]")
    assert client_type["name"] == "Client work"
    assert client_type["stages"] == ["Anchor", "Align", "Advance", "Close"]
    assert client_type["check"]["Close"] == ["Closing note sent"]


def test_content_is_blue(ui) -> None:
    finish_with(ui, "Kamsiob", "content")
    assert ui.js("S.groups[0]") == {
        "id": "content", "name": "Content", "color": "#2457F5", "priv": False
    }
    assert ui.js("S.types[0].stages") == [
        "Idea", "Script", "Record", "Edit", "Publish"
    ]


def test_personal_is_sage_and_private(ui) -> None:
    finish_with(ui, "Kamsiob", "personal")
    assert ui.js("S.groups[0]") == {
        "id": "personal", "name": "Personal", "color": "#6B8F71", "priv": True
    }
    assert ui.js("S.types[0].id") == "task"
    assert ui.js("S.types[0].stages") == ["Planned", "In progress", "Done"]


def test_programs_is_amber(ui) -> None:
    finish_with(ui, "Kamsiob", "programs")
    assert ui.js("S.groups[0]") == {
        "id": "programs", "name": "Programs", "color": "#D9890B", "priv": False
    }
    assert ui.js("S.types[0].stages") == ["Planned", "Funded", "Running", "Wrapped"]


def test_nothing_selected_gives_one_group_and_the_task_type(ui) -> None:
    finish_with(ui, "Kamsiob")
    assert [g["name"] for g in ui.js("S.groups")] == ["Projects"]
    assert [t["name"] for t in ui.js("S.types")] == ["Task"]


def test_three_kinds_create_three_groups_and_three_types(ui) -> None:
    finish_with(ui, "Example Studio", "apps", "clients", "personal")
    assert [g["id"] for g in ui.js("S.groups")] == ["apps", "clients", "personal"]
    assert [t["id"] for t in ui.js("S.types")] == ["app", "eng", "task"]


def test_finishing_lands_on_home_with_a_toast(ui) -> None:
    finish_with(ui, "Kamsiob", "apps")
    assert ui.js("S.view") == "home"
    assert ui.js("S.setupDone") is True
    assert any("Press Ctrl K" in t for t in ui.toasts())


def test_your_name_comes_from_the_organization(ui) -> None:
    finish_with(ui, "Alex Rivera", "apps")
    assert ui.js("S.you") == "Alex"
    assert "Alex" in ui.text(".hd h1")


def test_the_greeting_follows_the_clock(ui) -> None:
    finish_with(ui, "Alex", "apps")
    hour = ui.js("new Date().getHours()")
    expected = (
        "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    )
    assert ui.text(".hd h1").startswith(expected)


def test_setup_survives_a_restart(ui) -> None:
    finish_with(ui, "Example Studio", "apps", "content")
    ui.restart()
    assert ui.js("S.view") == "home"
    assert ui.js("S.org") == "Example Studio"
    assert [g["id"] for g in ui.js("S.groups")] == ["apps", "content"]


def test_revisiting_setup_only_adds_what_is_missing(ui) -> None:
    finish_with(ui, "Example Studio", "apps")
    ui.run("G('apps').name='My apps';G('apps').color='#123456';T('app').name='Product';")
    ui.run("S.view='setup';S.setupWork.programs=true;render();finishSetup();")

    groups = {g["id"]: g for g in ui.js("S.groups")}
    assert groups["apps"]["name"] == "My apps", "the edited group is left alone"
    assert groups["apps"]["color"] == "#123456"
    assert "programs" in groups, "the missing default is added"
    types = {t["id"]: t for t in ui.js("S.types")}
    assert types["app"]["name"] == "Product"
    assert "program" in types


def test_revisiting_setup_never_touches_projects(ui) -> None:
    finish_with(ui, "Example Studio", "apps")
    ui.run(
        "S.projects.push({id:'p1',name:'Keep me',group:'apps',type:'app',stage:2,"
        "enteredAt:NOW,when:'now',next:'',items:[],decisions:[],files:[],links:[],"
        "notes:'',pub:true,wait:null,lastAct:NOW,releases:[],people:[],hist:[],"
        "quiet:false,origin:null,parked:false,waitHist:[]});"
    )
    ui.run("S.view='setup';render();finishSetup();")
    assert [p["name"] for p in ui.js("S.projects")] == ["Keep me"]
