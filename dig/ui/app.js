/* ================== DIG, AND THE COMPUTER UNDER IT ==================
   The interface below is the approved prototype from
   docs/handoff-v2/design/dig-prototype.html, unchanged apart from the seams
   SPEC section 1 calls for: state arrives from the bridge instead of a seed
   function, every change is written back through it, and file pickers, folder
   opening, link opening, exports, and imports go to Python.
   ==================================================================== */

var DAY=86400000;
/* The prototype froze the clock at 2026-09-04T14:00 so its sample data would
   read well. The app reads the real one. Every use of NOW below is untouched. */
Object.defineProperty(window,'NOW',{get:function(){return new Date()}});
function d(daysAgo){return new Date(NOW-daysAgo*DAY)}

var S=null,BRIDGE=null,READY=false,SYS_THEME='light',DATA_PATH='',VERSION='';

/* IDs have to stay unique across sessions now that state is kept, so the
   prototype's counter, which restarted at 100 on every reload, is replaced. */
var _u=0;
function uid(){_u++;return 'x'+Date.now().toString(36)+_u.toString(36)}

/* The stages, checklists, groups, and colors the setup screen creates. */
var SETUP_TYPES={
  app:{id:'app',name:'App',stages:['Idea','Plan','Design','Build','Test','Release','Keep up'],check:{Plan:['Write the spec'],Design:['Approve the mockup','Write DESIGN.md'],Build:['Make the repo public','Keep HANDOFF.md current'],Test:['Test on a real device'],Release:['Store listing live','Publish the release post'],'Keep up':['Review the bug list']}},
  eng:{id:'eng',name:'Client work',stages:['Anchor','Align','Advance','Close'],check:{Anchor:['Intake complete'],Align:['Plan agreed with client'],Advance:['Deliverables handed over'],Close:['Closing note sent']}},
  content:{id:'content',name:'Content',stages:['Idea','Script','Record','Edit','Publish'],check:{}},
  task:{id:'task',name:'Task',stages:['Planned','In progress','Done'],check:{}},
  program:{id:'program',name:'Program',stages:['Planned','Funded','Running','Wrapped'],check:{}}
};
var SETUP_GROUPS={
  apps:{id:'apps',name:'Apps',color:'#0BA39E',priv:false},
  clients:{id:'clients',name:'Clients',color:'#D14A7A',priv:true},
  content:{id:'content',name:'Content',color:'#2457F5',priv:false},
  personal:{id:'personal',name:'Personal',color:'#6B8F71',priv:true},
  programs:{id:'programs',name:'Programs',color:'#D9890B',priv:false},
  projects:{id:'projects',name:'Projects',color:'#0BA39E',priv:false}
};
var SETUP_PICKS=[['apps','apps','app'],['clients','clients','eng'],['content','content','content'],['personal','personal','task'],['programs','programs','program']];

function blank(){return{org:'',you:'',theme:'system',setupDone:false,
  groups:[],types:[],projects:[],ideas:[],inbox:[],library:[],activity:[],
  view:'setup',projectId:null,ptab:'work',filterGroup:'all',sort:'activity',
  ideaSort:'oldest',libFilter:'all',publicOnly:true,resurfId:null,
  capType:'auto',capProject:'',toasts:[],uiWindow:null,
  setupWork:{apps:false,clients:false,content:false,personal:false,programs:false}}}

/* Dates travel as ISO strings and come back as Dates, at the exact places the
   data model puts them. Nothing guesses at what a date looks like. */
function reDate(v){return v==null?null:(v instanceof Date?v:new Date(v))}
function revive(s){
  s.projects.forEach(function(p){
    p.items=p.items||[];p.decisions=p.decisions||[];p.files=p.files||[];p.links=p.links||[];
    p.releases=p.releases||[];p.people=p.people||[];p.hist=p.hist||[];p.waitHist=p.waitHist||[];
    p.enteredAt=reDate(p.enteredAt)||NOW;p.lastAct=reDate(p.lastAct)||p.enteredAt;
    p.decisions.forEach(function(x){x.at=reDate(x.at)});
    p.releases.forEach(function(r){r.at=reDate(r.at)});
    p.hist.forEach(function(h){h.from=reDate(h.from);h.to=reDate(h.to)});
    if(p.wait)p.wait.since=reDate(p.wait.since)||NOW;
  });
  s.ideas.forEach(function(x){x.at=reDate(x.at)||NOW;x.opened=reDate(x.opened)});
  s.inbox.forEach(function(x){x.at=reDate(x.at)||NOW});
  s.activity.forEach(function(a){a.at=reDate(a.at)||NOW});
  return s;
}
function adopt(saved){
  var s=blank();
  if(!saved)return s;
  ['org','you','theme','setupDone','groups','types','projects','ideas','inbox','library','activity']
    .forEach(function(k){if(saved[k]!==undefined&&saved[k]!==null)s[k]=saved[k]});
  var ui=saved.ui||{};
  ['filterGroup','sort','ideaSort','libFilter','publicOnly','ptab','resurfId']
    .forEach(function(k){if(ui[k]!==undefined&&ui[k]!==null)s[k]=ui[k]});
  s.uiWindow=ui.window||null;
  s.view=s.setupDone?'home':'setup';
  return revive(s);
}
/* What goes to disk. SPEC section 2 puts the view's own settings under `ui`,
   so they are folded in here and spread back out on the way in. */
function persist(){return{org:S.org,you:S.you,theme:S.theme,setupDone:S.setupDone,
  groups:S.groups,types:S.types,projects:S.projects,ideas:S.ideas,inbox:S.inbox,
  library:S.library,activity:S.activity,
  ui:{filterGroup:S.filterGroup,sort:S.sort,ideaSort:S.ideaSort,libFilter:S.libFilter,
      publicOnly:S.publicOnly,ptab:S.ptab,resurfId:S.resurfId,window:S.uiWindow}}}

var saveTimer=null;
function scheduleSave(){if(!READY||!BRIDGE)return;if(saveTimer)clearTimeout(saveTimer);saveTimer=setTimeout(flushSave,150)}
function flushSave(){if(saveTimer){clearTimeout(saveTimer);saveTimer=null}if(!READY||!BRIDGE)return;BRIDGE.save(JSON.stringify(persist()))}
window.flushSave=flushSave;

function setMotion(on){document.documentElement.setAttribute('data-motion',on?'reduce':'full')}

/* A value safe to drop into a double quoted onclick attribute. */
function jsq(s){return esc(JSON.stringify(String(s==null?'':s)))}

function greetingLine(){
  var h=NOW.getHours();
  var g=h<12?'Good morning':(h<18?'Good afternoon':'Good evening');
  return S.you?g+', '+esc(S.you)+'.':g+'.';
}
function weekOf(){return new Date(NOW-6*DAY).toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'})}

function openLink(u){if(!BRIDGE)return;BRIDGE.openUrl(String(u),function(ok){if(!ok)toast('That is not an address Dig can open.')})}
function openStored(path){
  if(!path){toast('Dig does not keep a copy of that one.');return}
  if(!BRIDGE)return;
  BRIDGE.openPath(String(path),function(ok){if(!ok)toast('That file is not there anymore.')});
}
function openDataFolder(){if(BRIDGE)BRIDGE.openDataFolder(function(){})}

function finishSetup(){
  var field=document.querySelector('.setup input[type=text]');
  if(field)S.org=field.value.trim();
  var copy=function(x){return JSON.parse(JSON.stringify(x))};
  var addGroup=function(g){if(!S.groups.some(function(x){return x.id===g.id}))S.groups.push(copy(g))};
  var addType=function(t){if(!S.types.some(function(x){return x.id===t.id}))S.types.push(copy(t))};
  SETUP_PICKS.forEach(function(pick){
    if(!S.setupWork[pick[0]])return;
    addGroup(SETUP_GROUPS[pick[1]]);addType(SETUP_TYPES[pick[2]]);
  });
  if(!S.groups.length)addGroup(SETUP_GROUPS.projects);
  if(!S.types.length)addType(SETUP_TYPES.task);
  if(!S.you)S.you=(S.org||'').split(' ')[0];
  S.setupDone=true;
  go('home');
  toast('You\'re set. Press Ctrl K any time to add something.');
}

function start(){
  if(typeof qt==='undefined'||!qt.webChannelTransport){S=adopt(null);render();return}
  new QWebChannel(qt.webChannelTransport,function(channel){
    BRIDGE=channel.objects.bridge;
    BRIDGE.themeChanged.connect(function(t){SYS_THEME=t;if(S&&S.theme==='system')render()});
    BRIDGE.motionChanged.connect(setMotion);
    BRIDGE.pdfDone.connect(function(json){
      var r=JSON.parse(json);
      if(!r.ok){if(r.reason&&r.reason!=='cancelled')toast('The PDF did not save. '+esc(r.reason));return}
      toast('Saved <b>'+esc(r.name)+'</b>');
    });
    BRIDGE.load(function(json){
      var opening=JSON.parse(json);
      SYS_THEME=opening.theme||'light';
      DATA_PATH=opening.dataPath||'';
      VERSION=opening.version||'';
      setMotion(opening.reduceMotion);
      S=adopt(opening.state);
      pickResurf();
      READY=true;
      render();
      if(opening.notice)toast(esc(opening.notice));
    });
  });
}

/* ======================= HELPERS ======================= */
function G(id){return S.groups.find(function(g){return g.id===id})||{name:'No group',color:'#999',priv:false}}
function T(id){return S.types.find(function(t){return t.id===id})}
function Pr(id){return S.projects.find(function(p){return p.id===id})}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function ago(dt){var ms=NOW-dt;var h=ms/3600000;if(h<1)return Math.max(1,Math.round(ms/60000))+' min';if(h<24)return Math.round(h)+' hours';var dd=Math.round(h/24);if(dd===1)return '1 day';if(dd<14)return dd+' days';if(dd<60)return Math.round(dd/7)+' weeks';return Math.round(dd/30)+' months'}
function days(dt){return Math.max(0,Math.round((NOW-dt)/DAY))}
function fmt(dt){return dt.toLocaleDateString('en-US',{month:'short',day:'numeric'})}
function stageName(p){return T(p.type).stages[p.stage]}
function nextStage(p){return T(p.type).stages[p.stage+1]||null}
function isLast(p){return p.stage>=T(p.type).stages.length-1}
function unmet(p){var t=T(p.type),st=stageName(p),ex=t.check[st]||[];return ex.filter(function(e){var it=p.items.find(function(x){return x.text===e});return !(it&&it.done)})}
function nextDecNo(){var m=0;S.projects.forEach(function(p){p.decisions.forEach(function(x){if(x.no>m)m=x.no})});return m+1}
function dno(n){return 'D-'+String(n).padStart(4,'0')}
function toast(msg,undo){var id=uid();S.toasts.push({id:id,msg:msg,undo:undo});renderToasts();setTimeout(function(){S.toasts=S.toasts.filter(function(t){return t.id!==id});renderToasts()},3400)}
function log(p,text,kind){S.activity.unshift({group:p.group,pid:p.id,text:text,at:NOW,kind:kind});p.lastAct=NOW}
function pickResurf(){var pool=S.ideas.slice().sort(function(a,b){return b.at-a.at}).slice(3).filter(function(x){return x.id!==S.resurfId});if(!pool.length){S.resurfId=null;return}S.resurfId=pool[Math.floor(Math.random()*pool.length)].id}
function sbar(p){var t=T(p.type);return '<div class="sbar">'+t.stages.map(function(s,i){return '<i class="'+(i<p.stage?'d':(i===p.stage?'c':''))+'"></i>'}).join('')+'</div>'}
function tbadge(p){var t=T(p.type);var cls={app:'t-app',hw:'t-hw',eng:'t-eng',task:'t-task'}[t.id]||'t-x';return '<span class="badge '+cls+'">'+esc(t.name)+'</span>'}
function ini(s){return s.split(' ').map(function(w){return w[0]}).join('').slice(0,2).toUpperCase()}
function secIcon(kind){var m={next:['var(--blue-soft)','var(--blue)','<path d="M3 8h9M8.5 4.5L12 8l-3.5 3.5"/>'],wait:['var(--amber-soft)','var(--amber)','<circle cx="8" cy="8" r="5.5"/><path d="M8 5v3l2 1.5"/>'],inbox:['var(--teal-soft)','var(--teal)','<path d="M2.5 9h3l1 2h3l1-2h3V13h-11z"/><path d="M4 9V3.5h8V9"/>'],idea:['var(--green-soft)','var(--green)','<path d="M8 2.5a3.5 3.5 0 0 0-2 6.4v1.6h4V8.9a3.5 3.5 0 0 0-2-6.4zM6.5 12.5h3"/>'],rm:['var(--rose-soft)','var(--rose)','<path d="M2.5 12.5l3-6 3 3 2-4 3 5"/>'],dec:['var(--blue-soft)','var(--blue)','<path d="M3.5 8.5l2.5 2.5 6-6"/>'],file:['var(--coral-soft)','var(--coral)','<path d="M4 2.5h5l3 3v8H4z"/>'],rel:['var(--green-soft)','var(--green)','<path d="M8 2.5l1.7 3.4 3.8.5-2.7 2.7.6 3.8L8 11.1l-3.4 1.8.6-3.8-2.7-2.7 3.8-.5z"/>'],ppl:['var(--teal-soft)','var(--teal)','<circle cx="8" cy="6" r="2.5"/><path d="M3.5 13a4.5 4.5 0 0 1 9 0"/>']}[kind];return '<span class="ic" style="background:'+m[0]+';color:'+m[1]+'"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'+m[2]+'</svg></span>'}
var HZ=[['now','Now','what you\'re working on','var(--blue)'],['next','Next','lined up after','var(--teal)'],['later','Later','real, not soon','var(--amber)'],['someday','Someday','parked or dreaming','var(--ink-3)']];
/* Advancing into a last stage sets the horizon to "done", which is not one of
   the four columns, so the horizon badge has to have a word for it. The rest of
   the app already calls that state Finished. */
function hzLabel(w){var h=HZ.find(function(x){return x[0]===(w||'later')});return h?h[1]:'Finished'}

/* ======================= RENDER ======================= */
function render(){
  document.documentElement.setAttribute('data-theme',S.theme==='system'?SYS_THEME:S.theme);
  var app=document.getElementById('app');
  app.className='app';
  app.innerHTML=renderSide()+'<main class="main" id="main">'+renderView(S.view)+'</main>'+renderOverlays()+'<div class="toasts" id="toasts"></div>';
  renderToasts();
  scheduleSave();
}
function renderToasts(){var t=document.getElementById('toasts');if(!t)return;t.innerHTML=S.toasts.map(function(x){return '<div class="toast">'+x.msg+(x.undo?' <span class="u" onclick="'+x.undo+'">Undo</span>':'')+'</div>'}).join('')}
function ico(n){return{home:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M2.5 7.5L8 3l5.5 4.5V13a1 1 0 0 1-1 1H3.5a1 1 0 0 1-1-1z"/></svg>',projects:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="2" y="2" width="5" height="5" rx="1.2"/><rect x="9" y="2" width="5" height="5" rx="1.2"/><rect x="2" y="9" width="5" height="5" rx="1.2"/><rect x="9" y="9" width="5" height="5" rx="1.2"/></svg>',roadmap:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M2 12l4-3 3 2 5-5"/><path d="M11 6h3v3"/></svg>',ideas:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M8 2a4 4 0 0 0-2.5 7.1c.4.4.5.9.5 1.4V11h4v-.5c0-.5.1-1 .5-1.4A4 4 0 0 0 8 2zM6.5 13.5h3"/></svg>',library:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 3h4l1 1.5h5V13H3z"/></svg>',week:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 13V8M8 13V3M13 13V6"/></svg>'}[n]}
function renderSide(){
  var nav=[['home','Home','1'],['projects','Projects','2'],['roadmap','Roadmap','3'],['ideas','Ideas','4'],['library','Library','5'],['week','Your week','6']];
  return '<aside class="side"><div class="who"><div class="av"></div><div><div class="n">'+esc(S.org)+'</div><div class="s">Dig · stays on this computer</div></div></div>'+
  '<button class="add-btn" onclick="openCap()"><svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3v10M3 8h10"/></svg>Add something <kbd>Ctrl K</kbd></button>'+
  '<nav class="nav">'+nav.map(function(n){var on=S.view===n[0]||(n[0]==='projects'&&S.view==='project');var right=n[0]==='home'&&S.inbox.length?'<span class="cnt">'+S.inbox.length+'</span>':'<kbd class="k">'+n[2]+'</kbd>';return '<a class="'+(on?'on':'')+'" onclick="go(\''+n[0]+'\')">'+ico(n[0])+n[1]+right+'</a>'}).join('')+'</nav>'+
  '<div class="sec-h">Groups <a onclick="go(\'settings\')">edit</a></div><div class="groups"><a class="'+(S.filterGroup==='all'?'on':'')+'" onclick="setGroup(\'all\')"><i style="background:var(--ink-3)"></i>Everything<span class="c">'+S.projects.length+'</span></a>'+S.groups.map(function(g){var n=S.projects.filter(function(p){return p.group===g.id}).length;return '<a class="'+(S.filterGroup===g.id?'on':'')+'" onclick="setGroup(\''+g.id+'\')"><i style="background:'+g.color+'"></i>'+esc(g.name)+(g.priv?'<span class="lk">private</span>':'')+'<span class="c">'+n+'</span></a>'}).join('')+'</div>'+
  '<div class="side-foot"><a onclick="go(\'settings\')">Settings</a><a onclick="openKeys()">Shortcuts <kbd>?</kbd></a><div class="theme">'+['light','dark','system'].map(function(m){return '<button class="'+(S.theme===m?'on':'')+'" onclick="setTheme(\''+m+'\')">'+(m==='system'?'Auto':m[0].toUpperCase()+m.slice(1))+'</button>'}).join('')+'</div></div></aside>';
}
function renderView(v){switch(v){case 'home':return renderHome();case 'projects':return renderProjects();case 'project':return renderProject();case 'roadmap':return renderRoadmap();case 'week':return renderWeek();case 'ideas':return renderIdeas();case 'library':return renderLibrary();case 'settings':return renderSettings();case 'setup':return renderSetup()}return ''}

/* ---- HOME ---- */
function renderHome(){
  var active=S.projects.filter(function(p){return !p.quiet&&!p.parked&&!isLast(p)});
  var waiting=S.projects.filter(function(p){return p.wait});
  var upNext=S.projects.filter(function(p){return !p.wait&&!p.quiet&&!p.parked&&p.next}).sort(function(a,b){return days(b.enteredAt)-days(a.enteredAt)}).slice(0,4);
  var r=S.ideas.find(function(x){return x.id===S.resurfId});
  var row=function(p){var g=G(p.group);return '<div class="row click" id="row-'+p.id+'" onclick="openP(\''+p.id+'\')"><span class="dotc" style="background:'+g.color+'"></span><div class="grow"><div class="t">'+esc(p.next)+'</div><div class="m"><b>'+esc(p.name)+'</b> · '+esc(stageName(p))+(days(p.enteredAt)?' for '+days(p.enteredAt)+' days':'')+'</div></div><div class="acts"><button class="btn sm" onclick="event.stopPropagation();doneNext(\''+p.id+'\')">Done ✓</button><button class="btn sm ghost" onclick="event.stopPropagation();openP(\''+p.id+'\')">Open</button></div></div>'};
  return '<div class="view"><div class="hd"><div><h1>'+greetingLine()+'</h1><div class="sub"><b>'+active.length+'</b> projects active · <b>'+waiting.length+'</b> waiting on someone else · <b>'+S.inbox.length+'</b> in your inbox</div></div><div class="r"><div class="search" onclick="openPal()">Find anything <kbd>/</kbd></div></div></div>'+
  '<div class="sec"><div class="sec-t"><h2>'+secIcon('next')+'Up next</h2><span class="help">the next step on each project that\'s been sitting longest</span><a class="rt" onclick="go(\'projects\')">All projects →</a></div><div class="box">'+(upNext.length?upNext.map(row).join(''):'<div class="empty"><div class="gl" style="background:var(--blue-soft);color:var(--blue)"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 8h9M8.5 4.5L12 8l-3.5 3.5"/></svg></div><b>Nothing lined up</b>Open a project and write its next step.</div>')+'</div></div>'+
  '<div class="sec"><div class="sec-t"><h2>'+secIcon('wait')+'Waiting on someone else</h2><span class="help">days counted, nobody nagged</span></div><div class="box">'+(waiting.length?waiting.map(function(p){return '<div class="row click" id="wrow-'+p.id+'" onclick="openP(\''+p.id+'\')"><span class="waitdot"></span><div class="grow"><div class="t">'+esc(p.wait.what)+'</div><div class="m"><b>'+esc(p.name)+'</b></div></div><span class="badge w">'+days(p.wait.since)+' days</span><button class="btn sm ghost" onclick="event.stopPropagation();resolveWait(\''+p.id+'\')">It arrived</button></div>'}).join(''):'<div class="empty"><div class="gl" style="background:var(--amber-soft);color:var(--amber)"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="8" cy="8" r="5.5"/><path d="M8 5v3l2 1.5"/></svg></div><b>Nothing waiting</b>Everything is in your hands right now.</div>')+'</div></div>'+
  '<div class="sec"><div class="sec-t"><h2>'+secIcon('inbox')+'Inbox</h2><span class="help">things you added quickly, waiting to be put somewhere</span></div><div class="box">'+(S.inbox.length?S.inbox.map(function(u){var gp=u.guess&&Pr(u.guess);return '<div class="row" id="irow-'+u.id+'"><span class="badge '+(u.type==='bug'?'b':(u.type==='link'?'g':'i'))+'">'+u.type+'</span><div class="grow"><div class="t">'+esc(u.text)+'</div><div class="m">'+ago(u.at)+' ago'+(gp?' · looks like <b>'+esc(gp.name)+'</b>':'')+'</div></div><div class="acts">'+(gp?'<button class="btn sm" onclick="quickFile(\''+u.id+'\')">Put in '+esc(gp.name)+'</button>':'')+'<button class="btn sm ghost" onclick="openSort(\''+u.id+'\')">Choose…</button></div></div>'}).join(''):'<div class="empty"><div class="gl" style="background:var(--teal-soft);color:var(--teal)"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M2.5 9h3l1 2h3l1-2h3V13h-11z"/><path d="M4 9V3.5h8V9"/></svg></div><b>Inbox is empty</b>Press Ctrl K to add something. It lands here if you don\'t say where it goes.</div>')+'</div></div>'+
  '<div class="sec"><div class="sec-t"><h2>'+secIcon('idea')+'An old idea worth a second look</h2><span class="help">picked at random from ideas you haven\'t touched</span></div><div class="box">'+(r?'<div class="row"><div class="grow"><div class="t">'+esc(r.text)+'</div><div class="m">'+esc(r.desc)+'</div><div class="m">Written '+ago(r.at)+' ago · '+(r.opened?'last opened '+ago(r.opened)+' ago':'never opened since')+'</div></div><div class="acts"><button class="btn sm p" onclick="startIdea(\''+r.id+'\')">Start it</button><button class="btn sm ghost" onclick="openIdea(\''+r.id+'\')">Open</button><button class="btn sm ghost" onclick="pickResurf();render()">Show another</button></div></div>':'<div class="empty"><b>Nothing to resurface yet</b>Once you have a few ideas, one will show up here each day.</div>')+'</div></div></div>';
}
function leave(id,fn){var el=document.getElementById(id);if(el){el.classList.add('leave');setTimeout(fn,220)}else fn()}
function doneNext(id){var p=Pr(id);var was=p.next;leave('row-'+id,function(){p.next='';p.lastAct=NOW;render();toast('Nice. <b>'+esc(p.name)+'</b> moved forward. Open it to set the next step.',"Pr('"+id+"').next="+JSON.stringify(was).replace(/"/g,'&quot;')+";render()")})}
function quickFile(uid_){var u=S.inbox.find(function(x){return x.id===uid_});var p=Pr(u.guess);leave('irow-'+uid_,function(){p.items.unshift({id:uid(),text:u.text,done:false,tag:u.type==='bug'?'bug':''});p.lastAct=NOW;S.inbox=S.inbox.filter(function(x){return x.id!==uid_});render();toast('Put in <b>'+esc(p.name)+'</b>')})}

/* ---- PROJECTS ---- */
function renderProjects(){
  var ps=S.projects.filter(function(p){return S.filterGroup==='all'||p.group===S.filterGroup});
  if(S.sort==='waiting')ps=ps.filter(function(p){return p.wait});if(S.sort==='done')ps=ps.filter(function(p){return isLast(p)||p.quiet});if(S.sort==='parked')ps=ps.filter(function(p){return p.parked});if(S.sort==='activity')ps=ps.filter(function(p){return !p.parked});
  ps.sort(function(a,b){return b.lastAct-a.lastAct});
  var groups=S.groups.filter(function(g){return S.filterGroup==='all'||g.id===S.filterGroup});
  return '<div class="view wide"><div class="hd"><div><h1>Projects</h1><div class="sub">Everything you\'re working on, by group. Each one moves through stages.</div></div><div class="r"><div class="search" onclick="openPal()">Find a project <kbd>/</kbd></div><button class="btn" onclick="openShare(null)">Share as PDF</button><button class="btn p" onclick="openNew(\'\')">New project</button></div></div>'+
  '<div class="chips"><span class="chip '+(S.filterGroup==='all'?'on':'')+'" onclick="setGroup(\'all\')">All groups</span>'+S.groups.map(function(g){return '<span class="chip '+(S.filterGroup===g.id?'on':'')+'" onclick="setGroup(\''+g.id+'\')"><i style="background:'+g.color+'"></i>'+esc(g.name)+'</span>'}).join('')+'<span class="sp"></span><select onchange="S.sort=this.value;render()"><option value="activity" '+(S.sort==='activity'?'selected':'')+'>Active</option><option value="waiting" '+(S.sort==='waiting'?'selected':'')+'>Only waiting</option><option value="done" '+(S.sort==='done'?'selected':'')+'>Only finished</option><option value="parked" '+(S.sort==='parked'?'selected':'')+'>Only parked</option></select></div>'+
  groups.map(function(g){var list=ps.filter(function(p){return p.group===g.id});return '<div class="grp" style="--gc:'+g.color+'"><div class="grp-h"><span class="n"><span class="dotc" style="background:'+g.color+'"></span>'+esc(g.name)+'</span><span class="c">'+list.length+'</span>'+(g.priv?'<span class="lk">private · never shared</span>':'')+'<span class="add" onclick="S.filterGroup=\''+g.id+'\';go(\'roadmap\')">roadmap</span><span class="add" onclick="openNew(\''+g.id+'\')">+ project</span></div>'+(list.length?'<div class="cards">'+list.map(card).join('')+'</div>':'<div class="box empty"><b>No projects here</b>Add one, or start one from an idea.</div>')+'</div>'}).join('')+'</div>';
}
function card(p){var t=T(p.type),g=G(p.group),ns=nextStage(p);
  var line=p.wait?'<b>'+esc(stageName(p))+'</b><span class="badge w">Waiting '+days(p.wait.since)+'d</span>':(p.parked?'<span class="badge pk">Parked</span>':(p.quiet||isLast(p)?'<span class="badge s">Finished · '+esc(stageName(p))+'</span>':'<span><b>'+esc(stageName(p))+'</b> · stage '+(p.stage+1)+' of '+t.stages.length+'</span><span>'+(days(p.enteredAt)?days(p.enteredAt)+' days here':'today')+'</span>'));
  var nx=p.wait?'<span class="w">Waiting on</span>'+esc(p.wait.what):(p.quiet?'<span>Quiet since</span>'+fmt(p.lastAct):(p.next?'<span>Next step</span>'+esc(p.next):'<span>Next step</span><i style="color:var(--ink-3)">not set yet</i>'));
  var qa=p.wait?'<button class="btn sm" onclick="event.stopPropagation();resolveWait(\''+p.id+'\')">It arrived</button>':(p.parked?'<button class="btn sm" onclick="event.stopPropagation();togglePark(\''+p.id+'\')">Unpark</button>':(ns?'<button class="btn sm" onclick="event.stopPropagation();openAdvance(\''+p.id+'\')">Move to '+esc(ns)+' →</button><button class="btn sm ghost" onclick="event.stopPropagation();openWait(\''+p.id+'\')">Waiting on…</button>':''));
  return '<div class="pc '+(p.quiet?'quiet':'')+(p.parked?' parked':'')+'" style="--gc:'+g.color+'" onclick="openP(\''+p.id+'\')"><div class="top"><div class="t">'+esc(p.name)+'</div>'+tbadge(p)+'</div><div>'+sbar(p)+'<div class="stage-line">'+line+'</div></div><div class="nx">'+nx+'</div><div class="qa">'+qa+'</div></div>';
}

/* ---- ROADMAP ---- */
function renderRoadmap(){
  var g=S.filterGroup==='all'?null:G(S.filterGroup);
  var ps=S.projects.filter(function(p){return (!g||p.group===g.id)&&!p.quiet});
  var by=function(h){return ps.filter(function(p){return (p.when||'later')===h&&!(isLast(p))})};
  var finished=ps.filter(function(p){return isLast(p)});
  var counts=HZ.map(function(h){return by(h[0]).length});
  var col=function(h,i){var list=by(h[0]);var groupsHere=S.groups.filter(function(gg){return list.some(function(p){return p.group===gg.id})});
    return '<div class="hz"><div class="hz-h"><i style="background:'+h[3]+'"></i><span class="n">'+h[1]+'</span><span class="c">'+list.length+'</span><span class="d">'+h[2]+'</span></div>'+(list.length?groupsHere.map(function(gg){return (g?'':'<div class="grp-lbl"><i style="background:'+gg.color+'"></i>'+esc(gg.name)+'</div>')+list.filter(function(p){return p.group===gg.id}).map(function(p){return rcard(p,i)}).join('')}).join(''):'<div class="empty">Nothing here.</div>')+'</div>'};
  return '<div class="view wide"><div class="hd"><div><h1>Roadmap'+(g?' · '+esc(g.name):'')+'</h1><div class="sub">What comes first, what comes after. Hover a card to move it. No dates, no dragging, just order.</div></div><div class="r"><button class="btn" onclick="openShare(\'rm\')">Share roadmap</button><button class="btn p" onclick="openNew(\''+(g?g.id:'')+'\')">New project</button></div></div>'+
  '<div class="chips"><span class="chip '+(!g?'on':'')+'" onclick="S.filterGroup=\'all\';render()">All groups</span>'+S.groups.map(function(gg){return '<span class="chip '+(g&&g.id===gg.id?'on':'')+'" onclick="S.filterGroup=\''+gg.id+'\';render()"><i style="background:'+gg.color+'"></i>'+esc(gg.name)+'</span>'}).join('')+(g&&g.priv?'<span class="badge pk" style="margin-left:6px">private · never shared</span>':'')+'</div>'+
  '<div class="rm-sum">'+HZ.map(function(h,i){return '<div class="rm-k"><span class="sw" style="background:'+h[3]+'"></span><span class="n">'+counts[i]+'</span><span class="l"><b>'+h[1]+'</b>'+h[2]+'</span></div>'}).join('')+'</div>'+
  '<div class="horizons">'+HZ.map(col).join('')+'</div>'+
  (finished.length?'<div class="sec" style="margin-top:22px"><div class="sec-t"><h2>'+secIcon('rel')+'Finished</h2><span class="help">shipped or closed, kept for the record</span></div><div class="box">'+finished.map(function(p){return '<div class="row click" onclick="openP(\''+p.id+'\')"><span class="dotc" style="background:'+G(p.group).color+'"></span><div class="grow"><div class="t">'+esc(p.name)+'</div><div class="m">'+esc(G(p.group).name)+' · '+(p.releases.length?'latest '+esc(p.releases[p.releases.length-1].v)+' · '+fmt(p.releases[p.releases.length-1].at):esc(stageName(p)))+'</div></div><span class="badge s">Finished</span></div>'}).join('')+'</div></div>':'')+'</div>';
}
function rcard(p,hi){var g=G(p.group);var left=hi>0?'<button onclick="event.stopPropagation();setWhen(\''+p.id+'\',\''+HZ[hi-1][0]+'\')">← '+HZ[hi-1][1]+'</button>':'';var right=hi<3?'<button onclick="event.stopPropagation();setWhen(\''+p.id+'\',\''+HZ[hi+1][0]+'\')">'+HZ[hi+1][1]+' →</button>':'';
  return '<div class="rc" style="--gc:'+g.color+'" onclick="openP(\''+p.id+'\')"><div class="t"><span class="dotc" style="background:'+g.color+'"></span>'+esc(p.name)+(p.wait?'<span class="badge w" style="margin-left:auto">waiting</span>':'')+'</div><div class="m">'+esc(stageName(p))+' · stage '+(p.stage+1)+' of '+T(p.type).stages.length+(p.next?' · '+esc(p.next):'')+'</div><div class="sb2">'+sbar(p)+'</div><div class="mv">'+left+right+'</div></div>'}
function setWhen(id,w){var p=Pr(id);p.when=w;p.lastAct=NOW;render();toast('<b>'+esc(p.name)+'</b> → '+HZ.find(function(h){return h[0]===w})[1])}

/* ---- PROJECT PAGE ---- */
function renderProject(){
  var p=Pr(S.projectId);if(!p)return renderProjects();var t=T(p.type),g=G(p.group),st=stageName(p),ex=t.check[st]||[],ns=nextStage(p);
  var head='<div class="view" style="--gc:'+g.color+'"><div class="crumb"><a onclick="go(\'projects\')">Projects</a> / <a onclick="S.filterGroup=\''+g.id+'\';go(\'projects\')">'+esc(g.name)+'</a></div>'+
  '<div class="ph"><div class="sq">'+esc(ini(p.name))+'</div><div><h1>'+esc(p.name)+'</h1><div class="m">'+tbadge(p)+'<span class="badge g">'+(p.pub?'Can be shared':'Private')+'</span><span class="badge g">'+esc(hzLabel(p.when))+'</span>'+p.links.map(function(u){return '<a onclick="openLink('+jsq(u)+')">'+esc(u)+'</a>'}).join('')+'<a onclick="addLink(\''+p.id+'\')">+ link</a></div></div>'+
  '<div class="r"><button class="btn" onclick="openShare(\''+p.id+'\')">Share</button><button class="btn ghost" onclick="togglePark(\''+p.id+'\')">'+(p.parked?'Unpark':'Park')+'</button>'+(p.wait?'<button class="btn" onclick="resolveWait(\''+p.id+'\')">It arrived</button>':'<button class="btn" onclick="openWait(\''+p.id+'\')">Waiting on…</button>')+(ns?'<button class="btn p" onclick="openAdvance(\''+p.id+'\')">Move to '+esc(ns)+' →</button>':'<button class="btn" disabled>Finished</button>')+'</div></div>'+
  (p.wait?'<div class="box waitbar"><span class="waitdot"></span><span>Waiting on <b>'+esc(p.wait.what)+'</b> for '+days(p.wait.since)+' days</span><span style="margin-left:auto"><button class="btn sm" onclick="resolveWait(\''+p.id+'\')">It arrived</button></span></div>':'')+
  '<div class="stages">'+t.stages.map(function(s,i){return '<div class="st '+(i<p.stage?'done':(i===p.stage?'cur':''))+'" onclick="jumpStage(\''+p.id+'\','+i+')"><b>'+esc(s)+'</b><small>'+(i===p.stage?'you are here · '+days(p.enteredAt)+' days':(i<p.stage?'done':'later'))+'</small></div>'}).join('')+'</div>'+
  '<div class="tabs"><button class="'+(S.ptab==='work'?'on':'')+'" onclick="S.ptab=\'work\';render()">Work</button><button class="'+(S.ptab==='rm'?'on':'')+'" onclick="S.ptab=\'rm\';render()">Roadmap</button><button class="'+(S.ptab==='rec'?'on':'')+'" onclick="S.ptab=\'rec\';render()">Record</button></div>';
  if(S.ptab==='rm')return head+renderProjectRoadmap(p)+'</div>';
  if(S.ptab==='rec')return head+renderProjectRecord(p)+'</div>';
  var items=p.items.slice().sort(function(a,b){return (a.done?1:0)-(b.done?1:0)}).map(function(x){return '<div class="check '+(x.done?'ok':'')+'" onclick="toggleItem(\''+p.id+'\',\''+x.id+'\')"><div class="bx"></div><span class="t">'+esc(x.text)+'</span>'+(x.tag?'<span class="tg '+x.tag+'">'+(x.tag==='exp'?'part of this stage':'bug')+'</span>':'')+'<span class="x" onclick="event.stopPropagation();delItem(\''+p.id+'\',\''+x.id+'\')">✕</span></div>'}).join('');
  ex.forEach(function(e){if(!p.items.find(function(x){return x.text===e})){items='<div class="check" onclick="addExpected(\''+p.id+'\',\''+esc(e)+'\')"><div class="bx" style="border-style:dashed"></div><span class="t" style="color:var(--ink-3)">'+esc(e)+'</span><span class="tg exp">suggested for this stage</span></div>'+items}});
  return head+'<div class="two"><div>'+
  (p.origin?'<div class="box" style="padding:10px 14px;margin-bottom:14px;border-left:3px solid var(--gc)"><div style="font-size:11px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:var(--gc)">Started as an idea</div><div style="margin-top:3px">"'+esc(p.origin)+'"</div></div>':'')+
  '<div class="sec"><div class="sec-t"><h2>'+secIcon('next')+'Next step</h2></div><div class="box nextin"><input type="text" value="'+esc(p.next)+'" placeholder="The one thing that moves this forward" onchange="Pr(\''+p.id+'\').next=this.value;scheduleSave();toast(\'Next step saved\')"></div></div>'+
  '<div class="sec"><div class="sec-t"><h2>'+secIcon('dec')+esc(st)+' checklist</h2><span class="help">what this stage usually needs, plus anything you add</span><a class="rt" onclick="go(\'settings\')">edit the '+esc(t.name)+' template</a></div><div class="box">'+items+'<div class="check add"><div class="bx"></div><input placeholder="Add to the checklist… (start with ! for a bug)" onkeydown="if(event.key===\'Enter\'){addItem(\''+p.id+'\',this.value);this.value=\'\'}"><kbd>↵</kbd></div></div></div>'+
  '<div class="sec"><div class="sec-t"><h2>Notes</h2><span class="help">click to write · saves as you type</span></div><div class="box"><div class="notes-ed" contenteditable="true" oninput="Pr(\''+p.id+'\').notes=this.innerText;scheduleSave()">'+(esc(p.notes)||'<span style="color:var(--ink-3)">Talking points, the demo order, the sentence that matters.</span>')+'</div></div></div>'+
  '</div><aside class="rail">'+
  '<div><div class="sec-t"><h2>'+secIcon('ppl')+'People</h2><a class="rt" onclick="addPerson(\''+p.id+'\')">+ add</a></div><div class="box">'+(p.people.length?'<div class="people">'+p.people.map(function(x){return '<span class="pp"><span class="av">'+esc(ini(x.n))+'</span>'+esc(x.n)+'<small>'+esc(x.r)+'</small></span>'}).join('')+'</div>':'<div class="empty" style="padding:14px">Nobody yet. Reviewers, clients, collaborators.</div>')+'</div></div>'+
  '<div><div class="sec-t"><h2>'+secIcon('file')+'Files</h2><a class="rt" onclick="addFile(\''+p.id+'\')">+ add</a></div><div class="box">'+(p.files.length?p.files.map(function(f){return '<div class="file" onclick="openStored('+jsq(f.stored_path||'')+')"><span class="ic '+esc(f.type)+'">'+esc(f.type)+'</span><div>'+esc(f.name)+'<div class="m">'+esc(f.meta)+'</div></div></div>'}).join(''):'<div class="empty" style="padding:14px">Specs, mockups, exports, assets.</div>')+'</div></div>'+
  '<div><div class="sec-t"><h2>'+secIcon('rel')+'Releases</h2><a class="rt" onclick="addRelease(\''+p.id+'\')">+ add</a></div><div class="box">'+(p.releases.length?p.releases.slice().reverse().map(function(r){return '<div class="rel"><span class="v">'+esc(r.v)+'</span><span>'+esc(r.note)+'</span><span class="m">'+fmt(r.at)+'</span></div>'}).join(''):'<div class="empty" style="padding:14px">Nothing released yet.</div>')+'</div></div>'+
  '</aside></div>';
}
function renderProjectRoadmap(p){
  var t=T(p.type),g=G(p.group);
  var hist=function(s){return p.hist.find(function(h){return h.stage===s})};
  var rows=t.stages.map(function(s,i){var h=hist(s);var cls=i<p.stage?'done':(i===p.stage?'cur':'future');
    var body='';
    if(i<p.stage){body='<div class="bd">'+(h?fmt(h.from)+' → '+fmt(h.to)+' · '+Math.max(1,Math.round((h.to-h.from)/DAY))+' days':'')+p.releases.filter(function(r){return h&&r.at>=h.from&&r.at<=new Date(h.to.getTime()+DAY)}).map(function(r){return '<div><span class="rel">'+esc(r.v)+' · '+esc(r.note)+'</span></div>'}).join('')+'</div>'}
    else if(i===p.stage){var open=p.items.filter(function(x){return !x.done}),done=p.items.filter(function(x){return x.done});body='<div class="bd">since '+fmt(p.enteredAt)+' · '+days(p.enteredAt)+' days'+(p.next?'<div style="margin-top:6px"><b style="color:var(--ink)">Next:</b> '+esc(p.next)+'</div>':'')+'<div style="margin-top:6px">'+open.map(function(x){return '<div class="it"><span class="ck"></span>'+esc(x.text)+'</div>'}).join('')+done.map(function(x){return '<div class="it ok"><span class="ck"></span>'+esc(x.text)+'</div>'}).join('')+'</div></div>'}
    else{var ex=t.check[s]||[];body='<div class="bd" style="color:var(--ink-3)">'+(ex.length?'Will need: '+ex.map(esc).join(' · '):'Nothing preset. Add expectations in Settings.')+'</div>'}
    return '<div class="tl-s '+cls+'"><div class="nd">'+(i<p.stage?'✓':(i+1))+'</div><div><div class="h"><b>'+esc(s)+'</b><span>'+(i<p.stage?'done':(i===p.stage?'you are here':'later'))+'</span></div>'+body+'</div></div>'});
  return '<div class="two" style="--gc:'+g.color+'"><div><div class="sec-t" style="margin-top:4px"><h2>'+secIcon('rm')+'Where this project has been, and where it\'s going</h2></div><div class="box" style="padding:18px 18px 4px"><div class="tl">'+rows.join('')+'</div></div></div>'+
  '<aside class="rail"><div><div class="sec-t"><h2>On the roadmap</h2></div><div class="box" style="padding:12px 14px"><div style="font-size:12.5px;color:var(--ink-2);margin-bottom:8px">Which horizon this sits in on the '+esc(g.name)+' roadmap.</div><div style="display:flex;gap:6px;flex-wrap:wrap">'+HZ.map(function(h){return '<span class="chip '+((p.when||'later')===h[0]?'on':'')+'" onclick="setWhen(\''+p.id+'\',\''+h[0]+'\')">'+h[1]+'</span>'}).join('')+'</div></div></div>'+
  '<div><div class="sec-t"><h2>'+secIcon('rel')+'Releases</h2><a class="rt" onclick="addRelease(\''+p.id+'\')">+ add</a></div><div class="box">'+(p.releases.length?p.releases.slice().reverse().map(function(r){return '<div class="rel"><span class="v">'+esc(r.v)+'</span><span>'+esc(r.note)+'</span><span class="m">'+fmt(r.at)+'</span></div>'}).join(''):'<div class="empty" style="padding:14px">Nothing released yet.</div>')+'</div></div></aside></div>';
}
function renderProjectRecord(p){
  var g=G(p.group);var acts=S.activity.filter(function(a){return a.pid===p.id});
  return '<div class="two" style="--gc:'+g.color+'"><div><div class="sec-t" style="margin-top:4px"><h2>'+secIcon('dec')+'Decisions</h2><span class="help">numbered, dated, permanent</span><a class="rt" onclick="openDec(\''+p.id+'\')">+ record one</a></div><div class="box">'+(p.decisions.length?p.decisions.slice().sort(function(a,b){return b.no-a.no}).map(function(x){return '<div class="dec '+(x.superseded?'sup':'')+'"><b>'+dno(x.no)+'</b><span>'+esc(x.text)+(x.supersedes?' <i style="color:var(--ink-3)">replaces '+dno(x.supersedes)+'</i>':'')+'</span><span class="sd">'+fmt(x.at)+'</span></div>'}).join(''):'<div class="empty"><b>No decisions yet</b>Record one and it gets a number you can refer back to.</div>')+'</div>'+
  '<div class="sec-t" style="margin-top:22px"><h2>Past waits</h2></div><div class="box">'+(p.waitHist.length?p.waitHist.map(function(w){return '<div class="row"><div class="grow"><div class="t">'+esc(w.what)+'</div><div class="m">took '+w.days+' days</div></div></div>'}).join(''):'<div class="empty">Nothing recorded yet.</div>')+'</div></div>'+
  '<aside class="rail"><div><div class="sec-t"><h2>History</h2></div><div class="box">'+(acts.length?acts.map(function(a){return '<div class="row"><span class="dotc" style="background:'+g.color+'"></span><div class="grow"><div class="t" style="font-weight:400">'+esc(a.text)+'</div><div class="m">'+ago(a.at)+' ago</div></div></div>'}).join(''):'<div class="empty">Nothing yet.</div>')+'</div></div></aside></div>';
}

/* ---- WEEK ---- */
function renderWeek(){
  var pub=S.publicOnly;var gs=S.groups.filter(function(g){return !pub||!g.priv});var ids=gs.map(function(g){return g.id});
  var week=S.activity.filter(function(a){return days(a.at)<=7&&ids.indexOf(a.group)>=0});var k=function(x){return week.filter(function(a){return a.kind===x})};
  var waiting=S.projects.filter(function(p){return p.wait&&ids.indexOf(p.group)>=0});var next=S.projects.filter(function(p){return !p.wait&&!p.quiet&&!p.parked&&p.next&&ids.indexOf(p.group)>=0}).slice(0,4);
  var li=function(a){return '<li><i style="background:'+G(a.group).color+'"></i>'+esc(a.text)+'<span class="who">'+esc(G(a.group).name)+'</span></li>'};
  var sec=function(t,arr,alt){return '<h4>'+t+'</h4><ul>'+(arr.length?arr.map(li).join(''):'<div class="none">'+alt+'</div>')+'</ul>'};
  return '<div class="view"><div class="hd"><div><h1>Your week</h1><div class="sub">Written for you from what actually happened. Nothing is made up. Edit it, then share it.</div></div><div class="r"><button class="btn" onclick="S.publicOnly=!S.publicOnly;render()">'+(pub?'Hiding private groups ✓':'Including private groups')+'</button><button class="btn p" onclick="savePdfWeek()">Save as PDF</button></div></div>'+
  '<div class="sheet"><div class="top"><div><div class="o">'+esc(S.org)+'</div><div class="w">Week of '+weekOf()+'</div></div><div class="w">'+(pub?(S.groups.length-gs.length)+' private groups left out':'includes private groups')+'</div></div>'+
  '<div class="kpis"><div class="kpi" style="--kc:var(--green)"><div class="l">Shipped</div><div class="v">'+k('ship').length+'</div></div><div class="kpi" style="--kc:var(--blue)"><div class="l">Moved forward</div><div class="v">'+k('move').length+'</div></div><div class="kpi" style="--kc:var(--teal)"><div class="l">Decisions made</div><div class="v">'+k('decision').length+'</div></div><div class="kpi" style="--kc:var(--amber)"><div class="l">Waiting on others</div><div class="v">'+waiting.length+'</div></div></div>'+
  sec('Shipped',k('ship'),'Nothing shipped this week.')+sec('Moved forward',k('move'),'No stage changes this week.')+sec('Decided',k('decision'),'No decisions recorded this week.')+
  '<h4>Waiting on</h4><ul>'+(waiting.length?waiting.map(function(p){return '<li><i style="background:'+G(p.group).color+'"></i>'+esc(p.wait.what)+'<span class="who">'+days(p.wait.since)+' days</span></li>'}).join(''):'<div class="none">Nothing is waiting on anyone else.</div>')+'</ul>'+
  '<h4>Next week</h4><ul>'+(next.length?next.map(function(p){return '<li><i style="background:'+G(p.group).color+'"></i>'+esc(p.next)+'<span class="who">'+esc(p.name)+'</span></li>'}).join(''):'<div class="none">No next steps set.</div>')+'</ul>'+
  '<div class="ft"><span>Made by Dig from stage changes, decisions, releases, and waits.</span><span>If nothing moved, it says so.</span></div></div></div>';
}

/* ---- IDEAS ---- */
function renderIdeas(){
  var list=S.ideas.slice().sort(function(a,b){return S.ideaSort==='oldest'?a.at-b.at:b.at-a.at});if(S.filterGroup!=='all')list=list.filter(function(x){return x.group===S.filterGroup});
  return '<div class="view wide"><div class="hd"><div><h1>Ideas</h1><div class="sub">Things you might make one day. No stage, no deadline. Start one when you\'re ready.</div></div><div class="r"><button class="btn p" onclick="openCap(\'idea\')">Add an idea</button></div></div>'+
  '<div class="chips"><span class="chip '+(S.filterGroup==='all'?'on':'')+'" onclick="setGroup(\'all\')">All</span>'+S.groups.map(function(g){return '<span class="chip '+(S.filterGroup===g.id?'on':'')+'" onclick="setGroup(\''+g.id+'\')"><i style="background:'+g.color+'"></i>'+esc(g.name)+'</span>'}).join('')+'<span class="sp"></span><select onchange="S.ideaSort=this.value;render()"><option value="oldest" '+(S.ideaSort==='oldest'?'selected':'')+'>Oldest first</option><option value="newest" '+(S.ideaSort==='newest'?'selected':'')+'>Newest first</option></select></div>'+
  (list.length?'<div class="grid3">'+list.map(function(x){return '<div class="ic2"><div class="t">'+esc(x.text)+'</div><div class="d">'+esc(x.desc)+'</div><div class="m"><span>'+ago(x.at)+' ago'+(x.group?' · '+esc(G(x.group).name):'')+'</span><span class="bs"><button class="btn sm ghost" onclick="openIdea(\''+x.id+'\')">Open</button><button class="btn sm p" onclick="startIdea(\''+x.id+'\')">Start</button></span></div></div>'}).join('')+'</div>':'<div class="box empty"><b>No ideas here yet</b>Press Ctrl K and type one. That\'s all it takes.</div>')+'</div>';
}

/* ---- LIBRARY ---- */
function renderLibrary(){
  var list=S.library.filter(function(x){return S.libFilter==='all'||(S.libFilter==='unsorted'?!x.group:x.kind===S.libFilter)});
  return '<div class="view"><div class="hd"><div><h1>Library</h1><div class="sub">Links, notes, and files worth keeping. Paste a link into "Add something" and it lands here.</div></div><div class="r"><button class="btn p" onclick="openCap(\'link\')">Add a link or note</button></div></div>'+
  '<div class="chips">'+[['all','Everything'],['link','Links'],['note','Notes'],['file','Files'],['unsorted','Not in a group']].map(function(x){return '<span class="chip '+(S.libFilter===x[0]?'on':'')+'" onclick="S.libFilter=\''+x[0]+'\';render()">'+x[1]+'</span>'}).join('')+'</div>'+
  '<div class="box lib">'+(list.length?list.map(function(x){var open=x.kind==='link'?'openLink('+jsq(x.meta||x.title)+')':(x.kind==='file'?'openStored('+jsq(x.stored_path||'')+')':'');return '<div class="row'+(open?' click':'')+'"'+(open?' onclick="'+open+'"':'')+'><span class="k '+x.kind+'">'+x.kind.toUpperCase()+'</span><div class="grow"><div class="t">'+esc(x.title)+'</div><div class="m">'+esc(x.meta)+'</div></div><span class="w">'+(x.group?esc(G(x.group).name):'no group')+'<a onclick="event.stopPropagation();openSortLib(\''+x.id+'\')">'+(x.group?'move':'put in a group')+'</a></span></div>'}).join(''):'<div class="empty"><b>Nothing here yet</b>Links, notes, and files you add will show up here.</div>')+'</div></div>';
}

/* ---- SETTINGS ---- */
function renderSettings(){
  return '<div class="view"><div class="hd"><div><h1>Settings</h1><div class="sub">Change anything here and the app reshapes itself right away.</div></div></div><div class="set">'+
  '<h2>You</h2><div class="box"><div class="srow"><span style="color:var(--ink-3);width:110px">Organization</span><input type="text" value="'+esc(S.org)+'" onchange="S.org=this.value;render()"></div><div class="srow"><span style="color:var(--ink-3);width:110px">Your name</span><input type="text" value="'+esc(S.you)+'" onchange="S.you=this.value;render()"></div></div>'+
  '<h2>Groups</h2><div class="hint">Groups keep projects together and give them a color. A private group never shows up in anything you share.</div><div class="box">'+S.groups.map(function(g){return '<div class="srow"><input type="color" value="'+g.color+'" onchange="G(\''+g.id+'\').color=this.value;render()"><input type="text" value="'+esc(g.name)+'" onchange="G(\''+g.id+'\').name=this.value;render()"><span class="sp"></span><span class="tog '+(g.priv?'on':'')+'" onclick="G(\''+g.id+'\').priv=!G(\''+g.id+'\').priv;render()">'+(g.priv?'private':'shareable')+'</span><span class="del" onclick="delGroup(\''+g.id+'\')">remove</span></div>'}).join('')+'<div class="srow"><span class="act" onclick="addGroup()">+ add a group</span></div></div>'+
  '<h2>Project types and their stages</h2><div class="hint">Every project has a type. A type decides which stages it moves through and what each stage\'s checklist suggests.</div>'+
  S.types.map(function(t){return '<div class="box" style="margin-bottom:10px"><div class="srow"><input type="text" value="'+esc(t.name)+'" onchange="T(\''+t.id+'\').name=this.value;render()" style="font-weight:600"><span class="sp"></span><span style="font-size:12px;color:var(--ink-3)">'+S.projects.filter(function(p){return p.type===t.id}).length+' projects</span><span class="del" onclick="delType(\''+t.id+'\')">remove</span></div><div class="stages-ed">'+t.stages.map(function(s,i){return '<span class="stg-chip"><span style="font-family:var(--mono);font-size:10px;color:var(--ink-3)">'+(i+1)+'</span><input value="'+esc(s)+'" onchange="renameStage(\''+t.id+'\','+i+',this.value)"><span class="x" onclick="delStage(\''+t.id+'\','+i+')">✕</span></span>'}).join('')+'<span class="stg-chip add" onclick="addStage(\''+t.id+'\')">+ stage</span></div><div class="exp">'+t.stages.map(function(s){var e=t.check[s]||[];return '<div class="stg-name">'+esc(s)+' checklist suggests</div>'+e.map(function(x,ei){return '<div class="e"><span>· '+esc(x)+'</span><span class="x" onclick="delExp(\''+t.id+'\',\''+esc(s)+'\','+ei+')">remove</span></div>'}).join('')+'<div class="e"><input placeholder="Add something the '+esc(s)+' stage usually needs…" onkeydown="if(event.key===\'Enter\'){addExp(\''+t.id+'\',\''+esc(s)+'\',this.value);this.value=\'\'}"></div>'}).join('')+'</div></div>'}).join('')+
  '<div class="box"><div class="srow"><span class="act" onclick="addType()">+ add a type</span></div></div>'+
  '<h2>Appearance</h2><div class="box"><div class="srow"><span style="width:110px;color:var(--ink-3)">Theme</span><div class="theme">'+['light','dark','system'].map(function(m){return '<button class="'+(S.theme===m?'on':'')+'" onclick="setTheme(\''+m+'\')">'+(m==='system'?'Follow system':m[0].toUpperCase()+m.slice(1))+'</button>'}).join('')+'</div></div><div class="srow"><span style="width:110px;color:var(--ink-3)">Motion</span><span>Follows your system\'s reduce-motion setting.</span></div></div>'+
  '<h2>Your data</h2><div class="box"><div class="srow"><span style="width:110px;color:var(--ink-3)">Where it lives</span><span style="font-family:var(--mono);font-size:12px">'+esc(DATA_PATH)+'</span><span class="sp"></span><span class="act" onclick="openDataFolder()">Open folder</span></div><div class="srow"><span style="width:110px;color:var(--ink-3)">Backup</span><span>Export everything as one file, or bring one back in.</span><span class="sp"></span><span class="act" onclick="exportData()">Export</span><span class="act" onclick="importData()">Import</span></div><div class="srow"><span style="width:110px;color:var(--ink-3)">Internet</span><span>Never used. Dig makes no network calls.</span></div><div class="srow"><span style="width:110px;color:var(--ink-3)">License</span><span>Free and open source, AGPLv3 · <a style="color:var(--blue);cursor:pointer" onclick="toast(\'About dialog lives here in the real app\')">About Dig</a></span></div></div>'+
  '</div></div>';
}
function exportData(){
  if(!BRIDGE){toast('Exporting needs the app.');return}
  flushSave();
  BRIDGE.exportJson(JSON.stringify(persist()),function(json){
    var r=JSON.parse(json);
    if(!r.ok){if(r.reason&&r.reason!=='cancelled')toast(esc(r.reason));return}
    toast('Exported to <b>'+esc(r.name)+'</b>');
  });
}
var PENDING_IMPORT=null;
function importData(){
  if(!BRIDGE){toast('Importing needs the app.');return}
  BRIDGE.importJson(function(json){
    var r=JSON.parse(json);
    if(!r.ok){if(r.reason&&r.reason!=='cancelled')toast(esc(r.reason));return}
    PENDING_IMPORT=r.state;
    dlg('<div class="dh2"><h3>Bring this file in?</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body"><div style="font-size:15px;font-weight:500;margin-bottom:4px">'+esc(r.name)+'</div><div class="warn">This replaces everything Dig is holding right now: '+S.projects.length+' projects, '+S.ideas.length+' ideas, '+S.library.length+' in the library.</div><div class="ok">That file holds '+r.counts.projects+' projects, '+r.counts.ideas+' ideas, and '+r.counts.library+' in the library.</div><div class="helper">What is here now stays in the recovery history either way.</div></div><div class="foot"><button class="btn" onclick="PENDING_IMPORT=null;closeOv()">Cancel</button><button class="btn p" onclick="doImport()">Replace everything</button></div>');
  });
}
function doImport(){
  if(!PENDING_IMPORT)return;
  S=adopt(PENDING_IMPORT);PENDING_IMPORT=null;
  pickResurf();closeOv();go('home');flushSave();
  toast('Brought it in. Everything here is from that file now.');
}

/* ---- SETUP ---- */
function renderSetup(){
  var w=S.setupWork;var opts=[['apps','Apps or software','Things you build and release'],['clients','Client work','Projects you do for other people'],['content','Content','Videos, writing, a podcast, a channel'],['personal','Personal projects','Home, finances, things for yourself'],['programs','Programs or events','Ongoing efforts, campaigns, a gala']];
  return '<div class="view"><div class="setup"><div class="eyebrow">Welcome</div><h1>Dig keeps every project you\'re working on in one place.</h1><p class="lede">What stage each one is at, what its next step is, and what you decided along the way. Ideas wait until you start them. Everything stays on this computer.</p>'+
  '<label>What should we call this?</label><input type="text" value="'+esc(S.org)+'" placeholder="Your name, or your company" onchange="S.org=this.value">'+
  '<label>What kinds of things do you work on?</label><div class="pick">'+opts.map(function(o){return '<div class="pk '+(w[o[0]]?'on':'')+'" onclick="S.setupWork.'+o[0]+'=!S.setupWork.'+o[0]+';render()"><div class="bx"></div><div><div class="h">'+o[1]+'</div><div class="p">'+o[2]+'</div></div></div>'}).join('')+'</div>'+
  '<div class="setup-foot"><div class="note">This picks sensible groups, project types, and stages for you. Change every one of them later in Settings.</div><button class="btn p" onclick="finishSetup()">Let\'s go →</button></div></div></div>';
}

/* ---- OVERLAYS ---- */
function renderOverlays(){
  var popts='<option value="">Inbox (decide later)</option>'+S.projects.filter(function(p){return !p.parked}).map(function(p){return '<option value="'+p.id+'" '+(S.capProject===p.id?'selected':'')+'>'+esc(p.name)+'</option>'}).join('');
  var types=[['auto','Let Dig guess'],['idea','Idea'],['todo','To-do'],['bug','Bug'],['note','Note'],['link','Link'],['decision','Decision']];
  return '<div class="overlay" id="ov-cap" onclick="if(event.target===this)closeOv()"><div class="dlg"><input class="cap-in" id="cap-in" placeholder="Type anything. An idea, a to-do, a bug, a note, a link…" oninput="capDetect()" onkeydown="if(event.key===\'Enter\')doCapture()"><div class="types" id="cap-types">'+types.map(function(t){return '<span class="ty '+(t[0]==='auto'?'auto':'')+' '+(S.capType===t[0]?'on':'')+'" data-t="'+t[0]+'" onclick="S.capType=\''+t[0]+'\';capDetect()">'+t[1]+'</span>'}).join('')+'</div><div class="cap-row"><span>Put it in</span><select id="cap-p" onchange="S.capProject=this.value;capDetect()">'+popts+'</select><span id="cap-as" style="color:var(--ink-3)"></span><span class="hint"><kbd>↵</kbd> save <kbd>Esc</kbd> close</span></div></div></div>'+
  '<div class="overlay" id="ov-pal" onclick="if(event.target===this)closeOv()"><div class="dlg"><input class="cap-in" id="pal-in" placeholder="Find a project, idea, link, note, or decision…" oninput="palFilter(this.value)" onkeydown="palKey(event)"><div class="pal-list" id="pal-list"></div></div></div>'+
  '<div class="overlay" id="ov-dlg" onclick="if(event.target===this)closeOv()"><div class="dlg" id="dlg-body"></div></div>';
}
function dlg(html){document.getElementById('dlg-body').innerHTML=html;document.getElementById('ov-dlg').classList.add('open');var f=document.querySelector('#dlg-body input[type=text],#dlg-body textarea,#dlg-body select');if(f)setTimeout(function(){f.focus()},10)}
function closeOv(){document.querySelectorAll('.overlay').forEach(function(o){o.classList.remove('open')})}
function openKeys(){dlg('<div class="dh2"><h3>Keyboard shortcuts</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body"><div class="keys"><div><span>Add something</span><kbd>Ctrl K</kbd></div><div><span>Find anything</span><kbd>/</kbd></div><div><span>Home</span><kbd>1</kbd></div><div><span>Projects</span><kbd>2</kbd></div><div><span>Roadmap</span><kbd>3</kbd></div><div><span>Ideas</span><kbd>4</kbd></div><div><span>Library</span><kbd>5</kbd></div><div><span>Your week</span><kbd>6</kbd></div><div><span>Close anything</span><kbd>Esc</kbd></div><div><span>This card</span><kbd>?</kbd></div></div></div><div class="foot"><button class="btn p" onclick="closeOv()">Got it</button></div>')}

/* ======================= ACTIONS ======================= */
function go(v){S.view=v;render()}
function openP(id){S.projectId=id;S.view='project';render()}
function setGroup(id){S.filterGroup=id;if(S.view==='home'||S.view==='project'||S.view==='settings')S.view='projects';render()}
function setTheme(m){S.theme=m;render()}
function togglePark(id){var p=Pr(id);p.parked=!p.parked;if(p.parked){p.when='someday';p.wait=null}p.lastAct=NOW;render();toast(p.parked?'<b>'+esc(p.name)+'</b> is parked. It stays out of Home and the roadmap until you unpark it.':'<b>'+esc(p.name)+'</b> is back.')}
/* capture */
function openCap(type){S.capType=type||'auto';S.capProject='';render();document.getElementById('ov-cap').classList.add('open');var i=document.getElementById('cap-in');i.value='';capDetect();setTimeout(function(){i.focus()},10)}
function guessType(t){t=t.trim();if(/^https?:\/\//i.test(t)||/^[a-z0-9.-]+\.[a-z]{2,}(\/|$)/i.test(t))return 'link';if(/^!/.test(t)||/\b(bug|broken|crash|wrong|doesn't work|stale)\b/i.test(t))return 'bug';if(/^(fix|add|write|ship|call|send|update|check|make|finish)\b/i.test(t))return 'todo';return 'idea'}
function effType(){var raw=document.getElementById('cap-in').value;return S.capType==='auto'?guessType(raw):S.capType}
function capDetect(){var raw=document.getElementById('cap-in').value;var k=effType();document.querySelectorAll('#cap-types .ty').forEach(function(s){s.classList.toggle('on',s.dataset.t===S.capType)});var p=S.capProject?Pr(S.capProject):null;var as=document.getElementById('cap-as');var where=(k==='link'||k==='note')?'the Library':(k==='idea'&&!p?'Ideas':(p?p.name:'your inbox'));as.textContent=raw.trim()?('Saving as '+(S.capType==='auto'?'a '+k+' (guessed)':'a '+k)+' → '+where):''}
function doCapture(){var raw=document.getElementById('cap-in').value.trim();if(!raw)return;var k=effType();var text=raw.replace(/^!\s*/,'');var p=S.capProject?Pr(S.capProject):null;
  if(p&&(k==='todo'||k==='bug'||k==='idea')){p.items.unshift({id:uid(),text:text,done:false,tag:k==='bug'?'bug':''});p.lastAct=NOW;toast('Added to <b>'+esc(p.name)+'</b>\'s checklist')}
  else if(p&&k==='decision'){recordDecision(p.id,text,null)}
  else if(p&&(k==='note'||k==='link')){S.library.unshift({id:uid(),kind:k,title:text,meta:k==='link'?raw:'',group:p.group});toast('Saved to the Library under '+esc(G(p.group).name))}
  else if(k==='link'||k==='note'){S.library.unshift({id:uid(),kind:k,title:text,meta:k==='link'?raw:'',group:''});toast('Saved to the Library')}
  else if(k==='idea'){S.ideas.unshift({id:uid(),text:text,desc:'',at:NOW,opened:null,group:''});toast('Idea saved. It\'s in Ideas whenever you want it.')}
  else{S.inbox.unshift({id:uid(),text:text,type:k,at:NOW,guess:null});toast('Saved to your inbox. Put it somewhere when you\'re ready.')}
  closeOv();render()}
/* palette */
function openPal(){document.getElementById('ov-pal').classList.add('open');var i=document.getElementById('pal-in');i.value='';palFilter('');setTimeout(function(){i.focus()},10)}
var palIdx=0;
function palItems(q){q=q.toLowerCase();var out=[];S.projects.forEach(function(p){if(!q||p.name.toLowerCase().indexOf(q)>=0)out.push({k:'project',t:p.name,m:stageName(p)+' · '+G(p.group).name,go:"openP('"+p.id+"')"})});S.ideas.forEach(function(x){if(!q||x.text.toLowerCase().indexOf(q)>=0)out.push({k:'idea',t:x.text,m:ago(x.at)+' ago',go:"openIdea('"+x.id+"')"})});S.library.forEach(function(x){if(!q||x.title.toLowerCase().indexOf(q)>=0)out.push({k:x.kind,t:x.title,m:x.group?G(x.group).name:'',go:"go('library')"})});S.projects.forEach(function(p){p.decisions.forEach(function(x){if(q&&x.text.toLowerCase().indexOf(q)>=0)out.push({k:'decision',t:dno(x.no)+' '+x.text,m:p.name,go:"openP('"+p.id+"')"})})});return out.slice(0,12)}
function palFilter(q){palIdx=0;var it=palItems(q);document.getElementById('pal-list').innerHTML=it.length?it.map(function(x,i){return '<div class="pal-it '+(i===0?'hl':'')+'" onclick="closeOv();'+x.go+'"><span class="k">'+x.k+'</span><span>'+esc(x.t)+'</span><span class="m">'+esc(x.m)+'</span></div>'}).join(''):'<div class="empty">Nothing matches.</div>'}
function palKey(e){var its=document.querySelectorAll('.pal-it');if(!its.length)return;if(e.key==='ArrowDown')palIdx=Math.min(its.length-1,palIdx+1);else if(e.key==='ArrowUp')palIdx=Math.max(0,palIdx-1);else if(e.key==='Enter'){its[palIdx].click();return}else return;its.forEach(function(x,i){x.classList.toggle('hl',i===palIdx)});e.preventDefault()}
/* inbox */
function openSort(id){var u=S.inbox.find(function(x){return x.id===id});if(!u)return;dlg('<div class="dh2"><h3>Where should this go?</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body"><div style="font-size:15px;font-weight:500;margin-bottom:10px">'+esc(u.text)+'</div><label>It is</label><select id="s-kind"><option value="idea" '+(u.type==='idea'?'selected':'')+'>An idea for something new</option><option value="todo">A to-do on a project</option><option value="bug" '+(u.type==='bug'?'selected':'')+'>A bug on a project</option><option value="link" '+(u.type==='link'?'selected':'')+'>A link to keep</option><option value="note">A note to keep</option></select><div class="row2"><div><label>Project</label><select id="s-p"><option value="">None</option>'+S.projects.map(function(p){return '<option value="'+p.id+'" '+(u.guess===p.id?'selected':'')+'>'+esc(p.name)+'</option>'}).join('')+'</select></div><div><label>Group</label><select id="s-g"><option value="">None</option>'+S.groups.map(function(g){return '<option value="'+g.id+'">'+esc(g.name)+'</option>'}).join('')+'</select></div></div></div><div class="foot"><button class="btn ghost" onclick="delInbox(\''+id+'\')">Throw it away</button><span class="l"></span><button class="btn" onclick="closeOv()">Later</button><button class="btn p" onclick="doSort(\''+id+'\')">Put it there</button></div>')}
function doSort(id){var u=S.inbox.find(function(x){return x.id===id});var k=document.getElementById('s-kind').value,pid=document.getElementById('s-p').value,gid=document.getElementById('s-g').value;var p=pid?Pr(pid):null;
  if((k==='todo'||k==='bug')&&p){p.items.unshift({id:uid(),text:u.text,done:false,tag:k==='bug'?'bug':''});p.lastAct=NOW}else if(k==='link'||k==='note'){S.library.unshift({id:uid(),kind:k,title:u.text,meta:'',group:gid||(p?p.group:'')})}else{S.ideas.unshift({id:uid(),text:u.text,desc:'',at:u.at,opened:null,group:gid||''})}
  S.inbox=S.inbox.filter(function(x){return x.id!==id});closeOv();toast('Done');render()}
function delInbox(id){S.inbox=S.inbox.filter(function(x){return x.id!==id});closeOv();render();toast('Thrown away')}
function openSortLib(id){var x=S.library.find(function(y){return y.id===id});dlg('<div class="dh2"><h3>Which group?</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body"><div style="font-weight:500;margin-bottom:8px">'+esc(x.title)+'</div><label>Group</label><select id="sl-g"><option value="">None</option>'+S.groups.map(function(g){return '<option value="'+g.id+'" '+(x.group===g.id?'selected':'')+'>'+esc(g.name)+'</option>'}).join('')+'</select></div><div class="foot"><button class="btn danger ghost" onclick="S.library=S.library.filter(function(y){return y.id!==\''+id+'\'});closeOv();render()">Delete</button><button class="btn p" onclick="S.library.find(function(y){return y.id===\''+id+'\'}).group=document.getElementById(\'sl-g\').value;closeOv();render();toast(\'Moved\')">Save</button></div>')}
/* ideas */
function openIdea(id){var x=S.ideas.find(function(y){return y.id===id});x.opened=NOW;scheduleSave();dlg('<div class="dh2"><h3>Idea</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body"><label>What is it?</label><input type="text" id="id-t" value="'+esc(x.text)+'"><label>Notes</label><textarea id="id-d" rows="4">'+esc(x.desc)+'</textarea><label>Group</label><select id="id-g"><option value="">None yet</option>'+S.groups.map(function(g){return '<option value="'+g.id+'" '+(x.group===g.id?'selected':'')+'>'+esc(g.name)+'</option>'}).join('')+'</select><div class="helper">Written '+ago(x.at)+' ago</div></div><div class="foot"><button class="btn danger ghost" onclick="delIdea(\''+id+'\')">Delete</button><span class="l"></span><button class="btn" onclick="saveIdea(\''+id+'\')">Save</button><button class="btn p" onclick="saveIdea(\''+id+'\',true);startIdea(\''+id+'\')">Start as a project</button></div>')}
function saveIdea(id,q){var x=S.ideas.find(function(y){return y.id===id});x.text=document.getElementById('id-t').value;x.desc=document.getElementById('id-d').value;x.group=document.getElementById('id-g').value;scheduleSave();if(!q){closeOv();render();toast('Saved')}}
function delIdea(id){S.ideas=S.ideas.filter(function(y){return y.id!==id});if(S.resurfId===id)pickResurf();closeOv();render();toast('Deleted')}
function startIdea(id){var x=S.ideas.find(function(y){return y.id===id});openNew(x.group||'',x)}
/* new project */
function openNew(gid,from){dlg('<div class="dh2"><h3>'+(from?'Start this idea as a project':'New project')+'</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body"><label>Name</label><input type="text" id="np-n" value="'+esc(from?from.text:'')+'" placeholder="What is it called?"><div class="row2"><div><label>Group</label><select id="np-g">'+S.groups.map(function(g){return '<option value="'+g.id+'" '+(gid===g.id?'selected':'')+'>'+esc(g.name)+'</option>'}).join('')+'</select></div><div><label>Type</label><select id="np-t">'+S.types.map(function(t){return '<option value="'+t.id+'">'+esc(t.name)+' · '+t.stages.join(' → ')+'</option>'}).join('')+'</select></div></div><div class="row2"><div><label>First next step</label><input type="text" id="np-x" placeholder="The first thing that moves it forward"></div><div><label>On the roadmap</label><select id="np-w">'+HZ.map(function(h){return '<option value="'+h[0]+'" '+(h[0]==='next'?'selected':'')+'>'+h[1]+'</option>'}).join('')+'</select></div></div><div class="helper">It starts at the first stage of its type. Its group decides whether it can be shared.</div></div><div class="foot"><button class="btn" onclick="closeOv()">Cancel</button><button class="btn p" onclick="createP('+(from?"'"+from.id+"'":'null')+')">Create</button></div>')}
function createP(fromId){var n=document.getElementById('np-n').value.trim();if(!n)return;var gid=document.getElementById('np-g').value,tid=document.getElementById('np-t').value;var np={id:uid(),name:n,group:gid,type:tid,stage:0,enteredAt:NOW,when:document.getElementById('np-w').value,next:document.getElementById('np-x').value,items:[],decisions:[],files:[],links:[],notes:'',pub:!G(gid).priv,wait:null,lastAct:NOW,releases:[],people:[],hist:[],quiet:false,origin:null,parked:false,waitHist:[]};if(fromId){var x=S.ideas.find(function(y){return y.id===fromId});np.origin=x.text;np.notes=x.desc;S.ideas=S.ideas.filter(function(y){return y.id!==fromId});if(S.resurfId===fromId)pickResurf()}S.projects.unshift(np);log(np,n+' started','move');closeOv();S.ptab='work';openP(np.id);toast('<b>'+esc(n)+'</b> is a project now')}
/* stages */
function openAdvance(id){var p=Pr(id),ns=nextStage(p),un=unmet(p);dlg('<div class="dh2"><h3>Move '+esc(p.name)+' to '+esc(ns)+'</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body"><div style="color:var(--ink-2)">You\'ve been in <b>'+esc(stageName(p))+'</b> for '+days(p.enteredAt)+' days.</div>'+(un.length?'<div class="warn">A few things from this stage\'s checklist aren\'t done yet:<ul>'+un.map(function(e){return '<li>'+esc(e)+'</li>'}).join('')+'</ul></div>':'<div class="ok">Everything on this stage\'s checklist is done. Nice.</div>')+'<label>Next step in '+esc(ns)+'</label><input type="text" id="adv-x" placeholder="Optional, but it helps tomorrow-you"></div><div class="foot"><button class="btn" onclick="closeOv()">Not yet</button><button class="btn p" onclick="doAdvance(\''+id+'\')">'+(un.length?'Move anyway':'Move to '+esc(ns))+'</button></div>')}
function doAdvance(id){var p=Pr(id);p.hist.push({stage:stageName(p),from:p.enteredAt,to:NOW});p.stage++;p.enteredAt=NOW;var nx=document.getElementById('adv-x').value;p.next=nx||'';var shipped=/release|ship|close|done/i.test(stageName(p));log(p,p.name+' moved to '+stageName(p),shipped?'ship':'move');if(isLast(p)){p.quiet=true;p.when='done'}closeOv();render();toast('<b>'+esc(p.name)+'</b> is now in '+esc(stageName(p))+'.',"undoAdvance('"+id+"')")}
function undoAdvance(id){var p=Pr(id);if(p.stage>0){p.stage--;var h=p.hist.pop();p.enteredAt=h?h.from:d(1);p.quiet=false;S.activity.shift();render();toast('Put back')}}
function jumpStage(id,i){var p=Pr(id);if(i===p.stage)return;if(i===p.stage+1){openAdvance(id);return}if(i>p.stage)p.hist.push({stage:stageName(p),from:p.enteredAt,to:NOW});p.stage=i;p.enteredAt=NOW;p.quiet=isLast(p);log(p,p.name+' set to '+stageName(p),'move');render();toast('Now in '+esc(stageName(p)))}
/* waiting */
function openWait(id){var p=Pr(id);dlg('<div class="dh2"><h3>What is '+esc(p.name)+' waiting on?</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body"><label>Waiting on</label><input type="text" id="w-what" placeholder="A person, a review, a delivery, an answer…"><div class="helper">Dig shows it on Home and counts the days. Nothing will nag you.</div></div><div class="foot"><button class="btn" onclick="closeOv()">Cancel</button><button class="btn p" onclick="setWait(\''+id+'\')">Mark as waiting</button></div>')}
function setWait(id){var w=document.getElementById('w-what').value.trim();if(!w)return;var p=Pr(id);p.wait={what:w,since:NOW};p.lastAct=NOW;closeOv();render();toast('Waiting on '+esc(w))}
function resolveWait(id){var p=Pr(id);if(!p.wait)return;var fin=function(){p.waitHist.unshift({what:p.wait.what,days:days(p.wait.since)});var w=p.wait.what;p.wait=null;p.lastAct=NOW;render();toast('Great, that came through: '+esc(w))};leave('wrow-'+id,fin)}
/* items */
function toggleItem(pid,iid){var p=Pr(pid),x=p.items.find(function(y){return y.id===iid});x.done=!x.done;p.lastAct=NOW;render()}
function delItem(pid,iid){var p=Pr(pid);var x=p.items.find(function(y){return y.id===iid});p.items=p.items.filter(function(y){return y.id!==iid});render();toast('Removed',"Pr('"+pid+"').items.unshift("+JSON.stringify(x).replace(/"/g,'&quot;')+");render()")}
function addItem(pid,text){text=text.trim();if(!text)return;var p=Pr(pid);var bug=text.startsWith('!');p.items.unshift({id:uid(),text:text.replace(/^!\s*/,''),done:false,tag:bug?'bug':''});p.lastAct=NOW;render();setTimeout(function(){var i=document.querySelector('.check.add input');if(i)i.focus()},0)}
function addExpected(pid,text){var p=Pr(pid);p.items.unshift({id:uid(),text:text,done:false,tag:'exp'});render()}
/* decisions */
function openDec(id){var p=Pr(id);dlg('<div class="dh2"><h3>Record a decision · '+dno(nextDecNo())+'</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body"><label>What did you decide, and why?</label><textarea id="dc-t" rows="4" placeholder="Write it so future you understands the reasoning."></textarea><label>Does this replace an earlier decision?</label><select id="dc-s"><option value="">No</option>'+p.decisions.filter(function(x){return !x.superseded}).map(function(x){return '<option value="'+x.no+'">'+dno(x.no)+' · '+esc(x.text.slice(0,50))+'</option>'}).join('')+'</select><div class="helper">Decisions get a number and a date and stay on record. Replaced ones stay visible, crossed out.</div></div><div class="foot"><button class="btn" onclick="closeOv()">Cancel</button><button class="btn p" onclick="recordDecision(\''+id+'\',document.getElementById(\'dc-t\').value,document.getElementById(\'dc-s\').value);closeOv();render()">Record it</button></div>')}
function recordDecision(pid,text,sup){text=(text||'').trim();if(!text)return;var p=Pr(pid);var no=nextDecNo();var s=sup?parseInt(sup,10):null;if(s){var old=p.decisions.find(function(x){return x.no===s});if(old)old.superseded=true}p.decisions.push({no:no,text:text,at:NOW,supersedes:s,superseded:false});log(p,p.name+': '+dno(no)+' recorded','decision');toast(dno(no)+' recorded')}
/* links, files, people, releases */
function addLink(id){dlg('<div class="dh2"><h3>Add a link</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body"><label>Address or name</label><input type="text" id="lk" placeholder="github.com/… or Google Play"></div><div class="foot"><button class="btn" onclick="closeOv()">Cancel</button><button class="btn p" onclick="var t=document.getElementById(\'lk\').value.trim();if(t){Pr(\''+id+'\').links.push(t)};closeOv();render()">Add</button></div>')}
function addFile(id){
  if(!BRIDGE){toast('Adding a file needs the app.');return}
  BRIDGE.pickFile(id,'All files (*)',function(json){
    var r=JSON.parse(json);
    if(!r.ok){if(r.reason&&r.reason!=='cancelled')toast(esc(r.reason));return}
    var p=Pr(id);if(!p)return;
    p.files.unshift({type:r.type,name:r.name,meta:r.meta,stored_path:r.stored_path});
    p.lastAct=NOW;render();toast('Kept a copy of <b>'+esc(r.name)+'</b>');
  });
}
function addPerson(id){dlg('<div class="dh2"><h3>Add a person</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body"><div class="row2"><div><label>Name</label><input type="text" id="pn" placeholder="Who"></div><div><label>Role</label><input type="text" id="pr" placeholder="reviewer, client, collaborator"></div></div><div class="helper">Just a name and a role. Dig is not a contact list.</div></div><div class="foot"><button class="btn" onclick="closeOv()">Cancel</button><button class="btn p" onclick="var n=document.getElementById(\'pn\').value.trim();if(n){Pr(\''+id+'\').people.push({n:n,r:document.getElementById(\'pr\').value})};closeOv();render()">Add</button></div>')}
function addRelease(id){dlg('<div class="dh2"><h3>Record a release</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body"><div class="row2"><div><label>Version</label><input type="text" id="rv" placeholder="1.2.0"></div><div><label>What\'s in it</label><input type="text" id="rn" placeholder="One line"></div></div><div class="helper">Dated today. Shows up on the project\'s roadmap and in Your week.</div></div><div class="foot"><button class="btn" onclick="closeOv()">Cancel</button><button class="btn p" onclick="doRelease(\''+id+'\')">Record</button></div>')}
function doRelease(id){var v=document.getElementById('rv').value.trim();if(!v)return;var p=Pr(id);p.releases.push({v:v,at:NOW,note:document.getElementById('rn').value});log(p,p.name+' '+v+' released','ship');closeOv();render();toast('<b>'+esc(p.name)+' '+esc(v)+'</b> is on the record')}
/* share */
function openShare(id){var p=id&&id!=='rm'?Pr(id):null;var pubP=S.projects.filter(function(y){return y.pub&&!G(y.group).priv});var isRm=id==='rm';dlg('<div class="dh2"><h3>'+(p?'Share '+esc(p.name):(isRm?'Share the roadmap':'Share your projects'))+'</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body"><div class="share-prev">'+(p?'<div class="h">'+esc(p.name)+'</div><div class="s">'+esc(T(p.type).name)+' · '+esc(G(p.group).name)+' · '+esc(stageName(p))+'</div><div class="row3"><div><b>'+(p.stage+1)+' of '+T(p.type).stages.length+'</b><small>stages</small></div><div><b>'+p.items.filter(function(x){return x.done}).length+'</b><small>done</small></div><div><b>'+p.releases.length+'</b><small>releases</small></div></div><div style="color:var(--ink-2)">'+(esc(p.notes)||'No notes yet.')+'</div>':'<div class="h">'+esc(S.org)+(isRm?' · Roadmap':'')+'</div><div class="s">'+pubP.length+' shareable projects · '+S.groups.filter(function(g){return g.priv}).length+' private groups left out</div><div class="row3">'+(isRm?HZ.slice(0,3).map(function(h){return '<div><b>'+pubP.filter(function(y){return (y.when||'later')===h[0]}).length+'</b><small>'+h[1]+'</small></div>'}).join(''):'<div><b>'+S.projects.filter(function(y){return !y.quiet&&!y.parked}).length+'</b><small>active</small></div><div><b>'+S.activity.filter(function(a){return a.kind==='ship'&&days(a.at)<=90}).length+'</b><small>shipped this quarter</small></div><div><b>'+S.projects.reduce(function(s,y){return s+y.decisions.length},0)+'</b><small>decisions on record</small></div>')+'</div><div style="color:var(--ink-2)">Private groups never appear here. The page says so at the bottom.</div>')+'</div></div><div class="foot"><span class="l">Saves a PDF or an image, made on this computer.</span><button class="btn" onclick="closeOv()">Close</button><button class="btn p" onclick="doShare('+(id?jsq(id):'null')+')">Save</button></div>')}
/* settings */
function addGroup(){S.groups.push({id:uid(),name:'New group',color:'#D14A7A',priv:false});render()}
function delGroup(id){if(S.projects.some(function(p){return p.group===id})){toast('Move its projects to another group first');return}S.groups=S.groups.filter(function(g){return g.id!==id});render()}
function addType(){S.types.push({id:uid(),name:'New type',stages:['Start','Middle','Done'],check:{}});render()}
function delType(id){if(S.projects.some(function(p){return p.type===id})){toast('Some projects use this type');return}S.types=S.types.filter(function(t){return t.id!==id});render()}
function renameStage(tid,i,val){var t=T(tid);var old=t.stages[i];t.stages[i]=val;if(t.check[old]){t.check[val]=t.check[old];delete t.check[old]}render()}
function delStage(tid,i){var t=T(tid);if(t.stages.length<=2){toast('A type needs at least two stages');return}var n=t.stages[i];t.stages.splice(i,1);delete t.check[n];S.projects.forEach(function(p){if(p.type===tid&&p.stage>=t.stages.length)p.stage=t.stages.length-1});render()}
function addStage(tid){T(tid).stages.push('New stage');render()}
function addExp(tid,st,val){val=val.trim();if(!val)return;var t=T(tid);(t.check[st]=t.check[st]||[]).push(val);render()}
function delExp(tid,st,i){T(tid).check[st].splice(i,1);render()}

/* ---- PDF exports ----
   Rendered by the web engine from the same classes the screen uses, always in
   the light palette, with the bundled Geist. Private groups never appear in an
   overview, and every export says what was left out. */
function pdfSafe(){return S.projects.filter(function(p){return p.pub&&!G(p.group).priv})}
function omitted(){var n=S.groups.filter(function(g){return g.priv}).length;
  return n?n+(n===1?' private group left out':' private groups left out'):'No private groups to leave out'}
function pdfTop(title,sub){return '<div class="pdf-top"><div><div class="o">'+esc(S.org||'Dig')+'</div><div class="w">'+esc(sub)+'</div></div><div class="w">'+esc(title)+'</div></div>'}
function pdfFoot(left){return '<div class="pdf-foot"><span>'+left+'</span><span>Made by Dig, on this computer.</span></div>'}
function slug(s){return String(s).toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'')||'dig'}

function savePdfWeek(){
  var el=document.querySelector('.sheet');
  if(!el){toast('Open Your week first.');return}
  sendPdf(el.outerHTML,'your-week.pdf');
}
function doShare(id){
  var body,name;
  if(id&&id!=='rm'){var p=Pr(id);if(!p)return;body=pdfProject(p);name=slug(p.name)+'.pdf'}
  else if(id==='rm'){body=pdfRoadmap();name='roadmap.pdf'}
  else{body=pdfProjects();name='projects.pdf'}
  closeOv();sendPdf(body,name);
}
function sendPdf(body,name){
  if(!BRIDGE){toast('Saving a PDF needs the app.');return}
  BRIDGE.printPdf(body,name);
}
function pdfProject(p){
  var t=T(p.type),g=G(p.group);
  var shareable=p.pub&&!g.priv;
  return '<div style="--gc:'+g.color+'"><div class="share-prev">'+
    '<div class="h">'+esc(p.name)+'</div>'+
    '<div class="s">'+esc(t.name)+' · '+esc(g.name)+' · '+esc(stageName(p))+'</div>'+
    '<div class="row3"><div><b>'+(p.stage+1)+' of '+t.stages.length+'</b><small>stages</small></div>'+
    '<div><b>'+p.items.filter(function(x){return x.done}).length+'</b><small>done</small></div>'+
    '<div><b>'+p.releases.length+'</b><small>releases</small></div></div>'+
    '<div style="margin-top:6px">'+sbar(p)+'<div class="stage-line"><span><b>'+esc(stageName(p))+'</b> · stage '+(p.stage+1)+' of '+t.stages.length+'</span><span>'+(days(p.enteredAt)?days(p.enteredAt)+' days here':'today')+'</span></div></div>'+
    (p.next?'<h2 class="pdf-h">Next step</h2><div style="color:var(--ink-2)">'+esc(p.next)+'</div>':'')+
    (p.notes?'<h2 class="pdf-h">Notes</h2><div style="color:var(--ink-2);white-space:pre-wrap">'+esc(p.notes)+'</div>':'')+
    (p.releases.length?'<h2 class="pdf-h">Releases</h2><div class="box">'+p.releases.slice().reverse().map(function(r){return '<div class="rel"><span class="v">'+esc(r.v)+'</span><span>'+esc(r.note)+'</span><span class="m">'+fmt(r.at)+'</span></div>'}).join('')+'</div>':'')+
    '</div>'+pdfFoot(shareable?'One project, shared on purpose.':'This project is in a private group. It never appears in a shared overview.')+'</div>';
}
function pdfProjects(){
  var ps=pdfSafe();
  var groups=S.groups.filter(function(g){return !g.priv&&ps.some(function(p){return p.group===g.id})});
  return pdfTop('Projects',ps.length+(ps.length===1?' shareable project':' shareable projects'))+
    (groups.length?groups.map(function(g){var list=ps.filter(function(p){return p.group===g.id});
      return '<div class="grp" style="--gc:'+g.color+'"><div class="grp-h"><span class="n"><span class="dotc" style="background:'+g.color+'"></span>'+esc(g.name)+'</span><span class="c">'+list.length+'</span></div><div class="cards">'+list.map(card).join('')+'</div></div>'}).join(''):'<div class="box empty"><b>Nothing to share yet</b>Every project you have is in a private group.</div>')+
    pdfFoot(esc(omitted())+'. Private groups never appear here.');
}
function pdfRoadmap(){
  var ps=pdfSafe().filter(function(p){return !p.quiet});
  var by=function(h){return ps.filter(function(p){return (p.when||'later')===h&&!isLast(p)})};
  return pdfTop('Roadmap',ps.length+(ps.length===1?' shareable project':' shareable projects'))+
    '<div class="rm-sum">'+HZ.map(function(h){return '<div class="rm-k"><span class="sw" style="background:'+h[3]+'"></span><span class="n">'+by(h[0]).length+'</span><span class="l"><b>'+h[1]+'</b>'+h[2]+'</span></div>'}).join('')+'</div>'+
    '<div class="horizons">'+HZ.map(function(h,i){var list=by(h[0]);
      return '<div class="hz"><div class="hz-h"><i style="background:'+h[3]+'"></i><span class="n">'+h[1]+'</span><span class="c">'+list.length+'</span><span class="d">'+h[2]+'</span></div>'+(list.length?list.map(function(p){return rcard(p,i)}).join(''):'<div class="empty">Nothing here.</div>')+'</div>'}).join('')+'</div>'+
    pdfFoot(esc(omitted())+'. Private groups never appear here.');
}

/* ======================= KEYS ======================= */
document.addEventListener('keydown',function(e){
  if(!S)return;
  var typing=['INPUT','TEXTAREA','SELECT'].indexOf(document.activeElement.tagName)>=0||document.activeElement.isContentEditable;
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();openCap();return}
  if(e.key==='Escape'){closeOv();return}
  if(typing)return;
  if(e.key==='/'){e.preventDefault();openPal();return}
  if(e.key==='?'){openKeys();return}
  var m={'1':'home','2':'projects','3':'roadmap','4':'ideas','5':'library','6':'week'};if(m[e.key])go(m[e.key]);
});
window.addEventListener('beforeunload',flushSave);
start();
