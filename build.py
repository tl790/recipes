#!/usr/bin/env python3
"""
Build the static Recipe Library page for GitHub Pages.

The live library runs on claude.ai and stores recipes in the artifact's database.
This script bakes a snapshot of that database into one index.html that works
with no Claude and no login. Shopping lists on the static page save to the
browser only; "Log a cook" and Claude review are hidden.

Steps (run inside a Claude chat, because only Claude's Artifact tool can read the database):
  1. Artifact read on https://claude.ai/artifact/J5xRj7tvkJyJooZ8SZgNa6
     -> copies the page to /mnt/user-data/outputs/artifacts/<id>/index.html
  2. Artifact read_db, db_op "list", query {"limit":1000}, out_dir
     /mnt/user-data/outputs/export, once for collection "recipes" and once for "coffee"
  3. python3 build.py --src <artifact index.html> --export /mnt/user-data/outputs/export --out index.html
  4. Syntax-check the inline scripts, then push index.html to main (push_files).
     Pages redeploys in about a minute.

Do not export "shopping" or "lists": they are personal and stay out of the public repo.
"""
import argparse, glob, json, os, re

SHIM = r'''<script>
/* Static snapshot shim: replaces the claude.ai database with embedded data. Shopping lists save to this browser only. */
(function(){
const SEED=__SEED__;
const KEY='recipe-library-local-v1';
let local={}; try{ local=JSON.parse(localStorage.getItem(KEY)||'{}'); }catch(e){}
const persist=()=>{ try{ localStorage.setItem(KEY,JSON.stringify(local)); }catch(e){} };
const subs=new Map();
const cl=o=>JSON.parse(JSON.stringify(o));
const getCol=c=>{ const m=new Map(Object.entries(cl(SEED[c]||{}))); const l=local[c]||{}; for(const [k,v] of Object.entries(l)){ if(v===null) m.delete(k); else m.set(k,v); } return m; };
const mkSnap=(id,d)=>({id,exists:d!=null,data:()=>d==null?undefined:cl(d)});
const notify=c=>{ (subs.get(c)||[]).forEach(f=>f()); };
const db={
  doc(path){ const [c,id]=path.split('/'); return {
    async get(){ return mkSnap(id,getCol(c).get(id)); },
    async set(d){ (local[c]=local[c]||{})[id]=cl(d); persist(); notify(c); notify(path); },
    async update(p){ const cur=getCol(c).get(id)||{}; (local[c]=local[c]||{})[id]=Object.assign(cl(cur),cl(p)); persist(); notify(c); notify(path); },
    async delete(){ (local[c]=local[c]||{})[id]=null; persist(); notify(c); notify(path); },
    onSnapshot(ok){ const f=()=>ok(mkSnap(id,getCol(c).get(id))); (subs.get(path)||subs.set(path,[]).get(path)).push(f); setTimeout(f,0); return ()=>{}; }
  }; },
  collection(c){ return { onSnapshot(ok){ const f=()=>ok({docs:[...getCol(c).entries()].map(([id,d])=>mkSnap(id,d))}); (subs.get(c)||subs.set(c,[]).get(c)).push(f); setTimeout(f,0); return ()=>{}; } }; }
};
window.claude={ use:async n=>{ if(n==='db') return db; if(n==='user') return {isOwner:async()=>false}; return null; } };
})();
</script>
'''

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True, help="artifact index.html copied by Artifact read")
    ap.add_argument('--export', required=True, help="folder holding recipes/ and coffee/ JSON exports")
    ap.add_argument('--out', default='index.html')
    a = ap.parse_args()
    s = open(a.src, encoding='utf-8').read()
    data = {'recipes': {}, 'coffee': {}}
    for col in data:
        for f in sorted(glob.glob(os.path.join(a.export, col, '*.json'))):
            data[col][os.path.basename(f)[:-5]] = json.load(open(f, encoding='utf-8'))
    blob = json.dumps(data, ensure_ascii=False).replace('</', '<\\/')
    i = s.rindex('<script>')
    out = s[:i] + SHIM.replace('__SEED__', blob) + s[i:]
    open(a.out, 'w', encoding='utf-8').write(out)
    for n, t in enumerate(re.findall(r'<script>(.*?)</script>', out, re.S)):
        open(f'/tmp/chk{n}.js', 'w').write(t)
    print(f"wrote {a.out}: {len(out)} bytes, {len(data['recipes'])} recipes, {len(data['coffee'])} coffee docs")
    print("next: node --check /tmp/chk*.js, then push index.html")

if __name__ == '__main__':
    main()
