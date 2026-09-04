/* ================== DIG, AND THE COMPUTER UNDER IT ==================
   The interface below is the approved prototype from
   docs/handoff-v2/design/dig-prototype.html, unchanged apart from the seams
   SPEC section 1 calls for: state arrives from the bridge instead of a seed
   function, every change is written back through it, and file pickers, folder
   opening, link opening, exports, and imports go to Python.
   ==================================================================== */

var DAY=86400000;
/* The prototype froze the clock at 2026-09-04T14:00 so its sample data would
   read well. The app reads the real one. Every use of NOW below is untouched.
   It stays configurable so the fidelity pass can freeze it to the prototype's
   instant and compare the two side by side. */
Object.defineProperty(window,'NOW',{get:function(){return new Date()},configurable:true});

var S=null,BRIDGE=null,READY=false,SYS_THEME='light',DATA_PATH='',VERSION='';

/* Every record needs an id that is unique across every device, not just this
   session, so the prototype's counter, which restarted at 100 on every reload,
   is replaced by a UUID made here on whichever device creates the record. */
function uid(){
  if(window.crypto&&crypto.randomUUID)return crypto.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g,function(c){
    var r=Math.random()*16|0;return (c==='x'?r:(r&0x3|0x8)).toString(16)})}

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
  obStep:1,obExamples:false,startHere:null,groupId:null,
  period:'week',periodFrom:'',periodTo:'',reviewGroup:'all',textSize:'m',
  backupFolder:'',backupEvery:'',syncPort:8787,
  setupWork:{apps:false,clients:false,content:false,personal:false,programs:false}}}

/* Dates travel as ISO strings and come back as Dates, at the exact places the
   data model puts them. Nothing guesses at what a date looks like. */
function reDate(v){return v==null?null:(v instanceof Date?v:new Date(v))}
function S_hasType(s,id){return !!id&&s.types.some(function(t){return t.id===id})}
function revive(s){
  /* A document that came from somewhere else may be missing whole lists.
     Nothing below should have to wonder whether it got an array. */
  ['groups','types','projects','ideas','inbox','library','activity'].forEach(function(k){
    if(!Array.isArray(s[k]))s[k]=[]});
  s.types.forEach(function(t){
    if(!Array.isArray(t.stages)||!t.stages.length)t.stages=['Planned','Done'];
    if(!t.check||typeof t.check!=='object')t.check={}});
  s.projects=s.projects.filter(function(p){return p&&p.id});
  s.projects.forEach(function(p){
    if(!S_hasType(s,p.type))p.type=(s.types[0]||{}).id||'';
    p.stage=Math.max(0,Math.min(parseInt(p.stage,10)||0,
      ((s.types.find(function(t){return t.id===p.type})||{stages:['Planned','Done']}).stages.length-1)));
    p.items=p.items||[];p.decisions=p.decisions||[];p.files=p.files||[];p.links=p.links||[];
    p.releases=p.releases||[];p.people=p.people||[];p.hist=p.hist||[];p.waitHist=p.waitHist||[];
    p.enteredAt=reDate(p.enteredAt)||NOW;p.lastAct=reDate(p.lastAct)||p.enteredAt;
    p.decisions.forEach(function(x){x.at=reDate(x.at)});
    p.releases.forEach(function(r){r.at=reDate(r.at)});
    p.hist.forEach(function(h){h.from=reDate(h.from);h.to=reDate(h.to)});
    if(p.wait)p.wait.since=reDate(p.wait.since)||NOW;
  });
  s.libraryFiles=Array.isArray(s.libraryFiles)?s.libraryFiles:[];
  s.templates=Array.isArray(s.templates)?s.templates:[];
  s.ideas=s.ideas.filter(function(x){return x&&x.id});
  s.ideas.forEach(function(x){x.at=reDate(x.at)||NOW;x.opened=reDate(x.opened)});
  s.inbox.forEach(function(x){x.at=reDate(x.at)||NOW});
  s.activity.forEach(function(a){a.at=reDate(a.at)||NOW});
  return s;
}
function adopt(saved){
  var s=blank();
  if(!saved)return s;
  ['org','you','theme','setupDone','groups','types','projects','ideas','inbox','library','activity',
   'libraryFiles','templates','startHere','backupFolder','backupEvery']
    .forEach(function(k){if(saved[k]!==undefined&&saved[k]!==null)s[k]=saved[k]});
  var ui=saved.ui||{};
  ['filterGroup','sort','ideaSort','libFilter','publicOnly','ptab','resurfId',
   'period','periodFrom','periodTo','reviewGroup','textSize','syncPort']
    .forEach(function(k){if(ui[k]!==undefined&&ui[k]!==null)s[k]=ui[k]});
  s.uiWindow=ui.window||null;
  s.view=s.setupDone?'home':'setup';
  return revive(s);
}
/* What goes to disk. SPEC section 2 puts the view's own settings under `ui`,
   so they are folded in here and spread back out on the way in. */
function persist(){return{org:S.org,you:S.you,theme:S.theme,setupDone:S.setupDone,
  groups:S.groups,types:S.types,projects:S.projects,ideas:S.ideas,inbox:S.inbox,
  library:S.library,activity:S.activity,libraryFiles:S.libraryFiles||[],
  templates:S.templates||[],startHere:S.startHere,
  backupFolder:S.backupFolder||'',backupEvery:S.backupEvery||'',
  ui:{filterGroup:S.filterGroup,sort:S.sort,ideaSort:S.ideaSort,libFilter:S.libFilter,
      publicOnly:S.publicOnly,ptab:S.ptab,resurfId:S.resurfId,window:S.uiWindow,
      period:S.period,periodFrom:S.periodFrom,periodTo:S.periodTo,
      reviewGroup:S.reviewGroup,textSize:S.textSize,syncPort:S.syncPort}}}

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
    wireDropping();
    BRIDGE.saveFailed.connect(function(msg){stickyToast('save',msg?esc(msg):'')});
    BRIDGE.syncedFromElsewhere.connect(function(){reloadFromDisk()});
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
      if(BRIDGE.tookDocument)BRIDGE.tookDocument(opening.cursor||0);
      pickResurf();
      READY=true;
      applyTextSize();
      render();
      setTimeout(runScheduledBackup,1500);
      if(opening.notice)toast(esc(opening.notice));
    });
  });
}

/* ======================= HELPERS ======================= */
function G(id){return S.groups.find(function(g){return g.id===id})||{name:'No group',color:'#999',priv:false}}
/* Like G(), T() answers for a type that is not there, so a project whose
   type was removed shows something rather than taking the screen down. */
function T(id){return S.types.find(function(t){return t.id===id})||
  {id:'',name:'No type',stages:['Planned','Done'],check:{}}}
function Pr(id){return S.projects.find(function(p){return p.id===id})}
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function ago(dt){var ms=NOW-dt;var h=ms/3600000;if(h<1)return Math.max(1,Math.round(ms/60000))+' min';if(h<24)return Math.round(h)+' hours';var dd=Math.round(h/24);if(dd===1)return '1 day';if(dd<14)return dd+' days';if(dd<60)return Math.round(dd/7)+' weeks';return Math.round(dd/30)+' months'}
function days(dt){return Math.max(0,Math.round((NOW-dt)/DAY))}
function fmt(dt){return dt.toLocaleDateString('en-US',{month:'short',day:'numeric'})}
function stageName(p){return T(p.type).stages[p.stage]}
function nextStage(p){return T(p.type).stages[p.stage+1]||null}
function isLast(p){return p.stage>=T(p.type).stages.length-1}
function unmet(p){var t=T(p.type),st=stageName(p),ex=t.check[st]||[];return ex.filter(function(e){var it=p.items.find(function(x){return x.text===e});return !(it&&it.done)})}
function nextDecNo(){var m=0;
  S.projects.forEach(function(p){p.decisions.forEach(function(x){if(x.no>m)m=x.no})});
  S.groups.forEach(function(g){(g.decisions||[]).forEach(function(x){if(x.no>m)m=x.no})});
  return m+1}
function dno(n){return 'D-'+String(n).padStart(4,'0')}
/* A toast that stays until whatever it is about stops being true. Passing no
   message takes it down again. Used when Dig cannot write to the disk, which
   the person has to be able to see for longer than three seconds. */
function stickyToast(key,msg){
  S.toasts=S.toasts.filter(function(t){return t.stick!==key});
  if(msg)S.toasts.push({id:uid(),msg:msg,stick:key});
  renderToasts();
}
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
  /* Anything open is kept as it stands rather than drawn again. Drawing it
     again would replace the elements a person is typing into, and everything
     they had typed would go with them. Whatever is behind it is redrawn as
     usual. */
  var open=app.querySelector('.overlay.open');
  var keep=open?[].slice.call(app.querySelectorAll('.overlay')):null;
  app.className='app';
  app.innerHTML=renderSide()+'<main class="main" id="main">'+renderView(S.view)+'</main>'+(keep?'':renderOverlays())+'<div class="drop-veil" id="drop-veil"><div class="card"><b>Drop to keep a copy</b><span>Dig keeps its own copy. Your file is not moved.</span></div></div><div class="toasts" id="toasts"></div>';
  if(keep){
    var veil=document.getElementById('drop-veil');
    keep.forEach(function(o){app.insertBefore(o,veil)});
  }
  renderToasts();
  wireA11y();
  applyTextSize();
  scheduleSave();
}
function renderToasts(){var t=document.getElementById('toasts');if(!t)return;t.innerHTML=S.toasts.map(function(x){return '<div class="toast">'+x.msg+(x.undo?' <span class="u" onclick="'+x.undo+'">Undo</span>':'')+'</div>'}).join('')}
function ico(n){return{home:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M2.5 7.5L8 3l5.5 4.5V13a1 1 0 0 1-1 1H3.5a1 1 0 0 1-1-1z"/></svg>',projects:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><rect x="2" y="2" width="5" height="5" rx="1.2"/><rect x="9" y="2" width="5" height="5" rx="1.2"/><rect x="2" y="9" width="5" height="5" rx="1.2"/><rect x="9" y="9" width="5" height="5" rx="1.2"/></svg>',roadmap:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M2 12l4-3 3 2 5-5"/><path d="M11 6h3v3"/></svg>',ideas:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M8 2a4 4 0 0 0-2.5 7.1c.4.4.5.9.5 1.4V11h4v-.5c0-.5.1-1 .5-1.4A4 4 0 0 0 8 2zM6.5 13.5h3"/></svg>',library:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 3h4l1 1.5h5V13H3z"/></svg>',week:'<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 13V8M8 13V3M13 13V6"/></svg>'}[n]}
function renderSide(){
  var nav=[['home','Home','1'],['projects','Projects','2'],['roadmap','Roadmap','3'],['ideas','Ideas','4'],['library','Library','5'],['week','Your review','6']];
  return '<aside class="side"><div class="who"><div class="av"></div><div><div class="n">'+esc(S.org)+'</div><div class="s">Dig · stays on this computer</div></div></div>'+
  '<button class="add-btn" onclick="openCap()"><svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3v10M3 8h10"/></svg>Add something <kbd>Ctrl K</kbd></button>'+
  '<nav class="nav">'+nav.map(function(n){var on=S.view===n[0]||(n[0]==='projects'&&S.view==='project');var right=n[0]==='home'&&S.inbox.length?'<span class="cnt">'+S.inbox.length+'</span>':'<kbd class="k">'+n[2]+'</kbd>';return '<a class="'+(on?'on':'')+'" onclick="go(\''+n[0]+'\')">'+ico(n[0])+n[1]+right+'</a>'}).join('')+'</nav>'+
  '<div class="sec-h">Groups <a onclick="go(\'settings\')">edit</a></div><div class="groups"><a class="'+(S.filterGroup==='all'?'on':'')+'" onclick="setGroup(\'all\')"><i style="background:var(--ink-3)"></i>Everything<span class="c">'+S.projects.length+'</span></a>'+S.groups.map(function(g){var n=S.projects.filter(function(p){return p.group===g.id}).length;return '<a class="'+((S.view==='group'&&S.groupId===g.id)||(S.view!=='group'&&S.filterGroup===g.id)?'on':'')+'" onclick="openG(\''+g.id+'\')"><i style="background:'+g.color+'"></i>'+esc(g.name)+(g.priv?'<span class="lk">private</span>':'')+'<span class="c">'+n+'</span></a>'}).join('')+'</div>'+
  syncStatusLine()+'<div class="side-foot"><a onclick="go(\'settings\')">Settings</a><a onclick="openKeys()">Shortcuts <kbd>?</kbd></a><div class="theme">'+['light','dark','system'].map(function(m){return '<button class="'+(S.theme===m?'on':'')+'" onclick="setTheme(\''+m+'\')">'+(m==='system'?'Auto':m[0].toUpperCase()+m.slice(1))+'</button>'}).join('')+'</div></div></aside>';
}
function renderView(v){switch(v){case 'home':return renderHome();case 'projects':return renderProjects();case 'project':return renderProject();case 'roadmap':return renderRoadmap();case 'week':return renderWeek();case 'ideas':return renderIdeas();case 'library':return renderLibrary();case 'settings':return renderSettings();case 'group':return renderGroup();case 'people':return renderPeople();case 'notplanned':return renderNotPlanned();case 'setup':return renderSetup()}return ''}

/* ---- HOME ---- */
function renderHome(){
  var active=S.projects.filter(function(p){return !p.quiet&&!p.parked&&!isLast(p)});
  var waiting=S.projects.filter(function(p){return p.wait});
  var upNext=S.projects.filter(function(p){return !p.wait&&!p.quiet&&!p.parked&&p.next}).sort(function(a,b){return days(b.enteredAt)-days(a.enteredAt)}).slice(0,4);
  var r=S.ideas.find(function(x){return x.id===S.resurfId});
  var row=function(p){var g=G(p.group);return '<div class="row click" id="row-'+p.id+'" onclick="openP(\''+p.id+'\')"><span class="dotc" style="background:'+g.color+'"></span><div class="grow"><div class="t">'+esc(p.next)+'</div><div class="m"><b>'+esc(p.name)+'</b> · '+esc(stageName(p))+(days(p.enteredAt)?' for '+days(p.enteredAt)+' days':'')+'</div></div><div class="acts"><button class="btn sm" onclick="event.stopPropagation();doneNext(\''+p.id+'\')">Done ✓</button><button class="btn sm ghost" onclick="event.stopPropagation();openP(\''+p.id+'\')">Open</button></div></div>'};
  return '<div class="view">'+startHereCard()+'<div class="hd"><div><h1>'+greetingLine()+'</h1><div class="sub"><b>'+active.length+'</b> projects active · <b>'+waiting.length+'</b> waiting on someone else · <b>'+S.inbox.length+'</b> in your inbox</div></div><div class="r"><div class="search" onclick="openPal()">Find anything <kbd>/</kbd></div></div></div>'+
  '<div class="sec"><div class="sec-t"><h2>'+secIcon('next')+'Up next</h2><span class="help">the next step on each project that\'s been sitting longest</span><a class="rt" onclick="go(\'projects\')">All projects →</a></div><div class="box">'+(upNext.length?upNext.map(row).join(''):'<div class="empty"><div class="gl" style="background:var(--blue-soft);color:var(--blue)"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M3 8h9M8.5 4.5L12 8l-3.5 3.5"/></svg></div><b>Nothing lined up</b>Open a project and write its next step.</div>')+'</div></div>'+
  (quietOnes().length?'<div class="quietline" onclick="S.sort=\'quiet\';go(\'projects\')">'+quietOnes().length+(quietOnes().length===1?' project has':' projects have')+' gone quiet. Nothing has happened on '+(quietOnes().length===1?'it':'them')+' for three weeks.</div>':'')+
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
  if(S.sort==='waiting')ps=ps.filter(function(p){return p.wait});if(S.sort==='done')ps=ps.filter(function(p){return isLast(p)||p.quiet});if(S.sort==='parked')ps=ps.filter(function(p){return p.parked});if(S.sort==='quiet')ps=ps.filter(goneQuiet);if(S.sort==='activity')ps=ps.filter(function(p){return !p.parked});
  ps.sort(function(a,b){return b.lastAct-a.lastAct});
  var groups=S.groups.filter(function(g){return S.filterGroup==='all'||g.id===S.filterGroup});
  return '<div class="view wide"><div class="hd"><div><h1>Projects</h1><div class="sub">Everything you\'re working on, by group. Each one moves through stages.</div></div><div class="r"><div class="search" onclick="openPal()">Find a project <kbd>/</kbd></div><button class="btn" onclick="openShare(null)">Share as PDF</button><button class="btn p" onclick="openNew(\'\')">New project</button></div></div>'+
  '<div class="chips"><span class="chip '+(S.filterGroup==='all'?'on':'')+'" onclick="setGroup(\'all\')">All groups</span>'+S.groups.map(function(g){return '<span class="chip '+(S.filterGroup===g.id?'on':'')+'" onclick="setGroup(\''+g.id+'\')"><i style="background:'+g.color+'"></i>'+esc(g.name)+'</span>'}).join('')+'<span class="sp"></span><select onchange="S.sort=this.value;render()"><option value="activity" '+(S.sort==='activity'?'selected':'')+'>Active</option><option value="waiting" '+(S.sort==='waiting'?'selected':'')+'>Only waiting</option><option value="done" '+(S.sort==='done'?'selected':'')+'>Only finished</option><option value="parked" '+(S.sort==='parked'?'selected':'')+'>Only parked</option><option value="quiet" '+(S.sort==='quiet'?'selected':'')+'>Only gone quiet</option></select></div>'+
  groups.map(function(g){var list=ps.filter(function(p){return p.group===g.id});return '<div class="grp" style="--gc:'+g.color+'"><div class="grp-h"><span class="n" style="cursor:pointer" onclick="openG(\''+g.id+'\')"><span class="dotc" style="background:'+g.color+'"></span>'+esc(g.name)+'</span><span class="c">'+list.length+'</span>'+(g.priv?'<span class="lk">private · never shared</span>':'')+'<span class="add" onclick="S.filterGroup=\''+g.id+'\';go(\'roadmap\')">roadmap</span><span class="add" onclick="openNew(\''+g.id+'\')">+ project</span></div>'+(list.length?'<div class="cards">'+list.map(card).join('')+'</div>':'<div class="box empty"><b>No projects here</b>Add one, or start one from an idea.</div>')+'</div>'}).join('')+'</div>';
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
  var head='<div class="view" style="--gc:'+g.color+'"><div class="crumb"><a onclick="go(\'projects\')">Projects</a> / <a onclick="openG(\''+g.id+'\')">'+esc(g.name)+'</a></div>'+
  '<div class="ph"><div class="sq">'+esc(ini(p.name))+'</div><div><h1>'+esc(p.name)+'</h1><div class="m">'+tbadge(p)+'<span class="badge g">'+(p.pub?'Can be shared':'Private')+'</span><span class="badge g">'+esc(hzLabel(p.when))+'</span>'+p.links.map(function(u){return '<a onclick="openLink('+jsq(u)+')">'+esc(u)+'</a>'}).join('')+'<a onclick="addLink(\''+p.id+'\')">+ link</a></div></div>'+
  '<div class="r"><button class="btn" onclick="openProjectMore(\''+p.id+'\')">More</button><button class="btn" onclick="openShare(\''+p.id+'\')">Share</button><button class="btn ghost" onclick="togglePark(\''+p.id+'\')">'+(p.parked?'Unpark':'Park')+'</button>'+(p.wait?'<button class="btn" onclick="resolveWait(\''+p.id+'\')">It arrived</button>':'<button class="btn" onclick="openWait(\''+p.id+'\')">Waiting on…</button>')+(ns?'<button class="btn p" onclick="openAdvance(\''+p.id+'\')">Move to '+esc(ns)+' →</button>':'<button class="btn" disabled>Finished</button>')+'</div></div>'+
  (p.wait?'<div class="box waitbar"><span class="waitdot"></span><span>Waiting on <b>'+esc(p.wait.what)+'</b> for '+days(p.wait.since)+' days</span><span style="margin-left:auto"><button class="btn sm" onclick="resolveWait(\''+p.id+'\')">It arrived</button></span></div>':'')+
  '<div class="stages">'+t.stages.map(function(s,i){return '<div class="st '+(i<p.stage?'done':(i===p.stage?'cur':''))+'" onclick="jumpStage(\''+p.id+'\','+i+')"><b>'+esc(s)+'</b><small>'+(i===p.stage?'you are here · '+days(p.enteredAt)+' days':(i<p.stage?'done':'later'))+'</small></div>'}).join('')+'</div>'+
  '<div class="tabs"><button class="'+(S.ptab==='work'?'on':'')+'" onclick="S.ptab=\'work\';render()">Work</button><button class="'+(S.ptab==='rm'?'on':'')+'" onclick="S.ptab=\'rm\';render()">Roadmap</button><button class="'+(S.ptab==='rec'?'on':'')+'" onclick="S.ptab=\'rec\';render()">Record</button></div>';
  if(S.ptab==='rm')return head+renderProjectRoadmap(p)+'</div>';
  if(S.ptab==='rec')return head+renderProjectRecord(p)+'</div>';
  var items=p.items.slice().sort(function(a,b){return (a.done?1:0)-(b.done?1:0)}).map(function(x){return '<div class="check '+(x.done?'ok':'')+'" onclick="toggleItem(\''+p.id+'\',\''+x.id+'\')"><div class="bx"></div><span class="t">'+esc(x.text)+'</span>'+(x.tag?'<span class="tg '+x.tag+'">'+(x.tag==='exp'?'part of this stage':'bug')+'</span>':'')+'<span class="x" onclick="event.stopPropagation();delItem(\''+p.id+'\',\''+x.id+'\')">✕</span></div>'}).join('');
  ex.forEach(function(e){if(!p.items.find(function(x){return x.text===e})){items='<div class="check" onclick="addExpected('+jsq(p.id)+','+jsq(e)+')"><div class="bx" style="border-style:dashed"></div><span class="t" style="color:var(--ink-3)">'+esc(e)+'</span><span class="tg exp">suggested for this stage</span></div>'+items}});
  return head+'<div class="two"><div>'+
  (p.origin?'<div class="box" style="padding:10px 14px;margin-bottom:14px;border-left:3px solid var(--gc)"><div style="font-size:11px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:var(--gc)">Started as an idea</div><div style="margin-top:3px">"'+esc(p.origin)+'"</div></div>':'')+
  '<div class="sec"><div class="sec-t"><h2>'+secIcon('next')+'Next step</h2></div><div class="box nextin"><input type="text" value="'+esc(p.next)+'" placeholder="The one thing that moves this forward" onchange="Pr(\''+p.id+'\').next=this.value;tickStartHere(\'nextStep\');scheduleSave();toast(\'Next step saved\')"></div></div>'+
  '<div class="sec"><div class="sec-t"><h2>'+secIcon('dec')+esc(st)+' checklist</h2><span class="help">what this stage usually needs, plus anything you add</span><a class="rt" onclick="go(\'settings\')">edit the '+esc(t.name)+' template</a></div><div class="box">'+items+'<div class="check add"><div class="bx"></div><input placeholder="Add to the checklist… (start with ! for a bug)" onkeydown="if(event.key===\'Enter\'){addItem(\''+p.id+'\',this.value);this.value=\'\'}"><kbd>↵</kbd></div></div></div>'+
  '<div class="sec"><div class="sec-t"><h2>Notes</h2><span class="help">click to write · saves as you type</span></div><div class="box"><div class="notes-ed" contenteditable="true" oninput="Pr(\''+p.id+'\').notes=this.innerText;scheduleSave()">'+(esc(p.notes)||'<span style="color:var(--ink-3)">Talking points, the demo order, the sentence that matters.</span>')+'</div></div></div>'+
  '</div><aside class="rail">'+
  '<div><div class="sec-t"><h2>'+secIcon('ppl')+'People</h2><a class="rt" onclick="addPerson(\''+p.id+'\')">+ add</a></div><div class="box">'+(p.people.length?'<div class="people">'+p.people.map(function(x){return '<span class="pp"><span class="av">'+esc(ini(x.n))+'</span>'+esc(x.n)+'<small>'+esc(x.r)+'</small></span>'}).join('')+'</div>':'<div class="empty" style="padding:14px">Nobody yet. Reviewers, clients, collaborators.</div>')+'</div></div>'+
  '<div><div class="sec-t"><h2>'+secIcon('file')+'Files</h2><a class="rt" onclick="addFiles(\''+p.id+'\',\'\')">+ add files</a></div><div class="box">'+(p.files.length?p.files.filter(function(f){return !f.superseded}).map(function(f){return '<div class="filerow" onclick="openFile(\''+f.id+'\')"><span class="ic '+esc(f.type)+'" style="font-family:var(--mono);font-size:9.5px;border-radius:5px;padding:4px 6px;min-width:36px;text-align:center;font-weight:500;color:var(--ink-2);background:var(--panel-2)">'+esc(f.type||'FILE')+'</span><div class="grow"><div class="n">'+esc(f.name)+'</div><div class="m">'+esc(fileLine(f))+'</div></div></div>'}).join('')+(p.files.filter(function(f){return f.sha256}).length?'<div class="filerow" style="cursor:pointer;color:var(--ink-3)" onclick="saveAllFiles(\''+p.id+'\',\'\')"><div class="grow"><div class="n" style="font-weight:400">Save all files…</div></div></div>':''):'<div class="empty" style="padding:14px">Specs, mockups, exports, assets. Drop them anywhere on this page.</div>')+'</div></div>'+
  '<div><div class="sec-t"><h2>'+secIcon('rel')+'Releases</h2><a class="rt" onclick="addRelease(\''+p.id+'\')">+ add</a></div><div class="box">'+(p.releases.length?p.releases.slice().reverse().map(function(r){return '<div class="rel"><span class="v">'+esc(r.v)+'</span><span>'+esc(r.note)+'</span><span class="m">'+fmt(r.at)+'</span></div>'}).join(''):'<div class="empty" style="padding:14px">Nothing released yet.</div>')+'</div></div>'+
  '</aside></div>';
}
function stageLogs(p,stage){
  var mine=logsOf(p).filter(function(e){return (e.stage||'')===stage});
  if(!mine.length)return '';
  return mine.map(function(e){
    return '<div class="lg"><b>'+esc(fmt(new Date(e.at)))+'</b>'+esc(e.text)+'</div>'}).join('');
}
function renderProjectRoadmap(p){
  var t=T(p.type),g=G(p.group);
  var hist=function(s){return p.hist.find(function(h){return h.stage===s})};
  var rows=t.stages.map(function(s,i){var h=hist(s);var cls=i<p.stage?'done':(i===p.stage?'cur':'future');
    var body='';
    if(i<p.stage){body='<div class="bd">'+(h?fmt(h.from)+' → '+fmt(h.to)+' · '+Math.max(1,Math.round((h.to-h.from)/DAY))+' days':'')+p.releases.filter(function(r){return h&&r.at>=h.from&&r.at<=new Date(h.to.getTime()+DAY)}).map(function(r){return '<div><span class="rel">'+esc(r.v)+' · '+esc(r.note)+'</span></div>'}).join('')+stageLogs(p,s)+'</div>'}
    else if(i===p.stage){var open=p.items.filter(function(x){return !x.done}),done=p.items.filter(function(x){return x.done});body='<div class="bd">since '+fmt(p.enteredAt)+' · '+days(p.enteredAt)+' days'+(p.next?'<div style="margin-top:6px"><b style="color:var(--ink)">Next:</b> '+esc(p.next)+'</div>':'')+'<div style="margin-top:6px">'+open.map(function(x){return '<div class="it"><span class="ck"></span>'+esc(x.text)+'</div>'}).join('')+done.map(function(x){return '<div class="it ok"><span class="ck"></span>'+esc(x.text)+'</div>'}).join('')+'</div>'+stageLogs(p,s)+'</div>'}
    else{var ex=t.check[s]||[];body='<div class="bd" style="color:var(--ink-3)">'+(ex.length?'Will need: '+ex.map(esc).join(' · '):'Nothing preset. Add expectations in Settings.')+'</div>'}
    return '<div class="tl-s '+cls+'"><div class="nd">'+(i<p.stage?'✓':(i+1))+'</div><div><div class="h"><b>'+esc(s)+'</b><span>'+(i<p.stage?'done':(i===p.stage?'you are here':'later'))+'</span></div>'+body+'</div></div>'});
  return '<div class="two" style="--gc:'+g.color+'"><div><div class="sec-t" style="margin-top:4px"><h2>'+secIcon('rm')+'Where this project has been, and where it\'s going</h2></div><div class="box" style="padding:18px 18px 4px"><div class="tl">'+rows.join('')+'</div></div></div>'+
  '<aside class="rail"><div><div class="sec-t"><h2>On the roadmap</h2></div><div class="box" style="padding:12px 14px"><div style="font-size:12.5px;color:var(--ink-2);margin-bottom:8px">Which horizon this sits in on the '+esc(g.name)+' roadmap.</div><div style="display:flex;gap:6px;flex-wrap:wrap">'+HZ.map(function(h){return '<span class="chip '+((p.when||'later')===h[0]?'on':'')+'" onclick="setWhen(\''+p.id+'\',\''+h[0]+'\')">'+h[1]+'</span>'}).join('')+'</div></div></div>'+
  '<div><div class="sec-t"><h2>'+secIcon('rel')+'Releases</h2><a class="rt" onclick="addRelease(\''+p.id+'\')">+ add</a></div><div class="box">'+(p.releases.length?p.releases.slice().reverse().map(function(r){return '<div class="rel"><span class="v">'+esc(r.v)+'</span><span>'+esc(r.note)+'</span><span class="m">'+fmt(r.at)+'</span></div>'}).join(''):'<div class="empty" style="padding:14px">Nothing released yet.</div>')+'</div></div></aside></div>';
}
function renderProjectRecord(p){
  var g=G(p.group);var acts=S.activity.filter(function(a){return a.pid===p.id});
  return '<div class="two" style="--gc:'+g.color+'"><div><div class="sec-t" style="margin-top:4px"><h2>'+secIcon('dec')+'Decisions</h2><span class="help">numbered, dated, permanent</span><a class="rt" onclick="openDec(\''+p.id+'\')">+ record one</a></div><div class="box">'+(p.decisions.length?p.decisions.slice().sort(function(a,b){return b.no-a.no}).map(function(x){return '<div class="dec '+(x.superseded?'sup':'')+'"><b>'+dno(x.no)+'</b><span>'+esc(x.text)+(x.supersedes?' <i style="color:var(--ink-3)">replaces '+dno(x.supersedes)+'</i>':'')+'</span><span class="sd">'+fmt(x.at)+'</span></div>'}).join(''):'<div class="empty"><b>No decisions yet</b>Record one and it gets a number you can refer back to.</div>')+'</div>'+
  '<div class="sec-t" style="margin-top:22px"><h2>Log</h2><span class="help">what happened, in order</span></div>'+renderLogBox('project',p.id,p)+
  '<div class="sec-t" style="margin-top:22px"><h2>Past waits</h2></div><div class="box">'+(p.waitHist.length?p.waitHist.map(function(w){return '<div class="row"><div class="grow"><div class="t">'+esc(w.what)+'</div><div class="m">took '+w.days+' days</div></div></div>'}).join(''):'<div class="empty">Nothing recorded yet.</div>')+'</div></div>'+
  '<aside class="rail"><div><div class="sec-t"><h2>History</h2></div><div class="box">'+(acts.length?acts.map(function(a){return '<div class="row"><span class="dotc" style="background:'+g.color+'"></span><div class="grow"><div class="t" style="font-weight:400">'+esc(a.text)+'</div><div class="m">'+ago(a.at)+' ago</div></div></div>'}).join(''):'<div class="empty">Nothing yet.</div>')+'</div></div></aside></div>';
}

/* ======================= THE LOG (7.3) =======================
   Dated notes on a project or a group. Separate from Notes, which is the one
   standing description; these are what happened, in order. */

function logsOf(owner){return (owner&&owner.logs)||[]}
function addLog(kind,id,text,stage){
  text=(text||'').trim();if(!text)return null;
  var owner=kind==='project'?Pr(id):G(id);
  if(!owner)return null;
  owner.logs=owner.logs||[];
  var entry={id:uid(),text:text,at:NOW,stage:stage||(kind==='project'?stageName(owner):''),highlight:false};
  owner.logs.unshift(entry);
  if(kind==='project')owner.lastAct=NOW;
  return entry;
}
function logFromInput(kind,id,el){
  var entry=addLog(kind,id,el.value);
  if(!entry)return;
  el.value='';render();
  setTimeout(function(){var t=document.querySelector('.logadd textarea');if(t)t.focus()},0);
}
function toggleHighlight(kind,id,lid){
  var owner=kind==='project'?Pr(id):G(id);if(!owner)return;
  var e=(owner.logs||[]).find(function(x){return x.id===lid});
  if(e){e.highlight=!e.highlight;render()}
}
function delLog(kind,id,lid){
  var owner=kind==='project'?Pr(id):G(id);if(!owner)return;
  var e=(owner.logs||[]).find(function(x){return x.id===lid});
  owner.logs=(owner.logs||[]).filter(function(x){return x.id!==lid});
  render();toast('Taken out',"undoLog('"+kind+"','"+id+"',"+jsq(JSON.stringify(e))+")");
}
function undoLog(kind,id,json){
  var owner=kind==='project'?Pr(id):G(id);if(!owner)return;
  try{var e=JSON.parse(json)}catch(err){return}
  e.at=new Date(e.at);
  owner.logs=owner.logs||[];owner.logs.unshift(e);
  owner.logs.sort(function(a,b){return new Date(b.at)-new Date(a.at)});
  render();toast('Put back');
}
function renderLogBox(kind,id,owner){
  var logs=logsOf(owner);
  return '<div class="box">'+
    '<div class="logadd"><span class="when" style="padding-top:3px">today</span>'+
    '<textarea rows="1" placeholder="What happened? Enter saves, Shift and Enter for a new line" '+
    'oninput="this.style.height=\'auto\';this.style.height=this.scrollHeight+\'px\'" '+
    'onkeydown="if(event.key===\'Enter\'&&!event.shiftKey){event.preventDefault();logFromInput(\''+kind+'\',\''+id+'\',this)}"></textarea>'+
    '<kbd>↵</kbd></div>'+
    (logs.length?logs.map(function(e){
      return '<div class="logline"><span class="when">'+esc(fmt(new Date(e.at)))+'</span>'+
        '<span class="grow">'+esc(e.text)+'</span>'+
        '<span class="hl'+(e.highlight?' on':'')+'" title="Mark as a highlight" onclick="toggleHighlight(\''+kind+'\',\''+id+'\',\''+e.id+'\')">★</span>'+
        '<span class="x" onclick="delLog(\''+kind+'\',\''+id+'\',\''+e.id+'\')">✕</span></div>'}).join('')
      :'<div class="empty" style="padding:16px">Nothing written down yet. A line a day is plenty.</div>')+
  '</div>';
}

/* ======================= GONE QUIET (7.7) =======================
   Not a state anyone sets. A project nobody has touched for three weeks. */
var QUIET_DAYS=21;
function goneQuiet(p){
  return !p.wait&&!p.quiet&&!p.parked&&!isLast(p)&&days(p.lastAct)>=QUIET_DAYS;
}
function quietOnes(){return S.projects.filter(goneQuiet)}

/* ======================= GROUP PAGES (7.1) ======================= */

function openG(id){S.groupId=id;S.view='group';render()}
function renderGroup(){
  var g=S.groups.find(function(x){return x.id===S.groupId});
  if(!g)return renderProjects();
  var mine=S.projects.filter(function(p){return p.group===g.id});
  var live=mine.filter(function(p){return !p.parked});
  var byStage={};
  live.forEach(function(p){var s=stageName(p);byStage[s]=(byStage[s]||0)+1});
  var acts=S.activity.filter(function(a){return a.group===g.id}).slice(0,8);

  return '<div class="view wide" style="--gc:'+g.color+'">'+
  '<div class="crumb"><a onclick="go(\'projects\')">Projects</a> / '+esc(g.name)+'</div>'+
  '<div class="gh"><div class="sq"></div><div><h1>'+esc(g.name)+'</h1>'+
    '<div class="m"><span class="badge g">'+(g.priv?'Private':'Can be shared')+'</span>'+
    '<span>'+mine.length+(mine.length===1?' project':' projects')+'</span>'+
    (g.links||[]).map(function(u){return '<a onclick="openLink('+jsq(u)+')" style="color:var(--blue);cursor:pointer">'+esc(u)+'</a>'}).join('')+
    '<a onclick="addGroupLink(\''+g.id+'\')" style="color:var(--blue);cursor:pointer">+ link</a></div></div>'+
    '<div class="r"><button class="btn" onclick="openShare(\'g:'+g.id+'\')">Share</button>'+
    '<button class="btn" onclick="editGroup(\''+g.id+'\')">Edit</button>'+
    '<button class="btn p" onclick="openNew(\''+g.id+'\')">New project</button></div></div>'+

  '<div class="sec" style="margin-top:18px"><div class="sec-t"><h2>What this group is</h2><span class="help">click to write · saves as you type</span></div>'+
  '<div class="box"><div class="gdesc" contenteditable="true" oninput="G(\''+g.id+'\').description=this.innerText;scheduleSave()">'+
    (esc(g.description||'')||'<span style="color:var(--ink-3)">What this group is for, and who it is for.</span>')+'</div></div></div>'+

  '<div class="sec"><div class="sec-t"><h2>'+secIcon('next')+'Standing</h2><span class="help">where everything in this group has got to</span><a class="rt" onclick="S.filterGroup=\''+g.id+'\';go(\'projects\')">All projects →</a></div>'+
  '<div class="box">'+(live.length?'<div class="standing">'+Object.keys(byStage).map(function(s){
      return '<span class="st-c">'+esc(s)+'<b>'+byStage[s]+'</b></span>'}).join('')+'</div>'+
      live.map(function(p){var t=T(p.type);
        return '<div class="row click" onclick="openP(\''+p.id+'\')" style="--gc:'+g.color+'"><div class="grow"><div class="t">'+esc(p.name)+'</div>'+
        '<div class="m">'+esc(stageName(p))+' · stage '+(p.stage+1)+' of '+t.stages.length+(p.next?' · '+esc(p.next):'')+'</div></div>'+
        '<div style="width:110px">'+sbar(p)+'</div></div>'}).join('')
    :'<div class="empty"><b>Nothing in this group yet</b>Add a project, or move one here from Settings.</div>')+'</div></div>'+

  '<div class="sec"><div class="sec-t"><h2>'+secIcon('rm')+'Roadmap</h2><span class="help">what comes first in this group</span><a class="rt" onclick="S.filterGroup=\''+g.id+'\';go(\'roadmap\')">Open the roadmap →</a></div>'+
  '<div class="horizons">'+HZ.map(function(h,i){
    var list=mine.filter(function(p){return (p.when||'later')===h[0]&&!isLast(p)&&!p.quiet});
    return '<div class="hz"><div class="hz-h"><i style="background:'+h[3]+'"></i><span class="n">'+h[1]+'</span><span class="c">'+list.length+'</span></div>'+
      (list.length?list.map(function(p){return rcard(p,i)}).join(''):'<div class="empty">Nothing here.</div>')+'</div>'}).join('')+'</div></div>'+

  '<div class="two">'+
  '<div><div class="sec-t"><h2>'+secIcon('dec')+'Decisions</h2><span class="help">choices that span more than one project</span><a class="rt" onclick="openGroupDec(\''+g.id+'\')">+ record one</a></div>'+
  '<div class="box">'+((g.decisions||[]).length?g.decisions.slice().sort(function(a,b){return b.no-a.no}).map(function(x){
      return '<div class="dec '+(x.superseded?'sup':'')+'"><b>'+dno(x.no)+'</b><span>'+esc(x.text)+'</span><span class="sd">'+esc(fmt(new Date(x.at)))+'</span></div>'}).join('')
      :'<div class="empty"><b>No decisions yet</b>Record one and it gets a number you can refer back to.</div>')+'</div>'+
  '<div class="sec-t" style="margin-top:22px"><h2>Log</h2><span class="help">what happened, in order</span></div>'+
  renderLogBox('group',g.id,g)+'</div>'+

  '<aside class="rail">'+
  '<div><div class="sec-t"><h2>'+secIcon('file')+'Files</h2><a class="rt" onclick="addFiles(\'\',\''+g.id+'\')">+ add files</a></div>'+
  '<div class="box">'+((g.files||[]).length?g.files.filter(function(f){return !f.superseded}).map(function(f){
      return '<div class="filerow" onclick="openFile(\''+f.id+'\')"><span class="ic" style="font-family:var(--mono);font-size:9.5px;border-radius:5px;padding:4px 6px;min-width:36px;text-align:center;font-weight:500;color:var(--ink-2);background:var(--panel-2)">'+esc(f.type||'FILE')+'</span>'+
      '<div class="grow"><div class="n">'+esc(f.name)+'</div><div class="m">'+esc(fileLine(f))+'</div></div></div>'}).join('')
      :'<div class="empty" style="padding:14px">Anything that belongs to the whole group. Drop files anywhere on this page.</div>')+'</div></div>'+
  '<div><div class="sec-t"><h2>Recent activity</h2></div><div class="box">'+
    (acts.length?acts.map(function(a){return '<div class="row"><span class="dotc" style="background:'+g.color+'"></span><div class="grow"><div class="t" style="font-weight:400">'+esc(a.text)+'</div><div class="m">'+ago(new Date(a.at))+' ago</div></div></div>'}).join('')
      :'<div class="empty" style="padding:14px">Nothing yet.</div>')+'</div></div>'+
  '</aside></div></div>';
}
function addGroupLink(id){
  dlg('<div class="dh2"><h3>Add a link</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body"><label>Address or name</label><input type="text" id="glk" placeholder="example.com"></div><div class="foot"><button class="btn" onclick="closeOv()">Cancel</button><button class="btn p" onclick="var t=document.getElementById(\'glk\').value.trim();if(t){var g=G(\''+id+'\');g.links=g.links||[];g.links.push(t)};closeOv();render()">Add</button></div>');
}
function editGroup(id){
  var g=G(id);
  dlg('<div class="dh2"><h3>Edit this group</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body">'+
  '<div class="row2"><div><label>Name</label><input type="text" id="eg-n" value="'+esc(g.name)+'"></div>'+
  '<div><label>Color</label><input type="color" id="eg-c" value="'+g.color+'" style="width:100%;height:38px;border:1px solid var(--line-2);border-radius:8px;background:var(--bg);padding:3px"></div></div>'+
  '<label>Sharing</label><select id="eg-p"><option value="0"'+(!g.priv?' selected':'')+'>Can be shared</option><option value="1"'+(g.priv?' selected':'')+'>Private, never leaves this computer</option></select>'+
  '<div class="helper">A private group never appears in an export, a share, or the review.</div></div>'+
  '<div class="foot"><button class="btn" onclick="closeOv()">Cancel</button><button class="btn p" onclick="saveGroup(\''+id+'\')">Save</button></div>');
}
function saveGroup(id){
  var g=G(id);
  g.name=document.getElementById('eg-n').value.trim()||g.name;
  g.color=document.getElementById('eg-c').value;
  var priv=document.getElementById('eg-p').value==='1';
  if(priv!==g.priv){g.priv=priv;S.projects.forEach(function(p){if(p.group===id)p.pub=!priv})}
  closeOv();render();toast('Saved');
}
function openGroupDec(id){
  var g=G(id);
  dlg('<div class="dh2"><h3>Record a decision · '+dno(nextDecNo())+'</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body"><label>What did you decide, and why?</label><textarea id="gdc-t" rows="4" placeholder="Write it so future you understands the reasoning."></textarea><div class="helper">This one belongs to the whole group rather than one project.</div></div><div class="foot"><button class="btn" onclick="closeOv()">Cancel</button><button class="btn p" onclick="recordGroupDecision(\''+id+'\')">Record it</button></div>');
}
function recordGroupDecision(id){
  var text=(document.getElementById('gdc-t').value||'').trim();if(!text)return;
  var g=G(id);g.decisions=g.decisions||[];
  var no=nextDecNo();
  g.decisions.push({id:uid(),no:no,text:text,at:NOW,supersedes:null,superseded:false});
  S.activity.unshift({id:uid(),group:id,pid:'',text:esc(g.name)+': '+dno(no)+' recorded',at:NOW,kind:'decision'});
  closeOv();render();toast(dno(no)+' recorded');
}

/* ======================= DUPLICATE AND TEMPLATES (7.4) ======================= */

function openProjectMore(id){
  var p=Pr(id);if(!p)return;
  dlg('<div class="dh2"><h3>'+esc(p.name)+'</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body">'+
  '<div class="box"><div class="row click" onclick="closeOv();renameProject(\''+id+'\')"><div class="grow"><div class="t">Rename</div></div></div>'+
  '<div class="row click" onclick="closeOv();duplicateProject(\''+id+'\')"><div class="grow"><div class="t">Duplicate</div><div class="m">Same group, type, checklist, links, and people. Nothing that has happened.</div></div></div>'+
  '<div class="row click" onclick="closeOv();saveAsTemplate(\''+id+'\')"><div class="grow"><div class="t">Save as a template</div><div class="m">So the next one like it starts here.</div></div></div>'+
  '<div class="row click" onclick="closeOv();deleteProject(\''+id+'\')"><div class="grow"><div class="t" style="color:var(--red)">Delete this project</div><div class="m">It goes to Recently deleted for thirty days.</div></div></div>'+
  '</div></div><div class="foot"><button class="btn" onclick="closeOv()">Close</button></div>');
}
function deleteProject(id){
  var p=Pr(id);if(!p)return;
  dlg('<div class="dh2"><h3>Delete '+esc(p.name)+'?</h3><span class="x" onclick="closeOv()">✕</span></div>'+
  '<div class="body"><div class="warn">Its checklist, decisions, releases, files, and log go with it.</div>'+
  '<div class="helper">Nothing is gone for good. It sits in Recently deleted, in Settings, for thirty days.</div></div>'+
  '<div class="foot"><button class="btn" onclick="closeOv()">Keep it</button>'+
  '<button class="btn p danger" onclick="doDeleteProject(\''+id+'\')">Delete it</button></div>');
}
function doDeleteProject(id){
  var p=Pr(id);if(!p)return;
  var name=p.name;
  S.projects=S.projects.filter(function(x){return x.id!==id});
  closeOv();go('projects');
  toast('<b>'+esc(name)+'</b> deleted. It is in Recently deleted for thirty days.');
}
function duplicateProject(id){
  var p=Pr(id);if(!p)return;
  var copy={id:uid(),name:'Copy of '+p.name,group:p.group,type:p.type,stage:0,enteredAt:NOW,
    when:'next',next:'',notes:p.notes,pub:p.pub,wait:null,lastAct:NOW,
    items:(p.items||[]).map(function(x){return {id:uid(),text:x.text,done:false,tag:x.tag}}),
    decisions:[],files:[],links:(p.links||[]).slice(),releases:[],
    people:(p.people||[]).map(function(x){return {id:uid(),n:x.n,r:x.r}}),
    hist:[],logs:[],quiet:false,origin:null,parked:false,waitHist:[]};
  S.projects.unshift(copy);
  log(copy,copy.name+' started','move');
  S.projectId=copy.id;S.ptab='work';S.view='project';render();
  toast('Copied. Nothing that happened to the original came with it.');
  setTimeout(function(){renameProject(copy.id)},120);
}
function renameProject(id){
  var p=Pr(id);if(!p)return;
  dlg('<div class="dh2"><h3>Name it</h3><span class="x" onclick="closeOv()">✕</span></div>'+
  '<div class="body"><label>Name</label><input type="text" id="rn-n" value="'+esc(p.name)+'"></div>'+
  '<div class="foot"><button class="btn" onclick="closeOv()">Leave it</button>'+
  '<button class="btn p" onclick="var v=document.getElementById(\'rn-n\').value.trim();if(v)Pr(\''+id+'\').name=v;closeOv();render()">Save</button></div>');
}
function saveAsTemplate(id){
  var p=Pr(id);if(!p)return;
  dlg('<div class="dh2"><h3>Save as a template</h3><span class="x" onclick="closeOv()">✕</span></div>'+
  '<div class="body"><label>Call it</label><input type="text" id="tp-n" value="'+esc(p.name)+'">'+
  '<div class="helper">A template keeps the project type, the checklist, the links, and the people. It never keeps files, decisions, or the log.</div></div>'+
  '<div class="foot"><button class="btn" onclick="closeOv()">Cancel</button>'+
  '<button class="btn p" onclick="doSaveTemplate(\''+id+'\')">Save it</button></div>');
}
function doSaveTemplate(id){
  var p=Pr(id),name=(document.getElementById('tp-n').value||'').trim();
  if(!p||!name)return;
  S.templates=S.templates||[];
  S.templates.push({id:uid(),name:name,type:p.type,payload:{
    items:(p.items||[]).map(function(x){return {text:x.text,tag:x.tag}}),
    links:(p.links||[]).slice(),
    people:(p.people||[]).map(function(x){return {n:x.n,r:x.r}}),
    notes:p.notes}});
  closeOv();render();toast('<b>'+esc(name)+'</b> is a template now. It shows up when you make a new project.');
}
function applyTemplate(np,tid){
  var t=(S.templates||[]).find(function(x){return x.id===tid});
  if(!t)return np;
  var pay=t.payload||{};
  np.type=t.type||np.type;
  np.items=(pay.items||[]).map(function(x){return {id:uid(),text:x.text,done:false,tag:x.tag||''}});
  np.links=(pay.links||[]).slice();
  np.people=(pay.people||[]).map(function(x){return {id:uid(),n:x.n,r:x.r}});
  if(pay.notes&&!np.notes)np.notes=pay.notes;
  return np;
}
function delTemplate(id){
  S.templates=(S.templates||[]).filter(function(x){return x.id!==id});
  render();toast('Template removed');
}

/* ======================= RECENTLY DELETED (7.5) =======================
   Nothing is gone the moment you delete it. The store keeps a tombstone for
   thirty days, and this is where you get it back from. */

var DELETED=[];
var COLLECTION_NAMES={projects:'Project',ideas:'Idea',library:'Library',files:'File',
  decisions:'Decision',releases:'Release',log_entries:'Log entry',checklist_items:'Checklist item',
  people:'Person',links:'Link',groups:'Group',types:'Project type',inbox:'Inbox',
  activity:'Activity',templates:'Template',stage_history:'Stage span',wait_history:'Past wait'};
function loadDeleted(then){
  if(!BRIDGE)return;
  flushSave();
  setTimeout(function(){
    BRIDGE.recentlyDeleted(function(json){
      var r=JSON.parse(json);
      DELETED=r.ok?r.rows:[];
      if(then)then();else render();
    });
  },260);
}
function restoreDeleted(collection,id){
  if(!BRIDGE)return;
  BRIDGE.restoreDeleted(collection,id,function(json){
    var r=JSON.parse(json);
    if(!r.ok){toast(esc(r.reason));return}
    S=adopt(r.state);
    loadDeleted(function(){render();toast('Put back')});
  });
}
function renderDeletedBox(){
  if(!DELETED.length)
    return '<div class="box"><div class="empty" style="padding:18px">Nothing has been deleted in the last thirty days.</div></div>';
  return '<div class="box plain-list">'+DELETED.slice(0,60).map(function(d){
    return '<div class="row"><span class="k2">'+esc(COLLECTION_NAMES[d.collection]||d.collection)+'</span>'+
    '<div class="grow"><div class="t">'+esc(d.name)+'</div><div class="m">'+
      (d.when?esc(ago(new Date(d.when)))+' ago':'')+'</div></div>'+
    '<button class="btn sm" onclick="restoreDeleted(\''+d.collection+'\',\''+d.id+'\')">Restore</button></div>'}).join('')+'</div>';
}

/* ======================= PEOPLE (7.8) =======================
   Read only, and deliberately thin. A name, a role, and where they turn up. */

function everyone(){
  var by={};
  S.projects.forEach(function(p){(p.people||[]).forEach(function(x){
    var key=(x.n||'').trim().toLowerCase();if(!key)return;
    by[key]=by[key]||{name:x.n,roles:{},projects:[]};
    if(x.r)by[key].roles[x.r]=true;
    by[key].projects.push(p);
  })});
  return Object.keys(by).sort().map(function(k){return by[k]});
}
function renderPeople(){
  var list=everyone();
  return '<div class="view"><div class="crumb"><a onclick="go(\'settings\')">Settings</a> / People</div>'+
  '<div class="hd"><div><h1>People</h1><div class="sub">Everyone named on a project, and where they turn up. Dig is not a contact list, so there is nothing else here.</div></div></div>'+
  '<div class="box">'+(list.length?list.map(function(x){
    return '<div class="row"><span class="pp" style="padding:3px 10px 3px 4px"><span class="av">'+esc(ini(x.name))+'</span>'+esc(x.name)+'</span>'+
    '<div class="grow"><div class="m">'+esc(Object.keys(x.roles).join(', ')||'no role written down')+'</div></div>'+
    '<div class="acts">'+x.projects.map(function(p){
      return '<button class="btn sm ghost" onclick="openP(\''+p.id+'\')">'+esc(p.name)+'</button>'}).join('')+'</div></div>'}).join('')
    :'<div class="empty"><b>Nobody yet</b>Add a reviewer, a client, or a collaborator on any project and they will show up here.</div>')+'</div></div>';
}

/* ======================= NOT PLANNED (7.12) =======================
   What Dig does not do, and why. Decisions, not apologies. */

var NOT_PLANNED=[
  ['Boards and drag and drop','A board makes you arrange work instead of doing it. Stages already say where something is.'],
  ['Due dates on tasks','A date you set yourself is a date you will move. The next step and the days in a stage tell you more.'],
  ['Priorities','With this few projects you know which one matters. A priority field only adds a thing to keep tidy.'],
  ['Assignees','Dig is for one person. People are listed on a project so you know who is involved, not so work can be handed to them.'],
  ['Time tracking','It changes what you do to what is measurable, and it never survives contact with a real week.'],
  ['Money and invoicing','Your accountant has better software than anything that would fit in here.'],
  ['Notifications','Nothing in Dig is urgent enough to interrupt you. Open it when you want to know.'],
  ['Accounts and cloud','There is nothing to sign up for and nothing to leak. Your work is a file in your home folder.'],
  ['AI','Dig writes nothing for you. Everything it shows you is something you told it.']];
var CONSIDERING=[
  ['Encryption at rest with a passphrase','No date, no promise.'],
  ['An Android companion','The sync groundwork is in. The app is not.'],
  ['More file previews','Office formats mainly.']];
function renderNotPlanned(){
  return '<div class="view"><div class="crumb"><a onclick="go(\'settings\')">Settings</a> / Not planned</div>'+
  '<div class="hd"><div><h1>Not planned</h1><div class="sub">What Dig deliberately does not do, and why. These are decisions rather than gaps.</div></div></div>'+
  '<div class="box np">'+NOT_PLANNED.map(function(x){
    return '<div class="row"><div class="grow"><h3>'+esc(x[0])+'</h3><div class="why">'+esc(x[1])+'</div></div></div>'}).join('')+'</div>'+
  '<div class="sec" style="margin-top:26px"><div class="sec-t"><h2>Being considered</h2><span class="help">no dates, no promises</span></div>'+
  '<div class="box np">'+CONSIDERING.map(function(x){
    return '<div class="row"><div class="grow"><h3>'+esc(x[0])+'</h3><div class="why">'+esc(x[1])+'</div></div></div>'}).join('')+'</div></div></div>';
}

/* ======================= BACKUP AND RESTORE (7.9) =======================
   A JSON export is not a backup, because it does not carry the files. This is
   one zip with the whole document and every file it points at. */

function backupEverything(){
  if(!BRIDGE){toast('Backing up needs the app.');return}
  flushSave();
  BRIDGE.backupEverything(JSON.stringify(persist()),function(json){
    var r=JSON.parse(json);
    if(!r.ok){if(r.reason&&r.reason!=='cancelled')toast(esc(r.reason));return}
    toast('Backed up to <b>'+esc(r.name)+'</b>. '+r.projects+' projects and '+r.blobs+' files, '+esc(r.size)+'.');
  });
}
var PENDING_BACKUP=null;
function restoreBackup(){
  if(!BRIDGE)return;
  BRIDGE.chooseBackup(function(json){
    var r=JSON.parse(json);
    if(!r.ok){if(r.reason&&r.reason!=='cancelled')toast(esc(r.reason));return}
    PENDING_BACKUP=r;
    dlg('<div class="dh2"><h3>Restore from this backup?</h3><span class="x" onclick="PENDING_BACKUP=null;closeOv()">✕</span></div><div class="body">'+
    '<div style="font-size:15px;font-weight:500">'+esc(r.name)+'</div>'+
    '<div class="helper">Made '+esc(ago(new Date(r.made_at)))+' ago by Dig '+esc(r.dig||'')+'. It holds '+
      r.projects+' projects, '+r.ideas+' ideas, and '+r.blobs_present+' files.</div>'+
    '<div class="warn">This replaces everything Dig is holding right now: '+S.projects.length+' projects, '+
      S.ideas.length+' ideas, and '+S.library.length+' in the library.</div>'+
    '<div class="ok">Dig takes a backup of what is here first, without being asked.</div>'+
    '<label>Type RESTORE to go ahead</label>'+
    '<input type="text" id="rb-c" placeholder="RESTORE" oninput="document.getElementById(\'rb-go\').disabled=this.value.trim()!==\'RESTORE\'">'+
    '</div><div class="foot"><button class="btn" onclick="PENDING_BACKUP=null;closeOv()">Cancel</button>'+
    '<button class="btn p" id="rb-go" disabled onclick="doRestore()">Restore</button></div>');
  });
}
function doRestore(){
  if(!PENDING_BACKUP||!BRIDGE)return;
  BRIDGE.restoreBackup(JSON.stringify(persist()),function(json){
    var r=JSON.parse(json);
    if(!r.ok){toast(esc(r.reason));return}
    PENDING_BACKUP=null;
    S=adopt(r.state);pickResurf();closeOv();go('home');flushSave();
    toast('Restored. What was here before is kept as <b>'+esc(r.safety)+'</b>.');
  });
}
function pickBackupFolder(){
  if(!BRIDGE)return;
  BRIDGE.chooseBackupFolder(function(json){
    var r=JSON.parse(json);
    if(!r.ok)return;
    S.backupFolder=r.path;if(!S.backupEvery)S.backupEvery='weekly';
    render();toast('Scheduled backups go to that folder from now on.');
  });
}
function runScheduledBackup(){
  if(!BRIDGE||!S.backupFolder||!S.backupEvery)return;
  BRIDGE.scheduledBackup(JSON.stringify(persist()),S.backupFolder,S.backupEvery,function(json){
    var r=JSON.parse(json);
    if(r.ok)toast('Backed up quietly to <b>'+esc(r.name)+'</b>');
    else if(r.reason&&r.reason!=='off'&&r.reason!=='not due')toast(esc(r.reason));
  });
}

/* ======================= CSV IMPORT (7.10) =======================
   Nothing is written until the columns are right and the person has seen what
   the first few rows will become. */

var CSV_KIND='projects',CSV_MAP=null,CSV_INFO=null;
function importCsv(kind){
  if(!BRIDGE)return;
  CSV_KIND=kind;
  BRIDGE.chooseCsv(kind,'',function(json){
    var r=JSON.parse(json);
    if(!r.ok){if(r.reason&&r.reason!=='cancelled')toast(esc(r.reason));return}
    CSV_INFO=r;CSV_MAP=r.mapping;csvDialog();
  });
}
function csvDialog(){
  var r=CSV_INFO;if(!r)return;
  var labels={name:'Name',group:'Group',type:'Type',stage:'Stage',next:'Next step',
              text:'The idea',notes:'Notes'};
  dlg('<div class="dh2"><h3>Import '+esc(r.name||'a CSV')+'</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body">'+
  '<div class="helper">Dig has guessed which column is which. Change any that are wrong.</div>'+
  '<div class="row2" style="grid-template-columns:1fr 1fr">'+r.fields.map(function(f){
    return '<div><label>'+esc(labels[f]||f)+'</label><select onchange="CSV_MAP[\''+f+'\']=parseInt(this.value,10);csvRepreview()">'+
      '<option value="-1">Not in this file</option>'+
      r.header.map(function(h,i){return '<option value="'+i+'"'+(CSV_MAP[f]===i?' selected':'')+'>'+esc(h||('column '+(i+1)))+'</option>'}).join('')+
      '</select></div>'}).join('')+'</div>'+
  '<label>What the first few rows become</label>'+
  '<div class="box" id="csv-prev">'+csvPreviewRows()+'</div>'+
  '<div class="helper">'+r.total+(r.total===1?' row':' rows')+' will come in'+
    (r.skipped?', and '+r.skipped+' with nothing in the first column will be left out':'')+
    '. Groups and types that do not exist yet are created.</div>'+
  '</div><div class="foot"><button class="btn" onclick="closeOv()">Cancel</button>'+
  '<button class="btn p" onclick="doCsvImport()">Bring them in</button></div>');
}
function csvPreviewRows(){
  var r=CSV_INFO;if(!r||!r.rows.length)return '<div class="empty" style="padding:14px">Nothing to show.</div>';
  return r.rows.map(function(row){
    var bits=r.fields.filter(function(f){return row[f]}).map(function(f){return esc(row[f])});
    return '<div class="row"><div class="grow"><div class="t">'+(bits[0]||'<i style="color:var(--ink-3)">no name</i>')+'</div>'+
      '<div class="m">'+bits.slice(1).join(' · ')+'</div></div></div>'}).join('');
}
function csvRepreview(){
  BRIDGE.previewCsv(CSV_KIND,JSON.stringify(CSV_MAP),function(json){
    var r=JSON.parse(json);
    if(!r.ok)return;
    CSV_INFO.rows=r.rows;CSV_INFO.total=r.total;CSV_INFO.skipped=r.skipped;
    var box=document.getElementById('csv-prev');
    if(box)box.innerHTML=csvPreviewRows();
  });
}
function doCsvImport(){
  BRIDGE.readCsv(CSV_KIND,JSON.stringify(CSV_MAP),function(json){
    var r=JSON.parse(json);
    if(!r.ok){toast(esc(r.reason));return}
    var made=0;
    r.rows.forEach(function(row){
      if(CSV_KIND==='ideas'){
        S.ideas.unshift({id:uid(),text:row.text,desc:row.notes||'',at:NOW,opened:null,
          group:groupNamed(row.group)});
        made++;return;
      }
      var gid=groupNamed(row.group)||(S.groups[0]||{}).id||'';
      var t=typeNamed(row.type);
      var stage=0;
      if(row.stage){
        var at=T(t).stages.findIndex(function(s){return s.toLowerCase()===row.stage.toLowerCase()});
        if(at>=0)stage=at;
      }
      S.projects.unshift({id:uid(),name:row.name,group:gid,type:t,stage:stage,enteredAt:NOW,
        when:'next',next:row.next||'',items:[],decisions:[],files:[],links:[],notes:'',
        pub:!G(gid).priv,wait:null,lastAct:NOW,releases:[],people:[],hist:[],logs:[],
        quiet:false,origin:null,parked:false,waitHist:[]});
      made++;
    });
    closeOv();render();
    toast('Brought in '+made+(made===1?' row':' rows')+'.');
  });
}
function groupNamed(name){
  name=(name||'').trim();if(!name)return '';
  var found=S.groups.find(function(g){return g.name.toLowerCase()===name.toLowerCase()});
  if(found)return found.id;
  var made={id:uid(),name:name,color:'#D14A7A',priv:false,description:'',links:[],logs:[],files:[],decisions:[]};
  S.groups.push(made);return made.id;
}
function typeNamed(name){
  name=(name||'').trim();
  if(name){
    var found=S.types.find(function(t){return t.name.toLowerCase()===name.toLowerCase()});
    if(found)return found.id;
    var made={id:uid(),name:name,stages:['Planned','In progress','Done'],check:{}};
    S.types.push(made);return made.id;
  }
  return (S.types[0]||{}).id||'';
}

/* ======================= TEXT SIZE (7.11) ======================= */
var TEXT_SIZES=[['s','Small','13px',.93],['m','Default','14px',1],
  ['l','Large','15.5px',1.11],['xl','Larger','17px',1.21]];
/* The prototype sizes nearly every piece of text itself, in pixels, so setting
   a base size alone would move the sidebar and leave everything else where it
   was. Scaling the whole interface is what 7.11 asks for and is what a person
   means by larger text: the words, the boxes around them, and the space
   between, all in proportion. */
function applyTextSize(){
  var found=TEXT_SIZES.find(function(x){return x[0]===(S.textSize||'m')})||TEXT_SIZES[1];
  document.documentElement.style.setProperty('--base',found[2]);
  document.body.style.fontSize=found[2];
  if(BRIDGE&&BRIDGE.setZoom){BRIDGE.setZoom(found[3])}
  else{document.body.style.zoom=found[3]===1?'':found[3]}
}
function setTextSize(v){S.textSize=v;applyTextSize();render()}
function applyMotionAndSize(){applyTextSize()}

/* ======================= THE COMMAND LINE (7.6) =======================
   `dig add "something"` from a terminal or a keyboard shortcut lands here. */
function fromCommandLine(cmd){
  if(!cmd||!S)return;
  if(cmd.cmd==='open'){
    var want=(cmd.name||'').toLowerCase();
    var p=S.projects.find(function(x){return x.name.toLowerCase()===want})||
          S.projects.find(function(x){return x.name.toLowerCase().indexOf(want)>=0});
    if(p){openP(p.id);toast('Opened <b>'+esc(p.name)+'</b>')}
    else toast('No project called '+esc(cmd.name));
    return;
  }
  if(cmd.cmd!=='add')return;
  var text=(cmd.text||'').trim();if(!text)return;
  var project=null;
  if(cmd.project){
    var want2=cmd.project.toLowerCase();
    project=S.projects.find(function(x){return x.name.toLowerCase()===want2})||
            S.projects.find(function(x){return x.name.toLowerCase().indexOf(want2)>=0});
    if(!project){toast('No project called '+esc(cmd.project)+'. It went to your inbox instead.')}
  }
  var kind=cmd.kind==='auto'?guessType(text):cmd.kind;
  if(kind==='log'&&project){
    addLog('project',project.id,text);
    render();toast('Written in <b>'+esc(project.name)+'</b>\'s log');return;
  }
  if(project&&(kind==='todo'||kind==='bug'||kind==='idea')){
    project.items.unshift({id:uid(),text:text.replace(/^!\s*/,''),done:false,tag:kind==='bug'?'bug':''});
    project.lastAct=NOW;render();toast('Added to <b>'+esc(project.name)+'</b>\'s checklist');return;
  }
  if(kind==='link'||kind==='note'){
    S.library.unshift({id:uid(),kind:kind,title:text,meta:kind==='link'?text:'',
      group:project?project.group:''});
    render();toast('Saved to the Library');return;
  }
  if(kind==='idea'){
    S.ideas.unshift({id:uid(),text:text,desc:'',at:NOW,opened:null,group:''});
    render();toast('Idea saved');return;
  }
  S.inbox.unshift({id:uid(),text:text,type:kind==='log'?'note':kind,at:NOW,guess:project?project.id:null});
  render();toast('Saved to your inbox');
}
window.fromCommandLine=fromCommandLine;

/* ======================= SYNC (5B) =======================
   Off until you turn it on. When it is on it is your own machine answering
   your own devices over your own private network, and nothing else. */

var SYNC={running:false,port:8787,bound:[],reason:'',devices:[],code:null,tailscale:[],log:[]};
var CONFLICTS=[];
function loadSync(then){
  if(!BRIDGE)return;
  BRIDGE.syncStatus(function(json){SYNC=JSON.parse(json);if(then)then();else render()});
}
function syncOn(){
  if(!BRIDGE)return;
  BRIDGE.syncStart(S.syncPort||8787,function(json){
    SYNC=JSON.parse(json);render();
    if(!SYNC.running&&SYNC.reason)toast(esc(SYNC.reason));
    else if(SYNC.running)toast('Sync is on, at '+esc(SYNC.bound.filter(function(a){return a!=='127.0.0.1'}).join(', ')));
  });
}
function syncOff(){
  if(!BRIDGE)return;
  BRIDGE.syncStop(function(json){SYNC=JSON.parse(json);render();toast('Sync is off')});
}
function syncPair(){
  if(!BRIDGE)return;
  BRIDGE.syncPair(function(json){
    var r=JSON.parse(json);
    if(!r.ok){toast(esc(r.reason||'Dig could not make a code.'));return}
    loadSync(function(){
      dlg('<div class="dh2"><h3>Pair a device</h3><span class="x" onclick="closeOv()">✕</span></div>'+
      '<div class="body"><div class="box"><div class="pairbox">'+
        (r.qr?'<div class="qr">'+r.qr+'</div>':'')+
        '<div><div class="code">'+esc(r.code)+'</div>'+
        '<div class="where">'+esc(r.address)+' port '+r.port+'</div>'+
        '<div class="where">Good for five minutes, and only once.</div></div>'+
      '</div></div>'+
      '<div class="helper">Point the other device at the code, or type it in. Both devices have to be on your Tailscale network. Nothing goes through anyone else.</div>'+
      '</div><div class="foot"><button class="btn p" onclick="closeOv()">Done</button></div>');
    });
  });
}
function syncRevoke(id,name){
  if(!BRIDGE)return;
  BRIDGE.syncRevoke(id,function(){loadSync(function(){render();
    toast('<b>'+esc(name||'That device')+'</b> can no longer read anything.')})});
}
function loadConflicts(then){
  if(!BRIDGE)return;
  BRIDGE.syncConflicts(function(json){
    var r=JSON.parse(json);CONFLICTS=r.ok?r.rows:[];
    if(then)then();else render();
  });
}
function dismissConflicts(){
  if(!BRIDGE||!CONFLICTS.length)return;
  BRIDGE.syncConflictsSeen(JSON.stringify(CONFLICTS.map(function(c){return c.id})),function(){
    CONFLICTS=[];render();toast('Cleared')});
}
/* Something arriving from another device redraws the window, and redrawing the
   window empties whatever dialog is open along with anything typed into it. So
   if you are in the middle of something, it waits until you have closed it. */
var WAITING_TO_RELOAD=false;
function somethingIsOpen(){return !!document.querySelector('.overlay.open')}
function reloadFromDisk(){
  if(!BRIDGE)return;
  if(somethingIsOpen()){WAITING_TO_RELOAD=true;return}
  /* Hand over anything still being held before reading the disk back, or a
     change made a moment ago would be read over by what was there before it. */
  flushSave();
  BRIDGE.reload(function(json){
    var r=JSON.parse(json);
    if(!r.ok||!r.state)return;
    var where=S.view,which=S.projectId,tab=S.ptab;
    S=adopt(r.state);S.view=where;S.projectId=which;S.ptab=tab;
    if(BRIDGE.tookDocument)BRIDGE.tookDocument(r.cursor||0);
    render();toast('Something arrived from another device.');
    loadConflicts();
  });
}
function syncStatusLine(){
  if(!SYNC.running)return '';
  return '<div class="syncline on" onclick="go(\'settings\')"><i></i>Sync is on'+
    (SYNC.devices.length?', '+SYNC.devices.filter(function(d){return !d.revoked}).length+' paired':'')+'</div>';
}
function renderSyncSettings(){
  var addresses=SYNC.bound.filter(function(a){return a!=='127.0.0.1'});
  return '<h2>Sync with my other devices</h2>'+
  '<div class="hint">Off by default. When it is on, Dig answers only on loopback and on your Tailscale address, and only devices you have paired can read anything. Nothing passes through anyone else\'s servers.</div>'+
  '<div class="box">'+
  '<div class="srow"><span style="width:110px;color:var(--ink-3)">Server</span><span>'+
    (SYNC.running?'On, at '+esc(addresses.join(', ')||'loopback only')+' port '+SYNC.port
     :(SYNC.tailscale.length?'Off':'Off. There is no Tailscale address on this machine, so it cannot start.'))+
    '</span><span class="sp"></span>'+
    (SYNC.running?'<span class="del" onclick="syncOff()">turn off</span>'
     :'<span class="act" onclick="syncOn()">Turn it on</span>')+'</div>'+
  (SYNC.reason?'<div class="srow"><span style="width:110px;color:var(--ink-3)">Why not</span><span>'+esc(SYNC.reason)+'</span></div>':'')+
  '<div class="srow"><span style="width:110px;color:var(--ink-3)">Port</span>'+
    '<input type="text" value="'+(S.syncPort||8787)+'" onchange="S.syncPort=parseInt(this.value,10)||8787;render()">'+
    '<span class="sp"></span><span style="font-size:12px;color:var(--ink-3)">Takes effect next time it starts.</span></div>'+
  '<div class="srow"><span style="width:110px;color:var(--ink-3)">Devices</span><span>'+
    (SYNC.devices.length?SYNC.devices.filter(function(d){return !d.revoked}).length+' paired':'None paired yet')+
    '</span><span class="sp"></span>'+
    (SYNC.running?'<span class="act" onclick="syncPair()">Pair a device</span>':'')+'</div>'+
  SYNC.devices.map(function(d){
    return '<div class="srow devrow"><span style="width:110px"></span><span>'+esc(d.name)+
      (d.revoked?' <span class="badge rv">revoked</span>':'')+'</span>'+
      '<span class="sp"></span><span style="font-size:12px;color:var(--ink-3)">'+
      (d.last_synced?'last synced '+esc(ago(new Date(d.last_synced)))+' ago':'never synced')+'</span>'+
      (d.revoked?'':'<span class="del" onclick="syncRevoke(\''+d.id+'\','+jsq(d.name)+')">revoke</span>')+'</div>'}).join('')+
  '</div>'+
  (CONFLICTS.length?'<h2>Where two devices disagreed</h2><div class="hint">Nothing was thrown away. These are the versions that lost, kept so you can look.</div>'+
   '<div class="box">'+CONFLICTS.slice(0,20).map(function(c){
     return '<div class="conflict">'+esc(c.reason)+'<div class="m">'+esc(c.collection)+' · '+esc(ago(new Date(c.at)))+' ago</div></div>'}).join('')+
   '<div class="srow"><span class="sp"></span><span class="act" onclick="dismissConflicts()">I have seen these</span></div></div>':'');
}

/* ---- WEEK ---- */
/* ---- YOUR REVIEW (7.2) ----
   The week report, over any period and any scope. Nothing here is invented:
   every line comes from a stage change, a decision, a release, a wait, a file
   that was issued, or something written in a log. */

var PERIODS=[['week','This week'],['lastweek','Last week'],['month','This month'],
             ['lastmonth','Last month'],['quarter','This quarter'],['custom','A range you pick']];

function periodRange(){
  var n=NOW,y=n.getFullYear(),m=n.getMonth();
  var startOfDay=function(d){return new Date(d.getFullYear(),d.getMonth(),d.getDate())};
  var p=S.period||'week';
  if(p==='week')return {from:startOfDay(new Date(n-6*DAY)),to:n,label:'Week of '+longDate(new Date(n-6*DAY))};
  if(p==='lastweek'){var a=startOfDay(new Date(n-13*DAY)),b=new Date(startOfDay(new Date(n-7*DAY)).getTime()+DAY-1);
    return {from:a,to:b,label:'Week of '+longDate(a)}}
  if(p==='month')return {from:new Date(y,m,1),to:n,label:monthName(new Date(y,m,1))};
  if(p==='lastmonth'){var a=new Date(y,m-1,1),b=new Date(y,m,1,0,0,0,-1);
    return {from:a,to:b,label:monthName(a)}}
  if(p==='quarter'){var q=Math.floor(m/3),a=new Date(y,q*3,1);
    return {from:a,to:n,label:'Q'+(q+1)+' '+y}}
  var from=S.periodFrom?new Date(S.periodFrom):new Date(n-30*DAY);
  var to=S.periodTo?new Date(new Date(S.periodTo).getTime()+DAY-1):n;
  return {from:from,to:to,label:longDate(from)+' to '+longDate(to)};
}
function longDate(d){return d.toLocaleDateString('en-US',{month:'long',day:'numeric',year:'numeric'})}
function monthName(d){return d.toLocaleDateString('en-US',{month:'long',year:'numeric'})}
function isoDay(d){var x=new Date(d);return x.getFullYear()+'-'+String(x.getMonth()+1).padStart(2,'0')+'-'+String(x.getDate()).padStart(2,'0')}
function within(at,r){var t=new Date(at);return t>=r.from&&t<=r.to}

function reviewScope(){
  var pub=S.publicOnly;
  var gs=S.groups.filter(function(g){
    if(S.reviewGroup&&S.reviewGroup!=='all'&&g.id!==S.reviewGroup)return false;
    return !pub||!g.priv});
  return {groups:gs,ids:gs.map(function(g){return g.id}),
          hidden:S.groups.filter(function(g){return g.priv}).length};
}

function renderWeek(){
  var r=periodRange(),sc=reviewScope(),ids=sc.ids;
  var inScope=function(gid){return ids.indexOf(gid)>=0};
  var acts=S.activity.filter(function(a){return within(a.at,r)&&inScope(a.group)});
  var k=function(x){return acts.filter(function(a){return a.kind===x})};
  var projects=S.projects.filter(function(p){return inScope(p.group)});
  var waiting=projects.filter(function(p){return p.wait});
  var next=projects.filter(function(p){return !p.wait&&!p.quiet&&!p.parked&&p.next}).slice(0,4);
  var quiet=projects.filter(goneQuiet);
  var releases=[];
  projects.forEach(function(p){(p.releases||[]).forEach(function(x){
    if(within(x.at,r))releases.push({p:p,r:x})})});
  var issued=[];
  projects.forEach(function(p){(p.files||[]).forEach(function(f){
    if((f.version||f.doc_id)&&f.added_at&&within(f.added_at,r))issued.push({p:p,f:f})})});
  sc.groups.forEach(function(g){(g.files||[]).forEach(function(f){
    if((f.version||f.doc_id)&&f.added_at&&within(f.added_at,r))issued.push({g:g,f:f})})});
  var highlights=[];
  projects.forEach(function(p){logsOf(p).forEach(function(e){
    if(e.highlight&&within(e.at,r))highlights.push({p:p,e:e})})});
  sc.groups.forEach(function(g){logsOf(g).forEach(function(e){
    if(e.highlight&&within(e.at,r))highlights.push({g:g,e:e})})});
  highlights.sort(function(a,b){return new Date(b.e.at)-new Date(a.e.at)});

  var li=function(a){return '<li><i style="background:'+G(a.group).color+'"></i>'+esc(a.text)+'<span class="who">'+esc(G(a.group).name)+'</span></li>'};
  var sec=function(t,arr,alt){return '<h4>'+t+'</h4><ul>'+(arr.length?arr.map(li).join(''):'<div class="none">'+alt+'</div>')+'</ul>'};
  var row=function(color,text,right){return '<li><i style="background:'+color+'"></i>'+text+'<span class="who">'+right+'</span></li>'};

  return '<div class="view"><div class="hd"><div><h1>Your review</h1><div class="sub">Written for you from what actually happened. Nothing is made up. Edit it, then share it.</div></div>'+
  '<div class="r"><button class="btn" onclick="S.publicOnly=!S.publicOnly;render()">'+(S.publicOnly?'Hiding private groups ✓':'Including private groups')+'</button>'+
  '<button class="btn p" onclick="savePdfWeek()">Save as PDF</button></div></div>'+

  '<div class="chips"><select onchange="S.period=this.value;render()">'+
    PERIODS.map(function(x){return '<option value="'+x[0]+'"'+((S.period||'week')===x[0]?' selected':'')+'>'+x[1]+'</option>'}).join('')+'</select>'+
  (S.period==='custom'?'<input type="date" value="'+isoDay(r.from)+'" onchange="S.periodFrom=this.value;render()" style="font-size:12.5px;border:1px solid var(--line-2);border-radius:999px;padding:4px 10px;background:var(--panel);color:var(--ink)">'+
   '<input type="date" value="'+isoDay(r.to)+'" onchange="S.periodTo=this.value;render()" style="font-size:12.5px;border:1px solid var(--line-2);border-radius:999px;padding:4px 10px;background:var(--panel);color:var(--ink)">':'')+
  '<span class="chip '+((S.reviewGroup||'all')==='all'?'on':'')+'" onclick="S.reviewGroup=\'all\';render()">Everything</span>'+
  S.groups.map(function(g){return '<span class="chip '+(S.reviewGroup===g.id?'on':'')+'" onclick="S.reviewGroup=\''+g.id+'\';render()"><i style="background:'+g.color+'"></i>'+esc(g.name)+'</span>'}).join('')+'</div>'+

  '<div class="sheet"><div class="top"><div><div class="o">'+esc(S.org||'Your projects')+'</div><div class="w">'+esc(r.label)+
    ((S.reviewGroup&&S.reviewGroup!=='all')?' · '+esc(G(S.reviewGroup).name):'')+'</div></div>'+
    '<div class="w">'+(S.publicOnly?(sc.hidden?sc.hidden+(sc.hidden===1?' private group left out':' private groups left out'):'no private groups to leave out'):'includes private groups')+'</div></div>'+
  '<div class="kpis"><div class="kpi" style="--kc:var(--green)"><div class="l">Shipped</div><div class="v">'+k('ship').length+'</div></div>'+
  '<div class="kpi" style="--kc:var(--blue)"><div class="l">Moved forward</div><div class="v">'+k('move').length+'</div></div>'+
  '<div class="kpi" style="--kc:var(--teal)"><div class="l">Decisions made</div><div class="v">'+k('decision').length+'</div></div>'+
  '<div class="kpi" style="--kc:var(--amber)"><div class="l">Waiting on others</div><div class="v">'+waiting.length+'</div></div></div>'+
  sec('Shipped',k('ship'),'Nothing shipped in this period.')+
  sec('Moved forward',k('move'),'No stage changes in this period.')+
  sec('Decided',k('decision'),'No decisions recorded in this period.')+
  '<h4>Released</h4><ul>'+(releases.length?releases.map(function(x){
    return row(G(x.p.group).color,esc(x.p.name)+' '+esc(x.r.v)+(x.r.note?' · '+esc(x.r.note):''),esc(fmt(new Date(x.r.at))))}).join('')
    :'<div class="none">Nothing was released in this period.</div>')+'</ul>'+
  '<h4>Files issued</h4><ul>'+(issued.length?issued.map(function(x){
    var owner=x.p||x.g;
    return row(G(x.p?x.p.group:x.g.id).color,esc(x.f.name)+(x.f.version?' · '+esc(x.f.version):'')+(x.f.doc_id?' · '+esc(x.f.doc_id):''),esc(owner.name))}).join('')
    :'<div class="none">No documents were issued in this period.</div>')+'</ul>'+
  '<h4>Log highlights</h4><ul>'+(highlights.length?highlights.map(function(x){
    var owner=x.p||x.g;
    return row(G(x.p?x.p.group:x.g.id).color,esc(x.e.text),esc(owner.name))}).join('')
    :'<div class="none">Nothing was marked as a highlight in this period.</div>')+'</ul>'+
  '<h4>Waiting on</h4><ul>'+(waiting.length?waiting.map(function(p){
    return row(G(p.group).color,esc(p.wait.what),days(p.wait.since)+' days')}).join('')
    :'<div class="none">Nothing is waiting on anyone else.</div>')+'</ul>'+
  (quiet.length?'<h4>Gone quiet</h4><ul>'+quiet.map(function(p){
    return row(G(p.group).color,esc(p.name),days(p.lastAct)+' days')}).join('')+'</ul>':'')+
  '<h4>Next</h4><ul>'+(next.length?next.map(function(p){
    return row(G(p.group).color,esc(p.next),esc(p.name))}).join('')
    :'<div class="none">No next steps set.</div>')+'</ul>'+
  '<div class="ft"><span>Made by Dig from stage changes, decisions, releases, waits, files, and your log.</span><span>If nothing moved, it says so.</span></div></div></div>';
}

/* ---- IDEAS ---- */
function renderIdeas(){
  var list=S.ideas.slice().sort(function(a,b){return S.ideaSort==='oldest'?a.at-b.at:b.at-a.at});if(S.filterGroup!=='all')list=list.filter(function(x){return x.group===S.filterGroup});
  return '<div class="view wide"><div class="hd"><div><h1>Ideas</h1><div class="sub">Things you might make one day. No stage, no deadline. Start one when you\'re ready.</div></div><div class="r"><button class="btn p" onclick="openCap(\'idea\')">Add an idea</button></div></div>'+
  '<div class="chips"><span class="chip '+(S.filterGroup==='all'?'on':'')+'" onclick="setGroup(\'all\')">All</span>'+S.groups.map(function(g){return '<span class="chip '+(S.filterGroup===g.id?'on':'')+'" onclick="setGroup(\''+g.id+'\')"><i style="background:'+g.color+'"></i>'+esc(g.name)+'</span>'}).join('')+'<span class="sp"></span><select onchange="S.ideaSort=this.value;render()"><option value="oldest" '+(S.ideaSort==='oldest'?'selected':'')+'>Oldest first</option><option value="newest" '+(S.ideaSort==='newest'?'selected':'')+'>Newest first</option></select></div>'+
  (list.length?'<div class="grid3">'+list.map(function(x){return '<div class="ic2"><div class="t">'+esc(x.text)+'</div><div class="d">'+esc(x.desc)+'</div><div class="m"><span>'+ago(x.at)+' ago'+(x.group?' · '+esc(G(x.group).name):'')+'</span><span class="bs"><button class="btn sm ghost" onclick="openIdea(\''+x.id+'\')">Open</button><button class="btn sm p" onclick="startIdea(\''+x.id+'\')">Start</button></span></div></div>'}).join('')+'</div>':'<div class="box empty"><b>No ideas here yet</b>Press Ctrl K and type one. That\'s all it takes.</div>')+'</div>';
}

/* ---- LIBRARY ---- */
function libraryRows(){
  /* Links and notes are library entries; unowned files are file records. Both
     read as one list, with the same chips. */
  var rows=S.library.map(function(x){return {id:x.id,kind:x.kind,title:x.title,meta:x.meta,group:x.group,entry:x}});
  (S.libraryFiles||[]).forEach(function(f){
    rows.push({id:f.id,kind:'file',title:f.name,meta:fileLine(f),group:'',file:f})});
  return rows;
}
function renderLibrary(){
  var list=libraryRows().filter(function(x){return S.libFilter==='all'||(S.libFilter==='unsorted'?!x.group:x.kind===S.libFilter)});
  return '<div class="view"><div class="hd"><div><h1>Library</h1><div class="sub">Links, notes, and files worth keeping. Paste a link into "Add something" and it lands here.</div></div><div class="r"><button class="btn" onclick="addFiles(\'\',\'\')">Add files</button><button class="btn p" onclick="openCap(\'link\')">Add a link or note</button></div></div>'+
  '<div class="chips">'+[['all','Everything'],['link','Links'],['note','Notes'],['file','Files'],['unsorted','Not in a group']].map(function(x){return '<span class="chip '+(S.libFilter===x[0]?'on':'')+'" onclick="S.libFilter=\''+x[0]+'\';render()">'+x[1]+'</span>'}).join('')+'</div>'+
  '<div class="box lib">'+(list.length?list.map(function(x){var open=x.kind==='link'?'openLink('+jsq(x.meta||x.title)+')':(x.kind==='file'?'openFile(\''+x.id+'\')':'');return '<div class="row'+(open?' click':'')+'"'+(open?' onclick="'+open+'"':'')+'><span class="k '+x.kind+'">'+x.kind.toUpperCase()+'</span><div class="grow"><div class="t">'+esc(x.title)+'</div><div class="m">'+esc(x.meta)+'</div></div><span class="w">'+(x.group?esc(G(x.group).name):'no group')+'<a onclick="event.stopPropagation();'+(x.file?'moveFile(\''+x.id+'\')':'openSortLib(\''+x.id+'\')')+'">'+(x.group?'move':'put in a project or group')+'</a></span></div>'}).join(''):'<div class="empty"><b>Nothing here yet</b>Links, notes, and files you add will show up here. Drop a file anywhere on this page.</div>')+'</div></div>';
}

/* ---- SETTINGS ---- */
function renderSettings(){
  return '<div class="view"><div class="hd"><div><h1>Settings</h1><div class="sub">Change anything here and the app reshapes itself right away.</div></div></div><div class="set">'+
  '<h2>You</h2><div class="box"><div class="srow"><span style="color:var(--ink-3);width:110px">Organization</span><input type="text" value="'+esc(S.org)+'" onchange="S.org=this.value;render()"></div><div class="srow"><span style="color:var(--ink-3);width:110px">Your name</span><input type="text" value="'+esc(S.you)+'" onchange="S.you=this.value;render()"></div></div>'+
  '<h2>Groups</h2><div class="hint">Groups keep projects together and give them a color. A private group never shows up in anything you share.</div><div class="box">'+S.groups.map(function(g){return '<div class="srow"><input type="color" value="'+g.color+'" onchange="G(\''+g.id+'\').color=this.value;render()"><input type="text" value="'+esc(g.name)+'" onchange="G(\''+g.id+'\').name=this.value;render()"><span class="sp"></span><span class="tog '+(g.priv?'on':'')+'" onclick="G(\''+g.id+'\').priv=!G(\''+g.id+'\').priv;render()">'+(g.priv?'private':'shareable')+'</span><span class="del" onclick="delGroup(\''+g.id+'\')">remove</span></div>'}).join('')+'<div class="srow"><span class="act" onclick="addGroup()">+ add a group</span></div></div>'+
  '<h2>Project types and their stages</h2><div class="hint">Every project has a type. A type decides which stages it moves through and what each stage\'s checklist suggests.</div>'+
  S.types.map(function(t){return '<div class="box" style="margin-bottom:10px"><div class="srow"><input type="text" value="'+esc(t.name)+'" onchange="T(\''+t.id+'\').name=this.value;render()" style="font-weight:600"><span class="sp"></span><span style="font-size:12px;color:var(--ink-3)">'+S.projects.filter(function(p){return p.type===t.id}).length+' projects</span><span class="del" onclick="delType(\''+t.id+'\')">remove</span></div><div class="stages-ed">'+t.stages.map(function(s,i){return '<span class="stg-chip"><span style="font-family:var(--mono);font-size:10px;color:var(--ink-3)">'+(i+1)+'</span><input value="'+esc(s)+'" onchange="renameStage(\''+t.id+'\','+i+',this.value)"><span class="x" onclick="delStage(\''+t.id+'\','+i+')">✕</span></span>'}).join('')+'<span class="stg-chip add" onclick="addStage(\''+t.id+'\')">+ stage</span></div><div class="exp">'+t.stages.map(function(s){var e=t.check[s]||[];return '<div class="stg-name">'+esc(s)+' checklist suggests</div>'+e.map(function(x,ei){return '<div class="e"><span>· '+esc(x)+'</span><span class="x" onclick="delExp('+jsq(t.id)+','+jsq(s)+','+ei+')">remove</span></div>'}).join('')+'<div class="e"><input placeholder="Add something the '+esc(s)+' stage usually needs…" onkeydown="if(event.key===\'Enter\'){addExp('+jsq(t.id)+','+jsq(s)+',this.value);this.value=\'\'}"></div>'}).join('')+'</div></div>'}).join('')+
  '<div class="box"><div class="srow"><span class="act" onclick="addType()">+ add a type</span></div></div>'+
  renderSyncSettings()+
  '<h2>Getting started</h2><div class="box"><div class="srow"><span style="width:110px;color:var(--ink-3)">Setup</span><span>Walk through the welcome again. It only adds what is missing.</span><span class="sp"></span><span class="act" onclick="S.obStep=1;go(\'setup\')">Run setup again</span></div>'+
  (hasExamples()?'<div class="srow"><span style="width:110px;color:var(--ink-3)">Examples</span><span>The example projects, ideas, and notes Dig added so you could look around.</span><span class="sp"></span><span class="act" onclick="removeExamples()">Remove the examples</span></div>':'')+
  '</div>'+
  '<h2>Templates</h2><div class="hint">A template is the shape of a project you make often: its type, its checklist, its links, and its people.</div><div class="box">'+
  ((S.templates||[]).length?S.templates.map(function(t){
    return '<div class="srow"><span>'+esc(t.name)+'</span><span class="sp"></span><span style="font-size:12px;color:var(--ink-3)">'+esc((T(t.type)||{name:'no type'}).name)+' · '+((t.payload&&t.payload.items)||[]).length+' checklist items</span><span class="del" onclick="delTemplate(\''+t.id+'\')">remove</span></div>'}).join('')
    :'<div class="empty" style="padding:18px">No templates yet. Save one from any project, under More.</div>')+'</div>'+
  '<h2>Recently deleted</h2><div class="hint">Everything you delete waits here for thirty days before it goes for good.</div>'+
  renderDeletedBox()+
  '<h2>People</h2><div class="box"><div class="srow"><span style="width:110px;color:var(--ink-3)">Everyone</span><span>Every name on any project, and where they turn up.</span><span class="sp"></span><span class="act" onclick="go(\'people\')">Open the list</span></div></div>'+
  '<h2>Appearance</h2><div class="box"><div class="srow"><span style="width:110px;color:var(--ink-3)">Theme</span><div class="theme">'+['light','dark','system'].map(function(m){return '<button class="'+(S.theme===m?'on':'')+'" onclick="setTheme(\''+m+'\')">'+(m==='system'?'Follow system':m[0].toUpperCase()+m.slice(1))+'</button>'}).join('')+'</div></div><div class="srow"><span style="width:110px;color:var(--ink-3)">Text size</span><div class="textsize">'+TEXT_SIZES.map(function(x){return '<button class="'+((S.textSize||'m')===x[0]?'on':'')+'" onclick="setTextSize(\''+x[0]+'\')">'+x[1]+'</button>'}).join('')+'</div></div>'+
  '<div class="srow"><span style="width:110px;color:var(--ink-3)">Motion</span><span>Follows your system\'s reduce-motion setting.</span></div></div>'+
  '<h2>Your data</h2><div class="box"><div class="srow"><span style="width:110px;color:var(--ink-3)">Where it lives</span><span style="font-family:var(--mono);font-size:12px">'+esc(DATA_PATH)+'</span><span class="sp"></span><span class="act" onclick="openDataFolder()">Open folder</span></div><div class="srow"><span style="width:110px;color:var(--ink-3)">Backup</span><span>Everything, including your files, as one zip.</span><span class="sp"></span><span class="act" onclick="backupEverything()">Back up everything…</span><span class="act" onclick="restoreBackup()">Restore…</span></div>'+
  '<div class="srow"><span style="width:110px;color:var(--ink-3)">Scheduled</span><span>'+(S.backupFolder?'Every '+esc(S.backupEvery==='daily'?'day':'week')+' into '+esc(S.backupFolder)+', keeping the last ten.':'Off. Dig can put a quiet backup somewhere when one is due.')+'</span><span class="sp"></span>'+(S.backupFolder?'<span class="act" onclick="S.backupEvery=S.backupEvery===\'daily\'?\'weekly\':\'daily\';render()">'+esc(S.backupEvery==='daily'?'Make it weekly':'Make it daily')+'</span><span class="del" onclick="S.backupFolder=\'\';render()">turn off</span>':'<span class="act" onclick="pickBackupFolder()">Choose a folder</span>')+'</div>'+
  '<div class="srow"><span style="width:110px;color:var(--ink-3)">Just the text</span><span>The document on its own as JSON. It does not carry your files, so it is not a backup.</span><span class="sp"></span><span class="act" onclick="exportData()">Export</span><span class="act" onclick="importData()">Import</span></div>'+
  '<div class="srow"><span style="width:110px;color:var(--ink-3)">From a CSV</span><span>Projects or ideas somebody else\'s tool wrote out.</span><span class="sp"></span><span class="act" onclick="importCsv(\'projects\')">Projects…</span><span class="act" onclick="importCsv(\'ideas\')">Ideas…</span></div><div class="srow"><span style="width:110px;color:var(--ink-3)">Internet</span><span>Dig makes no outbound internet requests of any kind. There are no accounts and no cloud. Sync is off by default, and when you turn it on it is a direct connection between your own devices on your own private network, with nothing passing through anyone else\'s servers.</span></div><div class="srow"><span style="width:110px;color:var(--ink-3)">License</span><span>Free and open source, AGPLv3 · <a style="color:var(--blue);cursor:pointer" onclick="openAbout()">About Dig</a></span></div></div>'+
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
/* ======================= ONBOARDING =======================
   Five steps, run once on a machine Dig has not seen. It can be run again from
   Settings, which only ever adds what is missing and never touches anything
   that is already here. */

var OB_STEPS=5;
function renderSetup(){
  var step=Math.min(Math.max(S.obStep||1,1),OB_STEPS);
  var dots='<div class="dots">'+[1,2,3,4,5].map(function(n){
    return '<i class="'+(n===step?'on':(n<step?'done':''))+'"></i>'}).join('')+'</div>';
  return '<div class="view"><div class="ob">'+dots+'<div class="body">'+obBody(step)+'</div>'+obFoot(step)+'</div></div>';
}
function obBody(step){
  if(step===1)return '<div class="eyebrow">Welcome</div>'+
    '<h1 style="font-size:28px;font-weight:600;letter-spacing:-.025em;margin-top:6px">Dig keeps every project you\'re working on in one place.</h1>'+
    '<div class="three">'+
      '<div><i></i><span><b>What stage each one is at.</b> Every project moves through stages you decide on.</span></div>'+
      '<div><i></i><span><b>What its next step is.</b> One line saying the thing that moves it forward.</span></div>'+
      '<div><i></i><span><b>What you decided along the way.</b> Numbered, dated, and kept.</span></div>'+
    '</div>'+
    '<div class="plain">Dig makes no outbound internet requests of any kind. There are no accounts and no cloud. Sync is off by default, and when you turn it on it is a direct connection between your own devices on your own private network, with nothing passing through anyone else\'s servers.</div>';

  if(step===2)return '<div class="eyebrow">Who this is for</div>'+
    '<h1 style="font-size:24px;font-weight:600;letter-spacing:-.025em;margin-top:6px">What should Dig call this?</h1>'+
    '<p class="lede">Both of these are optional, and both are easy to change later in Settings.</p>'+
    '<label>Your name, or your company</label>'+
    '<input type="text" id="ob-org" value="'+esc(S.org)+'" placeholder="Example Studio" oninput="S.org=this.value">'+
    '<label>What to call you in the greeting</label>'+
    '<input type="text" id="ob-you" value="'+esc(S.you)+'" placeholder="Your first name" oninput="S.you=this.value">'+
    '<div class="plain">Leave them blank and Dig will simply say good morning.</div>';

  if(step===3){
    var w=S.setupWork;
    var opts=[['apps','Apps or software','Things you build and release'],
      ['clients','Client work','Projects you do for other people'],
      ['content','Content','Videos, writing, a podcast, a channel'],
      ['personal','Personal projects','Home, finances, things for yourself'],
      ['programs','Programs or events','Ongoing efforts, campaigns, a gala']];
    return '<div class="eyebrow">What you work on</div>'+
      '<h1 style="font-size:24px;font-weight:600;letter-spacing:-.025em;margin-top:6px">What kinds of things do you work on?</h1>'+
      '<p class="lede">This picks sensible groups, project types, and stages for you.</p>'+
      '<div class="pick">'+opts.map(function(o){
        return '<div class="pk '+(w[o[0]]?'on':'')+'" onclick="S.setupWork.'+o[0]+'=!S.setupWork.'+o[0]+';render()">'+
        '<div class="bx"></div><div><div class="h">'+o[1]+'</div><div class="p">'+o[2]+'</div></div></div>'}).join('')+'</div>'+
      '<div class="preview">'+obPreview()+'</div>'+
      '<div class="plain">Every group, type, stage, and checklist below can be changed later in Settings.</div>';
  }

  if(step===4)return '<div class="eyebrow">Start</div>'+
    '<h1 style="font-size:24px;font-weight:600;letter-spacing:-.025em;margin-top:6px">Start empty, or look around first?</h1>'+
    '<p class="lede">If you would rather see how it all fits together before putting your own work in, Dig can add a handful of examples you can throw away in one click.</p>'+
    '<div class="pick" style="grid-template-columns:1fr">'+
      '<div class="pk '+(!S.obExamples?'on':'')+'" onclick="S.obExamples=false;render()"><div class="bx"></div>'+
        '<div><div class="h">Start empty</div><div class="p">Nothing is created. Add your first project when you are ready.</div></div></div>'+
      '<div class="pk '+(S.obExamples?'on':'')+'" onclick="S.obExamples=true;render()"><div class="bx"></div>'+
        '<div><div class="h">Add a few examples to look around</div><div class="p">Four projects across two groups, some ideas, one thing waiting, and a file. Settings has a button that removes every one of them.</div></div></div>'+
    '</div>';

  return '<div class="eyebrow">Three things to know</div>'+
    '<h1 style="font-size:24px;font-weight:600;letter-spacing:-.025em;margin-top:6px">That is everything.</h1>'+
    '<div class="three">'+
      '<div><i></i><span><b>Ctrl K adds anything, from anywhere.</b> An idea, a to-do, a bug, a note, a link. Dig works out where it goes.</span></div>'+
      '<div><i></i><span><b>Projects move through stages, and you decide when.</b> Nothing advances on its own and nothing is ever overdue.</span></div>'+
      '<div><i></i><span><b>Nothing leaves this computer.</b> Dig makes no outbound internet requests of any kind. Sync is off by default, and when you turn it on it is a direct connection between your own devices on your own private network.</span></div>'+
    '</div>'+
    '<div class="plain"><a style="color:var(--blue);cursor:pointer" onclick="openKeys()">See all shortcuts</a></div>';
}
function obPreview(){
  var picks=SETUP_PICKS.filter(function(x){return S.setupWork[x[0]]});
  if(!picks.length)return '<span class="none">Nothing picked, so Dig will make one group called <b>Projects</b> and one project type, <b>Task</b>, with the stages Planned, In progress, Done.</span>';
  return 'Dig will make '+picks.map(function(x){
    var g=SETUP_GROUPS[x[1]],t=SETUP_TYPES[x[2]];
    return 'a group called <b>'+esc(g.name)+'</b>'+(g.priv?' (private)':'')+
      ' and a project type <b>'+esc(t.name)+'</b> that moves through '+t.stages.map(esc).join(' → ');
  }).join(', and ')+'.';
}
function obFoot(step){
  return '<div class="ob-foot">'+
    (step>1?'<button class="btn" onclick="obGo('+(step-1)+')">Back</button>':'')+
    '<span class="sp"></span>'+
    (step<OB_STEPS?'<span class="skip" onclick="obSkip()">Skip the rest</span>':'')+
    '<button class="btn p" onclick="'+(step<OB_STEPS?'obGo('+(step+1)+')':'obFinish()')+'">'+
      (step<OB_STEPS?'Continue':'Open Dig')+' →</button></div>';
}
function obGo(n){S.obStep=n;render()}
function obSkip(){S.obStep=OB_STEPS;render()}
function obFinish(){
  finishSetup();
  if(S.obExamples)addExamples();
  S.startHere={added:false,captured:false,nextStep:false,gone:false};
  render();
}

/* ---- the examples, which are nobody's real work ---- */
function addExamples(){
  if(S.projects.some(function(p){return p.example}))return;
  /* Each example goes in the group it would obviously belong to, if that
     group exists, and in the first group otherwise. Taking the first two
     groups regardless put a kitchen renovation in with the clients. */
  var pick=function(id,fallback){
    return S.groups.find(function(g){return g.id===id})||fallback||S.groups[0]};
  var gWork=pick('apps');
  var gClient=pick('clients',gWork);
  var gHome=pick('personal',S.groups.filter(function(g){return g.priv})[0]||S.groups[1]);
  /* One type across all four, so the examples read as one coherent pipeline
     using whichever stages this person actually chose. */
  var t=S.types[0],t2=t;
  var day=function(n){return new Date(NOW-n*DAY)};
  var mk=function(name,g,type,stage,days,when,next,notes){
    return {id:uid(),name:name,group:g.id,type:type.id,stage:Math.min(stage,type.stages.length-1),
      enteredAt:day(days),when:when,next:next,items:[],decisions:[],files:[],links:[],notes:notes||'',
      pub:!g.priv,wait:null,lastAct:day(days),releases:[],people:[],hist:[],logs:[],
      quiet:false,origin:null,parked:false,waitHist:[],example:true}};

  var wr=mk('Website refresh',gWork,t,1,6,'now','Agree the page list','Lead with the speed improvement.');
  wr.items=[{id:uid(),text:'Write down what the site is for',done:true,tag:''},
            {id:uid(),text:'Old gallery page still 404s',done:false,tag:'bug'}];
  wr.decisions=[{id:uid(),no:1,text:'Keep the existing content structure. Rewriting it would double the timeline for no measurable gain.',at:day(5),supersedes:null,superseded:false}];
  wr.logs=[{id:uid(),text:'Walked the current site with fresh eyes. Most of it is fine; it is the speed that is the problem.',at:day(4),stage:t.stages[1]||'',highlight:true}];
  wr.people=[{id:uid(),n:'Client',r:'approver'}];
  wr.links=['example.com'];

  var nco=mk('New client onboarding',gClient,t,0,3,'next','','');
  nco.wait={what:'the signed agreement',since:day(3)};

  var qr=mk('Quarterly report',gWork,t2,1,9,'now','Pull the numbers for section two','');
  qr.decisions=[{id:uid(),no:2,text:'Report in the same format as last quarter so the numbers stay comparable.',at:day(2),supersedes:null,superseded:false}];

  var kr=mk('Kitchen renovation',gHome,t2,0,14,'later','Measure the alcove before ordering','Nothing gets ordered before the measurements are checked twice.');

  S.projects.unshift(kr,qr,nco,wr);
  S.ideas.unshift(
    {id:uid(),text:'A better way to file receipts',desc:'One folder, one naming rule, done at the end of each month.',at:day(3),opened:null,group:'',example:true},
    {id:uid(),text:'Weekly walking route map',desc:'Somewhere new every week, within an hour of home.',at:day(30),opened:null,group:'',example:true},
    {id:uid(),text:'A short guide for new clients',desc:'What to expect, in one page, sent before the first call.',at:day(90),opened:null,group:'',example:true},
    {id:uid(),text:'Recipe box that actually gets used',desc:'Only the ones already cooked twice.',at:day(140),opened:day(60),group:'',example:true});
  pickResurf();
  S.inbox.unshift({id:uid(),text:'Send the revised page list',type:'todo',at:day(0.2),guess:wr.id,example:true});
  S.library.unshift({id:uid(),kind:'note',title:'The sentence that explains the work',
    meta:'"Fewer pages, faster, and easier to update." Use it in every proposal.',group:gWork.id,example:true});
  S.activity.unshift(
    {id:uid(),group:gWork.id,pid:wr.id,text:'Website refresh: D-0001 recorded',at:day(5),kind:'decision',example:true},
    {id:uid(),group:gWork.id,pid:wr.id,text:'Website refresh moved forward',at:day(6),kind:'move',example:true});
  scheduleSave();
}
function hasExamples(){
  return S.projects.some(function(x){return x.example})||S.ideas.some(function(x){return x.example})||
         S.inbox.some(function(x){return x.example})||S.library.some(function(x){return x.example})||
         (S.libraryFiles||[]).some(function(x){return x.example});
}
function removeExamples(){
  var n=0,drop=function(list){return (list||[]).filter(function(x){if(x.example){n++;return false}return true})};
  S.projects=drop(S.projects);S.ideas=drop(S.ideas);S.inbox=drop(S.inbox);
  S.library=drop(S.library);S.libraryFiles=drop(S.libraryFiles);S.activity=drop(S.activity);
  if(S.resurfId&&!S.ideas.some(function(x){return x.id===S.resurfId}))pickResurf();
  render();toast('Took out '+n+' example records. Everything you made yourself is untouched.');
}

/* ---- Start here, for the first session only ---- */
function startHereCard(){
  var s=S.startHere;
  if(!s||s.gone)return '';
  var done=[s.added,s.captured,s.nextStep];
  if(done.every(function(x){return x}))return '';
  var row=function(ok,text){return '<div class="step'+(ok?' ok':'')+'"><span class="bx"></span>'+text+'</div>'};
  return '<div class="starthere"><div class="top"><b>Start here</b>'+
    '<span style="font-size:12.5px;color:var(--ink-3)">three things, then this goes away</span>'+
    '<span class="x" onclick="dismissStartHere()">Dismiss</span></div>'+
    row(s.added,'Add your first project')+
    row(s.captured,'Capture something with <kbd>Ctrl K</kbd>')+
    row(s.nextStep,'Give a project its next step')+
    '</div>';
}
function dismissStartHere(){if(S.startHere){S.startHere.gone=true;render()}}
function tickStartHere(which){
  if(S.startHere&&!S.startHere.gone&&!S.startHere[which]){S.startHere[which]=true}
}

/* ---- OVERLAYS ---- */
function renderOverlays(){
  var popts='<option value="">Inbox (decide later)</option>'+S.projects.filter(function(p){return !p.parked}).map(function(p){return '<option value="'+p.id+'" '+(S.capProject===p.id?'selected':'')+'>'+esc(p.name)+'</option>'}).join('');
  var types=[['auto','Let Dig guess'],['idea','Idea'],['todo','To-do'],['bug','Bug'],['note','Note'],['link','Link'],['decision','Decision']];
  return '<div class="overlay" id="ov-cap" onclick="if(event.target===this)closeOv()"><div class="dlg"><input class="cap-in" id="cap-in" placeholder="Type anything. An idea, a to-do, a bug, a note, a link…" oninput="capDetect()" onkeydown="if(event.key===\'Enter\')doCapture()"><div class="types" id="cap-types">'+types.map(function(t){return '<span class="ty '+(t[0]==='auto'?'auto':'')+' '+(S.capType===t[0]?'on':'')+'" data-t="'+t[0]+'" onclick="S.capType=\''+t[0]+'\';capDetect()">'+t[1]+'</span>'}).join('')+'</div><div class="cap-row"><span>Put it in</span><select id="cap-p" onchange="S.capProject=this.value;capDetect()">'+popts+'</select><span id="cap-as" style="color:var(--ink-3)"></span><span class="hint"><kbd>↵</kbd> save <kbd>Esc</kbd> close</span></div></div></div>'+
  '<div class="overlay" id="ov-pal" onclick="if(event.target===this)closeOv()"><div class="dlg"><input class="cap-in" id="pal-in" placeholder="Find a project, idea, link, note, or decision…" oninput="palFilter(this.value)" onkeydown="palKey(event)"><div class="pal-list" id="pal-list"></div></div></div>'+
  '<div class="overlay" id="ov-dlg" onclick="if(event.target===this)closeOv()"><div class="dlg" id="dlg-body"></div></div>';
}
function dlg(html){document.getElementById('dlg-body').innerHTML=html;document.getElementById('ov-dlg').classList.add('open');wireA11y();var f=document.querySelector('#dlg-body input[type=text],#dlg-body textarea,#dlg-body select');if(f)setTimeout(function(){f.focus()},10);
  if(VIEWING&&document.getElementById('viewer-stage')){var v=fileById(VIEWING);if(v)setTimeout(function(){fillViewer(v)},0)}}
function closeOv(){
  document.querySelectorAll('.overlay').forEach(function(o){o.classList.remove('open')});
  if(WAITING_TO_RELOAD){WAITING_TO_RELOAD=false;setTimeout(reloadFromDisk,0)}
}
function openKeys(){dlg('<div class="dh2"><h3>Keyboard shortcuts</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body"><div class="keys"><div><span>Add something</span><kbd>Ctrl K</kbd></div><div><span>Find anything</span><kbd>/</kbd></div><div><span>Home</span><kbd>1</kbd></div><div><span>Projects</span><kbd>2</kbd></div><div><span>Roadmap</span><kbd>3</kbd></div><div><span>Ideas</span><kbd>4</kbd></div><div><span>Library</span><kbd>5</kbd></div><div><span>Your review</span><kbd>6</kbd></div><div><span>Close anything</span><kbd>Esc</kbd></div><div><span>This card</span><kbd>?</kbd></div></div></div><div class="foot"><button class="btn p" onclick="closeOv()">Got it</button></div>')}

/* ======================= ACTIONS ======================= */
function go(v){S.view=v;render();if(v==='settings'){loadDeleted();loadSync();loadConflicts()}}
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
  tickStartHere('captured');
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
function openNew(gid,from){
  if(!S.types.length){toast('Add a project type in Settings first. Every project moves through one.');return}
  dlg('<div class="dh2"><h3>'+(from?'Start this idea as a project':'New project')+'</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body"><label>Name</label><input type="text" id="np-n" value="'+esc(from?from.text:'')+'" placeholder="What is it called?"><div class="row2"><div><label>Group</label><select id="np-g">'+S.groups.map(function(g){return '<option value="'+g.id+'" '+(gid===g.id?'selected':'')+'>'+esc(g.name)+'</option>'}).join('')+'</select></div><div><label>Type</label><select id="np-t">'+S.types.map(function(t){return '<option value="'+t.id+'">'+esc(t.name)+' · '+t.stages.join(' → ')+'</option>'}).join('')+'</select></div></div>'+
    ((S.templates||[]).length?'<label>Start from a template</label><select id="np-tpl"><option value="">Start from nothing</option>'+S.templates.map(function(t){return '<option value="'+t.id+'">'+esc(t.name)+'</option>'}).join('')+'</select>':'')+'<div class="row2"><div><label>First next step</label><input type="text" id="np-x" placeholder="The first thing that moves it forward"></div><div><label>On the roadmap</label><select id="np-w">'+HZ.map(function(h){return '<option value="'+h[0]+'" '+(h[0]==='next'?'selected':'')+'>'+h[1]+'</option>'}).join('')+'</select></div></div><div class="helper">It starts at the first stage of its type. Its group decides whether it can be shared.</div></div><div class="foot"><button class="btn" onclick="closeOv()">Cancel</button><button class="btn p" onclick="createP('+(from?"'"+from.id+"'":'null')+')">Create</button></div>')}
function createP(fromId){var n=document.getElementById('np-n').value.trim();if(!n)return;var gid=document.getElementById('np-g').value,tid=document.getElementById('np-t').value;
  if(!tid||!S.types.some(function(t){return t.id===tid})){toast('Add a project type in Settings first. Every project moves through one.');return}var np={id:uid(),name:n,group:gid,type:tid,stage:0,enteredAt:NOW,when:document.getElementById('np-w').value,next:document.getElementById('np-x').value,items:[],decisions:[],files:[],links:[],notes:'',pub:!G(gid).priv,wait:null,lastAct:NOW,releases:[],people:[],hist:[],quiet:false,origin:null,parked:false,waitHist:[]};var tplEl=document.getElementById('np-tpl');
  if(tplEl&&tplEl.value)np=applyTemplate(np,tplEl.value);
  if(fromId){var x=S.ideas.find(function(y){return y.id===fromId});np.origin=x.text;np.notes=x.desc;S.ideas=S.ideas.filter(function(y){return y.id!==fromId});if(S.resurfId===fromId)pickResurf()}S.projects.unshift(np);log(np,n+' started','move');tickStartHere('added');closeOv();S.ptab='work';openP(np.id);toast('<b>'+esc(n)+'</b> is a project now')}
/* stages */
function openAdvance(id){var p=Pr(id),ns=nextStage(p),un=unmet(p);dlg('<div class="dh2"><h3>Move '+esc(p.name)+' to '+esc(ns)+'</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body"><div style="color:var(--ink-2)">You\'ve been in <b>'+esc(stageName(p))+'</b> for '+days(p.enteredAt)+' days.</div>'+(un.length?'<div class="warn">A few things from this stage\'s checklist aren\'t done yet:<ul>'+un.map(function(e){return '<li>'+esc(e)+'</li>'}).join('')+'</ul></div>':'<div class="ok">Everything on this stage\'s checklist is done. Nice.</div>')+'<label>Next step in '+esc(ns)+'</label><input type="text" id="adv-x" placeholder="Optional, but it helps tomorrow-you"></div><div class="foot"><button class="btn" onclick="closeOv()">Not yet</button><button class="btn p" onclick="doAdvance(\''+id+'\')">'+(un.length?'Move anyway':'Move to '+esc(ns))+'</button></div>')}
/* What the last stage move changed, so Undo can put back exactly that and
   nothing else. Without it, Undo removed whichever activity happened to be
   newest and left the horizon and the next step where the move had put them. */
var LAST_ADVANCE=null;
function doAdvance(id){var p=Pr(id);
  var before={stage:p.stage,enteredAt:p.enteredAt,next:p.next,when:p.when,quiet:p.quiet};
  p.hist.push({stage:stageName(p),from:p.enteredAt,to:NOW});p.stage++;p.enteredAt=NOW;
  var nx=document.getElementById('adv-x').value;p.next=nx||'';
  var shipped=/release|ship|close|done/i.test(stageName(p));
  log(p,p.name+' moved to '+stageName(p),shipped?'ship':'move');
  var logged=S.activity[0];
  if(isLast(p)){p.quiet=true;p.when='done'}
  LAST_ADVANCE={id:id,before:before,logged:logged};
  closeOv();render();toast('<b>'+esc(p.name)+'</b> is now in '+esc(stageName(p))+'.',"undoAdvance('"+id+"')")}
function undoAdvance(id){var p=Pr(id),u=LAST_ADVANCE;
  if(!p||!u||u.id!==id){toast('That move is no longer the one to put back');return}
  p.hist.pop();
  p.stage=u.before.stage;p.enteredAt=u.before.enteredAt;p.next=u.before.next;
  p.when=u.before.when;p.quiet=u.before.quiet;
  S.activity=S.activity.filter(function(a){return a!==u.logged});
  LAST_ADVANCE=null;render();toast('Put back')}
function jumpStage(id,i){var p=Pr(id);if(i===p.stage)return;if(i===p.stage+1){openAdvance(id);return}if(i>p.stage)p.hist.push({stage:stageName(p),from:p.enteredAt,to:NOW});p.stage=i;p.enteredAt=NOW;p.quiet=isLast(p);if(p.quiet)p.when='done';log(p,p.name+' set to '+stageName(p),'move');render();toast('Now in '+esc(stageName(p)))}
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
function addPerson(id){dlg('<div class="dh2"><h3>Add a person</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body"><div class="row2"><div><label>Name</label><input type="text" id="pn" placeholder="Who"></div><div><label>Role</label><input type="text" id="pr" placeholder="reviewer, client, collaborator"></div></div><div class="helper">Just a name and a role. Dig is not a contact list.</div></div><div class="foot"><button class="btn" onclick="closeOv()">Cancel</button><button class="btn p" onclick="var n=document.getElementById(\'pn\').value.trim();if(n){Pr(\''+id+'\').people.push({n:n,r:document.getElementById(\'pr\').value})};closeOv();render()">Add</button></div>')}
function addRelease(id){dlg('<div class="dh2"><h3>Record a release</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body"><div class="row2"><div><label>Version</label><input type="text" id="rv" placeholder="1.2.0"></div><div><label>What\'s in it</label><input type="text" id="rn" placeholder="One line"></div></div><div class="helper">Dated today. Shows up on the project\'s roadmap and in Your review.</div></div><div class="foot"><button class="btn" onclick="closeOv()">Cancel</button><button class="btn p" onclick="doRelease(\''+id+'\')">Record</button></div>')}
function doRelease(id){var v=document.getElementById('rv').value.trim();if(!v)return;var p=Pr(id);p.releases.push({v:v,at:NOW,note:document.getElementById('rn').value});log(p,p.name+' '+v+' released','ship');closeOv();render();toast('<b>'+esc(p.name)+' '+esc(v)+'</b> is on the record')}
/* share */
/* The preview for a group says what the page will hold, in the group's own
   words, so nothing about it is a surprise once it is a file. */
function openShareGroup(g){
  if(!g)return;
  var mine=S.projects.filter(function(p){return p.group===g.id});
  var live=mine.filter(function(p){return !p.parked});
  var decisions=mine.reduce(function(n,p){
    return n+p.decisions.filter(function(d){return !d.superseded}).length},0);
  var releases=mine.reduce(function(n,p){return n+p.releases.length},0);
  dlg('<div class="dh2"><h3>Share '+esc(g.name)+'</h3>'+
  '<span class="x" onclick="closeOv()">✕</span></div><div class="body">'+
  '<div class="share-prev" style="--gc:'+g.color+'">'+
    '<div class="h">'+esc(g.name)+'</div>'+
    '<div class="s">'+esc(S.org||'Dig')+' · '+live.length+
      (live.length===1?' project':' projects')+'</div>'+
    '<div class="row3"><div><b>'+live.length+'</b><small>projects</small></div>'+
    '<div><b>'+decisions+'</b><small>decisions</small></div>'+
    '<div><b>'+releases+'</b><small>releases</small></div></div>'+
    '<div style="color:var(--ink-2)">'+
      (g.priv?'This group is private, so the page says that and shows nothing else.'
            :(esc(g.description)||'No description yet.'))+'</div>'+
  '</div></div><div class="foot">'+
  '<span class="l">Saves a PDF, made on this computer.</span>'+
  '<button class="btn" onclick="closeOv()">Close</button>'+
  '<button class="btn p" onclick="doShare('+jsq('g:'+g.id)+')">Save</button></div>');
}
function openShare(id){
  if(id&&String(id).indexOf('g:')===0)return openShareGroup(G(String(id).slice(2)));
  var p=id&&id!=='rm'?Pr(id):null;var pubP=S.projects.filter(function(y){return y.pub&&!G(y.group).priv});var isRm=id==='rm';dlg('<div class="dh2"><h3>'+(p?'Share '+esc(p.name):(isRm?'Share the roadmap':'Share your projects'))+'</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body"><div class="share-prev">'+(p?'<div class="h">'+esc(p.name)+'</div><div class="s">'+esc(T(p.type).name)+' · '+esc(G(p.group).name)+' · '+esc(stageName(p))+'</div><div class="row3"><div><b>'+(p.stage+1)+' of '+T(p.type).stages.length+'</b><small>stages</small></div><div><b>'+p.items.filter(function(x){return x.done}).length+'</b><small>done</small></div><div><b>'+p.releases.length+'</b><small>releases</small></div></div><div style="color:var(--ink-2)">'+(esc(p.notes)||'No notes yet.')+'</div>':'<div class="h">'+esc(S.org)+(isRm?' · Roadmap':'')+'</div><div class="s">'+pubP.length+' shareable projects · '+S.groups.filter(function(g){return g.priv}).length+' private groups left out</div><div class="row3">'+(isRm?HZ.slice(0,3).map(function(h){return '<div><b>'+pubP.filter(function(y){return (y.when||'later')===h[0]}).length+'</b><small>'+h[1]+'</small></div>'}).join(''):'<div><b>'+S.projects.filter(function(y){return !y.quiet&&!y.parked}).length+'</b><small>active</small></div><div><b>'+S.activity.filter(function(a){return a.kind==='ship'&&days(a.at)<=90}).length+'</b><small>shipped this quarter</small></div><div><b>'+S.projects.reduce(function(s,y){return s+y.decisions.length},0)+'</b><small>decisions on record</small></div>')+'</div><div style="color:var(--ink-2)">Private groups never appear here. The page says so at the bottom.</div>')+'</div></div><div class="foot"><span class="l">Saves a PDF or an image, made on this computer.</span><button class="btn" onclick="closeOv()">Close</button><button class="btn p" onclick="doShare('+(id?jsq(id):'null')+')">Save</button></div>')}
/* settings */
function addGroup(){S.groups.push({id:uid(),name:'New group',color:'#D14A7A',priv:false});render()}
function delGroup(id){if(S.projects.some(function(p){return p.group===id})){toast('Move its projects to another group first');return}S.groups=S.groups.filter(function(g){return g.id!==id});render()}
function addType(){S.types.push({id:uid(),name:'New type',stages:['Start','Middle','Done'],check:{}});render()}
function delType(id){if(S.projects.some(function(p){return p.type===id})){toast('Some projects use this type');return}
  if(S.types.length<=1){toast('Keep at least one project type');return}S.types=S.types.filter(function(t){return t.id!==id});render()}
function renameStage(tid,i,val){var t=T(tid);var old=t.stages[i];t.stages[i]=val;if(t.check[old]){t.check[val]=t.check[old];delete t.check[old]}render()}
function delStage(tid,i){var t=T(tid);if(t.stages.length<=2){toast('A type needs at least two stages');return}var n=t.stages[i];t.stages.splice(i,1);delete t.check[n];S.projects.forEach(function(p){if(p.type===tid&&p.stage>=t.stages.length)p.stage=t.stages.length-1});render()}
function addStage(tid){T(tid).stages.push('New stage');render()}
function addExp(tid,st,val){val=val.trim();if(!val)return;var t=T(tid);(t.check[st]=t.check[st]||[]).push(val);render()}
function delExp(tid,st,i){T(tid).check[st].splice(i,1);render()}

/* ---- About ---- */
var ABOUT_LINKS=[
  ['YouTube','https://youtube.com/@kamsiob','youtube.com/@kamsiob'],
  ['GitHub','https://github.com/kamsiob','github.com/kamsiob'],
  ['Website','https://kamsiob.com','kamsiob.com'],
  ['Buy Me a Coffee','https://buymeacoffee.com/kamsiob','buymeacoffee.com/kamsiob'],
  ['Telegram','https://t.me/+g5LKm9rUnNcxMjk5','t.me/+g5LKm9rUnNcxMjk5'],
  ['Feedback','mailto:hello@kamsiob.com','hello@kamsiob.com']];
var ABOUT_MARK='<svg viewBox="0 0 512 512" width="24" height="24"><g fill="#fff"><rect x="112" y="304" width="76" height="96" rx="26"/><rect x="218" y="216" width="76" height="184" rx="26"/><rect x="324" y="112" width="76" height="288" rx="26"/></g></svg>';
function openAbout(){
  dlg('<div class="dh2"><h3>About Dig</h3><span class="x" onclick="closeOv()">✕</span></div><div class="body">'+
  '<div style="display:flex;align-items:center;gap:14px"><span style="width:44px;height:44px;border-radius:13px;background:var(--blue);box-shadow:inset 0 1px 0 rgba(255,255,255,.3),0 6px 16px rgba(36,87,245,.3);display:flex;align-items:center;justify-content:center;flex-shrink:0">'+ABOUT_MARK+'</span>'+
  '<div><div style="font-size:16px;font-weight:600;letter-spacing:-.02em">Dig '+esc(VERSION)+'</div>'+
  '<div style="font-size:12.5px;color:var(--ink-3);margin-top:2px">Free and open source, AGPLv3.</div></div></div>'+
  '<div class="plain" style="margin-top:14px;font-size:12.5px;color:var(--ink-3);border-left:2px solid var(--line-2);padding-left:12px;line-height:1.55">Dig makes no outbound internet requests of any kind. There are no accounts and no cloud. Sync is off by default, and when you turn it on it is a direct connection between your own devices on your own private network, with nothing passing through anyone else\'s servers.</div>'+
  '<label>Kamsiob</label><div class="box">'+ABOUT_LINKS.map(function(l){
    return '<div class="row click" onclick="openLink('+jsq(l[1])+')"><div class="grow"><div class="t">'+esc(l[0])+'</div><div class="m">'+esc(l[2])+'</div></div></div>'}).join('')+'</div>'+
  '<div class="ok" style="margin-top:14px">Built and carried by one person. If software made this way matters to you, there\'s a place to stand behind it. Either way, it\'s yours.</div>'+
  '<div class="helper" style="margin-top:12px"><a style="color:var(--blue);cursor:pointer" onclick="closeOv();go(\'notplanned\')">What Dig deliberately does not do</a></div>'+
  '</div><div class="foot"><span class="l">Local only, always.</span><button class="btn" onclick="closeOv()">Close</button><button class="btn p" onclick="openLink(\'https://buymeacoffee.com/kamsiob\')">Support this work</button></div>');
}

/* ======================= FILES =======================
   Every file lives in the blob store, kept once by its SHA256. A record points
   at the bytes and carries the name, the document id, the version, and which
   stage it belongs to. Moving a file between owners is a change to the record,
   never a copy. */

function allFiles(){
  var out=[];
  S.projects.forEach(function(p){(p.files||[]).forEach(function(f){out.push(f)})});
  S.groups.forEach(function(g){(g.files||[]).forEach(function(f){out.push(f)})});
  (S.libraryFiles||[]).forEach(function(f){out.push(f)});
  return out;
}
function fileById(id){return allFiles().find(function(f){return f.id===id})}
function ownerFiles(f){
  if(f.project_id){var p=Pr(f.project_id);return p?p.files:[]}
  if(f.group_id){var g=S.groups.find(function(x){return x.id===f.group_id});return g?g.files:[]}
  return S.libraryFiles||[];
}
function fileHome(pid,gid){
  if(pid){var p=Pr(pid);if(p){p.files=p.files||[];return p.files}}
  if(gid){var g=S.groups.find(function(x){return x.id===gid});if(g){g.files=g.files||[];return g.files}}
  S.libraryFiles=S.libraryFiles||[];return S.libraryFiles;
}
function fileSize(n){var v=Number(n)||0,u=['bytes','KB','MB','GB'];
  for(var i=0;i<u.length;i++){if(v<1024||i===3)return (i?v.toFixed(1).replace(/\.0$/,''):Math.round(v))+' '+u[i];v/=1024}}
function fileLine(f){
  var bits=[];
  if(f.doc_id)bits.push(f.doc_id);
  if(f.version)bits.push(f.version);
  bits.push(fileSize(f.size));
  return bits.join(' · ');
}

/* ---- getting them in ---- */
function addFiles(pid,gid){
  if(!BRIDGE){toast('Adding files needs the app.');return}
  BRIDGE.pickFiles(pid||'',gid||'',function(json){takeFiles(JSON.parse(json),pid,gid)});
}
function takeFiles(r,pid,gid){
  if(!r.ok){if(r.reason&&r.reason!=='cancelled')toast(esc(r.reason));return}
  var home=fileHome(pid,gid),added=0,clashes=[],first='';
  r.files.forEach(function(rec){
    rec.id=uid();rec.doc_id='';rec.version='';rec.descr='';rec.stage='';
    rec.previous_file_id=null;rec.superseded=false;
    var clash=home.find(function(x){return x.name===rec.name&&!x.superseded});
    if(clash){clashes.push({rec:rec,clash:clash,pid:pid,gid:gid});return}
    home.unshift(rec);added++;if(!first)first=rec.name;
  });
  if(pid&&Pr(pid))Pr(pid).lastAct=NOW;
  render();
  (r.refused||[]).forEach(function(n){toast('Dig could not take in <b>'+esc(n)+'</b>')});
  (r.large||[]).forEach(function(n){toast('<b>'+esc(n)+'</b> is a big file. It is kept, but it will make backups slow.')});
  if(added)toast(added===1?'Kept a copy of <b>'+esc(first)+'</b>':'Kept copies of '+added+' files');
  /* Asking comes after the re-render, because rendering rebuilds the overlays. */
  PENDING_CLASHES=clashes;
  askAboutClash();
}
var PENDING_CLASHES=[];
var PENDING_FILE=null;
function askAboutClash(){
  PENDING_FILE=PENDING_CLASHES.shift()||null;
  var f=PENDING_FILE;if(!f)return;
  dlg('<div class="dh2"><h3>There is already a file called that</h3><span class="x" onclick="skipClash()">✕</span></div>'+
  '<div class="body"><div style="font-size:15px;font-weight:500">'+esc(f.rec.name)+'</div>'+
  '<div class="helper">The one here is '+esc(fileLine(f.clash))+'. The new one is '+esc(fileSize(f.rec.size))+'.</div>'+
  '<div class="helper">Nothing is ever written over. Either keep both, or keep the old one on the record as the version before this.</div></div>'+
  '<div class="foot"><button class="btn" onclick="skipClash()">Cancel</button>'+
  '<button class="btn" onclick="resolveClash(\'both\')">Keep both</button>'+
  '<button class="btn p" onclick="resolveClash(\'version\')">Replace as a new version</button></div>');
}
function skipClash(){PENDING_FILE=null;closeOv();if(PENDING_CLASHES.length)askAboutClash()}
function resolveClash(how){
  var f=PENDING_FILE;if(!f)return;PENDING_FILE=null;
  var home=fileHome(f.pid,f.gid);
  if(how==='version'){
    f.rec.previous_file_id=f.clash.id;
    f.rec.doc_id=f.clash.doc_id||'';
    f.clash.superseded=true;
  }else{
    var stem=f.rec.name.replace(/(\.[^.]+)$/,''),ext=(f.rec.name.match(/\.[^.]+$/)||[''])[0],n=2;
    while(home.some(function(x){return x.name===stem+' ('+n+')'+ext}))n++;
    f.rec.name=stem+' ('+n+')'+ext;
  }
  home.unshift(f.rec);
  if(BRIDGE)BRIDGE.rememberMime(f.rec.sha256,f.rec.mime||'');
  if(f.pid&&Pr(f.pid))Pr(f.pid).lastAct=NOW;
  closeOv();render();
  toast(how==='version'?'<b>'+esc(f.rec.name)+'</b> is the current version. The one before it is kept.':'Kept as <b>'+esc(f.rec.name)+'</b>');
  if(PENDING_CLASHES.length)askAboutClash();
}

/* ---- dropping and pasting ---- */
var DROP_DEPTH=0;
function dropTarget(){
  if(S.view==='project'&&S.projectId)return {pid:S.projectId,gid:''};
  if(S.view==='group'&&S.groupId)return {pid:'',gid:S.groupId};
  if(S.view==='library')return {pid:'',gid:''};
  return null;
}
function wireDropping(){
  document.addEventListener('dragenter',function(e){
    if(!dropTarget()||!e.dataTransfer||Array.prototype.indexOf.call(e.dataTransfer.types||[],'Files')<0)return;
    e.preventDefault();DROP_DEPTH++;showVeil(true)});
  document.addEventListener('dragover',function(e){if(dropTarget())e.preventDefault()});
  document.addEventListener('dragleave',function(){if(DROP_DEPTH>0)DROP_DEPTH--;if(!DROP_DEPTH)showVeil(false)});
  document.addEventListener('drop',function(e){
    var where=dropTarget();DROP_DEPTH=0;showVeil(false);
    if(!where||!e.dataTransfer)return;
    e.preventDefault();
    var paths=[];
    for(var i=0;i<e.dataTransfer.files.length;i++){
      var f=e.dataTransfer.files[i];
      if(f.path)paths.push(f.path);
    }
    if(!paths.length){
      var uris=e.dataTransfer.getData('text/uri-list')||'';
      uris.split(/\r?\n/).forEach(function(u){
        if(u&&u.indexOf('file://')===0)paths.push(decodeURIComponent(u.slice(7)))});
    }
    if(!paths.length){toast('Dig could not tell what was dropped. Use Add files.');return}
    if(BRIDGE)BRIDGE.addPaths(JSON.stringify(paths),where.pid,where.gid,function(json){
      takeFiles(JSON.parse(json),where.pid,where.gid)});
  });
  document.addEventListener('paste',function(e){
    var where=dropTarget();if(!where||!e.clipboardData)return;
    var items=e.clipboardData.items||[];
    for(var i=0;i<items.length;i++){
      if(items[i].kind!=='file')continue;
      var blob=items[i].getAsFile();if(!blob)continue;
      e.preventDefault();
      var reader=new FileReader();
      reader.onload=function(){
        var stamp=new Date().toISOString().slice(0,19).replace('T',' ').replace(/:/g,'-');
        var ext=(blob.type.split('/')[1]||'bin').replace(/[^a-z0-9]/gi,'');
        BRIDGE.addPasted('Pasted '+stamp+'.'+ext,reader.result,where.pid,where.gid,function(json){
          takeFiles(JSON.parse(json),where.pid,where.gid)});
      };
      reader.readAsDataURL(blob);
      return;
    }
  });
}
function showVeil(on){
  var v=document.getElementById('drop-veil');
  if(v)v.classList.toggle('on',!!on);
}

/* ---- the viewer ---- */
var VIEWING=null;
function openFile(id){
  var f=fileById(id);if(!f)return;
  VIEWING=id;
  var siblings=ownerFiles(f).filter(function(x){return !x.superseded}),
      at=siblings.findIndex(function(x){return x.id===id});
  var stages=[''];
  if(f.project_id){var p=Pr(f.project_id);if(p)stages=stages.concat(T(p.type).stages)}
  var older=f.previous_file_id?fileById(f.previous_file_id):null;

  document.getElementById('dlg-body').className='dlg viewer';
  dlg('<div class="vh"><div class="grow"><h3>'+esc(f.name)+'</h3>'+
      '<div class="m"><span class="badge g">'+esc(f.type||'FILE')+'</span>'+esc(fileSize(f.size))+
      (f.added_at?' · added '+esc(fmt(new Date(f.added_at))):'')+'</div></div>'+
      '<div class="nav"><button onclick="stepFile(-1)"'+(at<=0?' disabled':'')+'>←</button>'+
      '<button onclick="stepFile(1)"'+(at>=siblings.length-1?' disabled':'')+'>→</button></div>'+
      '<span class="x" onclick="closeViewer()" style="cursor:pointer;color:var(--ink-3);font-size:16px">✕</span></div>'+
    '<div class="fields">'+
      '<div><label>Document id</label><input type="text" value="'+esc(f.doc_id)+'" placeholder="Optional" onchange="editFile(\''+f.id+'\',\'doc_id\',this.value)"></div>'+
      '<div><label>Version</label><input type="text" value="'+esc(f.version)+'" placeholder="v1.0" onchange="editFile(\''+f.id+'\',\'version\',this.value)"></div>'+
      '<div><label>Description</label><input type="text" value="'+esc(f.descr)+'" placeholder="One line" onchange="editFile(\''+f.id+'\',\'descr\',this.value)"></div>'+
      '<div><label>Stage</label><select onchange="editFile(\''+f.id+'\',\'stage\',this.value)">'+
        stages.map(function(s){return '<option value="'+esc(s)+'"'+(f.stage===s?' selected':'')+'>'+(s?esc(s):'Not tied to a stage')+'</option>'}).join('')+
      '</select></div></div>'+
    '<div class="stage" id="viewer-stage"><div class="none">Opening…</div></div>'+
    (older?'<div class="vers">This replaced <b>'+esc(older.name)+'</b>, '+esc(fileLine(older))+'.<a onclick="openFile(\''+older.id+'\')">Open the one before</a></div>':'')+
    '<div class="vfoot"><button class="btn" onclick="openWithSystem(\''+f.id+'\')">Open with the system app</button>'+
      '<button class="btn" onclick="saveFileCopy(\''+f.id+'\')">Save a copy…</button>'+
      '<button class="btn ghost" onclick="revealFile(\''+f.id+'\')">Reveal in folder</button>'+
      '<span class="sp"></span>'+
      '<button class="btn ghost" onclick="moveFile(\''+f.id+'\')">Move to…</button>'+
      '<button class="btn ghost danger" onclick="deleteFile(\''+f.id+'\')">Delete</button></div>');
}
var TEXT_KINDS=['md','markdown','json','csv','log','txt','text','py','js','ts','css','html',
  'htm','yml','yaml','toml','sh','ini','conf','cfg','xml','svg','sql','rs','go','java','c','h','cpp'];
function isTextFile(f){
  var mime=(f.mime||'').toLowerCase(),ext=(f.type||'').toLowerCase();
  if(mime.indexOf('text/')===0)return true;
  if(mime==='application/json'||mime==='application/xml')return true;
  return TEXT_KINDS.indexOf(ext)>=0;
}
/* The stage is filled once Python has handed back a path for the bytes, or the
   text itself for a text file. Nothing in the page ever sees the blob store. */
function fillViewer(f){
  var stage=document.getElementById('viewer-stage');
  if(!stage)return;
  if(!f.sha256){stage.innerHTML='<div class="none"><b>Dig does not have these bytes</b>The record is here, the file is not.</div>';return}
  if(!BRIDGE){stage.innerHTML='<div class="none">Viewing needs the app.</div>';return}
  if(isTextFile(f)){
    BRIDGE.readText(f.sha256,function(json){
      var r=JSON.parse(json);
      var box=document.getElementById('viewer-stage');
      if(!box||VIEWING!==f.id)return;
      if(!r.ok){box.innerHTML='<div class="none">'+esc(r.reason)+'</div>';return}
      box.innerHTML='<div class="text">'+textBody(f,r.text)+'</div>';
    });
    return;
  }
  BRIDGE.viewUrl(f.sha256,f.name,function(url){
    var box=document.getElementById('viewer-stage');
    if(!box||VIEWING!==f.id)return;
    if(!url){box.innerHTML='<div class="none">Dig could not open those bytes.</div>';return}
    var mime=(f.mime||'').toLowerCase();
    if(mime.indexOf('image/')===0)
      box.innerHTML='<img src="'+esc(url)+'" alt="'+esc(f.name)+'" onclick="this.classList.toggle(\'full\')">';
    else if(mime==='application/pdf')
      box.innerHTML='<embed src="'+esc(url)+'" type="application/pdf">';
    else if(mime.indexOf('video/')===0)
      box.innerHTML='<video src="'+esc(url)+'" controls></video>';
    else if(mime.indexOf('audio/')===0)
      box.innerHTML='<audio src="'+esc(url)+'" controls></audio>';
    else
      box.innerHTML='<div class="none"><b>No preview for this kind of file</b>Dig keeps it safely and hands it to whatever opens it.</div>';
  });
}
function textBody(f,text){
  var ext=(f.type||'').toLowerCase();
  if(ext==='csv')return csvTable(text);
  if(ext==='md'||ext==='markdown')
    return '<div style="padding:10px 16px 0"><span class="chip" onclick="toggleMd(this)">Show it as written</span></div>'+
           '<div class="md">'+esc(text)+'</div>';
  return '<pre>'+text.split(/\r?\n/).map(function(line,i){
    return '<span class="ln">'+(i+1)+'</span>'+esc(line)}).join('\n')+'</pre>';
}
function toggleMd(chip){
  var box=chip.parentNode.nextElementSibling;
  if(!box)return;
  var raw=box.getAttribute('data-raw')||box.textContent;
  box.setAttribute('data-raw',raw);
  if(chip.textContent==='Show it as written'){
    chip.textContent='Show it rendered';
    box.innerHTML='<pre style="padding:0">'+esc(raw)+'</pre>';
  }else{chip.textContent='Show it as written';box.textContent=raw}
}
function csvTable(text){
  var rows=text.split(/\r?\n/).filter(function(l){return l.length}).slice(0,400);
  return '<table>'+rows.map(function(line,i){
    var cells=line.split(',');
    return '<tr>'+cells.map(function(c){
      return (i?'<td>':'<th>')+esc(c.replace(/^"|"$/g,''))+(i?'</td>':'</th>')}).join('')+'</tr>'}).join('')+'</table>';
}
function stepFile(by){
  var f=fileById(VIEWING);if(!f)return;
  var siblings=ownerFiles(f).filter(function(x){return !x.superseded}),
      at=siblings.findIndex(function(x){return x.id===VIEWING});
  var next=siblings[at+by];
  if(next)openFile(next.id);
}
function closeViewer(){VIEWING=null;var b=document.getElementById('dlg-body');if(b)b.className='dlg';closeOv()}
function editFile(id,field,value){
  var f=fileById(id);if(!f)return;f[field]=value;scheduleSave();
}
function openWithSystem(id){var f=fileById(id);if(f&&BRIDGE)BRIDGE.openBlob(f.sha256,function(ok){if(!ok)toast('Dig does not have those bytes anymore.')})}
function revealFile(id){var f=fileById(id);if(f&&BRIDGE)BRIDGE.revealBlob(f.sha256,function(ok){if(!ok)toast('Dig does not have those bytes anymore.')})}
function saveFileCopy(id){
  var f=fileById(id);if(!f||!BRIDGE)return;
  BRIDGE.saveCopy(f.sha256,f.name,function(json){var r=JSON.parse(json);
    if(!r.ok){if(r.reason&&r.reason!=='cancelled')toast(esc(r.reason));return}
    toast('Saved <b>'+esc(r.name)+'</b>')});
}
function saveAllFiles(pid,gid){
  var list=fileHome(pid,gid).filter(function(f){return f.sha256});
  if(!list.length){toast('There are no files to save.');return}
  var name=pid&&Pr(pid)?slug(Pr(pid).name):(gid?slug(G(gid).name):'library-files');
  if(BRIDGE)BRIDGE.saveAllFiles(JSON.stringify(list),name,function(json){
    var r=JSON.parse(json);
    if(!r.ok){if(r.reason&&r.reason!=='cancelled')toast(esc(r.reason));return}
    toast('Saved '+r.count+' files into <b>'+esc(r.name)+'</b>')});
}
function moveFile(id){
  var f=fileById(id);if(!f)return;
  dlg('<div class="dh2"><h3>Move this file</h3><span class="x" onclick="closeOv()">✕</span></div>'+
  '<div class="body"><div style="font-weight:500;margin-bottom:8px">'+esc(f.name)+'</div>'+
  '<label>Put it with</label><select id="mv-to">'+
    '<option value="lib">The Library, in no project</option>'+
    S.groups.map(function(g){return '<option value="g:'+g.id+'"'+(f.group_id===g.id?' selected':'')+'>'+esc(g.name)+' (the group)</option>'}).join('')+
    S.projects.map(function(p){return '<option value="p:'+p.id+'"'+(f.project_id===p.id?' selected':'')+'>'+esc(p.name)+'</option>'}).join('')+
  '</select><div class="helper">The bytes do not move. Only where the file is filed.</div></div>'+
  '<div class="foot"><button class="btn" onclick="closeOv()">Cancel</button>'+
  '<button class="btn p" onclick="doMoveFile(\''+id+'\')">Move it</button></div>');
}
function doMoveFile(id){
  var f=fileById(id);if(!f)return;
  var to=document.getElementById('mv-to').value;
  var from=ownerFiles(f);
  var at=from.findIndex(function(x){return x.id===id});
  if(at>=0)from.splice(at,1);
  f.project_id=null;f.group_id=null;f.stage='';
  if(to.indexOf('p:')===0)f.project_id=to.slice(2);
  else if(to.indexOf('g:')===0)f.group_id=to.slice(2);
  fileHome(f.project_id,f.group_id).unshift(f);
  VIEWING=null;closeOv();render();toast('<b>'+esc(f.name)+'</b> moved');
}
function deleteFile(id){
  var f=fileById(id);if(!f)return;
  var home=ownerFiles(f);
  var at=home.findIndex(function(x){return x.id===id});
  if(at<0)return;
  var copy=home[at];
  home.splice(at,1);
  VIEWING=null;closeOv();render();
  toast('<b>'+esc(copy.name)+'</b> deleted. It is in Recently deleted for 30 days.',
        "undoDeleteFile("+jsq(JSON.stringify(copy))+")");
}
function undoDeleteFile(json){
  try{var f=JSON.parse(json)}catch(e){return}
  fileHome(f.project_id,f.group_id).unshift(f);
  render();toast('Put back');
}

/* ---- PDF exports ----
   Rendered by the web engine from the same classes the screen uses, always in
   the light palette, with the bundled Geist. Private groups never appear in an
   overview, and every export says what was left out. */
function pdfSafe(){return S.projects.filter(function(p){return p.pub&&!G(p.group).priv})}
function omitted(){
  var g=S.groups.filter(function(x){return x.priv}).length;
  var p=S.projects.filter(function(x){return !x.pub&&!G(x.group).priv}).length;
  var bits=[];
  if(g)bits.push(g+(g===1?' private group':' private groups'));
  if(p)bits.push(p+(p===1?' private project':' private projects'));
  return bits.length?bits.join(' and ')+' left out':'Nothing was left out'}
function pdfTop(title,sub){return '<div class="pdf-top"><div><div class="o">'+esc(S.org||'Dig')+'</div><div class="w">'+esc(sub)+'</div></div><div class="w">'+esc(title)+'</div></div>'}
function pdfFoot(left){return '<div class="pdf-foot"><span>'+left+'</span><span>Made by Dig, on this computer.</span></div>'}
function slug(s){return String(s).toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'')||'dig'}

function savePdfWeek(){
  var el=document.querySelector('.sheet');
  if(!el){toast('Open Your review first.');return}
  sendPdf(el.outerHTML,'your-week.pdf');
}
function doShare(id){
  var body,name;
  if(id&&String(id).indexOf('g:')===0){var g=G(String(id).slice(2));if(!g)return;
    body=pdfGroup(g);name=slug(g.name)+'.pdf'}
  else if(id&&id!=='rm'){var p=Pr(id);if(!p)return;body=pdfProject(p);name=slug(p.name)+'.pdf'}
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
/* One group on one page: what it is, where each project has got to, what was
   decided, and what shipped. A private group says so and shows nothing else,
   the same rule the rest of the sharing follows. */
function pdfGroup(g){
  var mine=S.projects.filter(function(p){return p.group===g.id});
  var live=mine.filter(function(p){return !p.parked});
  if(g.priv)return pdfTop(esc(g.name),'A private group')+
    '<div class="box empty"><b>This group is private</b>'+
    'A private group never leaves this computer, so there is nothing to share.</div>'+
    pdfFoot('Private groups never appear in anything shared.');
  var decisions=[];
  mine.forEach(function(p){p.decisions.forEach(function(d){
    if(!d.superseded)decisions.push({p:p,d:d})})});
  decisions.sort(function(a,b){return new Date(b.d.at)-new Date(a.d.at)});
  var releases=[];
  mine.forEach(function(p){p.releases.forEach(function(r){releases.push({p:p,r:r})})});
  releases.sort(function(a,b){return new Date(b.r.at)-new Date(a.r.at)});

  return pdfTop(esc(g.name),live.length+(live.length===1?' project':' projects'))+
    (g.description?'<div style="color:var(--ink-2);margin-bottom:14px">'+esc(g.description)+'</div>':'')+
    '<div class="grp" style="--gc:'+g.color+'"><div class="grp-h"><span class="n">'+
      '<span class="dotc" style="background:'+g.color+'"></span>'+esc(g.name)+'</span>'+
      '<span class="c">'+live.length+'</span></div>'+
      (live.length?'<div class="cards">'+live.map(card).join('')+'</div>'
        :'<div class="box empty"><b>Nothing in this group yet</b>'+
         'Add a project, or move one here from Settings.</div>')+'</div>'+
    (decisions.length?'<h2 class="pdf-h">Decisions</h2><div class="box">'+
      decisions.slice(0,12).map(function(x){
        return '<div class="dec"><b>'+dno(x.d.no)+'</b><span>'+esc(x.d.text)+'</span>'+
          '<span class="sd">'+esc(x.p.name)+' · '+fmt(x.d.at)+'</span></div>'}).join('')+
      '</div>':'')+
    (releases.length?'<h2 class="pdf-h">Released</h2><div class="box">'+
      releases.slice(0,12).map(function(x){
        return '<div class="rel"><span class="v">'+esc(x.r.v)+'</span>'+
          '<span>'+esc(x.p.name)+(x.r.note?' · '+esc(x.r.note):'')+'</span>'+
          '<span class="m">'+fmt(x.r.at)+'</span></div>'}).join('')+
      '</div>':'')+
    pdfFoot('One group, shared on purpose. Private groups never appear here.');
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

/* ======================= REACHABLE BY KEYBOARD (7.11) =======================
   The prototype drives almost everything from onclick on a span or a div,
   which a mouse can reach and a keyboard cannot. Rather than rewrite every
   render function, this walks what was just drawn and gives anything clickable
   the things a keyboard and a screen reader need: a stop in the tab order, a
   role, and a name. Enter and Space then act on it like a button. */

var ICON_NAMES={'✕':'Close','★':'Mark as a highlight','←':'Previous','→':'Next',
                '↵':'Enter','?':'Keyboard shortcuts'};
function wireA11y(){
  var app=document.getElementById('app');if(!app)return;
  app.querySelectorAll('[onclick]').forEach(function(el){
    var tag=el.tagName;
    if(tag==='BUTTON'||tag==='INPUT'||tag==='SELECT'||tag==='TEXTAREA')return;
    /* The dim behind a dialog closes it when clicked, but it is not a control
       and a keyboard already has Esc. */
    if(el.classList&&el.classList.contains('overlay'))return;
    if(!el.hasAttribute('tabindex'))el.setAttribute('tabindex','0');
    if(!el.hasAttribute('role'))el.setAttribute('role','button');
    if(!el.getAttribute('aria-label')){
      var text=(el.textContent||'').trim();
      if(!text||text.length<2){
        var name=ICON_NAMES[text]||el.getAttribute('title');
        if(name)el.setAttribute('aria-label',name);
      }
    }
  });
  /* Purely decorative marks should not be read out at all. */
  app.querySelectorAll('svg, .dotc, .sbar, .waitdot, .who .av, .groups i, .kpi .l')
    .forEach(function(el){
      if(el.tagName==='svg'&&!el.getAttribute('aria-hidden'))el.setAttribute('aria-hidden','true');
      if(el.classList&&(el.classList.contains('dotc')||el.classList.contains('sbar')||
         el.classList.contains('waitdot')||el.classList.contains('av')))
        el.setAttribute('aria-hidden','true');
    });
  /* Landmarks, so a screen reader can jump between the two halves. */
  var side=app.querySelector('.side'),main=app.querySelector('.main');
  if(side){side.setAttribute('role','navigation');side.setAttribute('aria-label','Sections and groups')}
  if(main)main.setAttribute('role','main');
  var nav=app.querySelector('.nav');
  if(nav)nav.setAttribute('aria-label','Go to');
  app.querySelectorAll('.nav a').forEach(function(a){
    a.setAttribute('role','link');
    if(a.classList.contains('on'))a.setAttribute('aria-current','page');
  });
  var toasts=document.getElementById('toasts');
  if(toasts){toasts.setAttribute('role','status');toasts.setAttribute('aria-live','polite')}
  var overlay=document.getElementById('ov-dlg');
  if(overlay){overlay.setAttribute('role','dialog');overlay.setAttribute('aria-modal','true')}
}
document.addEventListener('keydown',function(e){
  if(e.key!=='Enter'&&e.key!==' ')return;
  var el=document.activeElement;
  if(!el||!el.hasAttribute||!el.hasAttribute('onclick'))return;
  var tag=el.tagName;
  if(tag==='BUTTON'||tag==='INPUT'||tag==='SELECT'||tag==='TEXTAREA')return;
  e.preventDefault();el.click();
});

/* ======================= KEYS ======================= */
document.addEventListener('keydown',function(e){
  if(!S)return;
  var typing=['INPUT','TEXTAREA','SELECT'].indexOf(document.activeElement.tagName)>=0||document.activeElement.isContentEditable;
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();openCap();return}
  if(e.key==='Escape'){if(VIEWING)closeViewer();else closeOv();return}
  if(VIEWING&&!typing&&(e.key==='ArrowLeft'||e.key==='ArrowRight')){
    e.preventDefault();stepFile(e.key==='ArrowRight'?1:-1);return}
  if(typing)return;
  if(e.key==='/'){e.preventDefault();openPal();return}
  if(e.key==='?'){openKeys();return}
  var m={'1':'home','2':'projects','3':'roadmap','4':'ideas','5':'library','6':'week'};if(m[e.key])go(m[e.key]);
});
window.addEventListener('beforeunload',flushSave);
start();
