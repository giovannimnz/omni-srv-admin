#!/usr/bin/env node
import { createRequire } from 'node:module';
import { writeFile } from 'node:fs/promises';
const require = createRequire('/home/ubuntu/GitHub/vpn-atius/web/frontend/package.json');
const { chromium } = require('playwright');
const OUT=process.argv[2]||'/tmp/atius-login-ui-review-20260731/host-term-probe.json';
const hosts=[['sso-reference','https://sso.atius.com.br/login','Nenhum destino selecionado'],['grafana','https://grafana.atius.com.br/login','grafana.atius.com.br'],['portainer','https://portainer.atius.com.br/login','portainer.atius.com.br'],['docker','https://docker.atius.com.br/login','docker.atius.com.br'],['vpn','https://vpn.atius.com.br/login','vpn.atius.com.br'],['adguard','https://adguard.atius.com.br/login','adguard.atius.com.br']];
const cssProps=['display','fontFamily','fontSize','fontWeight','lineHeight','letterSpacing','textTransform','color','backgroundColor','marginTop','marginBottom','width','height','textAlign','gap','alignItems','justifyContent'];
const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox','--disable-gpu']});
const out={};
for(const [id,url,term] of hosts){
 const ctx=await browser.newContext({viewport:{width:1440,height:900},deviceScaleFactor:1,ignoreHTTPSErrors:true,locale:'pt-BR'}); const page=await ctx.newPage();
 await page.goto(url,{waitUntil:'domcontentloaded',timeout:45000}); await page.waitForLoadState('networkidle',{timeout:10000}).catch(()=>{}); await page.waitForTimeout(1000);
 out[id]=await page.evaluate(({term,cssProps})=>{
  const norm=s=>(s||'').replace(/\s+/g,' ').trim();
  const rect=el=>{const r=el.getBoundingClientRect(); return {x:+r.x.toFixed(3),y:+r.y.toFixed(3),w:+r.width.toFixed(3),h:+r.height.toFixed(3),top:+r.top.toFixed(3),bottom:+r.bottom.toFixed(3),left:+r.left.toFixed(3),right:+r.right.toFixed(3)}};
  const style=el=>{const cs=getComputedStyle(el), o={}; for(const p of cssProps)o[p]=cs[p]||''; return o};
  const path=el=>{const parts=[]; let e=el; while(e&&e.nodeType===1&&parts.length<7){let part=e.tagName.toLowerCase(); if(e.id)part+='#'+e.id; const cls=(typeof e.className==='string'?e.className.trim().split(/\s+/).slice(0,4).join('.'):''); if(cls)part+='.'+cls; const p=e.parentElement; if(p){const same=[...p.children].filter(c=>c.tagName===e.tagName); if(same.length>1)part+=`:nth-of-type(${same.indexOf(e)+1})`} parts.unshift(part); e=e.parentElement} return parts.join(' > ')};
  const arr=[]; for(const el of document.querySelectorAll('body *')){const t=norm(el.innerText||el.textContent); if(t===term || (t.includes(term)&&t.length<=term.length+20)){const r=el.getBoundingClientRect(); if(r.width>0&&r.height>0) arr.push({tag:el.tagName.toLowerCase(), path:path(el), class:typeof el.className==='string'?el.className:'', text:t, rect:rect(el), style:style(el), html:(el.outerHTML||'').slice(0,500)})}}
  arr.sort((a,b)=>(a.rect.w*a.rect.h)-(b.rect.w*b.rect.h));
  return {url:location.href, term, candidates:arr.slice(0,8)};
 }, {term,cssProps});
 console.log(id, out[id].candidates[0]?.path, out[id].candidates[0]?.text);
 await ctx.close();
}
await browser.close(); await writeFile(OUT, JSON.stringify(out,null,2)); console.log('OUT='+OUT);
