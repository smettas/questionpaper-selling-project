const catalog = JSON.parse(document.querySelector('#catalog').textContent);
const form = document.querySelector('#paper-form');
const filters = document.querySelector('#filters');
const subject = document.querySelector('#subject');
const chapter = document.querySelector('#chapter');
const topic = document.querySelector('#topic');
const difficulty = document.querySelector('#difficulty');
const available = document.querySelector('#available');
const results = document.querySelector('#question-results');
const selectedList = document.querySelector('#selected');
const selected = new Map();
const status = document.querySelector('#status');
const submit = form.querySelector('[type="submit"]');
const downloads = document.querySelector('#downloads');
const links = [document.querySelector('#question-pdf'), document.querySelector('#answer-pdf')];
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
  for (const link of links) {
    if (link.hasAttribute('href')) URL.revokeObjectURL(link.href);
    link.removeAttribute('href');
  }
}

function refreshSelection() {
  selectedList.replaceChildren();
  for (const question of selected.values()) {
    const item = document.createElement('li');
    item.append(`${question.subject} · Bank #${question.id} `);
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'remove';
    remove.textContent = 'Remove';
    remove.onclick = () => toggle(question);
    item.append(remove);
    selectedList.append(item);
  }
  for (const button of results.querySelectorAll('[data-question-id]')) {
    const added = selected.has(Number(button.dataset.questionId));
    button.textContent = added ? 'Remove question' : 'Add question';
    button.setAttribute('aria-pressed', String(added));
    button.disabled = !added && selected.size >= 300;
  }
  const start = Number(form.elements.start_number.value);
  const end = start + selected.size - 1;
  document.querySelector('#total').textContent = `${selected.size} questions selected`;
  document.querySelector('#number-range').textContent = start > 0 && selected.size
    ? `Paper and answer key numbering: ${start}–${end}` : '';
  form.elements.end_number.setCustomValidity(selected.size && form.elements.end_number.value &&
    Number(form.elements.end_number.value) !== end ? `Enter ${end} or leave the end number blank.` : '');
}

function toggle(question) {
  if (selected.has(question.id)) selected.delete(question.id);
  else if (selected.size < 300) selected.set(question.id, question);
  clearDownloads();
  refreshSelection();
}

function previewImage(url, alt, structured) {
  if (structured) {
    const link = document.createElement('a');
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener';
    link.textContent = `Open ${alt} (PDF)`;
    return link;
  }
  const image = document.createElement('img');
  image.src = url;
  image.alt = alt;
  image.loading = 'lazy';
  return image;
}

function showQuestions(questions) {
  results.replaceChildren();
  for (const question of questions) {
    const card = document.createElement('article');
    card.className = 'question-preview';
    const caption = document.createElement('h3');
    caption.textContent = `Bank #${question.id}`;
    const solution = document.createElement('details');
    const title = document.createElement('summary');
    title.textContent = 'View answer and solution';
    const answer = document.createElement('p');
    answer.textContent = `Correct option: (${question.answer})`;
    solution.append(title, answer, question.hint
      ? previewImage(question.hint, `Worked solution for question ${question.id}`, question.structured) : 'No worked solution was uploaded.');
    const add = document.createElement('button');
    add.type = 'button';
    add.className = 'secondary';
    add.dataset.questionId = question.id;
    add.onclick = () => toggle(question);
    card.append(caption, previewImage(question.image, `Question ${question.id}`, question.structured), solution, add);
    results.append(card);
  }
  refreshSelection();
}

async function loadQuestions(target = 1) {
  pending?.abort();
  const controller = new AbortController();
  pending = controller;
  available.textContent = 'Loading questions…';
  results.replaceChildren();
  document.querySelector('#pagination').hidden = true;
  const params = new URLSearchParams({
    subject: subject.value, chapter: chapter.value, topic: topic.value, difficulty: difficulty.value, page: target,
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

subject.onchange = () => { updateChapters(); loadQuestions(); };
chapter.onchange = () => { updateTopics(); loadQuestions(); };
topic.onchange = difficulty.onchange = () => loadQuestions();
previous.onclick = () => loadQuestions(page - 1);
next.onclick = () => loadQuestions(page + 1);
form.addEventListener('input', () => { clearDownloads(); refreshSelection(); });
updateChapters();
refreshSelection();
loadQuestions();

form.addEventListener('submit', async event => {
  event.preventDefault();
  clearDownloads();
  if (!selected.size) {
    status.textContent = 'Add at least one question.';
    return;
  }
  const generation = revision;
  const data = new FormData(form);
  data.set('question_ids', JSON.stringify(Array.from(selected.keys())));
  status.textContent = 'Generating your PDFs…';
  submit.disabled = true;
  try {
    const response = await fetch(form.action, {method: 'POST', body: data});
    if (!response.ok) throw new Error(response.status === 400 ? await response.text() : 'PDF generation failed.');
    const pdfs = await response.json();
    if (generation !== revision) return;
    [pdfs.question, pdfs.answer].forEach((encoded, index) => {
      const bytes = Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
      links[index].href = URL.createObjectURL(new Blob([bytes], {type: 'application/pdf'}));
    });
    downloads.hidden = false;
    status.textContent = 'Both PDFs are ready.';
  } catch (error) {
    if (generation === revision) status.textContent = error.message;
  } finally {
    submit.disabled = false;
  }
});
