import json
import sqlite3
import unittest

from query_saved_run_connections import lineage_connections, navigation_database, neighboring_cases


class SavedRunConnectionTests(unittest.TestCase):
    def test_context_join_keeps_nanoseconds_equal_times_and_instruments(self):
        clock = 1697581526067136130
        cases = [dict(instance=i, instrument_id=instrument, start_receive_ns=start,
                      decision_cutoff_ns=start - 1, pre_input_cursor=i)
                 for i, instrument, start in [(1, 150611, clock - 1), (2, 150611, clock),
                                               (3, 150611, clock), (4, 150611, clock + 1),
                                               (5, 999, clock)]]
        db = navigation_database([], cases)
        result = neighboring_cases(db, 150611, clock)
        self.assertEqual(result['all_prior_or_equal_start_line_range'], [1, 3])
        self.assertEqual(result['all_later_start_line_range'], [4, 4])
        self.assertEqual(result['nearest_prior_or_equal_start_line'], 3)
        self.assertEqual(result['nearest_later_start_line'], 4)
        db.close()

    def test_late_contradictory_lineage_roles_remain_separate(self):
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE record(record_sha256,known_by_ns,input_cursor,instrument_id,row_json,section)')
        clock = 1697581526067136130
        records = [dict(node_id='ord-17', parent_id='ord-17', status='CENSORED_SEGMENT_END',
                        side_orientation='A', entered_recv_ns=clock - 100),
                   dict(node_id='ord-17', parent_id=None, status='TERMINATED', side_orientation='B')]
        db.executemany('INSERT INTO record VALUES(?,?,?,?,?,?)',
                       [(str(i), clock + i + 1, 20 + i, 150611, json.dumps(r), 'lineage')
                        for i, r in enumerate(records)])
        links = lineage_connections(db, {(150611, 17), (999, 17)})
        self.assertEqual(len(links[(150611, 17)]), 3)
        self.assertNotIn((999, 17), links)
        self.assertEqual({r['source_status'] for r in links[(150611, 17)]},
                         {'CENSORED_SEGMENT_END', 'TERMINATED'})
        self.assertTrue(all(r['known_by_ns'] > clock for r in links[(150611, 17)]))
        self.assertEqual(links[(150611, 17)][0]['entered_recv_ns'], clock - 100)
        db.close()


if __name__ == '__main__':
    unittest.main()
