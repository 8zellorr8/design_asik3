"""Regression checks for public tooling, separate from algorithm implementations."""
import copy
import contextlib
import io
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import public_validate
import run


class ValidatorTests(unittest.TestCase):
    def test_published_answers(self):
        cases = json.loads((run.P / 'tools/public.json').read_text(encoding='utf-8'))
        for case in cases:
            with self.subTest(case=case['name']):
                self.assertTrue(public_validate.check(case['input'], case['output'], case['output']))

    def test_alternative_topological_order_and_labels(self):
        request = {'task': 'topo', 'n': 3, 'edges': [[0, 2], [1, 2]]}
        self.assertTrue(public_validate.check(request, {'acyclic': True, 'order': [1, 0, 2]},
                                             {'acyclic': True, 'order': [0, 1, 2]}))
        request = {'task': 'scc', 'n': 3, 'edges': [[0, 1], [1, 0], [1, 2]]}
        self.assertTrue(public_validate.check(request, {'component': [7, 7, 20], 'condensation': [[7, 20]]},
                                             {'component': [0, 0, 1], 'condensation': [[0, 1]]}))

    def test_alternative_optima_and_invalid_witnesses(self):
        request = {'task': 'kruskal', 'n': 4,
                   'edges': [[0, 1, -2], [0, 1, -2], [1, 2, 3], [0, 2, 3], [3, 3, -99]]}
        expected = {'cost': 1, 'components': 2, 'edge_ids': [0, 2]}
        for task in ('kruskal', 'prim'):
            request['task'] = task
            self.assertTrue(public_validate.check(request, dict(expected, edge_ids=[1, 3]), expected))
            for ids in ([0, 0], [0, 1], [0, 4], [0], [0, 2, 3]):
                self.assertFalse(public_validate.check(request, dict(expected, edge_ids=ids), expected))
        request = {'task': 'dag', 'n': 5, 'source': 0,
                   'edges': [[0, 1, 2], [0, 1, 2], [0, 2, 1], [1, 3, -3], [2, 3, -2]]}
        expected = {'acyclic': True, 'distance': [0, 2, 1, -1, None], 'parent_edge': [-1, 0, 2, 3, -1]}
        self.assertTrue(public_validate.check(request, dict(expected, parent_edge=[-1, 1, 2, 4, -1]), expected))
        for parents in ([-1, 0, 2, 0, -1], [-1, 0, 2, 3, 4], [0, 0, 2, 3, -1]):
            self.assertFalse(public_validate.check(request, dict(expected, parent_edge=parents), expected))
        request = {'task': 'scc', 'n': 3, 'edges': [[0, 1], [1, 0], [1, 2], [1, 2]]}
        expected = {'component': [0, 0, 1], 'condensation': [[0, 1]]}
        for answer in ({'component': [5, 5, 9], 'condensation': [[5, 9], [5, 9]]},
                       {'component': [5, 5, 9], 'condensation': []},
                       {'component': [5, 5, 5], 'condensation': []}):
            self.assertFalse(public_validate.check(request, answer, expected))

    def test_bad_types_missing_fields_and_witnesses(self):
        examples = [
            ({'task': 'dsu', 'n': 2, 'operations': [[0, 1]]}, {'states': [[1, 2]]}),
            ({'task': 'prim', 'n': 2, 'edges': [[0, 1, 2]]}, {'cost': 2, 'components': 1, 'edge_ids': [0]}),
            ({'task': 'topo', 'n': 2, 'edges': [[0, 1]]}, {'acyclic': True, 'order': [0, 1]}),
            ({'task': 'dag', 'n': 2, 'source': 0, 'edges': [[0, 1, 1]]},
             {'acyclic': True, 'distance': [0, 1], 'parent_edge': [-1, 0]}),
        ]
        for request, expected in examples:
            for malformed in [None, [], {}, {'error': 'TODO'}]:
                self.assertFalse(public_validate.check(request, malformed, expected))
            for key, value in expected.items():
                malformed = copy.deepcopy(expected)
                del malformed[key]
                self.assertFalse(public_validate.check(request, malformed, expected))
                if type(value) is bool:
                    malformed = copy.deepcopy(expected)
                    malformed[key] = int(value)
                    self.assertFalse(public_validate.check(request, malformed, expected))
                elif type(value) is int:
                    malformed = copy.deepcopy(expected)
                    malformed[key] = float(value)
                    self.assertFalse(public_validate.check(request, malformed, expected))
        self.assertFalse(public_validate.check(examples[2][0], {'acyclic': True, 'order': [False, True]}, examples[2][1]))
        self.assertFalse(public_validate.check(examples[3][0], {'acyclic': True, 'distance': [0, 1], 'parent_edge': [-1, -1]}, examples[3][1]))


class LauncherTests(unittest.TestCase):
    def test_custom_input_timeout(self):
        with tempfile.TemporaryDirectory() as folder:
            request_file = pathlib.Path(folder) / 'input.jsonl'
            request_file.write_text('{"task":"ping"}\n', encoding='utf-8')
            error_output = io.StringIO()
            with patch.object(sys, 'argv', ['run.py', '--language', 'Java', '--input', str(request_file)]), \
                    patch.object(run, 'build', return_value=['probe']), \
                    patch.object(run.subprocess, 'run', side_effect=subprocess.TimeoutExpired(['probe'], 20)) as execute, \
                    contextlib.redirect_stderr(error_output):
                self.assertEqual(run.main(), 1)
            self.assertEqual(execute.call_args.kwargs['timeout'], 20)
            self.assertIn('Input batch failed: program exceeded 20 seconds', error_output.getvalue())
            self.assertNotIn('compilation', error_output.getvalue())

    def test_manifest_and_explicit_override(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(run, 'P', pathlib.Path(folder)):
            manifest = pathlib.Path(folder) / 'submission.json'
            manifest.write_text('{"language":"Java"}', encoding='utf-8')
            self.assertEqual(run.select_language(None), 'Java')
            self.assertEqual(run.select_language('Java'), 'Java')
            for language in ('Python', 'Cpp', 'CSharp', 'Unknown', None):
                manifest.write_text(json.dumps({'language': language}), encoding='utf-8')
                with self.subTest(language=language):
                    with self.assertRaisesRegex(ValueError, 'Java only'):
                        run.select_language(None)
                    with self.assertRaisesRegex(ValueError, 'Java only'):
                        run.build(language)
                    if language is not None:
                        with self.assertRaisesRegex(ValueError, 'Java only'):
                            run.select_language(language)
                    self.assertEqual(run.select_language('Java'), 'Java')

    def test_protocol_and_runtime_diagnostics(self):
        with tempfile.TemporaryDirectory() as folder:
            script = pathlib.Path(folder) / 'probe.py'
            command = [sys.executable, str(script)]
            script.write_text('import sys\nfor line in sys.stdin: print("{\\"status\\":\\"ready\\"}")\n', encoding='utf-8')
            self.assertEqual(run.execute(command, [{'task': 'ping'}] * 2), [{'status': 'ready'}] * 2)
            for text, message in [
                ('print("debug")\n', 'expected 2'),
                ('print("{}")\nprint("{}")\nprint("{}")\n', 'expected 2'),
                ('print("{\\"error\\":\\"TODO dsu\\"}")\n', 'TODO dsu'),
                ('print("[]")\n', 'JSON object'),
                ('print("{\\"cost\\":NaN}")\n', 'not a JSON number'),
                ('import sys\nprint("trace detail",file=sys.stderr)\nsys.exit(4)\n', 'trace detail'),
            ]:
                script.write_text(text, encoding='utf-8')
                requests = [{'task': 'ping'}] * (2 if message.startswith('expected') else 1)
                with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                    run.execute(command, requests)

    def test_utf8_transport(self):
        with tempfile.TemporaryDirectory() as folder:
            script = pathlib.Path(folder) / 'probe.py'
            script.write_text('import sys,json\nfor line in sys.stdin:\n'
                              ' x=json.loads(line);sys.stdout.buffer.write((json.dumps(x,ensure_ascii=False)+"\\n").encode("utf-8"))\n',
                              encoding='utf-8')
            requests = [{'note': 'Қазақша русский café 🎓'}] * 2
            self.assertEqual(run.execute([sys.executable, str(script)], requests), requests)

    @unittest.skipUnless(shutil.which('javac') and shutil.which('java'), 'Java compiler is not installed')
    def test_java_input_helpers_and_json_transport(self):
        with tempfile.TemporaryDirectory() as folder:
            source = pathlib.Path(folder)
            for name in ('Input.java', 'Json.java', 'Main.java'):
                shutil.copyfile(run.P / 'src/Java' / name, source / name)
            (source / 'TransportProbe.java').write_text(r'''
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
public class TransportProbe {
    static Map<String, Object> handle(Map<String, Object> request) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("original", request);
        result.put("n", Input.vertexCount(request));
        int[][] rows = request.get("task").equals("dsu")
            ? Input.operations(request) : Input.edges(request);
        result.put("rows", rows);
        if (request.get("task").equals("dag")) {
            result.put("source", Input.source(request));
        }
        result.put("distance", new Long[]{0L, null, -1L, 3000000000L});
        result.put("flags", Arrays.asList(true, false));
        result.put("note", "quote=\" slash=\\ line=\n tab=\t");
        return result;
    }
}
''', encoding='utf-8')
            methods = ''.join('static Map<String,Object> ' + name
                              + '(Map<String,Object> x){return TransportProbe.handle(x);}'
                              for name in ('dsu', 'kruskal', 'prim', 'scc', 'topo', 'dag'))
            (source / 'Algorithms.java').write_text(
                'import java.util.*; public class Algorithms {' + methods + '}', encoding='utf-8')
            subprocess.run(['javac', '--release', '17', '-encoding', 'UTF-8', '-d', folder,
                            *map(str, source.glob('*.java'))], check=True, timeout=60)
            requests = [case['input'] for case in json.loads(
                (run.P / 'tools/public.json').read_text(encoding='utf-8'))]
            unicode_request = {
                'task': 'dsu', 'n': 0, 'operations': [],
                'note': 'Қазақша русский café 🎓\n\t\b\f\r"\\',
            }
            requests.append(unicode_request)
            command = ['java', '-Xmx384m', '-cp', folder, 'Main']
            answers = run.execute(command, requests * 2)
            for request, answer in zip(requests * 2, answers):
                with self.subTest(task=request['task']):
                    if request['task'] == 'ping':
                        self.assertEqual(answer, {'status': 'ready'})
                        continue
                    self.assertEqual(answer['original'], request)
                    self.assertEqual(answer['distance'], [0, None, -1, 3000000000])
                    self.assertEqual(answer['flags'], [True, False])
                    self.assertEqual(answer['note'], 'quote=" slash=\\ line=\n tab=\t')
                    if request['task'] != 'ping':
                        self.assertEqual(answer['n'], request['n'])
                        self.assertEqual(answer['rows'], request.get('operations', request.get('edges')))
                    if request['task'] == 'dag':
                        self.assertEqual(answer['source'], request['source'])
            literal = subprocess.run(
                command, input=json.dumps(unicode_request, ensure_ascii=False) + '\n',
                capture_output=True, text=True, encoding='utf-8', timeout=20,
            )
            self.assertEqual(literal.returncode, 0, literal.stderr)
            self.assertEqual(json.loads(literal.stdout)['original'], unicode_request)

    @unittest.skipUnless(shutil.which('javac') and shutil.which('java'), 'Java compiler is not installed')
    def test_java_helper_source(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(run, 'P', pathlib.Path(folder)):
            source = pathlib.Path(folder) / 'src/Java'
            source.mkdir(parents=True)
            (source / 'Main.java').write_text('public class Main {public static void main(String[] a){if(Helper.value()!=42)throw new Error();}}\n')
            (source / 'Helper.java').write_text('class Helper {static int value(){return 42;}}\n')
            self.assertEqual(subprocess.run(run.build('Java'), timeout=20).returncode, 0)

if __name__ == '__main__':
    unittest.main()
