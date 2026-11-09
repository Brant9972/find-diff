// Run: node singer/validate-primary-markets.cjs
// Guardrails for the production quiz: every active record must have an explicit,
// ID-based primary entertainment market. Birthplace and nationality are NOT used.
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const read = name => JSON.parse(fs.readFileSync(path.join(__dirname, name), "utf8"));
const audit = read("primary-market-audit.json");
const policy = read("regional-draw-policy.json");
const regionDraw = require("./regional-draw.js");
const kinds = [
  ["questions", "questions.json"],
  ["actors", "actors.json"],
  ["variety", "variety.json"]
];
const allowed = new Set(["taiwan","hongkong","mainland","korea","japan","southeast_asia","other"]);
const catalog = new Map(), unique = new Map();
for (const [category, file] of kinds) {
  const source = read(file);
  assert.ok(Array.isArray(source.questions), file + " has no questions");
  for (const q of source.questions) {
    const key = category + ":" + q.id;
    assert.ok(!catalog.has(key), "Duplicate role and ID: " + key);
    catalog.set(key, q);
    assert.ok(q.id && q.name, "Missing id/name in " + key);
    const prev = unique.get(q.id);
    if (prev) assert.equal(prev.name, q.name, "Different names share id " + q.id);
    else unique.set(q.id, q);
  }
}
assert.equal(audit.entries.length, catalog.size, "Audit must cover every question record");
assert.equal(Object.keys(policy.primaryMarketsById || {}).length, unique.size, "ID map must cover every unique person");
const audited = new Set();
for (const row of audit.entries) {
  const key = row.category + ":" + row.id;
  assert.ok(!audited.has(key), "Duplicated audit entry " + key);
  audited.add(key);
  const q = catalog.get(key);
  assert.ok(q, "Audit entry no longer exists in live bank: " + key);
  assert.equal(row.name, q.name, "Audit name mismatch " + key);
  assert.ok(allowed.has(row.primaryMarket), "Unclassified or invalid market: " + key);
  assert.ok(row.reviewStatus, "Missing reviewStatus: " + key);
  assert.equal(policy.primaryMarketsById[row.id], row.primaryMarket, "Policy/audit disagreement: " + key);
  assert.equal(regionDraw.regionOf(q, policy), row.primaryMarket, "Runtime mapping disagrees: " + key);
}
for (const key of catalog.keys()) assert.ok(audited.has(key), "Unclassified live entry: " + key);
const people = [...unique.values()];
const trials = 100;
for (const size of [10,20]) {
  for (let i=0;i<trials;i++) {
    const deck = regionDraw.makeDeck(people, [], size, policy);
    assert.equal(deck.length, size);
    assert.equal(new Set(deck).size, size);
    const low = deck.filter(id => ["hongkong","mainland"].includes(policy.primaryMarketsById[id])).length;
    assert.ok(low <= Math.floor(size * policy.mainlandHongkongMaxShareForShortRounds), "Regional short-round cap broken");
  }
}
const history = people.slice(0, 30).map(x => x.id);
assert.ok(regionDraw.makeDeck(people, history, 20, policy).every(id => !history.includes(id)), "Unexpected repeated person");
const all = regionDraw.makeDeck(people, [], people.length, policy);
assert.equal(new Set(all).size, people.length, "All mode excluded people");
console.log("Primary-market QA passed: "+catalog.size+" records, "+unique.size+" IDs, no unclassified people; regional draw regression passed.");
