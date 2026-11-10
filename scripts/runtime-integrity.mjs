/** Compare deployed runtime bytecode against compiler output after masking only
 * the compiler-reported immutable constructor values. Not a source audit. */
export function compareRuntime(artifact, deployedRuntime) {
  const template=artifact?.deployedBytecode;
  const isHex=x=>typeof x==='string' && /^0x(?:[0-9a-fA-F]{2})+$/.test(x);
  if(!isHex(template) || !isHex(deployedRuntime))
    return {ok:false,reason:'missing or invalid runtime code'};
  const a=Buffer.from(template.slice(2),'hex');
  const b=Buffer.from(deployedRuntime.slice(2),'hex');
  if(a.length!==b.length)
    return {ok:false,reason:'runtime length mismatch'};
  const references=artifact?.immutableReferences;
  if(!references || typeof references!=='object' || Array.isArray(references) || !Object.keys(references).length)
    return {ok:false,reason:'immutable reference metadata unavailable'};
  const marked=new Set();
  for(const positions of Object.values(references)){
    if(!Array.isArray(positions)||!positions.length) return {ok:false,reason:'bad immutable metadata'};
    for(const position of positions){
      const {start,length}=position||{};
      if(!Number.isInteger(start)||!Number.isInteger(length)||start<0||length<1||start+length>a.length)
        return {ok:false,reason:'invalid immutable offset'};
      for(let i=start;i<start+length;i++){
        if(marked.has(i)) return {ok:false,reason:'overlapping immutable references'};
        marked.add(i);
        a[i]=b[i]=0;
      }
    }
  }
  return a.equals(b)
    ? {ok:true,compared_bytes:a.length,immutable_bytes:marked.size}
    : {ok:false,reason:'deployed code does not match compiler output'};
}
