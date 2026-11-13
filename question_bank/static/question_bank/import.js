(() => {
    const catalog = JSON.parse(document.getElementById("import-catalog").textContent);
    const subject = document.getElementById("id_subject");
    const level = document.getElementById("id_level");
    const chapter = document.getElementById("id_chapter");
    const subtopic = document.getElementById("id_subtopic");
    const chapterList = document.getElementById("chapter-suggestions");
    const subtopicList = document.getElementById("subtopic-suggestions");
    const normalize = name => name.trim().replace(/\s+/g, " ").toLowerCase();

    function show(list, names) {
        list.replaceChildren(...Array.from(new Set(names), name => new Option(name)));
    }

    function updateSuggestions() {
        const chapters = catalog.chapters.filter(row =>
            row.subject === subject.value && row.level === Number(level.value));
        show(chapterList, chapters.map(row => row.name));
        const match = chapters.find(row => row.name === chapter.value) ??
            chapters.find(row => normalize(row.name) === normalize(chapter.value));
        show(subtopicList, catalog.subtopics.filter(row => row.chapter_id === match?.id)
            .map(row => row.name));
    }

    for (const field of [subject, level, chapter]) {
        field.addEventListener("change", () => {
            if (field !== chapter) chapter.value = "";
            subtopic.value = "";
            updateSuggestions();
        });
    }
    chapter.addEventListener("input", updateSuggestions);
    updateSuggestions();
})();
