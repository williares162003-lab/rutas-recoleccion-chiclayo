// La interfaz ejecuta el motor Python a través de la API local.

// ============================================================
// ESTADO Y UTILIDADES
// ============================================================

// entrada: datos iniciales del servidor; resultado: última ejecución; consulta: temporizador del sondeo.
let entrada, resultado, consulta;

// Atajo para buscar un elemento por su id.
const $ = id => document.getElementById(id);

// Formatea números al estilo peruano/español (separador de miles y decimales).
const numero = (n, dec = 2) => Number(n).toLocaleString('es-ES', {minimumFractionDigits:dec, maximumFractionDigits:dec});

// Evita que un texto del CSV se interprete como HTML.
const escapar = texto => String(texto).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

// Llama a la API del servidor y devuelve la respuesta en JSON (o lanza el error recibido).
async function api(url, options) {
  const r = await fetch(url, options);
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || 'No se pudo completar la solicitud.');
  return data;
}


// ============================================================
// PESTAÑAS
// ============================================================

// Al hacer clic en una pestaña se activa su panel y se ocultan los demás.
document.querySelectorAll('[data-tab]').forEach(b => b.onclick = () => {
  document.querySelectorAll('[data-tab],.panel').forEach(e => e.classList.remove('activo'));
  b.classList.add('activo');
  $(b.dataset.tab).classList.add('activo');
});


// ============================================================
// RESUMEN DE CAPACIDAD
// ============================================================

// Calcula cuántos viajes hacen falta con la capacidad escrita y cuántos permite la flota.
function resumen() {
  if (!entrada) return;
  const q = Number($('capacidad_kg').value), k = Number($('camiones').value), j = Number($('viajes_por_camion').value);
  $('capacidadResumen').textContent = `Demanda: 41 904,36 kg · ${q > 0 ? Math.ceil(41904.36/q) : '—'} viajes necesarios · ${k*j} disponibles.`;

  // Si se cambian los parámetros después de ejecutar, se avisa que el resultado es anterior.
  if(resultado) {
    const cambio=Object.entries(resultado.configuracion).some(([clave,valor])=>Number($(clave).value)!==valor);
    $('generacionesInfo').textContent=cambio?'Resultado anterior · parámetros modificados':resultado.generaciones_ejecutadas+' generaciones';
  }
}


// ============================================================
// GRÁFICO DE CONVERGENCIA
// ============================================================

// Dibuja en SVG la mejor distancia y el promedio de la población por generación.
function dibujar(historial) {
  // SVG independiente de librerías: representa los valores reales del historial.
  const w=760,h=255,left=62,right=18,top=18,bottom=38;
  const valores=historial.flatMap(p=>[p.mejor_km,p.promedio_km]);
  let min=Math.floor(Math.min(...valores)*.995),max=Math.ceil(Math.max(...valores)*1.005);
  if(max===min) max=min+1;

  // Escalas: generación -> posición horizontal, km -> posición vertical.
  const x=g=>left+(w-left-right)*g/Math.max(1,historial.at(-1).generacion);
  const y=v=>h-bottom-(h-top-bottom)*(v-min)/(max-min);

  // Cinco líneas guía horizontales con su valor en km.
  let lineas='';
  for(let i=0;i<=4;i++){
    const v=min+(max-min)*i/4;
    lineas+=`<line x1="${left}" y1="${y(v)}" x2="${w-right}" y2="${y(v)}" stroke="#e7edef"/><text x="${left-9}" y="${y(v)+4}" text-anchor="end" fill="#62757d" font-size="11">${numero(v,0)}</text>`;
  }

  // Cada curva es una polilínea con un punto por generación.
  const curva=(key,color,width)=>`<polyline fill="none" stroke="${color}" stroke-width="${width}" points="${historial.map(p=>`${x(p.generacion)},${y(p[key])}`).join(' ')}"/>`;
  $('grafico').innerHTML=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Convergencia de distancia en kilómetros por generación"><text x="14" y="15" font-size="11" fill="#62757d">km</text>${lineas}${curva('promedio_km','#b3c4cc',2)}${curva('mejor_km','#087a68',3)}<text x="${left}" y="${h-12}" font-size="11" fill="#62757d">0</text><text x="${w-right}" y="${h-12}" text-anchor="end" font-size="11" fill="#62757d">${historial.at(-1).generacion} generaciones</text></svg>`;
}


// ============================================================
// MOSTRAR RESULTADOS
// ============================================================

// Pinta métricas, viajes, gráfico y estado de una ejecución (nueva o guardada).
function mostrar(r, guardada=false) {
  resultado=r;

  // Métricas principales.
  $('baseKm').textContent=numero(r.referencia.distancia_km)+' km';
  $('agKm').textContent=numero(r.solucion.distancia_km)+' km';
  $('mejora').textContent=numero(r.mejora_porcentaje)+' %';
  $('generacionesInfo').textContent=r.generaciones_ejecutadas+' generaciones';
  $('planResumen').textContent=`${r.solucion.viajes_totales} viajes · ${numero(r.solucion.demanda_recogida_kg)} kg recogidos · capacidad ${numero(r.configuracion.capacidad_kg,0)} kg · ${r.configuracion.camiones} camiones · semilla ${r.configuracion.semilla}.`;

  // Plan de viajes: paradas con kg recogidos y barra de carga del camión.
  const nombres=Object.fromEntries(entrada.mercados.map(m=>[m.id_mercado,m.mercado]));
  $('viajes').innerHTML=r.solucion.viajes.map(v=>`<div class="viaje"><div class="cabecera"><strong>Viaje ${v.viaje} · Camión ${v.camion} · Turno ${v.turno_camion}</strong><strong>${numero(v.distancia_km)} km</strong></div><p>Base EPSEL → ${v.paradas.map(p=>`${escapar(nombres[p.id_mercado])} (${numero(p.kg)} kg)`).join(' → ')} → Reque → Base EPSEL</p><div class="carga"><span style="width:${100*v.carga_kg/v.capacidad_kg}%"></span></div><p>${numero(v.carga_kg)} / ${numero(v.capacidad_kg,0)} kg · ${numero(100*v.carga_kg/v.capacidad_kg,1)} % de capacidad</p></div>`).join('');

  // Curva de convergencia y botones de descarga.
  dibujar(r.historial);
  $('json').disabled=$('csv').disabled=false;
  $('estado').className='';
  $('estado').textContent=`${guardada?'Ejecución guardada':'Ejecución terminada'} · ${numero(r.tiempo_segundos)} s · ${r.motivo_parada==='estancamiento'?'parada por falta de mejora':'límite de generaciones'}. Mejor solución encontrada; óptimo global no certificado.`;

  // Mostrar una ejecución guardada también restaura sus parámetros visibles.
  Object.entries(r.configuracion).forEach(([k,v])=>$(k).value=v);
  resumen();
}


// ============================================================
// EJECUCIÓN DEL ALGORITMO
// ============================================================

// Bloquea o habilita los botones mientras se ejecuta el AG.
function ocupado(si) {
  $('ejecutar').disabled=$('ejemplo').disabled=si;
}

// Muestra un error en pantalla y detiene el sondeo.
function fallo(e) {
  clearTimeout(consulta);
  ocupado(false);
  $('estado').className='error';
  $('estado').textContent=e.message;
}

// Pregunta al servidor cada 250 ms cómo va el AG hasta que termine.
async function sondear() {
  try {
    const e=await api('/api/estado');
    if(e.estado==='terminado'){
      ocupado(false);
      mostrar(e.resultado);
      return;
    }
    if(e.estado==='error') throw new Error(e.error);
    $('estado').textContent=e.progreso?`Generación ${e.progreso.generacion} · mejor ${numero(e.progreso.mejor_km)} km…`:'Preparando población…';
    consulta=setTimeout(sondear,250);
  } catch(e) {
    fallo(e);
  }
}

// Botón «Optimizar rutas»: envía la configuración del formulario y empieza el sondeo.
$('config').onsubmit=async e=>{
  e.preventDefault();
  const c={};
  Object.keys(entrada.configuracion).forEach(k=>c[k]=Number($(k).value));
  ocupado(true);
  $('estado').className='';
  $('estado').textContent='Iniciando algoritmo…';
  try {
    await api('/api/optimizar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(c)});
    sondear();
  } catch(err){
    fallo(err);
  }
};

// Botón «Ver ejecución guardada»: carga resultados/ejecucion.json.
$('ejemplo').onclick=async()=>{
  try{
    mostrar(await api('/api/ejemplo'),true);
  }catch(e){
    fallo(e);
  }
};


// ============================================================
// DESCARGAS
// ============================================================

// Crea un archivo en el navegador y lo descarga.
function descargar(nombre,contenido,tipo){
  const u=URL.createObjectURL(new Blob([contenido],{type:tipo}));
  const a=document.createElement('a');
  a.href=u;
  a.download=nombre;
  a.click();
  setTimeout(()=>URL.revokeObjectURL(u),1000);
}

// Descarga el resultado completo en JSON.
$('json').onclick=()=>descargar('resultado_rutas.json',JSON.stringify(resultado,null,2),'application/json');

// Descarga el plan de viajes en CSV (una fila por parada).
$('csv').onclick=()=>{
  const filas=[['viaje','camion','turno_camion','orden_parada','id_mercado','recogido_kg','carga_viaje_kg','distancia_viaje_km']];
  resultado.solucion.viajes.forEach(v=>v.paradas.forEach((p,i)=>filas.push([v.viaje,v.camion,v.turno_camion,i+1,p.id_mercado,p.kg,v.carga_kg,v.distancia_km])));
  descargar('plan_viajes.csv','\ufeff'+filas.map(f=>f.join(',')).join('\r\n'),'text/csv;charset=utf-8');
};


// ============================================================
// CARGA INICIAL
// ============================================================

// Al abrir la página: llena el formulario, la tabla de mercados y la tabla de flota.
api('/api/datos').then(d=>{
  entrada=d;
  Object.entries(d.configuracion).forEach(([k,v])=>$(k).value=v);
  $('mercados').innerHTML=d.mercados.map(m=>`<tr><td>${escapar(m.mercado)}</td><td>${escapar(m.distrito)}</td><td>${numero(m.puestos_fijos_reportados,0)}</td><td>${numero(m.residuos_kg_dia_estimados)}</td><td>${escapar(m.latitud_wgs84)}, ${escapar(m.longitud_wgs84)}</td></tr>`).join('');
  $('flota').innerHTML=d.flota_publicada.map(v=>`<tr><td>${escapar(v.codigo_unidad)}</td><td>${escapar(v.placa_o_motor_original)}</td><td>${escapar(v.volumen_m3)}</td><td>No publicada</td></tr>`).join('');
  $('estado').textContent='Datos cargados. Configura y ejecuta el escenario.';
  $('config').querySelectorAll('input').forEach(i=>i.addEventListener('input',resumen));
  resumen();
}).catch(fallo);
