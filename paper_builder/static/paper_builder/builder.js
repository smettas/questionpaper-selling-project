const catalog = JSON.parse(document.querySelector('#catalog').textContent);
const form = document.querySelector('#paper-form');
const filters = document.querySelector('#filters');
const subject = document.querySelector('#subject');
const chapter = document.querySelector('#chapter');
const topic = document.querySelector('#topic');
const difficulty = document.querySelector('#difficulty');
const questionType = document.querySelector('#question-type');
const available = document.querySelector('#available');
const results = document.querySelector('#question-results');
const selectedList = document.querySelector('#selected');
const selected = new Map();
const subjectOrder = ['Physics', 'Chemistry', 'Biology'];
const exportSubject = form.elements.export_subject;
let shuffle = '';

function exportQuestions() {
  return Array.from(selected.values()).filter(question => !exportSubject.value || question.subject === exportSubject.value);
}
const status = document.querySelector('#status');
const submit = form.querySelector('[type="submit"]');
const downloads = document.querySelector('#downloads');

const previous = document.querySelector('#previous');
const next = document.querySelector('#next');
let page = 1;
let pending;
let revision = 0;

function fillOptions(select, placeholder, groups) {
  select.replaceChildren(new Option(placeholder, ''));
  for (const [label, items] of groups) {
    if (!items.length) continue;
    const group = label ? document.createElement('optgroup') : select;
    if (label) group.label = label;
    for (const item of items) group.append(new Option(item.name, item.id));
    if (label) select.append(group);
  }
}

function updateChapters() {
  fillOptions(chapter, 'All chapters', [11, 12].map(level => [
    `Class ${level}`, catalog.chapters.filter(row => row.level === level && row.subject === subject.value),
  ]));
  updateTopics();
}

function updateTopics() {
  fillOptions(topic, 'All subtopics', [['', catalog.topics.filter(row => row.chapter_id === Number(chapter.value))]]);
  topic.disabled = !chapter.value;
}

function clearDownloads() {
  revision++;
  status.textContent = '';
  downloads.hidden = true;
  for (const link of downloads.querySelectorAll('a')) URL.revokeObjectURL(link.href);
  downloads.replaceChildren();
}

function refreshSelection() {
  selectedList.replaceChildren();
  const groups = new Map(subjectOrder.map(name => [name, []]));
  for (const question of selected.values()) groups.get(question.subject).push(question);
  for (const [name, questions] of groups) {
    const section = document.createElement('section');
    const heading = document.createElement('h4');
    heading.textContent = `${name} · ${questions.length} selected`;
    section.append(heading);
    if (questions.length) {
      const list = document.createElement('ul');
      for (const question of questions) {
        const item = document.createElement('li');
        item.append(`Bank #${question.id} `);
        const remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'remove';
        remove.textContent = 'Remove';
        remove.onclick = () => toggle(question);
        item.append(remove);
        list.append(item);
      }
      section.append(list);
    }
    selectedList.append(section);
  }
  for (const option of exportSubject.options) {
    if (option.value) option.disabled = !groups.get(option.value).length;
  }
  if (exportSubject.selectedOptions[0]?.disabled) exportSubject.value = '';
  for (const button of results.querySelectorAll('[data-question-id]')) {
    const added = selected.has(Number(button.dataset.questionId));
    button.textContent = added ? '✓ Added · Remove' : '+ Add question';
    button.setAttribute('aria-pressed', String(added));
    button.disabled = !added && selected.size >= 300;
  }
  const start = Number(form.elements.start_number.value);
  const exportCount = exportQuestions().length;
  const end = start + exportCount - 1;
  document.querySelector('#total').textContent = `${selected.size} questions selected`;
  document.querySelector('#number-range').textContent = start > 0 && exportCount
    ? `Paper and answer key numbering: ${start}–${end}` : '';
  form.elements.end_number.setCustomValidity(exportCount && form.elements.end_number.value &&
    Number(form.elements.end_number.value) !== end ? `Enter ${end} or leave the end number blank.` : '');
}

function toggle(question) {
  if (selected.has(question.id)) selected.delete(question.id);
  else if (selected.size < 300) selected.set(question.id, question);
  clearDownloads();
  refreshSelection();
}

function previewImage(url, alt) {
  const image = document.createElement('img');
  image.src = url;
  image.alt = alt;
  image.loading = 'lazy';
  return image;
}

function formattedText(tokens) {
  const block = document.createElement('div');
  block.className = 'formatted-text';
  for (const [kind, value, alt] of tokens) {
    if (kind === 'math') {
      const image = previewImage(`data:image/svg+xml;base64,${value}`, alt);
      image.className = 'inline-math';
      block.append(image);
    } else if (kind === 'sub' || kind === 'sup') {
      const span = document.createElement(kind);
      span.textContent = value;
      block.append(span);
    } else {
      block.append(value);
    }
  }
  return block;
}

function appendDiagrams(target, preview, placement) {
  for (const diagram of preview.diagrams) {
    if (diagram.placement === placement) {
      target.append(previewImage(`data:image/png;base64,${diagram.png}`, 'Diagram'));
    }
  }
}

function showQuestions(questions) {
  results.replaceChildren();
  for (const question of questions) {
    const card = document.createElement('article');
    card.className = 'question-preview';
    const header = document.createElement('div');
    header.className = 'question-heading';
    const caption = document.createElement('h3');
    caption.textContent = `Question #${question.id}`;
    const add = document.createElement('button');
    add.type = 'button';
    add.className = 'secondary pick-button';
    add.dataset.questionId = question.id;
    add.onclick = () => toggle(question);
    add.setAttribute('aria-label', `Toggle question #${question.id}`);
    header.append(caption, add);
    card.append(header);
    const preview = question.preview;
    if (preview) {
      card.append(formattedText(preview.stem));
      appendDiagrams(card, preview, 'question');
      const options = document.createElement('ol');
      options.className = 'preview-options';
      for (const [index, tokens] of preview.options.entries()) {
        const option = document.createElement('li');
        option.append(`(${index + 1})`, formattedText(tokens));
        options.append(option);
      }
      card.append(options);
    } else {
      card.append(previewImage(question.image, `Question ${question.id}`));
    }
    const solution = document.createElement('section');
    solution.className = 'solution-preview';
    const answer = document.createElement('h4');
    answer.textContent = `Correct option (${question.answer})`;
    solution.append(answer);
    if (preview) {
      solution.append(formattedText(preview.hint));
      appendDiagrams(solution, preview, 'hint');
    } else {
      solution.append(question.hint ? previewImage(question.hint, 'Worked solution') : 'No worked solution was uploaded.');
    }
    card.append(solution);
    results.append(card);
  }
  refreshSelection();
}

function reshuffleQuestions() {
  shuffle = Array.from(crypto.getRandomValues(new Uint32Array(2)), value => value.toString(16).padStart(8, '0')).join('');
  loadQuestions(1);
}

async function loadQuestions(target) {
  pending?.abort();
  const controller = new AbortController();
  pending = controller;
  available.textContent = 'Loading questions…';
  results.replaceChildren();
  document.querySelector('#pagination').hidden = true;
  const params = new URLSearchParams({
    subject: subject.value, chapter: chapter.value, topic: topic.value, difficulty: difficulty.value, question_type: questionType.value, page: target, shuffle,
  });
  try {
    const response = await fetch(`${filters.dataset.url}?${params}`, {signal: controller.signal});
    if (!response.ok) throw new Error('Could not load questions.');
    const data = await response.json();
    if (pending !== controller) return;
    page = data.page;
    available.textContent = `${data.count} questions available`;
    document.querySelector('#pagination').hidden = data.pages <= 1;
    document.querySelector('#page-number').textContent = `Page ${page} of ${data.pages}`;
    previous.disabled = page === 1;
    next.disabled = page === data.pages;
    showQuestions(data.questions);
  } catch (error) {
    if (!controller.signal.aborted) available.textContent = error.message;
  }
}

subject.onchange = () => { updateChapters(); reshuffleQuestions(); };
chapter.onchange = () => { updateTopics(); reshuffleQuestions(); };
topic.onchange = difficulty.onchange = questionType.onchange = reshuffleQuestions;
document.querySelector('#shuffle-questions').onclick = reshuffleQuestions;
previous.onclick = () => loadQuestions(page - 1);
next.onclick = () => loadQuestions(page + 1);
form.addEventListener('input', event => {
  clearDownloads();
  if (!filters.contains(event.target)) refreshSelection();
});
updateChapters();
refreshSelection();
reshuffleQuestions();

form.addEventListener('submit', async event => {
  event.preventDefault();
  clearDownloads();
  const questions = exportQuestions();
  if (!questions.length) {
    status.textContent = 'Add at least one question.';
    return;
  }
  const generation = revision;
  const data = new FormData(form);
  data.set('question_ids', JSON.stringify(questions.map(question => question.id)));
  status.textContent = 'Generating your files…';
  submit.disabled = true;
  try {
    const response = await fetch(form.action, {method: 'POST', body: data});
    if (!response.ok) throw new Error(response.status === 400 ? await response.text() : 'File generation failed.');
    const {files} = await response.json();
    if (generation !== revision) return;
    for (const file of files) {
      const bytes = Uint8Array.from(atob(file.data), char => char.charCodeAt(0));
      const link = document.createElement('a');
      link.className = 'download';
      link.download = file.name;
      link.textContent = file.name;
      link.href = URL.createObjectURL(new Blob([bytes], {type: file.type}));
      downloads.append(link);
    }
    downloads.hidden = false;
    status.textContent = 'Your files are ready.';
  } catch (error) {
    if (generation === revision) status.textContent = error.message;
  } finally {
    submit.disabled = false;
  }
});

/* OJAS_SELECTED_PREVIEW_START */
(() => {
  'use strict';
  if (window.__ojasSelectedPreviewInstalled || typeof selected === 'undefined' || typeof selected.has !== 'function') return;
  const selection = document.getElementById('selected');
  if (!selection) return;
  window.__ojasSelectedPreviewInstalled = true;
  const help = document.createElement('p'); help.id='ojas-selected-preview-help'; help.style.cssText='font-size:12px;color:#65728b;margin:0 0 10px;'; help.textContent='Click or tap a question number to preview it.'; selection.before(help);
  const cache = new Map(), pending = new Map();
  let currentId = null, generation = 0, focusBack = null, oldOverflow = '', showing = false;
  let hoverTimer = null, hoverVersion = 0, hoverButton = null;
  const style = document.createElement('style');
  style.textContent = `
    #selected .ojas-selected-preview-trigger{display:inline!important;padding:3px 1px!important;margin:0 5px 0 0!important;border:0!important;border-radius:3px!important;background:transparent!important;color:#4432a6!important;font:inherit!important;text-align:left!important;text-decoration:underline;text-decoration-style:dotted;text-underline-offset:3px;min-height:0!important;box-shadow:none!important;cursor:pointer}
    #selected .ojas-selected-preview-trigger:focus-visible{outline:2px solid #7960d9;outline-offset:3px}
    .ojas-selected-preview-dialog{width:min(880px,calc(100vw - 24px));max-width:none;max-height:90vh;max-height:90dvh;padding:0;border:1px solid #dce3ef;border-radius:20px;background:#fff;color:#192540;box-shadow:0 24px 80px #15213b45;overflow:hidden;z-index:2147483001}
    .ojas-selected-preview-dialog[open]{display:flex;flex-direction:column}
    .ojas-selected-preview-dialog::backdrop{background:#14203980;backdrop-filter:blur(2px)}
    .ojas-selected-preview-dialog.ojas-preview-fallback{position:fixed;inset:5vh 0 auto;margin:0 auto}
    .ojas-selected-preview-fallback-backdrop{position:fixed;inset:0;background:#14203980;z-index:2147483000}
    .ojas-selected-preview-head{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:18px 22px;border-bottom:1px solid #e2e7f1;flex-shrink:0}
    .ojas-selected-preview-head h2{font-size:20px;margin:0;line-height:1.35}
    .ojas-selected-preview-head p{font-size:13px;color:#65728b;margin:4px 0 0}
    .ojas-selected-preview-close{flex-shrink:0;border:1px solid #dce3ef;border-radius:10px;padding:9px 13px;background:#f4f5fb;color:#293851;font-size:14px;cursor:pointer;min-height:42px}
    .ojas-selected-preview-body{padding:20px 22px;overflow:auto;overscroll-behavior:contain;min-height:100px;line-height:1.65;font-size:16px}
    .ojas-selected-preview-body .ojas-preview-diagram{display:block;max-width:100%;height:auto;margin:16px auto;object-fit:contain}
    .ojas-selected-preview-body img.inline-math,.ojas-selected-preview-hover img.inline-math{display:inline-block;max-width:100%;max-height:none;height:auto;margin:0;vertical-align:-.16em}
    .ojas-selected-preview-body .ojas-preview-line{white-space:pre-wrap;overflow-wrap:anywhere;margin:0 0 4px}
    .ojas-selected-preview-body .ojas-preview-options{list-style:none;margin:18px 0;padding:0;display:grid;gap:9px}
    .ojas-preview-options li{display:grid;grid-template-columns:2em minmax(0,1fr);gap:7px;background:#f5f6fc;border-radius:10px;padding:10px 12px}
    .ojas-selected-preview-body .ojas-preview-answer{background:#edf9f5;border-left:3px solid #1ca98c;border-radius:12px;padding:16px;margin-top:18px}
    .ojas-preview-answer h3{font-size:16px;margin:0 0 9px}
    .ojas-preview-matching{width:100%;border-collapse:collapse;margin:10px 0 14px;table-layout:fixed}
    .ojas-preview-matching th,.ojas-preview-matching td{padding:9px 11px;border:1px solid #dfe5ef;text-align:left;vertical-align:top;overflow-wrap:anywhere}
    .ojas-preview-matching th{background:#f0f1fb;font-weight:700}
    .ojas-selected-preview-foot{display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;padding:14px 22px;border-top:1px solid #e2e7f1;background:#fafbfe;flex-shrink:0}
    .ojas-selected-preview-navigation{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
    .ojas-selected-preview-foot button{font:600 14px system-ui;padding:10px 13px;border:1px solid #dce3ef;border-radius:10px;background:white;color:#3e3198;cursor:pointer;min-height:42px}
    .ojas-selected-preview-foot button:disabled{opacity:.4;cursor:default}
    .ojas-selected-preview-foot .ojas-preview-remove{border-color:#efd3d8;background:#fff2f4;color:#a52942}
    .ojas-preview-position{font-size:12px;color:#65728b}
    .ojas-selected-preview-hover{position:fixed;width:min(390px,calc(100vw - 24px));box-sizing:border-box;padding:14px 16px;border:1px solid #dbe1ee;border-radius:14px;background:#fff;color:#24324b;box-shadow:0 12px 35px #16233d30;z-index:2147483002;pointer-events:none;font:14px/1.5 system-ui}
    .ojas-selected-preview-hover[hidden],.ojas-selected-preview-fallback-backdrop[hidden]{display:none}
    .ojas-selected-preview-hover strong{display:block;color:#4633a7;font-size:13px;margin-bottom:7px}
    .ojas-selected-preview-hover .ojas-preview-hover-text{max-height:7.5em;overflow:hidden;white-space:pre-wrap;overflow-wrap:anywhere}
    .ojas-selected-preview-hover small{display:block;margin-top:8px;color:#68768c}
    @media(max-width:520px){.ojas-selected-preview-head,.ojas-selected-preview-foot{padding:13px 15px}.ojas-selected-preview-body{padding:16px 15px;font-size:15px}.ojas-selected-preview-head h2{font-size:18px}.ojas-selected-preview-foot{align-items:stretch}.ojas-selected-preview-foot .ojas-preview-remove{width:100%}}
  `;
  document.head.append(style);
  const dialog = document.createElement('dialog');
  dialog.className = 'ojas-selected-preview-dialog'; dialog.setAttribute('aria-labelledby','ojas-selected-preview-title'); dialog.setAttribute('aria-modal','true');
  const head = document.createElement('header'); head.className = 'ojas-selected-preview-head';
  const headings = document.createElement('div'), title = document.createElement('h2'), subtitle = document.createElement('p');
  title.id = 'ojas-selected-preview-title'; headings.append(title,subtitle);
  const close = document.createElement('button'); close.type='button'; close.className='ojas-selected-preview-close'; close.textContent='Close'; close.addEventListener('click',closePreview);
  head.append(headings,close);
  const body = document.createElement('div'); body.className='ojas-selected-preview-body'; body.setAttribute('aria-live','polite');
  const foot = document.createElement('footer'); foot.className='ojas-selected-preview-foot';
  const navigation = document.createElement('div'); navigation.className='ojas-selected-preview-navigation';
  const previous = document.createElement('button'), next = document.createElement('button'), position = document.createElement('span'), remove = document.createElement('button');
  previous.type=next.type=remove.type='button'; previous.textContent='Previous'; next.textContent='Next'; position.className='ojas-preview-position';
  previous.addEventListener('click',()=>move(-1)); next.addEventListener('click',()=>move(1));
  remove.className='ojas-preview-remove'; remove.textContent='Remove from paper';
  remove.addEventListener('click',()=>{
    const row = selected.get(currentId);
    if (row && typeof toggle === 'function') toggle(row);
    closePreview();
  });
  navigation.append(previous,position,next); foot.append(navigation,remove); dialog.append(head,body,foot);
  const fallback = document.createElement('div'); fallback.className='ojas-selected-preview-fallback-backdrop'; fallback.hidden=true; fallback.addEventListener('click',closePreview);
  document.body.append(fallback,dialog);
  const tooltip = document.createElement('div'); tooltip.className='ojas-selected-preview-hover'; tooltip.id='ojas-selected-preview-hover'; tooltip.setAttribute('role','tooltip'); tooltip.hidden=true; document.body.append(tooltip);

  function selectedIds() {
    const order = typeof subjectOrder !== 'undefined' ? subjectOrder : ['Physics','Chemistry','Biology'];
    const rows = Array.from(selected.values());
    return [...order.flatMap(name=>rows.filter(q=>q.subject===name)),...rows.filter(q=>!order.includes(q.subject))].map(q=>Number(q.id));
  }
  function updateNavigation() {
    const ids=selectedIds(), index=ids.indexOf(currentId);
    previous.disabled=index<=0; next.disabled=index<0||index>=ids.length-1; remove.disabled=!selected.has(currentId);
    position.textContent=index<0?'':`${index+1} of ${ids.length} selected`;
  }
  function move(amount) {
    const ids=selectedIds(), index=ids.indexOf(currentId), id=ids[index+amount];
    if (id) openQuestion(id);
  }
  function endpoint(id) {
    const template=selection.dataset.previewUrl;
    if (!template || !/\/0\/?$/.test(template)) throw new Error('Reload this page after the update to enable previews.');
    return template.replace(/\/0\/?$/,`/${id}/`);
  }
  function question(id) {
    const existing=selected.get(id);
    if (existing && (existing.preview || existing.image)) return Promise.resolve(existing);
    if (cache.has(id)) return Promise.resolve(cache.get(id));
    if (pending.has(id)) return pending.get(id);
    const request=fetch(endpoint(id),{credentials:'same-origin',cache:'no-store',headers:{'Accept':'application/json'}}).then(response=>{
      if (!response.ok) throw new Error(response.status===404?'This question is no longer available. You can remove it from your paper.':'The preview could not load. Please try again.');
      return response.json();
    }).then(row=>{
      if (Number(row.id)!==id) throw new Error('The preview did not match the selected question. Please retry.');
      cache.set(id,row); while(cache.size>24) cache.delete(cache.keys().next().value); return row;
    }).finally(()=>pending.delete(id));
    pending.set(id,request); return request;
  }
  function lines(tokens) {
    const result=[[]];
    for(const token of tokens||[]) {
      if(token[0]!=='text'){result[result.length-1].push(token);continue;}
      const parts=String(token[1]).split('\n');
      parts.forEach((part,index)=>{if(index)result.push([]);if(part)result[result.length-1].push(['text',part]);});
    }
    return result;
  }
  function textOf(tokens) {return (tokens||[]).map(t=>t[0]==='math'?(t[2]||'equation'):(t[1]||'')).join('');}
  function renderLine(tokens) {
    const node=document.createElement('div');node.className='ojas-preview-line';let first=true;
    for(const token of tokens||[]) {
      const [kind,value,alt]=token;
      if(kind==='math') {const image=document.createElement('img');image.className='inline-math';image.src=`data:image/svg+xml;base64,${value}`;image.alt=alt||'Equation';node.append(image);}
      else if(kind==='sub'||kind==='sup'){const script=document.createElement(kind);script.textContent=value;node.append(script);}
      else {
        const text=String(value||'');
        const match=first&&text.match(/^\s*((?:(?:Assertion|Reason)(?:\s*\([AR]\))?|Statement\s*(?:[IVX]+|\d+))\s*[:.)–—-])/i);
        if(match){const bold=document.createElement('strong');bold.textContent=match[0];node.append(bold,text.slice(match[0].length));}else node.append(text);
      }
      if(String(value||'').trim())first=false;
    }
    return node;
  }
  function splitRow(tokens) {
    const result=[[]];
    for(const token of tokens) {
      if(token[0]!=='text'){result[result.length-1].push(token);continue;}
      const parts=String(token[1]).split('|');
      parts.forEach((part,index)=>{if(index)result.push([]);if(part)result[result.length-1].push(['text',part.trim()]);});
    }
    return result.length===2?result:null;
  }
  function richText(tokens) {
    const out=document.createElement('div'), rows=lines(tokens);let table=null;
    for(const row of rows) {
      const cells=splitRow(row);
      if(cells && (/\b(?:List|Match)\s*[-–—]?\s*(?:I|1)\b/i.test(textOf(row)) || table)) {
        if(!table){table=document.createElement('table');table.className='ojas-preview-matching';out.append(table);}
        const tr=document.createElement('tr'), header=/^\s*(?:List|Match)\s*[-–—]?\s*(?:I|1)\b/i.test(textOf(row));
        for(const cell of cells){const td=document.createElement(header?'th':'td');if(header)td.scope='col';td.append(renderLine(cell));tr.append(td);}table.append(tr);
      } else {table=null;out.append(renderLine(row));}
    }
    return out;
  }
  function image(url,alt) {
    const img=document.createElement('img');img.className='ojas-preview-diagram';img.alt=alt;img.src=url;return img;
  }
  function diagrams(target,preview,placement) {
    for(const item of preview.diagrams||[])if(item.placement===placement)target.append(image(`data:image/png;base64,${item.png}`,'Question diagram'));
  }
  function renderQuestion(row) {
    body.replaceChildren();
    const metadata=[row.subject,row.level?`Class ${row.level}`:'',row.chapter,row.subtopic,row.difficulty].filter(Boolean);
    subtitle.textContent=metadata.join(' · ')||'Selected for your paper';
    const preview=row.preview;
    if(preview){body.append(richText(preview.stem));diagrams(body,preview,'question');const options=document.createElement('ol');options.className='ojas-preview-options';
      for(const [index,tokens]of(preview.options||[]).entries()){const option=document.createElement('li'),number=document.createElement('span');number.textContent=`(${index+1})`;option.append(number,richText(tokens));options.append(option);}body.append(options);
    }else if(row.image)body.append(image(row.image,`Question ${row.id}`));
    const answer=document.createElement('section');answer.className='ojas-preview-answer';const heading=document.createElement('h3');heading.textContent=`Correct option (${row.answer})`;answer.append(heading);
    if(preview){answer.append(richText(preview.hint));diagrams(answer,preview,'hint');}else if(row.hint)answer.append(image(row.hint,'Worked solution'));else answer.append('No worked solution was uploaded.');
    body.append(answer);body.scrollTop=0;
  }
  function showDialog() {
    if(showing)return;showing=true;oldOverflow=document.body.style.overflow;document.body.style.overflow='hidden';
    if(typeof dialog.showModal==='function')dialog.showModal();else{dialog.classList.add('ojas-preview-fallback');dialog.setAttribute('open','');fallback.hidden=false;}
    close.focus({preventScroll:true});
  }
  function closePreview() {
    if(!showing)return;showing=false;generation++;hideHover();
    if(typeof dialog.close==='function'&&dialog.open)dialog.close();else dialog.removeAttribute('open');
    fallback.hidden=true;document.body.style.overflow=oldOverflow;
    const target=focusBack&&focusBack.isConnected?focusBack:(selection.querySelector(`[data-selected-preview-id="${currentId}"]`)||selection.querySelector('.ojas-selected-preview-trigger'));
    if(target)target.focus({preventScroll:true});else{selection.tabIndex=-1;selection.focus({preventScroll:true});}
  }
  async function openQuestion(id,button) {
    id=Number(id);if(!Number.isSafeInteger(id)||!selected.has(id))return;
    hideHover();if(button)focusBack=button;currentId=id;const ticket=++generation;title.textContent=`Question #${id}`;subtitle.textContent='Selected for your paper';body.textContent='Loading question…';updateNavigation();showDialog();
    try{const row=await question(id);if(showing&&ticket===generation&&currentId===id)renderQuestion(row);}
    catch(error){if(showing&&ticket===generation){body.textContent=error.message||'The question could not load.';const retry=document.createElement('button');retry.type='button';retry.className='ojas-selected-preview-close';retry.textContent='Try again';retry.addEventListener('click',()=>openQuestion(id));body.append(document.createElement('br'),retry);}}
  }
  function hideHover() {clearTimeout(hoverTimer);hoverVersion++;tooltip.hidden=true;if(hoverButton)hoverButton.removeAttribute('aria-describedby');hoverButton=null;}
  function hover(button) {
    if(showing||!window.matchMedia('(hover: hover) and (pointer: fine)').matches)return;
    hideHover();hoverButton=button;const ticket=hoverVersion,id=Number(button.dataset.selectedPreviewId);
    hoverTimer=setTimeout(async()=>{
      try{const row=await question(id);if(ticket!==hoverVersion||showing||!button.isConnected)return;
        tooltip.replaceChildren();const label=document.createElement('strong');label.textContent=`${row.subject||'Selected question'} · Bank #${id}`;const excerpt=document.createElement('div');excerpt.className='ojas-preview-hover-text';
        if(row.preview)excerpt.append(richText(row.preview.stem));else excerpt.textContent='This question contains an image. Click to view it.';
        const hint=document.createElement('small');hint.textContent='Click to view the full question and options.';tooltip.append(label,excerpt,hint);tooltip.hidden=false;
        const bounds=button.getBoundingClientRect(),box=tooltip.getBoundingClientRect();let left=bounds.left-box.width-12;if(left<12)left=Math.min(bounds.right+12,window.innerWidth-box.width-12);left=Math.max(12,left);
        tooltip.style.left=`${left}px`;tooltip.style.top=`${Math.max(12,Math.min(bounds.top,window.innerHeight-box.height-12))}px`;button.setAttribute('aria-describedby',tooltip.id);
      }catch(_){/* Click offers a visible retry when a preview cannot load. */}
    },300);
  }
  function decorate() {
    for(const item of selection.querySelectorAll('li')) {
      if(item.querySelector('.ojas-selected-preview-trigger'))continue;
      const node=Array.from(item.childNodes).find(n=>n.nodeType===3&&/(?:Bank|Question)\s*#\s*\d+/i.test(n.textContent));if(!node)continue;
      const match=node.textContent.match(/(?:Bank|Question)\s*#\s*(\d+)/i),id=Number(match[1]);if(!selected.has(id))continue;
      const button=document.createElement('button');button.type='button';button.className='ojas-selected-preview-trigger';button.dataset.selectedPreviewId=String(id);button.textContent=match[0];button.setAttribute('aria-haspopup','dialog');button.setAttribute('aria-label',`Preview selected question ${id}`);
      button.addEventListener('click',()=>openQuestion(id,button));button.addEventListener('mouseenter',()=>hover(button));button.addEventListener('mouseleave',hideHover);button.addEventListener('focus',()=>hover(button));button.addEventListener('blur',hideHover);
      const index=match.index;node.replaceWith(document.createTextNode(node.textContent.slice(0,index)),button,document.createTextNode(node.textContent.slice(index+match[0].length)));
    }
    if(showing){if(!selected.has(currentId))closePreview();else updateNavigation();}
  }
  dialog.addEventListener('cancel',event=>{event.preventDefault();closePreview();});dialog.addEventListener('close',()=>{if(showing)closePreview();});
  dialog.addEventListener('click',event=>{if(event.target===dialog){const b=dialog.getBoundingClientRect();if(event.clientX<b.left||event.clientX>b.right||event.clientY<b.top||event.clientY>b.bottom)closePreview();}});
  dialog.addEventListener('keydown',event=>{
    if(event.key==='Escape'){event.preventDefault();closePreview();}
    if(event.key==='Tab'){const buttons=Array.from(dialog.querySelectorAll('button:not(:disabled),a[href],[tabindex="0"]'));const first=buttons[0],last=buttons[buttons.length-1];if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}
  });
  window.addEventListener('scroll',hideHover,true);window.addEventListener('resize',hideHover);
  new MutationObserver(decorate).observe(selection,{childList:true,subtree:true});decorate();
})();
/* OJAS_SELECTED_PREVIEW_END */
