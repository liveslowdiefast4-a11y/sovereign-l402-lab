import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {compareRuntime} from './runtime-integrity.mjs';

const artifact=JSON.parse(readFileSync('artifacts/SovereignEscrow.json','utf8'));
test('compiled artifact includes immutable metadata',()=>{
  assert.ok(Object.keys(artifact.immutableReferences).length>=3);
});
test('immutable constructor values can vary but runtime code cannot',()=>{
 const bytes=Buffer.from(artifact.deployedBytecode.slice(2),'hex');
 for(const slots of Object.values(artifact.immutableReferences)){
   for(const {start,length} of slots){
     for(let i=start;i<start+length;i++) bytes[i]=0xaa;
   }
 }
 const result=compareRuntime(artifact,'0x'+bytes.toString('hex'));
 assert.equal(result.ok,true,JSON.stringify(result));
 assert.ok(result.immutable_bytes>0);
});
test('one changed instruction denies match',()=>{
 const bytes=Buffer.from(artifact.deployedBytecode.slice(2),'hex');
 bytes[0]^=1;
 assert.equal(compareRuntime(artifact,'0x'+bytes.toString('hex')).ok,false);
});
test('truncated bytecode and absent metadata deny match',()=>{
 assert.equal(compareRuntime(artifact,'0x6000').ok,false);
 assert.equal(compareRuntime({...artifact,immutableReferences:{}},artifact.deployedBytecode).ok,false);
});
