import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {JsonRpcProvider,Wallet,ContractFactory,Contract,keccak256} from 'ethers';
// Testnet-only escrow deployment. Never accepts mainnet chain IDs.
const allowed=new Map([[84532,'Base Sepolia'],[421614,'Arbitrum Sepolia']]);
const endpoint=process.env.SOVEREIGN_TESTNET_RPC_URL;
const secret=process.env.SOVEREIGN_TESTNET_DEPLOYER_KEY;
const token=process.env.SOVEREIGN_TESTNET_TOKEN;
if(!endpoint?.startsWith('https://')||!secret||!token||!process.env.SOVEREIGN_TESTNET_DEPLOY_APPROVED)
  throw Error('Missing explicit testnet RPC, deployer, token or approval flag');
const provider=new JsonRpcProvider(endpoint,undefined,{staticNetwork:false});
const net=await provider.getNetwork();
const chain=Number(net.chainId);
if(!allowed.has(chain))throw Error('Mainnet/unknown chain refused');
const wallet=new Wallet(secret,provider);
const artifact=JSON.parse(readFileSync('artifacts/SovereignEscrow.json','utf8'));
if(!artifact.bytecode?.startsWith('0x')||artifact.bytecode.length<100)throw Error('Missing compiled escrow artifact');
if(!/^0x[a-fA-F0-9]{40}$/.test(token) || (await provider.getCode(token))==='0x')
 throw Error('ERC20 token address does not contain contract code');
const cost=await provider.getFeeData();
if(cost.maxFeePerGas === null)throw Error('Fee estimate missing');
const factory=new ContractFactory(artifact.abi,artifact.bytecode,wallet);
const deployment=await factory.getDeployTransaction(token);
const gas=await provider.estimateGas({...deployment,from:wallet.address});
const maxWei=gas*cost.maxFeePerGas;
const cap=BigInt(process.env.SOVEREIGN_TESTNET_MAX_GAS_WEI||'0');
if(cap<=0n||maxWei>cap)throw Error('Gas cost exceeds explicit testnet cap');
const escrow=await factory.deploy(token);
const txn=escrow.deploymentTransaction();
const confirmation=await txn.wait(5);
if(!confirmation||confirmation.status!==1)throw Error('Deploy not confirmed');
const address=await escrow.getAddress();
const code=await provider.getCode(address);
if(!code || code==='0x')throw Error('Deployed runtime bytecode missing');
const onchainToken=await escrow.token();
if(onchainToken.toLowerCase()!==token.toLowerCase())throw Error('Wrong constructor token');
const manifest={status:'TESTNET_DEPLOYED',chain_id:chain,network:allowed.get(chain),
 contract:address,transaction_hash:txn.hash,block_number:confirmation.blockNumber,
 runtime_keccak256:keccak256(code),deployer:wallet.address,
 token:onchainToken,confirmations_at_check:5,utc:new Date().toISOString(),
 caution:'No live funds, audit or ZK proof verified'};
mkdirSync('deployments',{recursive:true});
const path='deployments/escrow-'+chain+'-'+confirmation.blockNumber+'.json';
writeFileSync(path,JSON.stringify(manifest,null,2));
console.log(JSON.stringify(manifest,null,2));
