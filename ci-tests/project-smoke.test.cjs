const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');

test('dashboard entrypoint and Worker API exist', () => {
  assert.ok(fs.existsSync(path.join(root, 'dashboard', 'src', 'App.tsx')));
  assert.ok(fs.existsSync(path.join(root, 'worker', 'src', 'index.ts')));
});

test('D1 schema enforces unique Cloudflare build UUIDs', () => {
  const sql = fs.readFileSync(path.join(root, 'worker', 'migrations', '0001_init.sql'), 'utf8');
  assert.match(sql, /cloudflare_build_uuid TEXT NOT NULL UNIQUE/);
});

test('the source tree ships no generated training observations', () => {
  const dataset = path.join(root, 'dataset', 'real_pipeline_history.csv');
  assert.equal(fs.existsSync(dataset), false);
});
