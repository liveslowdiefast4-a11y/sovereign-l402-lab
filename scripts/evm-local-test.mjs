import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import ganache from 'ganache';
import solc from 'solc';
import {BrowserProvider,ContractFactory,keccak256,toUtf8Bytes} from 'ethers';
import {verifyPath} from './live-path-audit.mjs';

const file = name => readFileSync('contracts/'+name+'.sol','utf8');
const input={language:'Solidity',sources:{
 'SovereignEscrow.sol':{content:file('SovereignEscrow')},
 'MockToken.sol':{content:file('MockToken')}
},settings:{optimizer:{enabled:true,runs:200},outputSelection:{'*':{'*':['abi','evm.bytecode.object']}}}};
const out=JSON.parse(solc.compile(JSON.stringify(input)));
const errors=(out.errors||[]).filter(x=>x.severity==='error');
assert.equal(errors.length,0,errors.map(x=>x.formattedMessage).join('\n'));
const artifact=(source,name)=>out.contracts[source+'.sol'][name];
const provider=new BrowserProvider(ganache.provider({logging:{quiet:true},wallet:{totalAccounts:4},chain:{chainId:1337}}));
const [payer,providerSigner,attacker,feeSigner]=await Promise.all([provider.getSigner(0),provider.getSigner(1),provider.getSigner(2),provider.getSigner(3)]);
const tokenArtifact=artifact('MockToken','MockToken');
const token=await new ContractFactory(tokenArtifact.abi,'0x'+tokenArtifact.evm.bytecode.object,payer).deploy();
await token.waitForDeployment();
const escrowArtifact=artifact('SovereignEscrow','SovereignEscrow');
const escrow=await new ContractFactory(escrowArtifact.abi,'0x'+escrowArtifact.evm.bytecode.object,payer).deploy(await token.getAddress(),await feeSigner.getAddress(),100);
await escrow.waitForDeployment();
await (await token.mint(await payer.getAddress(),10000000)).wait();
await (await token.approve(await escrow.getAddress(),10000000)).wait();
const block=await provider.getBlock('latest');
const until=Number(block.timestamp)+7200;
const digest=keccak256(toUtf8Bytes('reviewer-approved-result'));
const order=keccak256(toUtf8Bytes('order-one'));
let checks=0;
const expectReject=async(p)=>{let denied=false;try{const tx=await p;await tx.wait()}catch{denied=true}assert(denied,'expected revert');checks++};
await expectReject(escrow.connect(attacker).fund(order,await providerSigner.getAddress(),10000,until,digest));
const depositTxn=await escrow.fund(order,await providerSigner.getAddress(),10000,until,digest);
const depositReceipt=await depositTxn.wait();checks++;
mkdirSync('artifacts',{recursive:true});
writeFileSync('artifacts/escrow-funding-local.json',JSON.stringify({
  chainId:1337,
  payer:await payer.getAddress(),
  provider:await providerSigner.getAddress(),
  token:await token.getAddress(),
  escrow:await escrow.getAddress(),
  orderId:order,
  commitment:digest,
  receipt:{
    transactionHash:depositReceipt.hash,
    status:'0x1',
    blockNumber:'0x'+depositReceipt.blockNumber.toString(16),
    blockHash:depositReceipt.blockHash,
    logs:depositReceipt.logs.map(l=>({address:l.address,topics:l.topics,data:l.data,removed:false}))
  }
},null,2));
assert.equal((await escrow.orders(order)).state,1n);checks++;
await expectReject(escrow.fund(order,await providerSigner.getAddress(),10000,until,digest));
await expectReject(escrow.connect(attacker).release(order,digest));
await expectReject(escrow.release(order,keccak256(toUtf8Bytes('wrong'))));
await expectReject(escrow.refund(order));
const releaseTxn=await escrow.release(order,digest);
const releaseReceipt=await releaseTxn.wait();checks++;
assert.equal(await token.balanceOf(await providerSigner.getAddress()),9900n);checks++;
assert.equal(await token.balanceOf(await feeSigner.getAddress()),100n);checks++;
await expectReject(escrow.release(order,digest));
await expectReject(escrow.refund(order));
const order2=keccak256(toUtf8Bytes('order-two'));
const refundFundTxn=await escrow.fund(order2,await providerSigner.getAddress(),25000,until,digest);
const refundFundReceipt=await refundFundTxn.wait();checks++;
await provider.send('evm_increaseTime',[7201]);await provider.send('evm_mine',[]);checks++;
const refundTxn=await escrow.refund(order2);
const refundReceipt=await refundTxn.wait();checks++;
assert.equal((await escrow.orders(order2)).state,3n);checks++;
await expectReject(escrow.release(order2,digest));
assert.equal(await token.balanceOf(await escrow.getAddress()),0n);checks++;
const formatReceipt=r=>({
  transactionHash:r.hash,status:'0x1',blockNumber:'0x'+r.blockNumber.toString(16),
  blockHash:r.blockHash,logs:r.logs.map(l=>({address:l.address,topics:l.topics,data:l.data,removed:false}))
});
writeFileSync('artifacts/escrow-payout-local.json',JSON.stringify({
  chainId:1337,token:await token.getAddress(),escrow:await escrow.getAddress(),
  provider:await providerSigner.getAddress(),payer:await payer.getAddress(),
  feeRecipient:await feeSigner.getAddress(),
  release:{orderId:order,receipt:formatReceipt(releaseReceipt),net:9900,fee:100},
  refund:{orderId:order2,receipt:formatReceipt(refundReceipt),amount:25000}
},null,2));
const auditInput={
 provider, chainId:1337, minConfirmations:1,
 ctx:{
  escrow:await escrow.getAddress(),
  token:await token.getAddress(),
  payer:await payer.getAddress(),
  provider:await providerSigner.getAddress(),
  feeRecipient:await feeSigner.getAddress(),
  feeBps:100
 },
 release:{id:order,commitment:digest,amount:'10000',
          fundTx:depositReceipt.hash,terminalTx:releaseReceipt.hash},
 refund:{id:order2,commitment:digest,amount:'25000',
         fundTx:refundFundReceipt.hash,terminalTx:refundReceipt.hash}
};
const audited=await verifyPath(auditInput);
assert.equal(audited.status,'HISTORICAL_PATH_REPRODUCED');
await assert.rejects(verifyPath({...auditInput,minConfirmations:1000}));
await assert.rejects(verifyPath({...auditInput,ctx:{...auditInput.ctx,provider:await attacker.getAddress()}}));
await assert.rejects(verifyPath({...auditInput,refund:{...auditInput.refund,terminalTx:auditInput.release.terminalTx}}));
assert.equal(audited.proofs.length,2);
console.log('LOCAL END-TO-END PATH PASS: deposit, 1% fee release, expiry refund, chain receipts, final states');
console.log('LOCAL EVM EXECUTION PASS',checks,'checks. Not testnet or real funds.');
