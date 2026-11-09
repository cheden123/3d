import {mkdir,copyFile,readFile,writeFile} from 'node:fs/promises';
await mkdir('web/vendor',{recursive:true});
for(const [src,dst] of [['build/three.module.js','three.module.js'],['build/three.core.js','three.core.js'],
  ['examples/jsm/controls/OrbitControls.js','OrbitControls.js'],['examples/jsm/loaders/STLLoader.js','STLLoader.js']]) {
  const text=await readFile('node_modules/three/'+src,'utf8');
  await writeFile('web/vendor/'+dst,text.replaceAll("from 'three'","from './three.module.js'"));
}
await copyFile('node_modules/three/LICENSE','web/vendor/THREE-LICENSE.txt');
