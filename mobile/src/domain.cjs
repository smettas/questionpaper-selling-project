const SUBJECTS=['physics','chemistry','biology'];
const SECTIONS=['physics','chemistry','botany','zoology'];
const TYPES=[['mcq','Standard MCQs'],['assertion-reason','Assertion–reason'],['statement','Statements'],['matching','Matching'],['diagram','Diagrams'],['graph','Graphs']];
function toggleId(ids,id){return ids.includes(id)?ids.filter(x=>x!==id):[...ids,id];}
function chooseChapter(scope,id,on,topics){const ch=on?[...new Set([...scope.chapters,id])]:scope.chapters.filter(x=>x!==id);const all=topics.filter(t=>t.chapter_id===id).map(t=>t.id);return{chapters:ch,topics:on?[...new Set([...scope.topics,...all])]:scope.topics.filter(x=>!all.includes(x))};}
function unique(rows){const seen=new Set();return rows.filter(x=>{if(seen.has(x.id))return false;seen.add(x.id);return true;});}
function swap(rows,id,replacement){if(replacement.id!==id&&rows.some(q=>q.id===replacement.id))throw Error('Replacement already selected.');return rows.map(q=>q.id===id?replacement:q);}
function quotasValid(quotas,total,available){if(Object.values(quotas).some(x=>!Number.isInteger(x)||x<0))return false;if(Object.values(quotas).reduce((a,b)=>a+b,0)!==total)return false;return Object.keys(quotas).every(k=>quotas[k]<=(available[k]||0));}
function shuffle(rows,random=Math.random){const a=[...rows];for(let i=a.length-1;i>0;i--){const j=Math.floor(random()*(i+1));[a[i],a[j]]=[a[j],a[i]];}return a;}
function cleanDraft(s){return{v:1,scope:s.scope,mode:s.mode,subject:s.subject,difficulty:s.difficulty,kind:s.kind,target:s.target,candidateCount:s.candidateCount,sections:s.sections,confirmBiology:s.confirmBiology,selected:unique(s.selected||[]).slice(0,300).map(({id,subject,chapter,subtopic,section,section_label,chapter_id,topic_id,difficulty,kind,visual,level})=>({id,subject,chapter,subtopic,section,section_label,chapter_id,topic_id,difficulty,kind,visual,level})),details:{...s.details,logo:undefined},plan:s.plan||null,savedAt:Date.now()};}
module.exports={SUBJECTS,SECTIONS,TYPES,toggleId,chooseChapter,unique,swap,quotasValid,shuffle,cleanDraft};
