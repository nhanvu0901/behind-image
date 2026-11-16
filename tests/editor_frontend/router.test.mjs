import test from 'node:test';
import assert from 'node:assert/strict';
import { parseHash, formatHash, projectHash, legacyTarget, legacyLibraryHash, STEP_IDS } from '../../bti/editor/static/js/router.js';

test('home and library routes', () => {
  assert.deepEqual(parseHash(''), { name: 'home' });
  assert.deepEqual(parseHash('#/'), { name: 'home' });
  assert.deepEqual(parseHash('#/library'), { name: 'library', sub: 'artworks' });
  assert.deepEqual(parseHash('#/library/books'), { name: 'library', sub: 'shelf' });
  assert.deepEqual(parseHash('#/library/book/payne_gae'), { name: 'library', sub: 'book', bid: 'payne_gae' });
  assert.deepEqual(parseHash('#/library/work/payne_gae/2'), { name: 'library', sub: 'work', bid: 'payne_gae', n: 2 });
  assert.deepEqual(parseHash('#/library/artwork/vinci-mona-lisa'), { name: 'library', sub: 'artwork', key: 'vinci-mona-lisa' });
  assert.equal(parseHash('#/library/work/payne_gae/x').name, 'notfound');
  assert.equal(parseHash('#/library/nope').name, 'notfound');
});

test('project routes: a step, or none (the shell then lands on the step the stage calls for)', () => {
  assert.deepEqual(parseHash('#/project/arn'), { name: 'project', pid: 'arn', step: null });
  for (const s of STEP_IDS) assert.deepEqual(parseHash(`#/project/arn/${s}`), { name: 'project', pid: 'arn', step: s });
  assert.equal(parseHash('#/project/arn/dance').name, 'notfound');
  assert.equal(parseHash('#/project/Bad%20Id/edit').name, 'notfound');
  assert.equal(parseHash('#/project/../edit').name, 'notfound');
  assert.equal(parseHash('#/project/arn/edit/extra').name, 'notfound');
  assert.equal(parseHash('#/project/arn/edit?x=1').step, 'edit');
  assert.equal(parseHash('#/whatever').name, 'notfound');
});

test('format and parse round trip', () => {
  for (const h of ['#/', '#/library', '#/library/books', '#/library/book/hodge_aid', '#/library/work/hodge_aid/3', '#/library/artwork/eyck-the-arnolfini-portrait', '#/project/arn', '#/project/arn_2/script']) {
    assert.equal(formatHash(parseHash(h)), h);
  }
  assert.equal(projectHash('x', 'edit'), '#/project/x/edit');
  assert.equal(projectHash('x'), '#/project/x');
});

test('the steps are the six steps of the pipeline, in order', () => {
  assert.deepEqual(STEP_IDS, ['artwork', 'script', 'voice', 'picks', 'edit', 'export']);
});

test('old library.html hash routes', () => {
  assert.equal(legacyLibraryHash(''), '#/library');
  assert.equal(legacyLibraryHash('#/'), '#/library');
  assert.equal(legacyLibraryHash('#/books'), '#/library/books');
  assert.equal(legacyLibraryHash('#/projects'), '#/');
  assert.equal(legacyLibraryHash('#/artwork/vinci-mona-lisa'), '#/library/artwork/vinci-mona-lisa');
  assert.equal(legacyLibraryHash('#/book/payne_gae'), '#/library/book/payne_gae');
  assert.equal(legacyLibraryHash('#/work/hodge_aid/3'), '#/library/work/hodge_aid/3');
  assert.equal(legacyLibraryHash('#/garbage/x'), '#/library');
});

test('old addresses redirect into the app and keep ?mock=1 and ?all=1', () => {
  assert.deepEqual(legacyTarget({ pathname: '/library.html', search: '', hash: '#/books' }), { search: '', hash: '#/library/books' });
  assert.deepEqual(legacyTarget({ pathname: '/library.html', search: '?mock=1', hash: '' }), { search: '?mock=1', hash: '#/library' });
  assert.deepEqual(legacyTarget({ pathname: '/script.html', search: '?project=arn', hash: '' }), { search: '', hash: '#/project/arn/script' });
  assert.deepEqual(legacyTarget({ pathname: '/script.html', search: '?project=arn&all=1', hash: '' }), { search: '?all=1', hash: '#/project/arn/script' });
  assert.deepEqual(legacyTarget({ pathname: '/script.html', search: '', hash: '' }), { search: '', hash: '#/' });
  assert.deepEqual(legacyTarget({ pathname: '/', search: '?project=arnolfini_edit', hash: '' }), { search: '', hash: '#/project/arnolfini_edit/edit' });
  assert.deepEqual(legacyTarget({ pathname: '/', search: '?project=arn&mock=1&all=1', hash: '' }), { search: '?mock=1&all=1', hash: '#/project/arn/edit' });
  assert.deepEqual(legacyTarget({ pathname: '/index.html', search: '?project=arn', hash: '' }), { search: '', hash: '#/project/arn/edit' });
});

test('addresses of the app itself are left alone; a bad project id never becomes a route', () => {
  assert.equal(legacyTarget({ pathname: '/', search: '', hash: '' }), null);
  assert.equal(legacyTarget({ pathname: '/', search: '?mock=1', hash: '#/project/a/edit' }), null);
  assert.equal(legacyTarget({ pathname: '/', search: '?all=1', hash: '#/library' }), null);
  assert.deepEqual(legacyTarget({ pathname: '/', search: '?project=../../x', hash: '' }), { search: '', hash: '#/' });
  assert.deepEqual(legacyTarget({ pathname: '/script.html', search: '?project=A%20B', hash: '' }), { search: '', hash: '#/' });
});
