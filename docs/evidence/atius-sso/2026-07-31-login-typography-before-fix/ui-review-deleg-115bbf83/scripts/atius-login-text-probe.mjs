#!/usr/bin/env node
import { createRequire } from 'node:module';
import { writeFile } from 'node:fs/promises';
const require = createRequire('/home/ubuntu/GitHub/vpn-atius/web/frontend/package.json');
const { chromium } = require('playwright');
const OUT = process.argv[2] || '/tmp/atius-login-ui-review-20260731/text-probe.json';
const hosts = [
  ['sso-reference','https://sso.atius.com.br/login'],
  ['grafana','https://grafana.atius.com.br/login'],
  ['portainer','https://portainer.atius.com.br/login'],
  ['docker','https://docker.atius.com.br/login'],
  ['vpn','https://vpn.atius.com.br/login'],
  ['adguard','https://adguard.atius.com.br/login'],
];
const cssProps = ['display','fontFamily','fontSize','fontWeight','lineHeight','letterSpacing','textTransform','color','backgroundColor','borderTopWidth','borderTopColor','borderRadius','paddingTop','paddingRight','paddingBottom','paddingLeft','marginTop','marginBottom','width','height','textAlign','gap','alignItems','justifyContent'];
function expr(){return ({cssProps})=>{
  const terms = ['Atius SSO','Entrar na Atius','DESTINO SEGURO','Nenhum destino selecionado','Email ou username','Senha','Entrar com Atius SSO'];
  const norm = s => (s||'').replace(/\s+/g,' ').trim();
  const own = el => norm(Array.from(el.childNodes).filter(n=>n.nodeType===Node.TEXT_NODE).map(n=>n.textContent).join(' '));
  const rect = el => { const r=el.getBoundingClientRect(); return {x:+r.x.toFixed(3),y:+r.y.toFixed(3),w:+r.width.toFixed(3),h:+r.height.toFixed(3),top:+r.top.toFixed(3),bottom:+r.bottom.toFixed(3),left:+r.left.toFixed(3),right:+r.right.toFixed(3)} };
  const style = el => { const cs=getComputedStyle(el); const o={}; for (const p of cssProps) o[p]=cs[p]||''; return o; };
  const path = el => {
    const parts=[]; let e=el;
    while(e && e.nodeType===1 && parts.length<8){
      let part=e.tagName.toLowerCase();
      if(e.id) part += '#'+e.id;
      const cls=(e.className && typeof e.className==='string') ? e.className.trim().split(/\s+/).slice(0,5).join('.') : '';
      if(cls) part += '.'+cls;
      const parent=e.parentElement;
      if(parent){ const same=Array.from(parent.children).filter(c=>c.tagName===e.tagName); if(same.length>1) part += `:nth-of-type(${same.indexOf(e)+1})`; }
      parts.unshift(part); e=e.parentElement;
    }
    return parts.join(' > ');
  };
  const candidates={};
  for(const term of terms){
    const arr=[];
    for(const el of Array.from(document.querySelectorAll('body *'))){
      const t=norm(el.innerText || el.textContent);
      const o=own(el);
      if(t===term || o===term || (term.includes('destino') && t.toUpperCase()===term) || (t.includes(term) && t.length <= term.length + 8)){
        const r=el.getBoundingClientRect();
        if(r.width>0 && r.height>0) arr.push({tag:el.tagName.toLowerCase(), selectorPath:path(el), class:typeof el.className==='string'?el.className:'', id:el.id||'', ownText:o, innerText:t, rect:rect(el), style:style(el), html:(el.outerHTML||'').slice(0,500)});
      }
    }
    candidates[term]=arr.slice(0,12);
  }
  function info(sel){ const el=document.querySelector(sel); return el?{selector:sel, tag:el.tagName.toLowerCase(), selectorPath:path(el), class:typeof el.className==='string'?el.className:'', id:el.id||'', text:norm(el.innerText||el.textContent), rect:rect(el), style:style(el), html:(el.outerHTML||'').slice(0,500)}:{selector:sel,missing:true}; }
  return {
    url: location.href,
    title: document.title,
    bodyText:norm(document.body.innerText || document.body.textContent),
    candidates,
    explicit: {
      submitButton: info('button[type="submit"]'),
      passwordToggleButton: info('button[type="button"]'),
      firstForm: info('form'),
      firstInput: info('input'),
      secondInput: info('input:nth-of-type(2)'),
      cardByMain: info('main'),
      cardByCardClass: info('.card'),
      cardTailwind: info('main, .mx-auto.max-w-md, .max-w-md, [class*="max-w-"]'),
    }
  };
}}
const browser=await chromium.launch({headless:true, executablePath:'/usr/bin/chromium', args:['--no-sandbox','--disable-gpu']});
const results={};
for(const [id,url] of hosts){
 const context=await browser.newContext({viewport:{width:1440,height:900},deviceScaleFactor:1,ignoreHTTPSErrors:true,locale:'pt-BR'});
 const page=await context.newPage();
 await page.goto(url,{waitUntil:'domcontentloaded',timeout:45000});
 await page.waitForLoadState('networkidle',{timeout:10000}).catch(()=>{});
 await page.waitForTimeout(1000);
 results[id]=await page.evaluate(expr(), {cssProps});
 console.log(id, results[id].url, results[id].bodyText.slice(0,100));
 await context.close();
}
await browser.close();
await writeFile(OUT, JSON.stringify(results,null,2));
console.log('OUT='+OUT);
