const catalog = JSON.parse(document.querySelector('#catalog').textContent);
const container = document.querySelector('#sections');
const form = document.querySelector('#paper-form');
const addButton = document.querySelector('#add-section');
const status = document.querySelector('#status');
const submit = form.querySelector('[type="submit"]');

function fields(section) {
  return Object.fromEntries(Array.from(section.querySelectorAll('[data-field]'),
    field => [field.dataset.field, field]));
}

function options(select, placeholder, groups) {
  select.replaceChildren(new Option(placeholder, ''));
  for (const [label, items] of groups) {
    if (!items.length) continue;
    const group = label ? document.createElement('optgroup') : select;
    if (label) group.label = label;
    for (const item of items) group.append(new Option(item.name, item.id));
    if (label) select.append(group);
  }
}

function update(section, change) {
  const {subject, chapter, topic, difficulty, count} = fields(section);
  const chapters = catalog.chapters.filter(item => item.subject === subject.value);
  if (change === 'subject') options(chapter, 'All chapters', [11, 12].map(level =>
    [`Class ${level}`, chapters.filter(item => item.level === level)]));
  const chapterIds = new Set(chapters.filter(item => !chapter.value || item.id === Number(chapter.value))
    .map(item => item.id));
  const topics = catalog.topics.filter(item => chapterIds.has(item.chapter_id));
  if (change === 'subject' || change === 'chapter') {
    options(topic, 'All subtopics', [['', chapter.value ? topics : []]]);
    topic.disabled = !chapter.value;
  }
  const ids = new Set(topics.filter(item => !topic.value || item.id === Number(topic.value)).map(item => item.id));
  const available = catalog.counts.filter(item => ids.has(item.subtopic_id) &&
    (!difficulty.value || difficulty.value === item.difficulty)).reduce((sum, item) => sum + item.total, 0);
  count.max = Math.min(available, 300);
  section.querySelector('.available').textContent = `${available} questions available`;
  refresh();
}

function refresh() {
  const sections = Array.from(container.children);
  let total = 0;
  sections.forEach((section, index) => {
    section.querySelector('legend').textContent = `Section ${index + 1}`;
    section.querySelector('.remove').hidden = sections.length === 1;
    total += Number(fields(section).count.value);
  });
  const start = Number(form.elements.start_number.value);
  const end = start + total - 1;
  const range = document.querySelector('#number-range');
  range.textContent = start > 0 && total > 0
    ? `Paper and answer key numbering: ${start}–${end}` : '';
  form.elements.end_number.setCustomValidity(form.elements.end_number.value &&
    Number(form.elements.end_number.value) !== end ? `Enter ${end} or leave the end number blank.` : '');
  addButton.disabled = sections.length >= 12;
  document.querySelector('#total').textContent = `${total} questions selected · up to 300 per paper`;
}

function addSection() {
  const section = document.querySelector('#section-template').content.firstElementChild.cloneNode(true);
  container.append(section);
  section.addEventListener('change', event => update(section, event.target.dataset.field));
  section.addEventListener('input', event => { if (event.target.dataset.field === 'count') refresh(); });
  section.querySelector('.remove').onclick = () => { section.remove(); refresh(); };
  update(section, 'subject');
}

form.elements.start_number.addEventListener('input', refresh);
form.elements.end_number.addEventListener('input', refresh);
addButton.onclick = addSection;
addSection();
form.addEventListener('submit', async event => {
  event.preventDefault();
  const data = new FormData(form);
  data.set('sections', JSON.stringify(Array.from(container.children, section =>
    Object.fromEntries(Object.entries(fields(section)).map(([name, field]) => [name, field.value])))));
  status.textContent = 'Generating your paper…';
  submit.disabled = true;
  try {
    const response = await fetch(form.action, {method: 'POST', body: data});
    if (!response.ok) throw new Error(response.status === 400 ? await response.text() : 'Download failed. Check the server log.');
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = url;
    link.download = 'NEET Paper and Answer Key.zip';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
    status.textContent = 'Download ready. Open the ZIP for both PDFs.';
  } catch (error) {
    status.textContent = error.message;
  } finally {
    submit.disabled = false;
  }
});
