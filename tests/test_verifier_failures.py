"""Vérifier que des incohérences réelles produisent un exit code non nul.

Seule la copie provisoire de la dernière exécution est utilisée puis restaurée.
"""
from pathlib import Path
import json
import os
import subprocess
import sys
import unittest

PROJECT = Path(__file__).resolve().parents[1]


class VerifierFailureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        status = PROJECT/'reports/pipeline_status.json'
        if not status.exists():
            raise unittest.SkipTest('Exécuter run_all.py avant les tests du vérificateur')
        cls.stage = Path(json.loads(status.read_text(encoding='utf-8'))['stage'])
        if not cls.stage.exists():
            raise unittest.SkipTest('Copie provisoire absente')

    def invoke(self, overrides=None):
        environment = dict(os.environ,ENERGYINSIGHT_OUTPUT_ROOT=str(self.stage),
                           ENERGYINSIGHT_TABLE_PREFIX='',PYTHONIOENCODING='utf-8')
        environment.update(overrides or {})
        previous = (self.stage/'reports/verification_results.json').read_bytes()
        try:
            result = subprocess.run([sys.executable,str(PROJECT/'reports/verify_project.py')],
                capture_output=True,text=True,encoding='utf-8',env=environment,timeout=300)
            data = json.loads((self.stage/'reports/verification_results.json').read_text(encoding='utf-8'))
            return result.returncode,data
        finally:
            (self.stage/'reports/verification_results.json').write_bytes(previous)

    def test_corrupt_threshold_is_rejected(self):
        path = self.stage/'models/model_metadata.json'
        previous = path.read_bytes()
        try:
            metadata = json.loads(previous)
            metadata['decision_threshold'] = 1.5
            path.write_text(json.dumps(metadata),encoding='utf-8')
            code,data = self.invoke()
            self.assertEqual(code,1)
            self.assertIn('threshold',data['errors'])
            self.assertIn('output_hash:models/model_metadata.json',data['errors'])
        finally:
            path.write_bytes(previous)

    def test_unreachable_mysql_is_critical(self):
        code,data = self.invoke({'MYSQL_PORT':'1'})
        self.assertEqual(code,1)
        self.assertTrue(any('OperationalError' in error for error in data['errors']))


if __name__=='__main__':
    unittest.main()
