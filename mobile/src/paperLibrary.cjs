function monthKey(date=new Date()){return date.getFullYear()+'-'+String(date.getMonth()+1).padStart(2,'0');}
function shiftMonth(value,delta){const[y,m]=value.split('-').map(Number);return monthKey(new Date(y,m-1+delta,1));}
function monthLabel(value){if(!value)return 'All dates';const[y,m]=value.split('-').map(Number);return new Date(y,m-1,1).toLocaleDateString(undefined,{month:'long',year:'numeric'});}
function localPapers(files,month,search=''){const needle=search.trim().toLowerCase();return files.filter(f=>/\.(pdf|docx)$/i.test(f.name)&&f.name.toLowerCase().includes(needle)&&(!month||(f.created&&monthKey(new Date(f.created))===month))).sort((a,b)=>(b.created||0)-(a.created||0));}
module.exports={monthKey,shiftMonth,monthLabel,localPapers};
