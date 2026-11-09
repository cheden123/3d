import * as THREE from './vendor/three.module.js';
import {OrbitControls} from './vendor/OrbitControls.js';
import {STLLoader} from './vendor/STLLoader.js';

const $=id=>document.getElementById(id);
const defaults={shape:'A',diameter:14,height:16,bore:6,depth:.9,twist:180,engraving:.65};
const forms=[['A','Гладкая бочка','Плавные линии'],['B','Тактическая','10 канавок'],['C','Шестигранная','Чёткая форма'],['D','Спиральная','3 винтовые линии'],['E','Гранёная','12 граней'],['F','Руническая','Углублённый знак'],['G','Сегментированная','4 кольца'],['H','Коническая','Сужение к торцу']];
const paths={A:'M8 8Q1 23 8 39Q16 44 24 39Q31 23 24 8Z',B:'M6 8H26V40H6ZM10 9V39M16 9V39M22 9V39',C:'M5 11L16 5 27 11V37L16 43 5 37ZM16 14V43M5 11L16 17 27 11',D:'M6 8H26V40H6ZM6 35 26 14M6 23 20 8M12 40 26 26',E:'M9 7H23L28 17V33L23 41H9L4 33V17ZM9 7 12 17V33L9 41M23 7 20 17V33L23 41M4 17H28M4 33H28',F:'M5 10 16 5 27 10V38L16 43 5 38ZM11 16V35M11 17 21 23M11 25 21 31',G:'M6 8H26V40H6ZM6 15H26M6 18H26M6 23H26M6 26H26M6 31H26M6 34H26',H:'M10 8H22L28 40H4Z'};
let settings={...defaults},sequence=0,timer,result=null,mesh=null,renderer=null,controls=null,scene,camera,grid,material;
let toastTimer;
let render=()=>{};
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,4500);}
function setStatus(text,busy=false){$('status').textContent=text;$('status').classList.toggle('busy',busy);}
function downloads(enabled){for(const id of ['download-stl','download-step','download-fusion'])$(id).disabled=!enabled;}
function format(n){return Number(n).toLocaleString('ru-RU',{maximumFractionDigits:2});}
function applySelection(){for(const b of document.querySelectorAll('.shape'))b.setAttribute('aria-pressed',b.dataset.shape===settings.shape);$('model-name').textContent=forms.find(f=>f[0]===settings.shape)[1];}
for(const [key,name,desc] of forms){const b=document.createElement('button');b.type='button';b.className='shape';b.dataset.shape=key;b.title=name;b.setAttribute('aria-pressed',key==='A');b.innerHTML=`<svg viewBox="0 0 32 48" aria-hidden="true"><path d="${paths[key]}"/><ellipse cx="16" cy="8" rx="4" ry="2"/></svg><span>${key==='G'?'Сегменты':name}<small>${desc}</small></span>`;b.onclick=()=>{settings.shape=key;applySelection();detailControls();changed();};$('shapes').append(b);}
function control(key,label,min,max,step,unit='мм',parent='size-controls'){
 const row=document.createElement('div');row.className='control';
 row.innerHTML=`<div class="control-top"><label for="${key}-number">${label}</label><div class="value-box"><input id="${key}-number" type="number" min="${min}" max="${max}" step="${step}" value="${settings[key]}" inputmode="decimal"><span>${unit}</span></div></div><input id="${key}-range" type="range" min="${min}" max="${max}" step="${step}" value="${settings[key]}" aria-label="${label}"><div class="limits"><span>${min} ${unit}</span><span>${max} ${unit}</span></div>`;
 $(parent).append(row);
 const number=$(key+'-number'),range=$(key+'-range');
 function update(source){const v=Number(source.value);if(source===range)number.value=range.value;else if(source.value!==''&&Number.isFinite(v))range.value=source.value;settings[key]=source.value===''?null:v;changed();}
 number.oninput=()=>update(number);range.oninput=()=>update(range);
}
function detailControls(){
 $('detail-controls').replaceChildren();
 if(settings.shape==='D'){control('depth','Глубина канавок',.5,1.3,.05,'мм','detail-controls');control('twist','Закручивание',90,270,5,'°','detail-controls');$('detail-note').textContent='Больше угол — сильнее закручены три спиральные канавки.';}
 else if(settings.shape==='F'){control('engraving','Глубина орнамента',.3,1,.05,'мм','detail-controls');$('detail-note').textContent='Знак вырезан в поверхности бусины. Он будет виден на печати.';}
 else $('detail-note').textContent='У этой формы нет дополнительных настроек. Меняйте основные размеры выше.';
}
function syncControls(){for(const key of Object.keys(defaults)){if(key==='shape')continue;for(const suffix of ['number','range'])if($(key+'-'+suffix))$(key+'-'+suffix).value=settings[key];}applySelection();detailControls();}
for(const args of [['diameter','Ширина бусины',12,20,.1],['height','Высота бусины',12,24,.1],['bore','Размер отверстия',4,10,.1]])control(...args);
detailControls();

function home(){if(!camera)return;controls.target.set(0,0,8);camera.position.set(29,-39,30);controls.update();}
try{
 renderer=new THREE.WebGLRenderer({canvas:$('canvas'),antialias:true,alpha:true});renderer.setPixelRatio(Math.min(devicePixelRatio,2));renderer.setClearColor(0,0);renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.25;
 scene=new THREE.Scene();scene.up.set(0,0,1);camera=new THREE.PerspectiveCamera(34,1,.1,300);camera.up.set(0,0,1);
 controls=new OrbitControls(camera,$('canvas'));controls.enableDamping=false;controls.addEventListener('change',()=>render());controls.minDistance=18;controls.maxDistance=110;controls.maxPolarAngle=Math.PI*.86;home();
 scene.add(new THREE.HemisphereLight(0xffffff,0x8b8679,2.5));
 for(const [color,power,pos] of [[0xfff3df,4,[20,-35,45]],[0xffffff,2,[-30,10,20]],[0xe6f1f6,3,[0,30,40]]]){const l=new THREE.DirectionalLight(color,power);l.position.set(...pos);scene.add(l);}
 grid=new THREE.GridHelper(72,24,0xd4d4c9,0xe0e0d7);grid.rotation.x=Math.PI/2;grid.position.z=-.04;grid.material.transparent=true;grid.material.opacity=.6;scene.add(grid);
 material=new THREE.MeshStandardMaterial({color:'#c17f4e',metalness:.38,roughness:.43});
 render=()=>renderer.render(scene,camera);
 new ResizeObserver(()=>{const box=$('canvas-wrap').getBoundingClientRect();renderer.setSize(box.width,box.height,false);camera.aspect=box.width/box.height;camera.updateProjectionMatrix();render();}).observe($('canvas-wrap'));
}catch(e){$('canvas-wrap').textContent='3D-просмотр недоступен в этом браузере. Создание и сохранение файлов продолжают работать.';}
$('home-view').onclick=home;
$('grid-toggle').onclick=()=>{if(grid){grid.visible=!grid.visible;$('grid-toggle').setAttribute('aria-pressed',grid.visible);render();}};
for(const b of document.querySelectorAll('.swatch'))b.onclick=()=>{if(material)material.color.set(b.dataset.color);for(const s of document.querySelectorAll('.swatch')){s.classList.toggle('active',s===b);s.setAttribute('aria-pressed',s===b);}render();};

async function post(path,data){const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const json=await response.json();if(!response.ok)throw new Error(json.error||'Не удалось выполнить действие.');return json;}
function changed(){sequence++;result=null;downloads(false);$('verified').textContent='Обновляется';$('error').hidden=true;setStatus('Обновляем модель…',true);clearTimeout(timer);const id=sequence;timer=setTimeout(()=>generate(id),500);}
async function generate(id){
 const snapshot={...settings};
 try{
  if(Object.values(snapshot).some(v=>v===null))throw new Error('Введите число в каждое поле.');
  const generated=await post('api/generate',snapshot);
  if(id!==sequence)return;
  let geometry;
  if(renderer){const response=await fetch(`files/${generated.id}/model.stl`);if(!response.ok)throw new Error('Не удалось загрузить предпросмотр. Обновите модель.');geometry=new STLLoader().parse(await response.arrayBuffer());}
  if(id!==sequence){geometry?.dispose();return;}
  if(renderer){if(mesh){scene.remove(mesh);mesh.geometry.dispose();}mesh=new THREE.Mesh(geometry,material);scene.add(mesh);render();}
  result=generated;downloads(true);$('verified').textContent='✓ Цельное тело';
  $('dimensions').textContent=generated.dimensions.map(format).join(' × ')+' мм';$('bore-value').textContent=format(snapshot.bore)+' мм';$('volume').textContent=format(generated.volume/1000)+' см³';$('wall').textContent='≥ '+format(generated.wall)+' мм';
  setStatus('Модель готова · размеры проверены');
  try{localStorage.setItem('bead-studio-v1',JSON.stringify(settings));}catch{}
 }catch(error){if(id!==sequence)return;result=null;downloads(false);$('verified').textContent='Нужна правка';$('error').textContent=error.message;$('error').hidden=false;setStatus('Проверьте настройки',true);}
}
$('reset').onclick=()=>{settings={...defaults,shape:settings.shape,height:settings.shape==='F'?18:16};syncControls();changed();};
$('refresh').onclick=()=>{changed();clearTimeout(timer);generate(sequence);};
function downloadFile(url){const a=document.createElement('a');a.href=url;a.download='';document.body.append(a);a.click();a.remove();}
for(const [id,file] of [['download-stl','model.stl'],['download-step','model.step'],['download-fusion','fusion.zip']])$(id).onclick=()=>{if(!result)return;downloadFile(`files/${result.id}/${file}`);toast(file==='fusion.zip'?'Проект Fusion сохранён. Распакуйте ZIP и откройте START_HERE.txt.':'Файл передан браузеру для сохранения.');};
$('save-project').onclick=()=>{if(!result){toast('Дождитесь готовой модели, затем сохраните настройки.');return;}const blob=new Blob([JSON.stringify({version:1,settings:result.settings},null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='Моя бусина.bead.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),5000);};
$('load-project').onclick=()=>$('project-file').click();
$('project-file').onchange=async()=>{try{const file=$('project-file').files[0];if(!file)return;if(file.size>8192)throw new Error('Файл настроек слишком большой. Выберите файл .bead.json.');const data=JSON.parse(await file.text());if(data.version!==1||!data.settings||Array.isArray(data.settings)||typeof data.settings!=='object'||Object.keys(data.settings).length!==Object.keys(defaults).length||Object.keys(data.settings).some(k=>!(k in defaults))||!forms.some(f=>f[0]===data.settings.shape)||Object.entries(data.settings).some(([k,v])=>k!=='shape'&&(typeof v!=='number'||!Number.isFinite(v))))throw new Error('Это не файл настроек «Мастера бусин».');settings={...data.settings};syncControls();changed();toast('Настройки загружены.');}catch(e){toast(e.message==='Unexpected end of JSON input'?'Не удалось прочитать файл настроек.':e.message);}finally{$('project-file').value='';}};
$('help').onclick=()=>$('help-dialog').showModal();for(const id of ['help-close','help-done'])$(id).onclick=()=>$('help-dialog').close();
let alive=true;
$('stop').onclick=async()=>{try{await post('api/stop',{});alive=false;document.body.classList.add('stopped');downloads(false);toast('Программа завершена. Эту вкладку можно закрыть.');}catch{toast('Программа уже завершена. Эту вкладку можно закрыть.');}};
setInterval(()=>{if(alive)post('api/heartbeat',{}).catch(()=>{downloads(false);setStatus('Программа завершена. Запустите её заново.',true);});},15000);
try{const saved=JSON.parse(localStorage.getItem('bead-studio-v1'));if(saved&&Object.keys(defaults).every(k=>k in saved)&&Object.keys(saved).every(k=>k in defaults)&&forms.some(f=>f[0]===saved.shape)){settings={...saved};syncControls();}}catch{}
applySelection();changed();
