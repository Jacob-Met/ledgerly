import {expect, it} from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import {loadPyodide} from 'pyodide';

it('executes the native overdue-batch contracts in the actual Pyodide runtime', async () => {
  const web = process.cwd();
  const root = path.resolve(web, '..');
  const py = await loadPyodide();
  for (const directory of ['/project/ledgerly', '/project/web-demo/python', '/project/tests', '/project/fixtures'])
    py.FS.mkdirTree(directory);
  for (const name of ['__init__.py', 'agent.py', 'extract.py', 'paypal.py'])
    py.FS.writeFile(`/project/ledgerly/${name}`, fs.readFileSync(path.join(web, 'public/python/ledgerly', name), 'utf8'));
  for (const name of ['bridge.py', 'review.py'])
    py.FS.writeFile(`/project/web-demo/python/${name}`, fs.readFileSync(path.join(web, 'public/python', name), 'utf8'));
  py.FS.writeFile('/project/fixtures/01_simple_usd_hourly.txt', fs.readFileSync(path.join(web, 'public/fixtures/01_simple_usd_hourly.txt'), 'utf8'));
  py.FS.writeFile('/project/tests/test_browser_overdue_scan.py', fs.readFileSync(path.join(root, 'tests/test_browser_overdue_scan.py'), 'utf8'));
  const report = JSON.parse(String(await py.runPythonAsync(`
import io, json, sys, unittest
sys.path[:0] = ['/project', '/project/tests']
suite = unittest.defaultTestLoader.loadTestsFromName('test_browser_overdue_scan')
output = io.StringIO()
result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
json.dumps({'tests_run': result.testsRun, 'successful': result.wasSuccessful(),
            'failures': [{'test': case.id(), 'detail': detail} for case, detail in result.failures],
            'errors': [{'test': case.id(), 'detail': detail} for case, detail in result.errors],
            'output': output.getvalue(), 'python': sys.version})
  `)));
  console.log(JSON.stringify({native_tests_run: report.tests_run, successful: report.successful, python: report.python}));
  expect(report.errors, report.output).toEqual([]);
  expect(report.failures, report.output).toEqual([]);
  expect(report.tests_run).toBe(6);
  expect(report.successful).toBe(true);
}, 60000);
