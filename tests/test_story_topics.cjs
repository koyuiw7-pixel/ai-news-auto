const assert=require('node:assert/strict');const fs=require('node:fs');const Module=require('node:module');const path=require('node:path');const test=require('node:test');const ts=require('typescript');
const root=path.resolve(__dirname,'..');const file=path.join(root,'lib/stories.ts');
const now=new Date().toISOString();
function article(slug,title){return {slug,title,tags:[],keywords:[],genreSlug:'ai',genre:'AI',type:'news',hasEasy:true,generatedAt:now,publishedAt:now,highlights:[],thumbnail:'',lede:title,verdict:{status:'available',japan:'ok',free:true,audience:'一般ユーザー'}}}
const items=[article('notebook','Googleの学習AIに無料の教科書'),article('students','Geminiで学生の勉強を助ける'),article('other','AIニュースの別の話')];
const mocks={
 '@/lib/articles':{getAllArticles:()=>items,coverPath:()=>'/cover.png'},
 '@/lib/companies':{COMPANIES:[],companyOf:()=>({slug:'google',name:'Google',color:'#000'})},
 '@/lib/general':{easyGist:(a)=>a.lede,pickGeneral:(a,n)=>a.slice(0,n)},
 '@/lib/sections':{BROAD_SECTIONS:[]},
 '@/lib/verdict':{freeLabel:()=>'',japanLabel:()=>'',usability:()=> 'go',USABILITY_LABEL:{go:'使える'}}
};
const source=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const m=new Module(file,module);m.filename=file;m.paths=Module._nodeModulePaths(path.dirname(file));const orig=m.require.bind(m);m.require=(name)=>mocks[name]||orig(name);m._compile(source,file);
test('総合ニュースに重なっても2件の勉強テーマを表示',()=>{const bundles=m.exports.getStoryBundles();const study=bundles.find(b=>b.key==='study');assert.ok(study);assert.deepEqual(study.items.map(a=>a.slug),['notebook','students']);assert.equal(study.label,'勉強に使えるAI');});
test('AIモデルの学習効率だけの記事を勉強向けに混ぜない',()=>{items.push(article('training','AIモデル学習効率の最適化'));const study=m.exports.getStoryBundles().find(b=>b.key==='study');assert.ok(!study.items.some(x=>x.slug==='training'));});
