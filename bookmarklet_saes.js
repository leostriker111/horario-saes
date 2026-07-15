// Bookmarklet "Copiar horario SAES"
// ----------------------------------
// El SAES renderiza el horario en una tabla (GridView ctl00_mainCopy_dbgHorarios)
// después de que llenas los filtros y picas "Visualizar información". Replicar ese
// flujo headless es frágil (cadena de autopostbacks ASP.NET), así que en vez de
// scrapear a ciegas, aprovechamos que la tabla YA está en la página: este
// bookmarklet la copia al portapapeles en el formato de tabs que Horario SAES carga.
//
// Uso:
//   1. En el SAES, elige carrera / turno / plan / periodo y pica "Visualizar información".
//   2. Pica este bookmarklet -> copia la tabla al portapapeles.
//   3. Pégala en un .txt (o encadena varias carreras para las equivalencias) y
//      cárgala en la app con 📥 Cargar datos -> Desde un TXT.
//   Repite el paso 1-2 por cada carrera (Informática, Ciencias, etc.) y pega todo
//   en el mismo .txt: así juntas las materias equivalentes de otras carreras.
//
// Para instalarlo: crea un marcador y pega como URL la versión minificada de abajo.

(function () {
  var g = document.querySelector('#ctl00_mainCopy_dbgHorarios');
  if (!g) {
    alert('No encontré la tabla de horarios. Primero pica "Visualizar información".');
    return;
  }
  var txt = [].map.call(g.rows, function (r) {
    return [].slice.call(r.cells, 0, 10).map(function (c) {
      return c.textContent.replace(/\s+/g, ' ').trim();
    }).join('\t');
  }).join('\n');
  navigator.clipboard.writeText(txt).then(function () {
    alert('¡Copiado! ' + (g.rows.length - 1) + ' grupos. Pégalos en tu .txt.');
  }, function () {
    // fallback si clipboard falla
    var ta = document.createElement('textarea');
    ta.value = txt; document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); ta.remove();
    alert('¡Copiado! ' + (g.rows.length - 1) + ' grupos.');
  });
})();

// --- versión minificada para pegar como marcador (URL) ---
// javascript:(function(){var g=document.querySelector('#ctl00_mainCopy_dbgHorarios');if(!g){alert('Primero pica Visualizar informacion.');return;}var t=[].map.call(g.rows,function(r){return [].slice.call(r.cells,0,10).map(function(c){return c.textContent.replace(/\s+/g,' ').trim();}).join('\t');}).join('\n');navigator.clipboard.writeText(t).then(function(){alert('Copiado! '+(g.rows.length-1)+' grupos.');},function(){var a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();document.execCommand('copy');a.remove();alert('Copiado! '+(g.rows.length-1)+' grupos.');});})();
