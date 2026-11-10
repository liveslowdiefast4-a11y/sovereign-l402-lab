import {readFileSync} from 'node:fs';
import {JsonRpcProvider, Contract, keccak256, getAddress} from 'ethers';
import {compareRuntime} from './runtime-integrity.mjs';

// Read-only gate for an EXISTING Base deployment. This does not deploy,
// sign, enable payments, or authorize access to any customer's funds.
export const BASE_CHAIN_ID=8453;
export const BASE_USDC='0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913';
export const ZERO_CODE='0x';

export function fail(reason){ return {ok:false,reason}; }
export async function assessMainnet({provider,escrowAddress,feeRecipient,
                                      expectedFeeBps=100,artifact,approvedRuntimeHash}) {
  try {
    const network=await provider.getNetwork();
    if(Number(network.chainId)!==BASE_CHAIN_ID) return fail('wrong chain');
    const target=getAddress(escrowAddress);
    const fees=getAddress(feeRecipient);
    const tokenAddress=getAddress(BASE_USDC);
    if(target===fees) return fail('fee recipient is contract');
    const tokenCode=await provider.getCode(tokenAddress);
    if(tokenCode===ZERO_CODE) return fail('USDC bytecode absent');
    const contractCode=await provider.getCode(target);
    if(contractCode===ZERO_CODE) return fail('escrow deployment absent');
    if(!artifact || !artifact.deployedBytecode || artifact.deployedBytecode==='0x')
      return fail('pinned runtime artifact missing');
    // Immutable fields embedded in runtime bytecode require a separate,
    // compiler-produced immutable-reference mask. Exact hash comparisons
    // of unpatched artifacts are NOT sufficient.
    if(!Array.isArray(artifact.abi) || !artifact.abi.length)
      return fail('artifact ABI missing');
    if(!/^0x[a-fA-F0-9]{64}$/.test(approvedRuntimeHash||''))
      return fail('signed release runtime hash pin missing');
    if(keccak256(contractCode).toLowerCase()!==approvedRuntimeHash.toLowerCase())
      return fail('contract runtime does not match approved hash');
    const integrity=compareRuntime(artifact,contractCode);
    if(!integrity.ok) return fail('runtime integrity: '+integrity.reason);
    const escrow=new Contract(target,artifact.abi,provider);
    const token=new Contract(tokenAddress,
      ['function decimals() view returns (uint8)','function symbol() view returns (string)'],
      provider);
    const [onchainToken,onchainFeeRecipient,onchainFeeBps,decimals,symbol]=await Promise.all([
      escrow.token(),escrow.feeRecipient(),escrow.feeBps(),token.decimals(),token.symbol()
    ]);
    if(getAddress(onchainToken)!==tokenAddress) return fail('escrow token is not native Base USDC');
    if(getAddress(onchainFeeRecipient)!==fees) return fail('escrow fee wallet mismatch');
    if(Number(onchainFeeBps)!==expectedFeeBps || expectedFeeBps!==100)
      return fail('escrow fee must equal approved 1%');
    if(Number(decimals)!==6 || symbol!=='USDC') return fail('unexpected token metadata');
    return {
      ok:true,
      status:'DEPLOYMENT_ATTRIBUTES_VERIFIED_ONLY',
      chain_id:BASE_CHAIN_ID,
      escrow:target,
      token:tokenAddress,
      fee_recipient:fees,
      fee_bps:Number(onchainFeeBps),
      runtime_keccak256:keccak256(contractCode),
      runtime_integrity:integrity,
      warnings:[
        'Matching a locally supplied compilation artifact is not an independently approved release hash.',
        'No real deposit, release, expiry refund or transaction reconciliation was verified.',
        'No payer identity, onchain authorization or regulatory compliance was verified.',
        'Result does not authorize customer-fund activation.'
      ]
    };
  } catch (err){
    return fail('unavailable or inconsistent RPC/contract evidence');
  }
}

if(process.argv[1]?.endsWith('mainnet-preflight.mjs')){
  const rpc=process.env.SOVEREIGN_MAINNET_RPC_URL;
  const escrow=process.env.SOVEREIGN_MAINNET_ESCROW_ADDRESS;
  const feeRecipient=process.env.SOVEREIGN_MAINNET_FEE_RECIPIENT;
  if(!rpc?.startsWith('https://') || !escrow || !feeRecipient)
    throw Error('Read-only mainnet RPC, escrow address and fee wallet required');
  const artifact=JSON.parse(readFileSync('artifacts/SovereignEscrow.json','utf8'));
  const result=await assessMainnet({provider:new JsonRpcProvider(rpc),escrowAddress:escrow,feeRecipient,artifact,approvedRuntimeHash:process.env.SOVEREIGN_APPROVED_RUNTIME_HASH});
  console.log(JSON.stringify(result,null,2));
  if(!result.ok) process.exitCode=1;
}
