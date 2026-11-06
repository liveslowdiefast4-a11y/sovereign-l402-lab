import tempfile, pathlib, time, unittest, json, hmac, hashlib
from sovereign_l402.gateway import Settings, canonical, sha
from sovereign_l402.settlement_gateway import SettlementGateway
from sovereign_l402.evm_settlement import ExpectedPayment, TRANSFER_TOPIC

TOKEN, SENDER, RECEIVER = ('0x'+v*40 for v in ('1','2','3'))
TX = '0x'+'ab'*32
BLOCK = '0x'+'cd'*32
def topic(address): return '0x'+'0'*24+address[2:]
class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.key=b'x'*32
        self.settings=Settings('test-tenant',self.key,str(pathlib.Path(self.tmp.name)/'ledger.db'))
        self.policy=ExpectedPayment(84532,TOKEN,SENDER,RECEIVER,100,12)
        self.body=b'{"hello":"world"}'
        self.receipt={'transactionHash':TX,'status':'0x1','blockNumber':'0x64','blockHash':BLOCK,
          'logs':[{'address':TOKEN,'topics':[TRANSFER_TOPIC,topic(SENDER),topic(RECEIVER)],'data':'0x64'}]}
        self.data={'eth_chainId':'0x14a34','eth_getTransactionReceipt':self.receipt,
                   'eth_blockNumber':'0x6f','eth_getBlockByNumber':{'hash':BLOCK}}
        self.gateway=SettlementGateway(self.settings,self.policy,self.rpc)
    def rpc(self,method,params): return self.data[method]
    def ticket(self,**changes):
        claim={'version':1,'tenant':'test-tenant','path':'/v1/verify','body_sha256':sha(self.body),
               'nonce':'n'*24,'expires':int(time.time())+60,'settlement_id':TX}
        claim.update(changes)
        return json.dumps({'claim':claim,'mac':hmac.new(self.key,canonical(claim),hashlib.sha256).hexdigest()})
    def call(self,ticket=None):
        return self.gateway.handle('POST','/v1/verify',self.body,ticket)[0]
    def test_no_payment_402(self): self.assertEqual(self.call(),402)
    def test_paid_200(self): self.assertEqual(self.call(self.ticket()),200)
    def test_replay_402(self):
        t=self.ticket();self.assertEqual(self.call(t),200);self.assertEqual(self.call(t),402)
    def test_unmined_402(self):
        self.data['eth_getTransactionReceipt']=None;self.assertEqual(self.call(self.ticket()),402)
    def test_wrong_chain_402(self):
        self.data['eth_chainId']='0x1';self.assertEqual(self.call(self.ticket()),402)
    def test_underpaid_402(self):
        self.receipt['logs'][0]['data']='0x63';self.assertEqual(self.call(self.ticket()),402)
    def test_reverted_402(self):
        self.receipt['status']='0x0';self.assertEqual(self.call(self.ticket()),402)
    def test_sender_mismatch_402(self):
        self.receipt['logs'][0]['topics'][1]=topic(RECEIVER);self.assertEqual(self.call(self.ticket()),402)
    def test_bad_receipt_402(self):
        self.assertEqual(self.call(self.ticket(nonce='z'*24).replace('z','v')),402)
    def test_reorg_402(self):
        self.data['eth_getBlockByNumber']={'hash':TX};self.assertEqual(self.call(self.ticket()),402)
    def test_rpc_down_402(self):
        def broken(*a): raise TimeoutError()
        self.gateway=SettlementGateway(self.settings,self.policy,broken)
        self.assertEqual(self.call(self.ticket()),402)
    def test_payment_not_burned_when_rpc_down(self):
        t=self.ticket()
        self.data['eth_getTransactionReceipt']=None
        self.assertEqual(self.call(t),402)
        self.data['eth_getTransactionReceipt']=self.receipt
        self.assertEqual(self.call(t),200)
    def test_amount_bound_402(self):
        self.gateway=SettlementGateway(self.settings,ExpectedPayment(84532,TOKEN,SENDER,RECEIVER,101,12),self.rpc)
        self.assertEqual(self.call(self.ticket()),402)
