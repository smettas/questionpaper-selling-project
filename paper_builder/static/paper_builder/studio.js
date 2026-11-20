/* OJAS Paper Studio. Presentation layer: existing nodes/listeners/IDs stay intact. */
(function(){
'use strict';
if(window.__ojasStudio)return;
const $=id=>document.getElementById(id),paper=document.getElementById('paper-form'),bank=document.querySelector('.card.bank'),sidebar=document.querySelector('.card.details');
if(!paper||!bank||!sidebar||!$('test-patterns')||!$('syllabus-builder')||!$('selected'))return;
window.__ojasStudio=true;
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const hide=(node,value)=>{if(node&&node.hidden!==value)node.hidden=value;};
const text=(node,value)=>{if(node&&node.textContent!==value)node.textContent=value;};
const button=(label,fn,cls='sy-small')=>{const b=el('button',label,cls);b.type='button';b.addEventListener('click',fn);return b;};
const uid=(()=>{let i=0;return()=>`ui-control-${++i}`;})();
const reduced=()=>window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
const softScroll=n=>{if(n?.isConnected)n.scrollIntoView({block:'start',behavior:reduced()?'auto':'smooth'});};
const mode=()=>$('tp-profile')?.value||($('sy-covered')?.getAttribute('aria-pressed')==='true'?'syllabus':'manual');
const preset=()=>!['manual','syllabus'].includes(mode());
let frame=null,pendingReview=null,activeStep=0,selectMenu=null;
const widgets=new Set(),widgetMap=new WeakMap();

// Keep the existing form intact; regroup only its original controls.
const header=document.querySelector('body>header');
if(header){const originalBrand=header.querySelector('.brand')||el('div',undefined,'brand');
 const inner=el('div',undefined,'ui-header-inner'),mark=el('span',undefined,'ui-brand-mark');mark.setAttribute('aria-hidden','true');
 const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 24 24');const path=document.createElementNS(ns,'path');path.setAttribute('d','M3 5.5c3-1 6-.7 9 1.2 3-1.9 6-2.2 9-1.2v13c-3-1-6-.7-9 1.2-3-1.9-6-2.2-9-1.2z M12 6.7v13 M6 9h3 M15 9h3 M6 12h3 M15 12h3');svg.append(path);mark.append(svg);
 const brandText=el('span','OJAS Question Builder');brandText.append(el('small','PAPER STUDIO','ui-brand-subtitle'));originalBrand.replaceChildren(mark,brandText);
 const right=el('div',undefined,'ui-header-right');right.append(el('span','Teacher workspace','ui-header-pill'));
 const helpToggle=button('How it works',()=>{help.hidden=!help.hidden;helpToggle.setAttribute('aria-expanded',String(!help.hidden));if(!help.hidden)softScroll(help);},'ui-help');helpToggle.setAttribute('aria-expanded','false');helpToggle.setAttribute('aria-controls','ui-help-panel');right.append(helpToggle);inner.append(originalBrand,right);header.replaceChildren(inner);
}
const main=document.querySelector('main'),heading=main?.querySelector('h1'),intro=main?.querySelector('.intro');
if(heading){heading.before(el('span','QUESTION WORKSPACE','ui-overline'));text(heading,'Your syllabus. Your paper.');}
text(intro,'Choose your syllabus, review the questions, and export a paper ready for your classroom.');
const help=el('section',undefined,'ui-help-panel');help.id='ui-help-panel';help.hidden=true;
for(const[label,body]of[['1. Configure','Choose a pattern and covered chapters. All topics in a new chapter are included automatically.'],['2. Review','Load questions, keep the ones you want, and replace individual questions as needed.'],['3. Export','Check the selected count, add your academy details, and generate PDF or Word files.']]){const p=el('p');p.append(el('strong',label+' · '),body);help.append(p);}
main.insertBefore(help,paper);
const steps=el('nav',undefined,'ui-steps');steps.setAttribute('aria-label','Paper building stages');
const stepButtons=[];for(const[index,name,note]of[[0,'Configure','Pattern & syllabus'],[1,'Review','Choose your questions'],[2,'Export','Paper & answer key']]){
 const b=button('',()=>{activeStep=index;if(index===0){setup.open=true;softScroll(setup);}else if(index===1){if(!review.hidden)softScroll(review);else{setup.open=true;softScroll(setup);}}else{identity.open=true;softScroll(sidebar);}updateChrome();},'ui-step');
 b.append(el('span',String(index+1),'ui-step-number'));const title=el('span');title.append(el('span',name,'ui-step-name'),el('small',note,'ui-step-note'));b.append(title);steps.append(b);stepButtons.push(b);
}main.insertBefore(steps,help);
const setup=el('details',undefined,'ui-setup');setup.id='ui-setup';setup.open=true;
const summary=el('summary'),summaryText=el('span',undefined,'ui-setup-heading');summaryText.append(el('span','Configure your paper'),el('small','Choose a test pattern and syllabus','ui-setup-meta'));summary.append(summaryText);setup.append(summary);
const setupBody=el('div',undefined,'ui-setup-body');setup.append(setupBody);bank.querySelector('h2')?.after(setup);
const review=el('section',undefined,'ui-review-stage');review.id='ui-review-stage';review.hidden=true;review.setAttribute('aria-label','Question review');bank.append(review);
const manualReview=el('div'),coveredReview=el('div'),presetReview=el('div');manualReview.id='ui-review-manual';coveredReview.id='ui-review-covered';presetReview.id='ui-review-preset';review.append(manualReview,coveredReview,presetReview);
for(const id of ['question-results','pagination'])if($(id))manualReview.append($(id));
coveredReview.append($('sy-review'));presetReview.append($('tp-review'));
for(const id of ['test-patterns','syllabus-builder','filters','shuffle-questions','available'])if($(id))setupBody.append($(id));
const countExplain=el('p','Final questions go in the paper. Candidates give you extra questions to review.','ui-count-explain');$('sy-count-status')?.before(countExplain);

// Optional custom mix is kept compact, without hiding invalid requests.
const mix=el('details',undefined,'ui-mix');mix.id='ui-mix';mix.open=!!$('sy-use-quotas')?.checked;
const mixSummary=el('summary','Question mix · Automatic'),mixBody=el('div',undefined,'ui-mix-body');mix.append(mixSummary,mixBody);
const quotaCheck=$('sy-use-quotas').closest('label'),tableWrap=setupBody.querySelector('.sy-table-wrap'),quotaNote=tableWrap?.nextElementSibling;
quotaCheck.before(mix);mixBody.append(quotaCheck);if(tableWrap)mixBody.append(tableWrap);if(quotaNote?.classList.contains('sy-note'))mixBody.append(quotaNote);mixBody.append($('sy-quota-status'));
const chips=el('div',undefined,'ui-format-chips');mixBody.append(chips);
const mixAlert=el('section',undefined,'ui-mix-alert');mixAlert.hidden=true;mixAlert.setAttribute('role','status');const mixAlertText=el('div');mixAlert.append(mixAlertText);
const autoMix=button('Use automatic mix',()=>{const input=$('sy-use-quotas');input.checked=false;input.dispatchEvent(new Event('change',{bubbles:true}));updateChrome();});
const allTypes=button('Use all types',()=>{const input=$('sy-type');input.value='';input.dispatchEvent(new Event('change',{bubbles:true}));updateChrome();});
const matchTotal=button('Use mix total',()=>{const n=quotaState().sum;if(n>0&&n<=300){$('sy-count').value=n;$('sy-count').dispatchEvent(new Event('input',{bubbles:true}));updateChrome();}});mixAlert.append(autoMix,allTypes,matchTotal);mixBody.append(mixAlert);
$('sy-use-quotas').addEventListener('change',()=>{mix.open=$('sy-use-quotas').checked;queueChrome();});
$('sy-load').setAttribute('aria-describedby','ui-mix-validation');mixAlertText.id='ui-mix-validation';

function topNode(name){const input=paper.elements[name];if(!input)return null;let n=input.closest('label')||input;while(n.parentElement&&n.parentElement!==sidebar)n=n.parentElement;return n.parentElement===sidebar?n:null;}
const inputNodes={};for(const name of ['institution','title','watermark','date','marks','duration','start_number','end_number','logo'])inputNodes[name]=topNode(name);
const selectedHeading=[...sidebar.querySelectorAll('h3')].find(n=>/Selected questions/i.test(n.textContent));
const selectedBox=el('section',undefined,'ui-selected-box');selectedBox.id='ui-selected-box';selectedBox.append(selectedHeading||el('h3','Selected questions'));
const totalNode=$('total');selectedBox.append(totalNode);const track=el('div',undefined,'ui-progress-track'),fill=el('div',undefined,'ui-progress-fill');track.append(fill);selectedBox.append(track);const progressNote=el('p',undefined,'ui-progress-note');selectedBox.append(progressNote);
const selectedSearch=el('input',undefined,'ui-selected-search');selectedSearch.type='search';selectedSearch.placeholder='Find a selected question number';selectedSearch.setAttribute('aria-label','Find a selected question');selectedBox.append(selectedSearch);
if($('ojas-selected-preview-help'))selectedBox.append($('ojas-selected-preview-help'));selectedBox.append($('selected'));
const sidebarHeading=sidebar.querySelector('h2');if(sidebarHeading){sidebarHeading.replaceChildren(el('span','Paper workspace'));sidebarHeading.after(selectedBox);}else sidebar.prepend(selectedBox);
function settingsGroup(title,hint,nodes,opened=false){const detail=el('details',undefined,'ui-settings-group');detail.open=opened;const s=el('summary',title),h=el('small',hint,'ui-settings-hint');s.append(h);const body=el('div',undefined,'ui-settings-content');const used=new Set();for(const node of nodes)if(node&&!used.has(node)){used.add(node);body.append(node);}detail.append(s,body);return detail;}
const identity=settingsGroup('Paper identity','Academy and paper title',[inputNodes.institution,inputNodes.title],true);
const branding=settingsGroup('Branding','Watermark and logo',[inputNodes.watermark,inputNodes.logo]);
const timing=settingsGroup('Test details','Date, marks, timing and numbering',[inputNodes.date,inputNodes.marks,inputNodes.duration,inputNodes.start_number,inputNodes.end_number,$('number-range')]);
const exportFieldset=sidebar.querySelector('.export-settings'),exportSettings=settingsGroup('Export settings','PDF · One column',[exportFieldset]);
sidebar.append(identity,branding,timing,exportSettings);
const submit=sidebar.querySelector('button[type=submit]'),exportActions=el('div',undefined,'ui-export-actions');if(submit){text(submit,'Generate paper');exportActions.append(submit);}if($('downloads'))exportActions.append($('downloads'));if($('status'))exportActions.append($('status'));sidebar.append(exportActions);

// Accessible custom selects. The original select remains the source of truth.
function closeSelect(focus=false){if(!selectMenu)return;const w=selectMenu;selectMenu=null;w.menu.hidden=true;w.button.setAttribute('aria-expanded','false');w.button.removeAttribute('aria-activedescendant');if(focus&&w.button.isConnected)w.button.focus({preventScroll:true});}
function positionSelect(w){const r=w.button.getBoundingClientRect(),vw=window.innerWidth,vh=window.innerHeight;const width=Math.max(160,Math.min(Math.max(r.width,200),vw-24));const height=Math.max(80,Math.min(360,vh-24));w.menu.style.width=width+'px';w.menu.style.maxHeight=height+'px';w.menu.style.left=Math.max(12,Math.min(r.left,vw-width-12))+'px';w.menu.style.top='0px';const actual=w.menu.getBoundingClientRect().height||Math.min(height,w.items.length*40+12),below=vh-r.bottom-12;let top=below>=actual?r.bottom+6:r.top-actual-6;if(top<12)top=Math.max(12,Math.min(r.bottom+6,vh-actual-12));w.menu.style.top=top+'px';}
function activateOption(w,index){if(!w.items.length)return;index=Math.max(0,Math.min(index,w.items.length-1));let count=0;while(w.items[index]?.disabled&&count++<w.items.length)index=(index+1)%w.items.length;if(w.items[index]?.disabled)return;w.active=index;for(const[i,item]of w.items.entries())item.node.classList.toggle('is-active',i===index);w.button.setAttribute('aria-activedescendant',w.items[index].node.id);w.items[index].node.scrollIntoView?.({block:'nearest'});}
function selectOption(w,item){if(w.select.disabled||item.disabled)return;if(w.select.selectedIndex===item.index){closeSelect(true);return;}w.select.selectedIndex=item.index;w.select.dispatchEvent(new Event('input',{bubbles:true}));w.select.dispatchEvent(new Event('change',{bubbles:true}));refreshWidget(w);closeSelect(true);queueChrome();}
function menuSignature(w){return [...w.select.options].map(o=>[o.value,o.textContent,o.disabled,o.selected,o.parentElement?.label||'',o.parentElement?.disabled||false].join(':')).join('|');}
function buildMenu(w){w.menu.replaceChildren();w.items=[];let lastGroup=null;for(const[index,o]of [...w.select.options].entries()){const group=o.parentElement?.tagName==='OPTGROUP'?o.parentElement:null;if(group&&lastGroup!==group){const g=el('div',group.label,'ui-option-group');g.setAttribute('role','presentation');w.menu.append(g);}lastGroup=group;
 const n=el('div',o.textContent,'ui-option'),disabled=o.disabled||!!group?.disabled;n.id=uid();n.setAttribute('role','option');n.setAttribute('aria-selected',String(index===w.select.selectedIndex));n.setAttribute('aria-disabled',String(disabled));const item={node:n,index,disabled,label:o.textContent};n.addEventListener('pointerdown',e=>e.preventDefault());n.addEventListener('click',()=>selectOption(w,item));n.addEventListener('mouseenter',()=>{const at=w.items.indexOf(item);if(at>=0)activateOption(w,at);});w.menu.append(n);w.items.push(item);}
 w.signature=menuSignature(w);
}
function openSelect(w,direction=0){if(w.select.disabled)return;closeSelect();buildMenu(w);selectMenu=w;w.menu.hidden=false;w.button.setAttribute('aria-expanded','true');positionSelect(w);let at=Math.max(0,w.items.findIndex(o=>o.index===w.select.selectedIndex));if(direction)at=Math.max(0,Math.min(at+direction,w.items.length-1));activateOption(w,at);}
function refreshWidget(w){const current=w.select.options[w.select.selectedIndex];text(w.value,current?.textContent||'Choose an option');if(w.button.disabled!==w.select.disabled)w.button.disabled=w.select.disabled;w.button.title=current?.textContent||'';if(selectMenu===w){if(w.select.disabled){closeSelect();return;}const signature=menuSignature(w);if(signature!==w.signature){w.signature=signature;buildMenu(w);positionSelect(w);activateOption(w,Math.max(0,w.items.findIndex(o=>o.index===w.select.selectedIndex)));}}}
function enhanceSelect(select){if(widgetMap.has(select)||select.closest('dialog')||select.multiple||select.size>1)return;
 const label=select.closest('label'),base=label?[...label.childNodes].filter(n=>n!==select&&!(n.nodeType===1&&n.classList.contains('ui-select'))).map(n=>n.textContent).join(' ').trim():(select.getAttribute('aria-label')||'Choose an option');
 const wrapper=el('span',undefined,'ui-select'),b=button('',null,'ui-select-button'),value=el('span',undefined,'ui-select-value'),chevron=el('span',undefined,'ui-select-chevron'),menu=el('div',undefined,'ui-option-menu');
 select.before(wrapper);wrapper.append(select,b);select.classList.add('ui-select-native');select.tabIndex=-1;select.setAttribute('aria-hidden','true');const labelText=el('span',base);labelText.style.cssText='position:absolute;width:1px;height:1px;clip-path:inset(50%);overflow:hidden;';labelText.id=uid();value.id=uid();wrapper.append(labelText);b.append(value,chevron);b.setAttribute('role','combobox');b.setAttribute('aria-haspopup','listbox');b.setAttribute('aria-expanded','false');b.setAttribute('aria-labelledby',`${labelText.id} ${value.id}`);menu.id=uid();menu.hidden=true;menu.setAttribute('role','listbox');menu.setAttribute('aria-label',base||'Options');b.setAttribute('aria-controls',menu.id);document.body.append(menu);
 const w={select,button:b,value,menu,items:[],active:0,signature:'',observer:null,typed:'',timer:null};widgetMap.set(select,w);widgets.add(w);b.addEventListener('click',()=>selectMenu===w?closeSelect():openSelect(w));
 b.addEventListener('keydown',event=>{const key=event.key;if(['ArrowDown','ArrowUp','Home','End','Enter',' ','Escape'].includes(key)){event.preventDefault();event.stopPropagation();if(key==='Escape'){closeSelect(true);return;}if(key==='Enter'||key===' '){if(selectMenu===w){const item=w.items[w.active];if(item)selectOption(w,item);}else openSelect(w);return;}if(selectMenu!==w){openSelect(w,key==='ArrowUp'?-1:0);return;}let index=w.active;if(key==='Home')index=w.items.findIndex(item=>!item.disabled);else if(key==='End')index=w.items.map(item=>item.disabled).lastIndexOf(false);else{const step=key==='ArrowUp'?-1:1;index=(index+step+w.items.length)%w.items.length;let guard=0;while(w.items[index]?.disabled&&guard++<w.items.length)index=(index+step+w.items.length)%w.items.length;}activateOption(w,index);}else if(key==='Tab')closeSelect();else if(key.length===1&&!event.ctrlKey&&!event.metaKey&&!event.altKey){event.preventDefault();clearTimeout(w.timer);w.typed+=key.toLocaleLowerCase();w.timer=setTimeout(()=>w.typed='',650);if(selectMenu!==w)openSelect(w);const index=w.items.findIndex(item=>!item.disabled&&item.label.trim().toLocaleLowerCase().startsWith(w.typed));if(index>=0)activateOption(w,index);}});
 select.addEventListener('change',()=>{refreshWidget(w);queueChrome();});w.observer=new MutationObserver(()=>{refreshWidget(w);queueChrome();});w.observer.observe(select,{childList:true,subtree:true,attributes:true,attributeFilter:['disabled','label','selected']});refreshWidget(w);
}
function enhanceTree(node){if(node.nodeType!==1)return;if(node.matches('select'))enhanceSelect(node);for(const select of node.querySelectorAll('select'))enhanceSelect(select);}

function quotaState(){const rows=[...$('sy-count-rows').children],sum=rows.reduce((n,row)=>n+Number(row.querySelector('input')?.value||0),0);let problem='';for(const row of rows){const input=row.querySelector('input'),value=Number(input?.value||0),available=Number(row.children[1]?.textContent||0),label=row.firstChild.textContent;if(!Number.isInteger(value)||value<0||value>300){problem='Use whole numbers from 0 to 300 in the custom mix.';break;}if(value>available){problem=`${label}: you requested ${value}, but this filter has ${available}. Change the type filter or adjust the mix.`;break;}}if(!problem&&sum!==Number($('sy-count').value))problem=`Your mix totals ${sum}; the review batch is ${$('sy-count').value||0}. Use the mix total or adjust your counts.`;return{sum,problem};}
function updateMix(){const enabled=$('sy-use-quotas').checked,state=quotaState();text(mixSummary,enabled?`Question mix · Custom (${state.sum})`:'Question mix · Automatic');hide(mixAlert,!(enabled&&state.problem));text(mixAlertText,state.problem);hide(allTypes,!$('sy-type').value);hide(matchTotal,state.sum<1||state.sum>300||state.sum===Number($('sy-count').value));text(matchTotal,`Use ${state.sum} candidates`);
 const counts=[...$('sy-count-rows').children].map(r=>[r.firstChild.textContent,r.children[1]?.textContent||'0']).filter(([,n])=>Number(n)>0);const signature=JSON.stringify(counts);if(chips.dataset.signature!==signature){chips.dataset.signature=signature;chips.replaceChildren(...counts.map(([name,n])=>el('span',`${name} ${n}`,'ui-format-chip')));}}
function polishCard(card){if(card.dataset.uiCard)return;card.dataset.uiCard='true';let head=card.querySelector('.sy-q-heading,.question-heading');const keep=card.querySelector('[data-keep],[data-tp-keep],[data-question-id]');if(!head){head=el('div',undefined,'ui-card-head');const caption=[...card.children].find(n=>/^H[1-6]$/.test(n.tagName));if(caption){caption.before(head);head.append(caption);}else card.prepend(head);}head.classList.add('ui-card-head');if(keep){keep.classList.add('ui-action-keep');head.append(keep);}const actions=card.querySelector('.sy-q-actions');if(actions){for(const b of actions.querySelectorAll('button'))if(/remove/i.test(b.textContent))b.classList.add('ui-action-danger');card.append(actions);}}
function filterSelected(){const term=selectedSearch.value.trim().toLocaleLowerCase();for(const group of $('selected').querySelectorAll('section')){const list=group.querySelector('ul'),items=[...group.querySelectorAll('li')];group.classList.toggle('ui-selected-empty',!list);for(const li of items){const hide=!!term&&!li.textContent.toLocaleLowerCase().includes(term);if(li.hidden!==hide)li.hidden=hide;const remove=li.querySelector('.remove');if(remove){const id=li.textContent.match(/#\s*(\d+)/)?.[1];remove.setAttribute('aria-label',id?`Remove question ${id} from paper`:'Remove from paper');}}hide(group,!!term&&!items.some(li=>!li.hidden));}}
function sourceCards(){const kind=mode(),container=kind==='manual'?$('question-results'):kind==='syllabus'?$('sy-candidates'):$('tp-questions');return[...container.querySelectorAll('.sy-question,.question-preview')];}
function sourceSignature(){return sourceCards().map(c=>c.dataset.syId||c.dataset.tpId||c.querySelector('[data-question-id]')?.dataset.questionId||c.querySelector('h3,h4')?.textContent).join(',');}
function visibleStatus(){return mode()==='manual'?$('available'):mode()==='syllabus'?$('sy-review-status'):$('tp-status');}
function queueChrome(){if(frame!==null)return;frame=requestAnimationFrame(()=>{frame=null;updateChrome();});}
function updateChrome(){const kind=mode(),isManual=kind==='manual',isCovered=kind==='syllabus';hide(manualReview,!isManual);hide(coveredReview,!isCovered);hide(presetReview,isManual||isCovered);
 const sourceVisible=isManual?sourceCards().length>0:isCovered?!$('sy-review').hidden:!$('tp-review').hidden;hide(review,!sourceVisible);
 const meta=isCovered?[...[$('sy-subject').selectedOptions[0]?.textContent,$('sy-chapter-summary').textContent,$('sy-topic-summary').textContent.replace(/^Topics\s*·\s*/,'')]].join(' · '):$('tp-profile').selectedOptions[0]?.textContent||'Browse the question bank';text(summaryText.querySelector('small'),meta);
 const count=typeof selected!=='undefined'?selected.size:0;let target=0;
 if(isCovered){target=Number($('sy-target').value)||0;}else if(!isManual){target=kind==='custom40'?40:180;}
 const subjectLabel=isCovered?$('sy-subject').selectedOptions[0]?.textContent:'';const progressCount=isCovered?[...selected.values()].filter(q=>q.subject===subjectLabel).length:count;const ratio=target?Math.min(1,progressCount/target):0;fill.style.width=(ratio*100)+'%';hide(track,!target);hide(progressNote,!target);text(progressNote,`${subjectLabel?subjectLabel+' · ':''}${progressCount} of ${target} target questions`);track.setAttribute('role','progressbar');track.setAttribute('aria-label',subjectLabel?`Selected ${subjectLabel} questions`:'Selected question count');track.setAttribute('aria-valuemin','0');track.setAttribute('aria-valuemax',String(target||300));track.setAttribute('aria-valuenow',String(progressCount));
 hide(selectedSearch,count<8);if(!count&&selectedSearch.value)selectedSearch.value='';filterSelected();
 for(const card of sourceCards())polishCard(card);
 updateMix();for(const w of [...widgets]){if(!w.select.isConnected){w.observer.disconnect();clearTimeout(w.timer);w.menu.remove();widgets.delete(w);if(selectMenu===w)closeSelect();}else refreshWidget(w);}
 const format=paper.elements.output_format?.selectedOptions[0]?.textContent||'PDF',columns=paper.elements.page_columns?.selectedOptions[0]?.textContent||'One column';text(exportSettings.querySelector('.ui-settings-hint'),`${format} · ${columns}`);
 const brandingParts=[];if(paper.elements.watermark?.value.trim())brandingParts.push('Watermark set');if(paper.elements.logo?.files?.length)brandingParts.push('Logo added');text(branding.querySelector('.ui-settings-hint'),brandingParts.join(' · ')||'Watermark and logo');
 text(timing.querySelector('.ui-settings-hint'),[paper.elements.marks?.value?`${paper.elements.marks.value} marks`:null,paper.elements.duration?.value?`${paper.elements.duration.value} minutes`:null].filter(Boolean).join(' · ')||'Date, marks, timing and numbering');
 const currentStatus=visibleStatus(),signature=sourceSignature(),sourceError=currentStatus?.classList.contains('sy-error')||currentStatus?.classList.contains('tp-error');
 if(pendingReview&&sourceError){setup.open=true;mix.open=$('sy-use-quotas').checked;pendingReview=null;}
 if(pendingReview&&signature&&signature!==pendingReview.signature){const b=$(pendingReview.id);if(!b?.disabled){setup.open=false;activeStep=1;pendingReview=null;softScroll(review);}}
 if(!sourceVisible&&activeStep===1)activeStep=0;
 for(const[index,b]of stepButtons.entries()){b.classList.toggle('is-active',index===activeStep);b.classList.toggle('is-done',index===0&&sourceVisible||index===1&&count>0);if(index===activeStep)b.setAttribute('aria-current','step');else b.removeAttribute('aria-current');}
 if(submit)submit.setAttribute('aria-busy',String(submit.disabled));
 const stat=$('sy-review-status')?.textContent||'';$('sy-load').setAttribute('aria-busy',String($('sy-load').disabled&&/^Choosing random candidates/.test(stat)));
 $('tp-generate').setAttribute('aria-busy',String($('tp-generate').disabled&&/^Building your test/.test($('tp-status').textContent||'')));
}

paper.addEventListener('click',event=>{const b=event.target.closest('button');if(!b)return;if(b.id==='sy-load'&&$('sy-use-quotas').checked){const state=quotaState();if(state.problem){event.preventDefault();event.stopImmediatePropagation();mix.open=true;setup.open=true;updateMix();softScroll(mix);return;}}
 if(['sy-load','tp-generate','shuffle-questions'].includes(b.id))pendingReview={id:b.id,signature:sourceSignature()};
 if(b.type==='submit'){activeStep=2;queueChrome();}
},true);
paper.addEventListener('input',queueChrome);paper.addEventListener('change',event=>{if(setup.contains(event.target))activeStep=0;else if(review.contains(event.target))activeStep=1;else if(sidebar.contains(event.target))activeStep=2;queueChrome();});
paper.addEventListener('focusin',event=>{if(setup.contains(event.target))activeStep=0;else if(review.contains(event.target))activeStep=1;else if(sidebar.contains(event.target))activeStep=2;queueChrome();});
selectedSearch.addEventListener('input',event=>{event.stopPropagation();filterSelected();});selectedSearch.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();event.stopPropagation();}});
setup.addEventListener('toggle',()=>{if(setup.open)activeStep=0;queueChrome();});
paper.addEventListener('invalid',event=>{for(let node=event.target.parentElement;node;node=node.parentElement)if(node.tagName==='DETAILS')node.open=true;},true);
paper.addEventListener('reset',()=>{closeSelect();pendingReview=null;activeStep=0;setup.open=true;selectedSearch.value='';setTimeout(queueChrome,0);});
review.addEventListener('keydown',event=>{if(event.key==='Enter'&&event.target.id==='sy-more-count'){event.preventDefault();event.stopPropagation();$('sy-more').click();}});
document.addEventListener('pointerdown',event=>{if(selectMenu&&!selectMenu.menu.contains(event.target)&&!selectMenu.button.contains(event.target))closeSelect();const b=event.target.closest('button');if(!b||b.disabled||reduced()||b.classList.contains('ui-select-button'))return;const rect=b.getBoundingClientRect(),size=Math.max(rect.width,rect.height);if(size<1)return;const ripple=el('span',undefined,'ui-ripple');ripple.style.cssText=`width:${size}px;height:${size}px;left:${event.clientX-rect.left-size/2}px;top:${event.clientY-rect.top-size/2}px`;b.append(ripple);setTimeout(()=>ripple.remove(),550);});
window.addEventListener('resize',()=>closeSelect());window.addEventListener('scroll',event=>{if(selectMenu&&!selectMenu.menu.contains(event.target))closeSelect();},true);
const observer=new MutationObserver(records=>{for(const r of records)for(const n of r.addedNodes)enhanceTree(n);if(selectMenu&&!selectMenu.select.isConnected)closeSelect();queueChrome();});
observer.observe(paper,{childList:true,subtree:true,attributes:true,attributeFilter:['hidden','disabled']});
document.body.classList.add('ojas-studio');document.title='OJAS Question Builder · Paper Studio';enhanceTree(paper);updateChrome();
window.OjasStudio={version:1};
})();
