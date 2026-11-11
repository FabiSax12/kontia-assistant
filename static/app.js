// Asistente Kontia: chat en JS vanilla, sin dependencias.
const chat = document.getElementById("chat");
const formulario = document.getElementById("formulario");
const campo = document.getElementById("mensaje");
const botonEnviar = document.getElementById("enviar");
const modalPrivacidad = document.getElementById("privacidad");
const modalContacto = document.getElementById("contacto");

let interaccionContacto = null;

function leerAlmacen(clave) {
  try { return localStorage.getItem(clave); } catch (e) { return null; }
}
function guardarAlmacen(clave, valor) {
  try { localStorage.setItem(clave, valor); } catch (e) { /* sin almacenamiento: se pregunta de nuevo */ }
}

// session_id anónimo generado en el navegador
function nuevoId() {
  if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
  return "s-" + Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
}
let sessionId = leerAlmacen("kontia_session") || nuevoId();
guardarAlmacen("kontia_session", sessionId);

function el(etiqueta, clase, texto) {
  const nodo = document.createElement(etiqueta);
  if (clase) nodo.className = clase;
  if (texto !== undefined) nodo.textContent = texto;
  return nodo;
}

function colones(n) {
  return "₡" + Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}

function bajar() { chat.scrollTop = chat.scrollHeight; }

function burbuja(texto, clase) {
  const b = el("div", "burbuja " + clase, texto);
  chat.appendChild(b);
  bajar();
  return b;
}

function filaCalculo(tabla, etiqueta, valor) {
  const tr = document.createElement("tr");
  tr.appendChild(el("td", null, etiqueta));
  tr.appendChild(el("td", null, valor));
  tabla.appendChild(tr);
}

function desgloseCalculo(calculo) {
  const d = calculo.datos;
  const tabla = document.createElement("table");
  if (calculo.tool === "calcular_aguinaldo") {
    filaCalculo(tabla, "Aguinaldo", colones(d.monto));
    filaCalculo(tabla, "Tiempo contado", d.meses_contados + " meses" + (d.dias_residuales ? " y " + d.dias_residuales + " días" : ""));
    filaCalculo(tabla, "Periodo", d.periodo_inicio + " al " + d.periodo_fin);
    filaCalculo(tabla, "Fecha límite", d.fecha_limite);
  } else if (calculo.tool === "calcular_cargas_sociales") {
    filaCalculo(tabla, "Salario bruto", colones(d.salario_bruto));
    filaCalculo(tabla, "Cuota patronal (" + (d.tasa_patronal * 100).toFixed(2) + " %)", colones(d.patronal));
    filaCalculo(tabla, "Cuota obrera (" + (d.tasa_obrera * 100).toFixed(2) + " %)", colones(d.obrera));
    filaCalculo(tabla, "Neto antes de renta", colones(d.neto_antes_renta));
  } else if (calculo.tool === "calcular_costo_empleado") {
    filaCalculo(tabla, "Salario del periodo", colones(d.salario_periodo));
    filaCalculo(tabla, "Aguinaldo", colones(d.aguinaldo));
    filaCalculo(tabla, "CCSS patronal", colones(d.ccss_patronal));
    filaCalculo(tabla, "INS", colones(d.ins));
    filaCalculo(tabla, "Costo total", colones(d.costo_total));
  }
  return tabla;
}

function tarjetaFicha(ficha, calculo) {
  const t = el("div", "tarjeta");
  t.appendChild(el("strong", null, "Ficha: " + ficha.titulo));
  t.appendChild(el("div", null, "Revisada el " + ficha.fecha_revision));
  const fuente = el("div");
  if (/^https?:\/\//.test(ficha.fuente)) {
    const a = el("a", null, ficha.fuente);
    a.href = ficha.fuente; a.target = "_blank"; a.rel = "noopener noreferrer";
    fuente.appendChild(a);
  } else {
    fuente.textContent = "Fuente oficial: " + ficha.fuente;
  }
  t.appendChild(fuente);
  if (calculo) t.appendChild(desgloseCalculo(calculo));
  return t;
}

function abrirContacto(idInteraccion) {
  interaccionContacto = idInteraccion;
  document.getElementById("msg-contacto").textContent = "";
  modalContacto.showModal();
}

function estrellas(idInteraccion) {
  const caja = el("div", "estrellas");
  caja.appendChild(el("span", null, "¿Te sirvió?"));
  for (let n = 1; n <= 5; n++) {
    const b = el("button", null, String(n));
    b.type = "button";
    b.setAttribute("aria-label", "Calificar con " + n);
    b.addEventListener("click", async () => {
      try {
        await fetch("/api/feedback", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ interaction_id: idInteraccion, rating: n }),
        });
        caja.querySelectorAll("button").forEach((x) => { x.disabled = true; });
        b.classList.add("activa");
      } catch (e) { /* sin conexión: se puede reintentar */ }
    });
    caja.appendChild(b);
  }
  const pedir = el("button", "enlace", "Pedir revisión de un contador");
  pedir.type = "button";
  pedir.addEventListener("click", () => abrirContacto(idInteraccion));
  caja.appendChild(pedir);
  return caja;
}

function mostrarRespuesta(datos) {
  const b = burbuja(datos.respuesta, "asistente");
  if (datos.ficha) b.appendChild(tarjetaFicha(datos.ficha, datos.calculo));
  if (datos.derivado) {
    const caja = el("div", "derivacion", "Tu consulta necesita a una persona. ");
    const boton = el("button", "enlace", "Dejar mi contacto");
    boton.type = "button";
    boton.addEventListener("click", () => abrirContacto(datos.interaction_id));
    caja.appendChild(boton);
    b.appendChild(caja);
  }
  if (datos.interaction_id) b.appendChild(estrellas(datos.interaction_id));
  bajar();
}

formulario.addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const texto = campo.value.trim();
  if (!texto) return;
  burbuja(texto, "usuario");
  campo.value = "";
  botonEnviar.disabled = true;
  const espera = burbuja("escribiendo…", "asistente escribiendo");
  try {
    const r = await fetch("/api/chat", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, mensaje: texto }),
    });
    if (!r.ok) throw new Error("http " + r.status);
    const datos = await r.json();
    espera.remove();
    mostrarRespuesta(datos);
  } catch (e) {
    espera.remove();
    burbuja("No pude conectarme en este momento. Revisá tu conexión e intentá de nuevo.", "asistente");
  } finally {
    botonEnviar.disabled = false;
    campo.focus();
  }
});

document.getElementById("form-contacto").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const msg = document.getElementById("msg-contacto");
  const acepto = document.getElementById("acepto").checked;
  if (!acepto) { msg.textContent = "Necesitamos tu consentimiento para guardar tu contacto."; return; }
  try {
    const r = await fetch("/api/derivacion", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        interaction_id: interaccionContacto,
        contacto: document.getElementById("dato-contacto").value.trim(),
        acepto: true,
      }),
    });
    if (!r.ok) throw new Error("http " + r.status);
    modalContacto.close();
    burbuja("Listo, un contador te va a contactar. Gracias.", "asistente");
  } catch (e) {
    msg.textContent = "No pudimos guardar tu contacto. Intentá de nuevo.";
  }
});
document.getElementById("cancelar-contacto").addEventListener("click", () => modalContacto.close());

// Aviso de privacidad: obligatorio antes de escribir
function bloquear(bloqueado) {
  campo.disabled = bloqueado;
  botonEnviar.disabled = bloqueado;
}
modalPrivacidad.addEventListener("cancel", (ev) => ev.preventDefault()); // Esc no lo cierra
document.getElementById("aceptar").addEventListener("click", () => {
  guardarAlmacen("kontia_privacidad_ok", "1");
  modalPrivacidad.close();
  bloquear(false);
  campo.focus();
});
if (leerAlmacen("kontia_privacidad_ok") !== "1") {
  bloquear(true);
  modalPrivacidad.showModal();
}

burbuja("Hola, soy el Asistente Kontia. Preguntame sobre aguinaldo, cargas sociales de la CCSS, INS o Hacienda.", "asistente");
