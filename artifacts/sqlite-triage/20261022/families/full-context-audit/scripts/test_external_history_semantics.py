import unittest
from external_history_semantics import normalize, normalize_aliases, ns_utc


class ExternalHistorySemanticsTests(unittest.TestCase):
    def test_duplicate_cot_columns_keep_wrapper_and_store_fields(self):
        row={'publication_confidence':'derived','publication_confidence__source_column_17':'source',
             'publication_delayed':False,'publication_delayed__source_column_18':True}
        got=normalize_aliases('cot.023651',row)
        self.assertEqual(got['publication_confidence'],'derived')
        self.assertEqual(got['store_publication_confidence'],'source')
        self.assertTrue(got['store_publication_delayed'])
        with self.assertRaises(AssertionError):
            normalize_aliases('cot.023651',dict(row,store_publication_confidence='conflicting'))

    def test_old_calendar_placement_is_not_backdated_to_session_open(self):
        row=dict(published_ns=1697493600000000000,sessions_since_prompt_expiry=14,
                 last_prompt_symbol='NGV23',last_prompt_expiry='2023-09-27')
        got=normalize('calendar.sessions_since_prompt_expiry',row,'20231017')
        self.assertEqual(got['available_ns'],1697565600000000000)
        self.assertIsNone(got['event_ns'])
        self.assertEqual(got['source_published_ns'],row['published_ns'])

    def test_mos_same_forecast_target_has_same_scope_across_file_horizon_change(self):
        row=dict(published_ns=1697430600000000000,model='GFS',runtime_utc='2023-10-16 00:00:00',
                 target_day='2023-10-18',horizon_days=1,gw_hdd=5,gw_cdd=0,n_metros=16,coverage=1.,metros_missing=[])
        older=normalize('mos.gw_by_cycle',row,'20231017')
        newer=normalize('mos.gw_by_cycle',dict(row,horizon_days=0),'20231018')
        self.assertEqual(older['scope'],newer['scope'])
        self.assertEqual(older['observation'],newer['observation'])
        self.assertEqual(older['numeric'],newer['numeric'])
        self.assertEqual(older['provenance']['source_horizon_days'],1)
        self.assertEqual(newer['provenance']['source_horizon_days'],0)

    def test_statistics_unused_quantity_and_reference_are_unavailable(self):
        row=dict(published_ns=1697500807388465967,event_time_ns=1697500807388321007,
                 ts_event=1697500807388321007,ts_ref=18446744073709551615,
                 instrument_id=21258,raw_symbol='NG:BF Z3-F4-G4',stat_type=7,
                 price=-.297,quantity=9223372036854775807,update_action=1,stat_flags=0)
        got=normalize('curve.statistics',row,'20231018')
        self.assertIsNone(got['numeric']['quantity'])
        self.assertEqual(got['states']['quantity'],'UNDEFINED_STAT_QUANTITY')
        self.assertIsNone(got['provenance']['reference_ns'])
        self.assertEqual(got['numeric']['price'],-.297)
        self.assertNotIn('instrument_id',got['numeric'])

    def test_weather_latest_missing_and_real_zero_stay_distinct(self):
        row=dict(published_ns=1697321400000000000,station='ATL',valid_utc='2023-10-14 22:00',
                 tmpf='M',p01i='0.00',skyc1='FEW')
        got=normalize('weather.obs_hourly',row,'20231018')
        self.assertIsNone(got['numeric']['tmpf'])
        self.assertEqual(got['states']['tmpf'],'SOURCE_MISSING_MARKER_M')
        self.assertEqual(got['numeric']['p01i'],0.)
        self.assertEqual(got['categories']['skyc1'],'FEW')

    def test_exact_timestamp_and_eia_scopes(self):
        self.assertEqual(ns_utc('2023-10-14 22:00'),1697320800000000000)
        row=dict(published_ns=1696896000000000000,period_utc='2023-10-09T22',
                 respondent='CISO',route='fuel-type-data',fueltype_or_type='COL',value=0.,units='megawatthours')
        a=normalize('eia930.hourly',row,'20231018')
        b=normalize('eia930.hourly',dict(row,respondent='US48'),'20231018')
        self.assertNotEqual(a['scope'],b['scope'])
        self.assertEqual(a['numeric']['value'],0.)

    def test_unknown_field_blocks_completeness(self):
        with self.assertRaises(ValueError):
            normalize('weather.obs_hourly',dict(published_ns=10,station='ATL',valid_utc='2023-10-14 22:00',unreviewed_field=7),'20231018')

    def test_deleted_statistic_is_not_an_observed_live_value(self):
        row=dict(published_ns=10,ts_event=9,ts_ref=8,instrument_id=1,raw_symbol='NGX3',
                 stat_type=3,price=3.1,quantity=0,update_action=2,stat_flags=0)
        got=normalize('curve.statistics',row,'20231018')
        self.assertIsNone(got['numeric']['price'])
        self.assertEqual(got['states']['price'],'DELETED_STATISTIC')


if __name__=='__main__':unittest.main()
