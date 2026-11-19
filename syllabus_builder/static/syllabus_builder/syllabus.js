/* OJAS syllabus review: integrates with the existing selected Map and export form. */
(function () {
  'use strict';
  const root = document.getElementById('syllabus-builder');
  if (!root || typeof selected === 'undefined' || typeof toggle !== 'function') return;
  const $ = id => document.getElementById(id);
  const types = [['mcq','Standard MCQs'],['assertion-reason','Assertion–reason'],['statement','Statement-based'],['matching','Match the following'],['diagram','Diagrams'],['graph','Graphs']];
  const labels = Object.fromEntries(types);
  const names = {physics:'Physics',chemistry:'Chemistry',biology:'Biology'};
  const chosen = new Set(), topics = new Set(), candidates = [], seen = new Set(), cache = new Map();
  const quotas = {}, countCells = {}, quotaCells = [], targets = {};
  const paperFields = ['institution','title','watermark','date','marks','duration','start_number','end_number','export_subject','page_columns','option_layout','arrangement','output_format'];
  const panel = $('sy-panel'), output = $('sy-candidates');
  const manualNodes = ['filters','shuffle-questions','available','question-results','pagination'].map($).filter(Boolean);
  const manualHidden = new Map();
  const DRAFT = 'ojas.syllabus-builder.v1';
  let active = false, busy = false, countVersion = 0, pageVersion = 0, scopeVersion = 0;
  let countTimer, countsController, batchScope = null, batchVersion = 0, currentPage = 0, reportId = null, reportFocus = null;
  let currentCounts = null, reporting = false, saveTimer;

  function el(tag, text, cls) { const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node; }
  function button(text, action, cls='sy-small') { const node=el('button',text,cls);node.type='button';node.addEventListener('click',action);return node; }
  function say(id, text, isError=false) { const node=$(id);node.textContent=text;node.classList.toggle('sy-error',isError); }
  function csrf() { return form.querySelector('[name=csrfmiddlewaretoken]')?.value || ''; }
  async function api(url, data, signal) {
    const options={credentials:'same-origin',signal};
    if(data!==undefined){options.method='POST';options.headers={'Content-Type':'application/json','X-CSRFToken':csrf()};options.body=JSON.stringify(data);}
    const response=await fetch(url,options);
    let value;try{value=await response.json();}catch(_){throw new Error('The server could not complete this request. Please try again.');}
    if(!response.ok){let message=value.error||'Request failed.';
      if(value.shortages)message+=' '+Object.entries(value.shortages).map(([k,v])=>`${labels[k]||'Matching questions'}: requested ${v.requested}, available ${v.available}`).join('; ');
      throw new Error(message);
    }
    return value;
  }
  function setMode(value) {
    if(value===active){panel.hidden=!value;return;}
    active=value;panel.hidden=!value;
    $('sy-manual').setAttribute('aria-pressed',String(!value));$('sy-covered').setAttribute('aria-pressed',String(value));
    for(const node of manualNodes){if(value){manualHidden.set(node,node.hidden);node.hidden=true;}else node.hidden=manualHidden.get(node)||false;}
    if(!value && typeof reshuffleQuestions==='function')reshuffleQuestions();
    queueSave();
  }
  function subjectChapters(){return catalog.chapters.filter(c=>c.subject===$('sy-subject').value);}
  function selectedChapters(){return subjectChapters().filter(c=>chosen.has(c.id));}
  function chapterTopics(id){return catalog.topics.filter(t=>t.chapter_id===id);}
  function check(label, checked, action) {
    const node=el('label',undefined,'sy-check'), input=el('input');input.type='checkbox';input.checked=checked;
    input.addEventListener('change',()=>action(input.checked));node.append(input,el('span',label));return node;
  }
  function renderChapters() {
    const box=$('sy-chapters');box.replaceChildren();
    for(const level of [11,12]){
      const rows=subjectChapters().filter(c=>c.level===level);if(!rows.length)continue;
      box.append(el('h4',`Class ${level}`,'sy-level'));
      for(const ch of rows){const row=check(ch.name,chosen.has(ch.id),value=>{
        if(value){chosen.add(ch.id);for(const t of chapterTopics(ch.id))topics.add(t.id);}else{chosen.delete(ch.id);for(const t of chapterTopics(ch.id))topics.delete(t.id);}
        renderTopics();changed();
      });row.dataset.chapterName=ch.name.toLowerCase();box.append(row);}
    }
    if(!box.childNodes.length)box.append(el('p','No published chapters are available for this subject.'));
    searchChapters();
  }
  function searchChapters(){const term=$('sy-chapter-search').value.toLowerCase().trim();for(const row of $('sy-chapters').querySelectorAll('[data-chapter-name]'))row.hidden=!row.dataset.chapterName.includes(term);}
  function renderTopics() {
    const box=$('sy-topics');box.replaceChildren();
    for(const ch of selectedChapters()){
      const group=el('section',undefined,'sy-topic-group'),list=el('div',undefined,'sy-topic-list'), rows=chapterTopics(ch.id);
      const included=rows.filter(t=>topics.has(t.id)).length;
      group.append(el('h4',ch.name),el('span',`${included} of ${rows.length} topics included`,'sy-topic-counter'));
      const tools=el('div',undefined,'sy-tools');tools.append(button('Select all topics',()=>{for(const t of rows)topics.add(t.id);renderTopics();changed();}),button('Clear topics',()=>{for(const t of rows)topics.delete(t.id);renderTopics();changed();}));group.append(tools);
      for(const t of rows)list.append(check(t.name,topics.has(t.id),value=>{value?topics.add(t.id):topics.delete(t.id);group.querySelector('.sy-topic-counter').textContent=`${rows.filter(r=>topics.has(r.id)).length} of ${rows.length} topics included`;changed();}));
      group.append(list);box.append(group);
    }
    if(!chosen.size)box.append(el('p','Select chapters first. All their topics will be included automatically.','sy-note'));
    updateSummaries();
  }
  function updateSummaries(){
    $('sy-chapter-summary').textContent=chosen.size?`${chosen.size} chapter${chosen.size===1?'':'s'} selected`:'Choose chapters';
    const total=selectedChapters().reduce((n,c)=>n+chapterTopics(c.id).length,0);
    $('sy-topic-summary').textContent=`Topics · ${topics.size} of ${total} included${topics.size===total&&total?' · all topics':''}`;
  }
  function scope(){return{subject:$('sy-subject').value,chapters:[...chosen],topics:[...topics],difficulty:$('sy-difficulty').value,question_type:$('sy-type').value};}
  function changed(){scopeVersion++;countVersion++;countsController?.abort();currentCounts=null;updateSummaries();$('sy-stale').hidden=!batchScope;say('sy-count-status','Updating available counts…');$('sy-load').disabled=true;clearTimeout(countTimer);countTimer=setTimeout(loadCounts,180);queueSave();}
  function quotaSummary(){
    const enabled=$('sy-use-quotas').checked;
    for(const cell of quotaCells)cell.hidden=!enabled;
    const sum=Object.values(quotas).reduce((n,input)=>n+Number(input.value||0),0);
    say('sy-quota-status',enabled?`${sum} of ${$('sy-count').value||0} candidates allocated. Counts must add up exactly.`:'Automatic mix · questions are spread across chapters and topics where available.');
  }
  async function loadCounts(){
    const ticket=++countVersion;countsController?.abort();countsController=new AbortController();
    const sc=scope();
    if(!sc.chapters.length||!sc.topics.length){currentCounts=null;for(const c of Object.values(countCells))c.textContent='0';say('sy-count-status',sc.chapters.length?'No topics included. Select topics or use “Select all topics”.':'Select at least one chapter.');$('sy-load').disabled=true;return;}
    const params=new URLSearchParams({subject:sc.subject,difficulty:sc.difficulty,question_type:sc.question_type});for(const id of sc.chapters)params.append('chapters',id);for(const id of sc.topics)params.append('topics',id);
    try{const data=await api(`${root.dataset.countsUrl}?${params}`,undefined,countsController.signal);if(ticket!==countVersion)return;
      currentCounts=data;for(const [key,cell]of Object.entries(countCells))cell.textContent=data.buckets[key]||0;
      for(const option of $('sy-type').options)option.textContent=option.value?`${labels[option.value]} (${data.type_counts?.[option.value]||0})`:`All types (${data.scope_total??data.total})`;
      const diff=['easy','moderate','hard'].map(k=>`${k}: ${data.difficulty[k]||0}`).join(' · ');
      say('sy-count-status',`${data.total.toLocaleString()} unique questions available · ${diff}`);$('sy-load').disabled=busy||!data.total;
    }catch(error){if(error.name!=='AbortError'&&ticket===countVersion){say('sy-count-status',error.message,true);$('sy-load').disabled=true;}}
  }
  function integer(id,min,max){const value=Number($(id).value);if(!Number.isInteger(value)||value<min||value>max)throw new Error(`Enter a whole number from ${min} to ${max} for ${$(id).closest('label')?.firstChild?.textContent||id}.`);return value;}
  function allocated(count){if(!$('sy-use-quotas').checked)return undefined;const result={};for(const[key,input]of Object.entries(quotas)){const n=Number(input.value||0);if(!Number.isInteger(n)||n<0||n>300)throw new Error('Type counts must be whole numbers from 0 to 300.');result[key]=n;}if(Object.values(result).reduce((a,b)=>a+b,0)!==count)throw new Error('The type counts must add up to the number of candidates.');return result;}
  function excludes(){return[...new Set([...seen,...selected.keys(),...candidates.map(q=>q.id)])].slice(-10000);}
  function remember(rows){for(const q of rows)seen.add(q.id);while(seen.size>9000)seen.delete(seen.values().next().value);}
  async function operation(fn){if(busy)return;busy=true;controls();try{await fn();}catch(error){say('sy-review-status',error.message,true);$('sy-review').hidden=false;}finally{busy=false;controls();queueSave();}}
  function controls(){for(const id of ['sy-load','sy-more','sy-reshuffle','sy-keep-all'])$(id).disabled=busy||(id==='sy-load'&&!currentCounts?.total);for(const card of output.querySelectorAll('[data-sy-id]'))for(const control of card.querySelectorAll('[data-replace],[data-remove]'))control.disabled=busy||(control.hasAttribute('data-replace')&&selected.has(Number(card.dataset.syId)));}
  async function loadBatch(){await operation(async()=>{
    const target=integer('sy-target',1,300);const count=integer('sy-count',1,300), sc=scope(), version=scopeVersion, allocation=allocated(count);
    say('sy-review-status','Choosing random candidates…');$('sy-review').hidden=false;
    const data=await api(root.dataset.sampleUrl,{...sc,count,exclude:excludes(),quotas:allocation});
    // A slow response must never replace a batch for a newly changed syllabus.
    if(version!==scopeVersion){say('sy-review-status','The syllabus changed while loading. Load a new batch to apply it.');return;}
    batchScope=sc;targets[sc.subject]=target;batchVersion++;candidates.splice(0,candidates.length,...data.questions);remember(data.questions);cache.clear();currentPage=0;$('sy-stale').hidden=true;
    say('sy-review-status','Candidates are not added to the paper until you keep them.');await renderPage();
  });}
  function keptCount(){return[...selected.values()].filter(q=>q.subject===names[batchScope?.subject||$('sy-subject').value]).length;}
  function reviewCount(){
    const kept=candidates.filter(q=>selected.has(q.id)).length;
    $('sy-review-count').textContent=`${candidates.length} candidates · ${kept} kept from this batch · ${keptCount()} selected for ${names[batchScope?.subject||$('sy-subject').value]} · target ${targets[batchScope?.subject]||$('sy-target').value||'—'}`;
    $('sy-targets').textContent=Object.entries(targets).map(([key,target])=>`${names[key]}: ${[...selected.values()].filter(q=>q.subject===names[key]).length} / ${target} selected`).join(' · ');
  }
  function selectedChanged(){reviewCount();for(const card of output.querySelectorAll('[data-sy-id]')){const id=Number(card.dataset.syId),kept=selected.has(id);card.classList.toggle('is-kept',kept);const b=card.querySelector('[data-keep]');if(b){b.textContent=kept?'✓ Kept · Unkeep':'Keep for paper';b.setAttribute('aria-pressed',String(kept));}const replace=card.querySelector('[data-replace]');if(replace)replace.disabled=kept||busy;}
    queueSave();
  }
  function keep(q){if(!selected.has(q.id)&&selected.size>=300){say('sy-review-status','A paper can contain up to 300 questions. Remove one before adding more.',true);return;}toggle(cache.get(q.id)||q);selectedChanged();}
  async function refreshUnkept(mode,id){if(!batchScope)return;
    await operation(async()=>{
      let slots=[];let count;
      if(mode==='more'){count=integer('sy-more-count',1,100);if(candidates.length+count>300)throw new Error('A review batch can contain up to 300 candidates. Remove some candidates first.');}
      else{slots=candidates.filter(q=>!selected.has(q.id)&&(id===undefined||q.id===id)).map(q=>q.id);count=slots.length;if(!count){say('sy-review-status','All these candidates are kept. Unkeep a question before replacing it.');return;}}
      say('sy-review-status','Choosing new questions from this batch’s syllabus…');
      const sc=batchScope, token=batchVersion;
      const data=await api(root.dataset.sampleUrl,{...sc,count,exclude:excludes()});if(sc!==batchScope||token!==batchVersion)return;
      remember(data.questions);if(mode==='more')candidates.push(...data.questions.filter(q=>!selected.has(q.id)&&!candidates.some(old=>old.id===q.id)));else slots.forEach((oldId,i)=>{const at=candidates.findIndex(q=>q.id===oldId);if(at<0||selected.has(oldId)||selected.has(data.questions[i].id))return;cache.delete(oldId);candidates[at]=data.questions[i];});
      say('sy-review-status','Updated. Kept questions are unchanged. Type allocations apply to the initial batch; replacements use its syllabus and type filter.');await renderPage();
    });
  }
  function tokenLines(tokens){const rows=[[]];for(const t of tokens||[]){if(t[0]!=='text'){rows.at(-1).push(t);continue;}String(t[1]).split('\n').forEach((text,i)=>{if(i)rows.push([]);if(text)rows.at(-1).push(['text',text]);});}return rows;}
  function line(tokens){const out=el('div',undefined,'sy-text');let first=true;
    for(const[k,value,alt]of tokens||[]){if(k==='math'){const img=el('img');img.src=`data:image/svg+xml;base64,${value}`;img.alt=alt||'Equation';img.className='sy-math';out.append(img);}else if(k==='sub'||k==='sup')out.append(el(k,value));else{const s=String(value||''),match=first&&s.match(/^\s*((?:(?:Assertion|Reason)(?:\s*\([AR]\))?|Statement\s*(?:[IVX]+|\d+))\s*[:.)–—-])/i);if(match)out.append(el('strong',match[0]),s.slice(match[0].length));else out.append(s);}if(String(value||'').trim())first=false;}return out;}
  function cells(tokens){const result=[[]];for(const t of tokens){if(t[0]!=='text'){result.at(-1).push(t);continue;}String(t[1]).split('|').forEach((text,i)=>{if(i)result.push([]);if(text)result.at(-1).push(['text',text.trim()]);});}return result.length===2?result:null;}
  function rich(tokens){const out=el('div');let table=null;for(const row of tokenLines(tokens)){const text=row.map(t=>t[0]==='math'?(t[2]||''):(t[1]||'')).join(''), parts=cells(row),head=/^\s*(?:List|Match)\s*[-–—]?\s*(?:I|1)\b/i.test(text);if(parts&&(head||table)){if(!table){table=el('table',undefined,'sy-matching');out.append(table);}const tr=el('tr');for(const part of parts){const td=el(head?'th':'td');if(head)td.scope='col';td.append(line(part));tr.append(td);}table.append(tr);}else{table=null;out.append(line(row));}}return out;}
  function image(url,alt){const img=el('img');img.src=url;img.alt=alt;img.className='sy-diagram';img.loading='lazy';return img;}
  function figures(node,preview,placement){for(const d of preview.diagrams||[])if(d.placement===placement)node.append(image(`data:image/png;base64,${d.png}`,'Question diagram'));}
  function reportButton(id){return button('Report correction',event=>openReport(id,event.currentTarget),'sy-report-link');}
  function card(q,failed){
    const box=el('article',undefined,'sy-question');box.dataset.syId=q.id;
    const heading=el('div',undefined,'sy-q-heading');heading.append(el('h4',`Question #${q.id}`));box.append(heading,el('p',[q.subject,q.level?`Class ${q.level}`:'',q.chapter,q.subtopic,q.difficulty,labels[q.visual||q.kind]||''].filter(Boolean).join(' · '),'sy-meta'));
    const actions=el('div',undefined,'sy-q-actions'),keepButton=button('Keep for paper',()=>keep(q));keepButton.dataset.keep='';const replace=button('Replace',()=>refreshUnkept('replace',q.id));replace.dataset.replace='';
    actions.append(keepButton,replace,button('Remove candidate',()=>{if(selected.has(q.id))toggle(q);const at=candidates.findIndex(x=>x.id===q.id);if(at>=0)candidates.splice(at,1);cache.delete(q.id);renderPage();queueSave();}),reportButton(q.id));box.append(actions);
    if(failed){box.append(el('p',failed,'sy-error'),button('Retry preview',()=>{cache.delete(q.id);renderPage();}));keepButton.disabled=true;return box;}
    if(q.preview){box.append(rich(q.preview.stem));figures(box,q.preview,'question');const opts=el('ol',undefined,'sy-options');for(const[i,tokens]of(q.preview.options||[]).entries()){const li=el('li');li.append(el('span',`(${i+1})`),rich(tokens));opts.append(li);}box.append(opts);}
    else if(q.image)box.append(image(q.image,`Question ${q.id}`));
    const solution=el('details',undefined,'sy-solution');solution.append(el('summary',`Show answer and explanation${q.answer?` · option (${q.answer})`:''}`));
    if(q.preview){solution.append(rich(q.preview.hint));figures(solution,q.preview,'hint');}else if(q.hint)solution.append(image(q.hint,'Worked solution'));box.append(solution);return box;
  }
  async function renderPage(){
    const ticket=++pageVersion;const pages=Math.max(1,Math.ceil(candidates.length/12));currentPage=Math.min(currentPage,pages-1);
    $('sy-page').textContent=`Page ${currentPage+1} of ${pages}`;$('sy-prev').disabled=currentPage<=0;$('sy-next').disabled=currentPage>=pages-1;reviewCount();output.textContent='Loading candidate previews…';
    const rows=candidates.slice(currentPage*12,currentPage*12+12),missing=rows.filter(q=>!cache.has(q.id));let failed=new Map();
    try{if(missing.length){const params=new URLSearchParams();for(const q of missing)params.append('ids',q.id);const data=await api(`${root.dataset.detailsUrl}?${params}`);if(ticket!==pageVersion)return;for(const q of data.questions){cache.set(q.id,q);if(selected.has(q.id))selected.set(q.id,q);}failed=new Map((data.failed||[]).map(x=>[x.id,x.error]));}}
    catch(error){if(ticket!==pageVersion)return;failed=new Map(missing.map(q=>[q.id,error.message]));}
    if(ticket!==pageVersion)return;output.replaceChildren();for(const q of rows)output.append(card({...q,...cache.get(q.id)},failed.get(q.id)));if(!rows.length)output.append(el('p','No candidates in this batch. Add more or load a new batch.'));selectedChanged();
    const keepIds=new Set([...selected.keys(),...rows.map(q=>q.id)]);for(const id of cache.keys())if(!keepIds.has(id))cache.delete(id);
  }
  function openReport(id,trigger){reportId=id;reportFocus=trigger;$('sy-report-question').textContent=`Bank question #${id}`;$('sy-report-note').value='';say('sy-report-status','A report does not change or delete the question.');const dlg=$('sy-report-dialog');if(typeof dlg.showModal==='function')dlg.showModal();else{dlg.setAttribute('open','');dlg.classList.add('sy-report-fallback');}$('sy-report-note').focus();}
  function closeReport(){if(reporting)return;const dlg=$('sy-report-dialog');if(typeof dlg.close==='function')dlg.close();else{dlg.removeAttribute('open');dlg.classList.remove('sy-report-fallback');}if(reportFocus?.isConnected)reportFocus.focus();}
  async function sendReport(){if(reporting)return;const note=$('sy-report-note').value.trim();if(note.length<10){say('sy-report-status','Please describe the issue in at least 10 characters.',true);return;}reporting=true;$('sy-report-send').disabled=true;
    try{const data=await api(root.dataset.reportUrl,{question_id:reportId,category:$('sy-report-category').value,note});say('sy-report-status',`Report #${data.id}: ${data.message}`);}catch(error){say('sy-report-status',error.message,true);}finally{reporting=false;$('sy-report-send').disabled=false;}}
  function decorateManual(){for(const article of document.querySelectorAll('#question-results .question-preview')){if(article.querySelector('.sy-report-link'))continue;const match=article.querySelector('h3')?.textContent.match(/#(\d+)/);if(match)article.append(reportButton(Number(match[1])));}}
  function queueSave(){clearTimeout(saveTimer);saveTimer=setTimeout(saveDraft,250);}
  function saveDraft(){try{localStorage.setItem(DRAFT,JSON.stringify({v:1,active,scope:scope(),target:$('sy-target').value,count:$('sy-count').value,quotaEnabled:$('sy-use-quotas').checked,quotas:Object.fromEntries(Object.entries(quotas).map(([k,v])=>[k,v.value])),batchScope,candidates:candidates.map(({id,subject,chapter,chapter_id,level,subtopic,topic_id,difficulty,kind,visual})=>({id,subject,chapter,chapter_id,level,subtopic,topic_id,difficulty,kind,visual})),seen:[...seen].slice(-9000),shuffleFinal:$('sy-shuffle-final').checked,targets,kept:[...selected.values()].slice(0,300).map(q=>({id:q.id,subject:q.subject})),fields:Object.fromEntries([...form.elements].filter(n=>paperFields.includes(n.name)&&typeof n.value==='string').map(n=>[n.name,n.value.slice(0,240)])),savedAt:Date.now()}));}catch(_){/* Never interrupt selection when storage is full. */}}
  function validScope(sc){return sc&&Object.hasOwn(names,sc.subject)&&Array.isArray(sc.chapters)&&sc.chapters.length<=150&&Array.isArray(sc.topics)&&sc.topics.length<=2000&&sc.chapters.every(Number.isSafeInteger)&&sc.topics.every(Number.isSafeInteger);}
  function restoreDraft(){let d;try{d=JSON.parse(localStorage.getItem(DRAFT)||'null');}catch(_){return;}if(!d||d.v!==1||!validScope(d.scope)||!Array.isArray(d.candidates)||d.candidates.length>300)return;
    $('sy-subject').value=d.scope.subject;const validCh=new Set(subjectChapters().map(c=>c.id));for(const id of d.scope.chapters)if(validCh.has(id))chosen.add(id);const validT=new Set(catalog.topics.filter(t=>chosen.has(t.chapter_id)).map(t=>t.id));for(const id of d.scope.topics)if(validT.has(id))topics.add(id);
    if(['','easy','moderate','hard'].includes(d.scope.difficulty))$('sy-difficulty').value=d.scope.difficulty;if(['',...types.map(x=>x[0])].includes(d.scope.question_type))$('sy-type').value=d.scope.question_type;
    for(const[id,key]of[['sy-target','target'],['sy-count','count']]){const n=Number(d[key]);if(Number.isInteger(n)&&n>0&&n<=300)$(id).value=n;}
    $('sy-use-quotas').checked=!!d.quotaEnabled;for(const[k,v]of Object.entries(d.quotas||{}))if(quotas[k]&&/^\d{1,3}$/.test(String(v)))quotas[k].value=v;
    $('sy-shuffle-final').checked=!!d.shuffleFinal;for(const[key,n]of Object.entries(d.targets||{}))if(Object.hasOwn(names,key)&&Number.isInteger(n)&&n>0&&n<=300)targets[key]=n;
    if(validScope(d.batchScope)){batchScope=d.batchScope;const seenIds=new Set();for(const q of d.candidates)if(q&&Number.isSafeInteger(q.id)&&q.id>0&&Object.values(names).includes(q.subject)&&!seenIds.has(q.id)){candidates.push(q);seenIds.add(q.id);}for(const id of (Array.isArray(d.seen)?d.seen:[]).slice(-9000))if(Number.isSafeInteger(id)&&id>0)seen.add(id);remember(candidates);$('sy-review').hidden=false;renderPage();}
    // The Android host restores its own selected Map and paper fields. Avoid
    // pre-empting that restore, which deliberately skips a nonempty Map.
    if(!/OjasQuestionBuilder\//.test(navigator.userAgent)&&selected.size===0){
      for(const [name,value]of Object.entries(d.fields||{})){const input=form.elements[name];if(!input||!paperFields.includes(name)||typeof value!=='string'||value.length>240)continue;if(input.tagName==='SELECT'&&![...input.options].some(o=>o.value===value))continue;input.value=value;}
      for(const q of (Array.isArray(d.kept)?d.kept:[]).slice(0,300))if(q&&Number.isSafeInteger(q.id)&&q.id>0&&Object.values(names).includes(q.subject))selected.set(q.id,{id:q.id,subject:q.subject});
      clearDownloads();refreshSelection();
    }
    renderChapters();renderTopics();quotaSummary();setMode(!!d.active);changed();if(batchScope)$('sy-stale').hidden=JSON.stringify(scope())===JSON.stringify(batchScope);
  }
  function shuffleSelected(){const order=['Physics','Chemistry','Biology'],all=[...selected.values()],out=[];for(const name of order){const rows=all.filter(q=>q.subject===name);for(let i=rows.length-1;i>0;i--){const values=new Uint32Array(1);crypto.getRandomValues(values);const j=values[0]%(i+1);[rows[i],rows[j]]=[rows[j],rows[i]];}out.push(...rows);}selected.clear();for(const q of out)selected.set(q.id,q);clearDownloads();refreshSelection();}

  for(const[key,label]of types){const row=el('tr'),cell=el('td','0'),quota=el('td'),input=el('input');input.type='number';input.min='0';input.max='300';input.value='0';input.setAttribute('aria-label',`${label} candidates requested`);input.addEventListener('input',()=>{quotaSummary();queueSave();});quotas[key]=input;countCells[key]=cell;quota.hidden=true;quota.append(input);quotaCells.push(quota);row.append(el('th',label),cell,quota);row.firstChild.scope='row';$('sy-count-rows').append(row);}
  quotaCells.push(...root.querySelectorAll('.sy-quota-cell'));
  $('sy-manual').onclick=()=>setMode(false);$('sy-covered').onclick=()=>{setMode(true);loadCounts();};
  $('sy-subject').onchange=()=>{$('sy-target').value=targets[$('sy-subject').value]||45;chosen.clear();topics.clear();$('sy-chapter-search').value='';renderChapters();renderTopics();changed();};
  $('sy-chapter-search').oninput=searchChapters;
  $('sy-all-chapters').onclick=()=>{for(const c of subjectChapters()){chosen.add(c.id);for(const t of chapterTopics(c.id))topics.add(t.id);}renderChapters();renderTopics();changed();};
  $('sy-clear-chapters').onclick=()=>{chosen.clear();topics.clear();renderChapters();renderTopics();changed();};
  $('sy-difficulty').onchange=$('sy-type').onchange=changed;
  $('sy-use-quotas').onchange=()=>{quotaSummary();queueSave();};$('sy-count').oninput=()=>{quotaSummary();queueSave();};$('sy-target').oninput=()=>{const n=Number($('sy-target').value),key=$('sy-subject').value;if(Object.hasOwn(targets,key)&&Number.isInteger(n)&&n>0&&n<=300)targets[key]=n;reviewCount();queueSave();};$('sy-shuffle-final').onchange=queueSave;
  $('sy-load').onclick=loadBatch;$('sy-more').onclick=()=>refreshUnkept('more');$('sy-reshuffle').onclick=()=>refreshUnkept('reshuffle');
  $('sy-keep-all').onclick=()=>{if(selected.size+candidates.filter(q=>!selected.has(q.id)).length>300){say('sy-review-status','This would exceed the 300-question paper limit.',true);return;}for(const q of candidates)if(!selected.has(q.id))selected.set(q.id,cache.get(q.id)||q);clearDownloads();refreshSelection();selectedChanged();};
  $('sy-prev').onclick=()=>{currentPage--;renderPage();};$('sy-next').onclick=()=>{currentPage++;renderPage();};
  $('sy-report-send').onclick=sendReport;$('sy-report-close').onclick=closeReport;
  $('sy-report-dialog').addEventListener('cancel',event=>{event.preventDefault();closeReport();});
  $('sy-report-dialog').addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();closeReport();}if(event.key==='Tab'){const nodes=[...$('sy-report-dialog').querySelectorAll('button:not(:disabled),select,textarea')];const first=nodes[0],last=nodes.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}});
  root.addEventListener('keydown',event=>{if(event.key==='Enter'&&event.target.matches('input:not([type=checkbox])')){event.preventDefault();if(!busy&&currentCounts?.total)loadBatch();}});
  // Capture runs before the existing download handler; export still uses the same Map.
  form.addEventListener('submit',event=>{if($('sy-report-dialog').hasAttribute('open')){event.preventDefault();event.stopImmediatePropagation();return;}if(!active||!batchScope)return;try{integer('sy-target',1,300);const only=form.elements.export_subject?.value;for(const[key,target]of Object.entries(targets)){if(only&&only!==names[key])continue;const n=[...selected.values()].filter(q=>q.subject===names[key]).length;if(n!==target)throw new Error(`${names[key]} has ${n} selected questions; the target is ${target}. Keep/remove questions or update the target before generating.`);}if($('sy-shuffle-final').checked)shuffleSelected();}catch(error){event.preventDefault();event.stopImmediatePropagation();say('sy-review-status',error.message,true);$('sy-review-status').scrollIntoView({block:'center',behavior:'smooth'});}},true);
  new MutationObserver(selectedChanged).observe($('selected'),{childList:true,subtree:true});
  new MutationObserver(decorateManual).observe($('question-results'),{childList:true});decorateManual();
  // Prevent a manual browser request that was already in flight from unhiding pagination.
  new MutationObserver(()=>{if(active&&!$('pagination').hidden)$('pagination').hidden=true;}).observe($('pagination'),{attributes:true,attributeFilter:['hidden']});
  window.addEventListener('pagehide',saveDraft);
  // The Android host's New Paper button clears the same form. Clear this draft too.
  form.addEventListener('reset',()=>{scopeVersion++;countVersion++;countsController?.abort();for(const key of Object.keys(targets))delete targets[key];candidates.length=0;chosen.clear();topics.clear();seen.clear();cache.clear();batchScope=null;currentPage=0;pageVersion++;try{localStorage.removeItem(DRAFT);}catch(_){}setTimeout(()=>{renderChapters();renderTopics();$('sy-review').hidden=true;changed();},0);});
  renderChapters();renderTopics();quotaSummary();$('sy-load').disabled=true;restoreDraft();
  window.OjasSyllabus={version:1};
})();
