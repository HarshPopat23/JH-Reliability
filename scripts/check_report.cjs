// Optional DOM integration check; this does not verify browser rendering/layout.
// npm install --prefix .ui-check jsdom@26.1.0 --no-audit --no-fund
// ACLAB_JSDOM_PATH=../.ui-check/node_modules/jsdom node scripts/check_report.cjs
const fs = require('fs');
const path = require('path');
const assert = require('node:assert/strict');
const {JSDOM, ResourceLoader, VirtualConsole} = require(process.env.ACLAB_JSDOM_PATH || 'jsdom');
const input = process.argv[2] || 'evidence/v02/comparison/report.html';
const output = process.argv[3];
const external = [], errors = [];
class BlockNetwork extends ResourceLoader {
  fetch(url) { external.push(url); return null; }
}
const console = new VirtualConsole();
console.on('jsdomError', error => errors.push(error.message));
const dom = new JSDOM(fs.readFileSync(input,'utf8'),{url:'file://'+path.resolve(input),runScripts:'dangerously',resources:new BlockNetwork(),virtualConsole:console});
const document = dom.window.document;
const data = JSON.parse(document.getElementById('data').textContent);
const rows = () => Array.from(document.querySelectorAll('#rows tr'));
const select = (id,value) => { const node=document.getElementById(id); node.value=value; node.dispatchEvent(new dom.window.Event('change')); };
assert.equal(rows().length,data.records.length);
select('kind','live_model');
assert.equal(rows().length,data.records.filter(r=>r.evidence_kind==='live_model').length);
select('kind','scripted_demo');
assert.equal(rows().length,data.records.filter(r=>r.evidence_kind==='scripted_demo').length);
select('kind','');
const search=document.getElementById('search');
search.value='no-such-variant-3897'; search.dispatchEvent(new dom.window.Event('input'));
assert.equal(rows().length,0);
search.value=data.records[0].id; search.dispatchEvent(new dom.window.Event('input'));
assert.ok(rows().length>=1);
search.value=''; search.dispatchEvent(new dom.window.Event('input'));
document.querySelector('[data-sort="p95"]').click();
let times=rows().map(n=>Number(n.children[4].textContent));
assert.ok(times.every((n,i)=>!i||n>=times[i-1]));
document.querySelector('[data-sort="p95"]').click();
times=rows().map(n=>Number(n.children[4].textContent));
assert.ok(times.every((n,i)=>!i||n<=times[i-1]));
assert.equal(document.querySelectorAll('#pairs details').length,data.comparisons.length);
assert.equal(document.querySelectorAll('#details details').length,data.records.length);
assert.equal(document.getElementById('eligible').textContent,String(data.comparisons.filter(c=>c.paired_eligible).length));
assert.deepEqual(errors,[]); assert.deepEqual(external,[]);
const result={checked:true,engine:'jsdom 26.1.0',variants:data.records.length,search:true,evidence_filter:true,latency_sort_both_directions:true,details_render:true,javascript_errors:errors,external_requests:external,real_browser_rendering_checked:false,note:'DOM integration checks only. Headless Chromium download was unavailable; visual layout, native details expansion, and browser compatibility remain unverified.'};
if(output) fs.writeFileSync(output,JSON.stringify(result,null,2)+'\n');
process.stdout.write(JSON.stringify(result,null,2)+'\n');
dom.window.close();
