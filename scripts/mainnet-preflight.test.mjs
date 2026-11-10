import assert from 'node:assert/strict';
import {test} from 'node:test';
import {keccak256} from 'ethers';
import {assessMainnet,BASE_USDC} from './mainnet-preflight.mjs';
const target='0x0000000000000000000000000000000000000051';
const fee='0x0000000000000000000000000000000000000061';
const artifact={abi:[{type:'function',name:'token',stateMutability:'view',inputs:[],outputs:[{type:'address'}]},
 {type:'function',name:'feeRecipient',stateMutability:'view',inputs:[],outputs:[{type:'address'}]},
 {type:'function',name:'feeBps',stateMutability:'view',inputs:[],outputs:[{type:'uint16'}]}],
 deployedBytecode:'0x6000',immutableReferences:{'4':[{start:1,length:1}]}};
function fake({chain=8453,tokenCode='0x6000',escrowCode='0x6001',decimals=6,symbol='USDC',
                  actualToken=BASE_USDC,actualFee=fee,bps=100}={}){
 const provider={
   getNetwork:async()=>({chainId:BigInt(chain)}),
   getCode:async a=>a.toLowerCase()===BASE_USDC.toLowerCase()?tokenCode:escrowCode,
   call:async ({to,data})=>{
     const sig=data.slice(0,10).toLowerCase();
     const selectors={
       '0xfc0c546a':()=>actualToken.slice(2).padStart(64,'0'),
       '0x46904840':()=>actualFee.slice(2).padStart(64,'0'),
       '0x24a9d853':()=>BigInt(bps).toString(16).padStart(64,'0'),
       '0x313ce567':()=>BigInt(decimals).toString(16).padStart(64,'0'),
       '0x95d89b41':()=>('20'.padStart(64,'0')+'04'.padStart(64,'0')+Buffer.from(symbol).toString('hex').padEnd(64,'0'))
     };
     if(!selectors[sig]) throw Error('unknown selector: '+sig);
     return '0x'+selectors[sig]();
   },
   getBlockNumber:async()=>1234,
   _detectNetwork:async()=>({name:'base',chainId:8453n})
 };
 return provider;
}
test('read-only mainnet preflight refuses wrong chain',async()=>{
 const r=await assessMainnet({provider:fake({chain:42161}),escrowAddress:target,feeRecipient:fee,artifact,approvedRuntimeHash:keccak256('0x6001')});
 assert.equal(r.ok,false);assert.equal(r.reason,'wrong chain');
});
test('read-only preflight refuses missing deployed escrow',async()=>{
 const r=await assessMainnet({provider:fake({escrowCode:'0x'}),escrowAddress:target,feeRecipient:fee,artifact,approvedRuntimeHash:keccak256('0x6001')});
 assert.equal(r.ok,false);assert.equal(r.reason,'escrow deployment absent');
});
test('read-only preflight refuses missing native USDC',async()=>{
 const r=await assessMainnet({provider:fake({tokenCode:'0x'}),escrowAddress:target,feeRecipient:fee,artifact,approvedRuntimeHash:keccak256('0x6001')});
 assert.equal(r.ok,false);assert.equal(r.reason,'USDC bytecode absent');
});
test('read-only preflight refuses missing trusted artifact',async()=>{
 const r=await assessMainnet({provider:fake(),escrowAddress:target,feeRecipient:fee,artifact:null});
 assert.equal(r.ok,false);
});

test('attributes verified does not authorize funds',async()=>{
 const r=await assessMainnet({provider:fake(),escrowAddress:target,feeRecipient:fee,artifact,approvedRuntimeHash:keccak256('0x6001')});
 assert.equal(r.ok,true);assert.equal(r.status,'DEPLOYMENT_ATTRIBUTES_VERIFIED_ONLY');
 assert.equal(r.warnings.length,4);
});
test('rejects onchain different fee recipient',async()=>{
 const r=await assessMainnet({provider:fake({actualFee:target}),escrowAddress:target,feeRecipient:fee,artifact,approvedRuntimeHash:keccak256('0x6001')});
 assert.equal(r.ok,false);
});
test('rejects onchain different fee',async()=>{
 const r=await assessMainnet({provider:fake({bps:150}),escrowAddress:target,feeRecipient:fee,artifact,approvedRuntimeHash:keccak256('0x6001')});
 assert.equal(r.ok,false);
});
test('rejects wrong token metadata',async()=>{
 const r=await assessMainnet({provider:fake({decimals:18}),escrowAddress:target,feeRecipient:fee,artifact,approvedRuntimeHash:keccak256('0x6001')});
 assert.equal(r.ok,false);
});

test('preflight fails without independently pinned approved runtime hash',async()=>{
 const r=await assessMainnet({provider:fake(),escrowAddress:target,feeRecipient:fee,artifact});
 assert.equal(r.ok,false);
 assert.equal(r.reason,'signed release runtime hash pin missing');
});
test('preflight rejects wrong release runtime hash',async()=>{
 const r=await assessMainnet({provider:fake(),escrowAddress:target,feeRecipient:fee,artifact,
                            approvedRuntimeHash:keccak256('0x6002')});
 assert.equal(r.ok,false);
});
