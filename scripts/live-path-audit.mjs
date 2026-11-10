/** Read-only proof that a deposit, buyer release and expiry refund
 * succeeded against one pinned EVM escrow and one token. Never sends funds. */
import {readFileSync} from 'node:fs';
import {Contract,Interface,getAddress,JsonRpcProvider} from 'ethers';
import {assessMainnet,BASE_USDC} from './mainnet-preflight.mjs';
const abi=JSON.parse(readFileSync('artifacts/SovereignEscrow.json','utf8')).abi;
const escrowEvents=new Interface(abi);
const tokenEvents=new Interface(['event Transfer(address indexed from,address indexed to,uint256 value)']);
const same=(a,b)=>getAddress(a)===getAddress(b);
const requireOk=(v,m)=>{if(!v)throw Error(m)};
const hex32=x=>typeof x==='string'&&/^0x[0-9a-fA-F]{64}$/.test(x);
function events(receipt,contract,iface,eventName){
 return receipt.logs.filter(log=>same(log.address,contract)).flatMap(log=>{
  try{const parsed=iface.parseLog(log);return parsed?.name===eventName?[parsed.args]:[]}
  catch{return []}
 });
}
async function receipt(provider,tx,latest,minConf){
 requireOk(hex32(tx),'malformed transaction hash');
 const result=await provider.getTransactionReceipt(tx);
 requireOk(result?.status===1,'missing or reverted transaction '+tx);
 requireOk(latest-result.blockNumber+1>=minConf,'insufficient confirmations');
 const block=await provider.getBlock(result.blockNumber);
 requireOk(block?.hash?.toLowerCase()===result.blockHash.toLowerCase(),'noncanonical block');
 return result;
}
function transferMatches(logs,from,to,amount){
 return logs.filter(t=>same(t.from,from)&&same(t.to,to)&&t.value===amount).length;
}
function checkDeposit(r,ctx,o){
 const funded=events(r,ctx.escrow,escrowEvents,'Funded');
 requireOk(funded.length===1,'missing unique Funded event');
 const f=funded[0];
 requireOk(f.orderId.toLowerCase()===o.id.toLowerCase()&&same(f.payer,ctx.payer)&&
           same(f.provider,ctx.provider)&&f.amount===BigInt(o.amount)&&
           f.commitment.toLowerCase()===o.commitment.toLowerCase(),'incorrect Funded evidence');
 const transfers=events(r,ctx.token,tokenEvents,'Transfer');
 requireOk(transfers.length===1&&transferMatches(transfers,ctx.payer,ctx.escrow,BigInt(o.amount))===1,
           'escrow deposit token transfer invalid');
}
function checkRelease(r,ctx,o){
 const released=events(r,ctx.escrow,escrowEvents,'Released');
 requireOk(released.length===1&&released[0].orderId.toLowerCase()===o.id.toLowerCase(),
           'missing unique Released event');
 const amount=BigInt(o.amount),fee=amount*BigInt(ctx.feeBps)/10000n,net=amount-fee;
 requireOk(released[0].providerAmount===net&&released[0].feeAmount===fee,
           'released amount or fee mismatch');
 const transfers=events(r,ctx.token,tokenEvents,'Transfer');
 requireOk(transfers.length===(fee?2:1),'unexpected released token transfers');
 requireOk(transferMatches(transfers,ctx.escrow,ctx.provider,net)===1,'provider net payout invalid');
 if(fee)requireOk(transferMatches(transfers,ctx.escrow,ctx.feeRecipient,fee)===1,'fee transfer invalid');
 return {net:String(net),fee:String(fee)};
}
function checkRefund(r,ctx,o){
 const refunded=events(r,ctx.escrow,escrowEvents,'Refunded');
 requireOk(refunded.length===1&&refunded[0].orderId.toLowerCase()===o.id.toLowerCase()&&
          refunded[0].amount===BigInt(o.amount),'refund event invalid');
 const transfers=events(r,ctx.token,tokenEvents,'Transfer');
 requireOk(transfers.length===1&&transferMatches(transfers,ctx.escrow,ctx.payer,BigInt(o.amount))===1,
           'payer did not receive full refund');
}
export async function verifyPath({provider,ctx,release,refund,chainId=8453,minConfirmations=12}){
 requireOk(Number.isInteger(minConfirmations)&&minConfirmations>=1,'invalid confirmations');
 requireOk(Number((await provider.getNetwork()).chainId)===chainId,'wrong blockchain');
 requireOk(ctx.feeBps===100,'unapproved protocol fee');
 for(const [name,o] of [['release',release],['refund',refund]]){
  requireOk(o&&hex32(o.id)&&hex32(o.commitment)&&hex32(o.fundTx)&&hex32(o.terminalTx),
            name+' manifest invalid');
  requireOk(BigInt(o.amount)>0n,name+' amount invalid');
 }
 const ids=[release.id,refund.id],txs=[release.fundTx,release.terminalTx,refund.fundTx,refund.terminalTx];
 requireOk(new Set(ids.map(s=>s.toLowerCase())).size===2,'duplicate order');
 requireOk(new Set(txs.map(s=>s.toLowerCase())).size===4,'duplicate transaction');
 const escrow=new Contract(ctx.escrow,abi,provider);
 requireOk(same(await escrow.token(),ctx.token),'wrong asset');
 requireOk(same(await escrow.feeRecipient(),ctx.feeRecipient),'wrong fee recipient');
 requireOk(Number(await escrow.feeBps())===ctx.feeBps,'wrong contract fee');
 const latest=await provider.getBlockNumber();
 const proofs=[];
 for(const [name,o] of [['release',release],['refund',refund]]){
  const funded=await receipt(provider,o.fundTx,latest,minConfirmations);
  const terminated=await receipt(provider,o.terminalTx,latest,minConfirmations);
  requireOk(terminated.blockNumber>=funded.blockNumber,'terminal transaction predates deposit');
  checkDeposit(funded,ctx,o);
  const details=name==='release'?checkRelease(terminated,ctx,o):(checkRefund(terminated,ctx,o),{});
  const state=await escrow.orders(o.id);
  requireOk(same(state.payer,ctx.payer)&&same(state.provider,ctx.provider)&&
            state.amount===BigInt(o.amount)&&state.commitment.toLowerCase()===o.commitment.toLowerCase(),
            'on-chain order does not match manifest');
  requireOk(Number(state.state)===(name==='release'?2:3),'on-chain order state incorrect');
  proofs.push({order:o.id,status:name==='release'?'RELEASED':'REFUNDED',fundTx:o.fundTx,
              terminalTx:o.terminalTx,amount:String(o.amount),...details});
 }
 return {ok:true,status:'HISTORICAL_PATH_REPRODUCED',chainId,
         inspectedAtBlock:latest,minConfirmations,proofs,
         caveat:'Historical transaction verification is not authorization to receive future customer funds.'};
}
if(process.argv[1]?.endsWith('live-path-audit.mjs')){
 const rpc=process.env.SOVEREIGN_MAINNET_RPC_URL;
 const file=process.env.SOVEREIGN_MAINNET_ACCEPTANCE_EVIDENCE;
 if(!rpc?.startsWith('https://')||!file)throw Error('Missing read-only RPC and acceptance manifest');
 const input=JSON.parse(readFileSync(file,'utf8'));
 const provider=new JsonRpcProvider(rpc);
 const artifact=JSON.parse(readFileSync('artifacts/SovereignEscrow.json','utf8'));
 const preflight=await assessMainnet({provider,escrowAddress:input.ctx.escrow,
                                     feeRecipient:input.ctx.feeRecipient,artifact,approvedRuntimeHash:process.env.SOVEREIGN_APPROVED_RUNTIME_HASH});
 requireOk(preflight.ok,'Mainnet preflight failed: '+preflight.reason);
 requireOk(same(input.ctx.token,BASE_USDC),'not Base native USDC');
 console.log(JSON.stringify(await verifyPath({provider,...input}),null,2));
}
