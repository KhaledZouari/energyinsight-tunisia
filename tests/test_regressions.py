"""Régressions qui ont changé les résultats ou la sécurité de publication."""
from pathlib import Path
import importlib.util
import sys
import unittest
import pandas as pd
from sqlalchemy import DateTime

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from database_io import prepare_dates, sql_types
from project_config import identifier
from ml_features import build_features, FEATURES


class RegressionTests(unittest.TestCase):
    def test_iso_dates_do_not_swap_month_day(self):
        dates = pd.Series(['2018-12-07','2013-02-12','invalid'])
        parsed = pd.to_datetime(dates,format='%Y-%m-%d',errors='coerce')
        self.assertEqual(parsed.iloc[0],pd.Timestamp('2018-12-07'))
        self.assertEqual(parsed.iloc[1],pd.Timestamp('2013-02-12'))
        self.assertTrue(pd.isna(parsed.iloc[2]))

    def test_all_sql_dates_are_datetime_and_invalid_dates_null(self):
        frame = pd.DataFrame({c:['2019-12-07','bad',None] for c in
            ['creation_date','month','first_invoice_date','last_invoice_date']})
        frame = prepare_dates(frame)
        for column in frame:
            self.assertTrue(frame[column].iloc[1:].isna().all())
            self.assertIsInstance(sql_types(frame)[column],DateTime)

    def test_features_do_not_depend_on_target_or_client_identifier(self):
        frame = pd.DataFrame({c:[1,2] for c in FEATURES})
        frame['target'] = [0,1]
        frame['client_id'] = ['client_a','client_b']
        first = build_features(frame)
        frame['target'] = [1,0]
        frame['client_id'] = ['client_c','client_d']
        pd.testing.assert_frame_equal(first,build_features(frame))

    def test_sql_identifier_rejects_injection(self):
        with self.assertRaises(ValueError):
            identifier('clients; DROP TABLE clients')


if __name__=='__main__':
    unittest.main()
