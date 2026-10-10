// Node is a development/CI check only; browser and Python users need no Node dependency.
const assert = require('node:assert/strict');
const view = require('../assets/dashboard_controls.js');
const dates = ['2025-12', '2026-01', '2026-03', '2026-04'];
const before = JSON.stringify(dates);
assert.deepEqual(view.rangeFor('12','','','2026-08'),{from:'2025-09',to:'2026-08'});
assert.deepEqual(view.indicesInWindow(dates,{from:'2026-01',to:'2026-03'}),[1,2]);
assert.equal(JSON.stringify(dates),before); // Missing February is neither inserted nor interpolated.
assert.deepEqual(view.indicesInWindow(dates,{from:'2030-01',to:'2030-12'}),[]);
assert.equal(view.monthNumber('2026-Q2'),view.monthNumber('2026-04'));
assert.equal(view.monthNumber('2026-13'),null);
assert.throws(()=>view.rangeFor('custom','2026-08','2026-01','2026-08'));
assert.deepEqual(view.rangeFor('all','','','2026-08'),{from:null,to:null});
const rows=[
  {key:'cpi',name:'CPI',provider:'原创模拟',sample:true},
  {key:'afre_flow',name:'社融',provider:'credit',source_url:'https://data.example.org/item',stale:true,verification_status:'仅取得数据，原文未核验'},
  {key:'dr007',name:'DR007',missing:true,provider:null},
  {key:'retail',name:'社零',provider:'eastmoney',verification_status:'原文已核验'}
];
assert.equal(view.filterRows(rows,{state:'sample'}).length,1);
assert.equal(view.filterRows(rows,{state:'missing'})[0].key,'dr007');
assert.equal(view.filterRows(rows,{state:'unverified'})[0].key,'afre_flow');
assert.equal(view.filterRows(rows,{state:'verified'})[0].key,'retail');
assert.equal(view.filterRows(rows,{state:'stale',source:'data.example.org',query:'社融'})[0].key,'afre_flow');
assert.equal(view.filterRows(rows,{state:'acquired'}).length,2);
const observations=[{indicator:'pmi',contribution:0.1},{indicator:'retail',contribution:-0.4},{indicator:'gdp',contribution:null}];
const frozen=JSON.stringify(observations);
assert.deepEqual(view.sortContributions(observations,'absolute').map(row=>row.indicator),['retail','pmi','gdp']);
assert.equal(JSON.stringify(observations),frozen);
const sensitivity={'0.5':0.6,'1.0':0.4,'2.0':null};
const priorSensitivity=JSON.stringify(sensitivity);
const scenarios=view.scenarioObservations(sensitivity,'absolute');
assert.equal(scenarios[0].scale,'0.5');
assert.equal(scenarios[2].change,null);
assert.ok(view.scenarioObservations({'0.5':0.3},'absolute').every(row=>row.change===null));
assert.equal(JSON.stringify(sensitivity),priorSensitivity);
console.log('View controls checked: date windows, gaps, source/state filtering, unknowns and immutable ordering.');
