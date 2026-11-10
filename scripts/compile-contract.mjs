import {readFileSync,mkdirSync,writeFileSync} from 'node:fs';
import solc from 'solc';
const name='SovereignEscrow.sol';
const input={language:'Solidity',sources:{[name]:{content:readFileSync('contracts/'+name,'utf8')}},
 settings:{optimizer:{enabled:true,runs:200},outputSelection:{'*':{'*':['abi','evm.bytecode.object','evm.deployedBytecode.object','evm.deployedBytecode.immutableReferences']}}}};
const output=JSON.parse(solc.compile(JSON.stringify(input)));
const errors=(output.errors||[]).filter(x=>x.severity==='error');
if(errors.length){for(const e of errors)console.error(e.formattedMessage);process.exit(1)}
const artifact=output.contracts?.[name]?.SovereignEscrow;
if(!artifact?.evm?.bytecode?.object)throw Error('No compiled bytecode');
mkdirSync('artifacts',{recursive:true});
writeFileSync('artifacts/SovereignEscrow.json',JSON.stringify({
 contractName:'SovereignEscrow',compiler:solc.version(),abi:artifact.abi,
 bytecode:'0x'+artifact.evm.bytecode.object,
 deployedBytecode:'0x'+artifact.evm.deployedBytecode.object,
 immutableReferences:artifact.evm.deployedBytecode.immutableReferences
},null,2));
console.log('SOLC',solc.version(),'bytecode bytes',artifact.evm.bytecode.object.length/2,'ABI entries',artifact.abi.length);
