"""Redrawing without throwing the page away.

Every render function builds a string of HTML. That string used to be assigned
straight to the window, which replaced everything in it: the scroll position
went, the focus went, whatever was half typed went, and every row on the screen
played its entry animation again. These are the things that must not happen.
"""

from __future__ import annotations



def started(ui, projects: int = 6, items: int = 12) -> str:
    """A document big enough that a list has to scroll, and the id of the
    heaviest project in it."""
    ui.run("S.org='Riverbank';S.you='Sam';S.setupWork.apps=true;obGo(4);"
           "S.obExamples=true;obFinish();", settle=700)
    ui.run(
        f"(function(){{var t=S.types[0],g=S.groups[0];"
        f"for(var i=0;i<{projects};i++){{"
        "var p={id:uid(),name:'Project number '+i,group:g.id,type:t.id,stage:1,"
        "enteredAt:new Date(NOW-i*DAY),when:'now',next:'Next on '+i,items:[],"
        "decisions:[],files:[],links:[],notes:'',pub:true,wait:null,"
        "lastAct:new Date(NOW-i*DAY),releases:[],people:[],hist:[],logs:[],"
        "quiet:false,origin:null,parked:false,waitHist:[]};"
        f"for(var j=0;j<{items};j++){{"
        "p.items.push({id:uid(),text:'Something to tick, number '+j,done:false,tag:''});"
        "p.logs.push({id:uid(),text:'What happened on day '+j,at:new Date(NOW-j*DAY),"
        "stage:t.stages[0],highlight:false});}"
        "S.projects.push(p)}render()})();", settle=600)
    return ui.js("S.projects[S.projects.length-1].id")


def scroll_to(ui, where: int) -> int:
    ui.run(f"document.querySelector('.main').scrollTop={where};", settle=200)
    return ui.js("document.querySelector('.main').scrollTop")


# ------------------------------------------------------------- keeping the place


def test_ticking_something_does_not_throw_you_back_to_the_top(ui) -> None:
    pid = started(ui)
    ui.run(f"openP({pid!r});S.ptab='work';render();", settle=400)
    was = scroll_to(ui, 400)
    assert was > 0, "the list is not long enough to test with"

    ui.run(f"toggleItem({pid!r}, Pr({pid!r}).items[6].id);", settle=300)
    assert ui.js("document.querySelector('.main').scrollTop") == was


def test_starring_a_log_entry_does_not_throw_you_back_to_the_top(ui) -> None:
    pid = started(ui)
    ui.run(f"openP({pid!r});S.ptab='rec';render();", settle=400)
    was = scroll_to(ui, 300)
    ui.run(f"toggleHighlight('project',{pid!r},Pr({pid!r}).logs[2].id);", settle=300)
    assert ui.js("document.querySelector('.main').scrollTop") == was


# ------------------------------------------------------- keeping what was typed


def test_something_else_changing_does_not_take_the_focus(ui) -> None:
    pid = started(ui)
    ui.run(f"openP({pid!r});S.ptab='rec';render();", settle=400)
    ui.run("var t=document.querySelector('.logadd textarea');t.focus();"
           "t.value='half a thought';", settle=200)

    ui.run(f"toggleHighlight('project',{pid!r},Pr({pid!r}).logs[0].id);", settle=300)

    assert ui.js("document.activeElement.tagName") == "TEXTAREA"
    assert ui.js("document.querySelector('.logadd textarea').value") == "half a thought"


def test_a_box_that_grew_as_you_typed_stays_grown(ui) -> None:
    pid = started(ui)
    ui.run(f"openP({pid!r});S.ptab='rec';render();", settle=400)
    ui.run("var t=document.querySelector('.logadd textarea');t.focus();"
           "t.value='one\\ntwo\\nthree\\nfour';"
           "t.dispatchEvent(new Event('input',{bubbles:true}));", settle=250)
    tall = ui.js("document.querySelector('.logadd textarea').offsetHeight")
    assert tall > 30, "the box did not grow, so there is nothing to keep"

    ui.run(f"toggleHighlight('project',{pid!r},Pr({pid!r}).logs[0].id);", settle=300)
    assert ui.js("document.querySelector('.logadd textarea').offsetHeight") == tall


def test_what_is_being_written_in_the_notes_is_not_wiped(ui) -> None:
    pid = started(ui)
    ui.run(f"openP({pid!r});S.ptab='work';render();", settle=400)
    ui.run("var n=document.querySelector('[contenteditable]');n.focus();"
           "n.innerText='half a note';", settle=200)
    ui.run(f"toggleItem({pid!r}, Pr({pid!r}).items[0].id);", settle=300)
    assert ui.js("document.querySelector('[contenteditable]').innerText") == "half a note"


# ------------------------------------------------------------ keeping the calm


def running(ui) -> dict:
    return ui.js(
        "(function(){var c={};document.getAnimations().forEach(function(a){"
        "if(a.playState==='running'){var k=a.animationName||'?';c[k]=(c[k]||0)+1}});"
        "return c})()"
    ) or {}


def test_changing_one_row_does_not_replay_every_row(ui) -> None:
    """Every row playing its entry animation again on every click is what made
    the window shudder when anything at all happened."""
    pid = started(ui)
    ui.run(f"openP({pid!r});S.ptab='rec';render();", settle=1200)
    assert running(ui).get("rowin", 0) == 0, "the screen never settled"

    ui.run(f"toggleItem({pid!r}, Pr({pid!r}).items[0].id);", settle=40)
    assert running(ui).get("rowin", 0) == 0, "one tick set every row off again"


def test_a_row_that_is_genuinely_new_still_arrives(ui) -> None:
    """The entry animation is part of the design. It should play when something
    is actually new, and only then."""
    pid = started(ui)
    ui.run(f"openP({pid!r});S.ptab='rec';render();", settle=1200)
    before = ui.count(".dec")

    ui.run(f"recordDecision({pid!r},'Something decided just now.','');render();", settle=40)
    assert ui.count(".dec") == before + 1
    assert running(ui).get("rowin", 0) >= 1, "the new decision did not arrive"


def test_the_rows_that_stayed_are_the_same_elements(ui) -> None:
    """Which is why they do not animate, lose their scroll, or flicker.

    Ticking something sends it to the bottom of the list, so the rows move.
    Moving them is the point: not one of them is built again."""
    pid = started(ui)
    ui.run(f"openP({pid!r});S.ptab='work';render();", settle=400)
    ui.run("window.__was=[].slice.call(document.querySelectorAll('.check'));", settle=100)
    before = ui.js("window.__was.length")

    ui.run(f"toggleItem({pid!r}, Pr({pid!r}).items[2].id);", settle=300)

    kept = ui.js(
        "(function(){var now=[].slice.call(document.querySelectorAll('.check'));"
        "return window.__was.filter(function(e){return now.indexOf(e)>=0}).length})()"
    )
    assert kept == before, f"only {kept} of {before} rows were kept"


def test_a_row_that_went_away_is_gone(ui) -> None:
    pid = started(ui)
    ui.run(f"openP({pid!r});S.ptab='work';render();", settle=400)
    before = ui.count(".check")
    ui.run(f"delItem({pid!r}, Pr({pid!r}).items[3].id);", settle=300)
    assert ui.count(".check") == before - 1


def test_moving_to_another_screen_still_draws_it_whole(ui) -> None:
    started(ui)
    for view in ("projects", "roadmap", "ideas", "library", "week", "settings", "home"):
        ui.run(f"go({view!r});", settle=300)
        assert ui.js("S.view") == view
        assert ui.count(".main *") > 5, f"{view} came out empty"


def test_the_sidebar_keeps_up_without_being_rebuilt(ui) -> None:
    pid = started(ui)
    ui.run("go('home');", settle=300)
    ui.run("window.__nav=document.querySelector('.nav');", settle=100)
    ui.run("go('projects');", settle=300)
    assert ui.js("window.__nav===document.querySelector('.nav')"), (
        "the sidebar was thrown away and built again"
    )
    assert ui.js("document.querySelector('.nav a.on').textContent").strip().startswith(
        "Projects"
    )
