import tempfile
import multiprocessing
import unittest
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from sovereign_l402.ledger import BudgetLedger, BudgetError

def attempt(args):
    path,i=args
    return BudgetLedger(path).reserve('demo', f'req-{i}', 100)

class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=str(Path(self.tmp.name)/'budget.db')
        self.ledger=BudgetLedger(self.path)
        self.ledger.create_budget('demo',1000)
    def tearDown(self): self.tmp.cleanup()
    def test_idempotent_reserve_and_settlement(self):
        self.assertTrue(self.ledger.reserve('demo','x',150))
        self.assertFalse(self.ledger.reserve('demo','x',150))
        self.assertTrue(self.ledger.finish('x','SETTLED'))
        self.assertFalse(self.ledger.finish('x','SETTLED'))
        self.assertEqual(self.ledger.snapshot('demo'),dict(cap_msat=1000,spent_msat=150,reserved_msat=0))
    def test_cancel_and_forbidden_revival(self):
        self.ledger.reserve('demo','y',400)
        self.ledger.finish('y','CANCELED')
        with self.assertRaises(BudgetError): self.ledger.finish('y','SETTLED')
        self.assertEqual(self.ledger.snapshot('demo')['reserved_msat'],0)
    def test_collision_and_overflow(self):
        self.ledger.reserve('demo','y',800)
        with self.assertRaises(BudgetError): self.ledger.reserve('demo','y',100)
        with self.assertRaises(BudgetError): self.ledger.reserve('demo','z',300)
        self.assertEqual(self.ledger.snapshot('demo')['reserved_msat'],800)
    def test_40_process_requests(self):
        with ProcessPoolExecutor(max_workers=8, mp_context=multiprocessing.get_context("spawn")) as pool:
            results=[]
            for f in [pool.submit(attempt,(self.path,i)) for i in range(40)]:
                try: results.append(f.result())
                except BudgetError: results.append(False)
        self.assertEqual(sum(results),10)
        snap=self.ledger.snapshot('demo')
        self.assertEqual(snap['reserved_msat'],1000)
        self.assertLessEqual(snap['spent_msat']+snap['reserved_msat'],snap['cap_msat'])
    def test_30_thread_replay(self):
        with ThreadPoolExecutor(max_workers=30) as pool:
            outcomes=list(pool.map(lambda _: self.ledger.reserve('demo','same',250),range(30)))
        self.assertEqual(sum(outcomes),1)
        self.assertEqual(self.ledger.snapshot('demo')['reserved_msat'],250)
