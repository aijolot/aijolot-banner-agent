/* global React, Icon */
// Aijolot Banner Agent — i18n ES/EN.
// El español es el idioma fuente del UI; `t("texto es")` devuelve la traducción
// EN cuando el switcher está en inglés (fallback: el texto ES, visible — nunca
// crashea por una key faltante). El idioma también viaja al backend en CADA
// request (header X-Aijolot-Lang) y en structured_brief.language, para que el
// agente responda, redacte y razone en el MISMO idioma que el UI.

const AIJOLOT_LANG = (function () {
  try { return localStorage.getItem("AIJOLOT_LANG") === "en" ? "en" : "es"; } catch (e) { return "es"; }
})();

function setAijolotLang(lang) {
  try { localStorage.setItem("AIJOLOT_LANG", lang === "en" ? "en" : "es"); } catch (e) { /* no storage */ }
  location.reload();
}

// Diccionario ES → EN (el ES vive inline en los componentes).
const I18N_EN = {
  // Shell / dashboard
  "Estudio de Banners": "Banner Studio",
  "Agente CEOD activo": "CEOD Agent active",
  "Nueva campaña": "New campaign",
  "Del brief al código nativo de Shopify en segundos. Banners responsivos, optimizados para SEO y de carga ultrarrápida — sin salir de marca.":
    "From brief to native Shopify code in seconds. Responsive, SEO-optimized, ultra-fast banners — always on brand.",
  "Campañas activas": "Active campaigns",
  "Banners publicados": "Published banners",
  "CTR promedio": "Average CTR",
  "Peso ahorrado": "Weight saved",
  "Campañas recientes": "Recent campaigns",
  "Esperando campañas backend": "Waiting for backend campaigns",
  "No hay campañas creadas aún": "No campaigns yet",
  "Crea tu primera campaña con «Nueva campaña»; aparecerá aquí.": "Create your first campaign with “New campaign”; it will appear here.",
  "Continuar": "Continue",
  "Ver performance": "View performance",
  // Stepper
  "Ubicación": "Placement",
  "Brief": "Brief",
  "Plan": "Plan",
  "Generación": "Generation",
  "Lienzo": "Canvas",
  "Performance": "Performance",
  "Brief comercial": "Commercial brief",
  "Plan de campaña": "Campaign plan",
  "Lienzo colaborativo": "Collaborative canvas",
  // Calendario
  "Calendario comercial": "Commercial calendar",
  "Anticipación": "Lead time",
  "días": "days",
  "día": "day",
  "Fechas de mi nicho": "My niche dates",
  "Buscando…": "Searching…",
  "Preparar campaña": "Prepare campaign",
  "fuera de ventana": "outside window",
  "Campaña creada": "Campaign created",
  "Retail MX/Global": "Retail MX/Global",
  "Nicho (agente)": "Niche (agent)",
  "Manual": "Manual",
  "Sin fechas próximas en el calendario.": "No upcoming dates in the calendar.",
  "Campaña creada con el brief de la fecha — revisa y planéala.": "Campaign created with the date's brief — review and plan it.",
  // Sugerencias
  "El agente sugiere": "The agent suggests",
  "Fecha comercial": "Commercial date",
  "Catálogo": "Catalog",
  "Descartar": "Dismiss",
  "Crear campaña": "Create campaign",
  "Aplicar refresh": "Apply refresh",
  "Vigente hasta": "Valid until",
  // Brief
  "Paso 2 de 6 · Brief comercial": "Step 2 of 6 · Commercial brief",
  "Brief completo": "Brief complete",
  "El agente preparó este brief": "The agent prepared this brief",
  "Aceptar brief y planear": "Accept brief and plan",
  "Brief con el agente": "Brief with the agent",
  "Describe la campaña en lenguaje natural": "Describe the campaign in natural language",
  "Avanzar al plan": "Continue to plan",
  // Plan
  "Paso 3 de 6 · Plan de campaña": "Step 3 of 6 · Campaign plan",
  "Revisa el plan antes de generar": "Review the plan before generating",
  "Volver al brief": "Back to brief",
  "Aprobar y generar": "Approve and generate",
  "Generando…": "Generating…",
  "Plan listo · sin costo de imagen": "Plan ready · no image cost",
  "Armando el plan…": "Building the plan…",
  "Piezas y ubicaciones propuestas": "Proposed pieces and placements",
  "pieza": "piece",
  "piezas": "pieces",
  "Se genera al aprobar": "Generated on approval",
  "Usar ubicación": "Use placement",
  "Aplicada": "Applied",
  "La pieza 1 es la que se genera al aprobar este plan; las demás quedan como backlog de la campaña.":
    "Piece 1 is generated when you approve this plan; the rest become the campaign backlog.",
  "Modo creativo": "Creative mode",
  "Recomendado por el agente": "Recommended by the agent",
  "Definido por ti": "Set by you",
  "Producto recortado": "Product cut-out",
  "Escena completa": "Full scene",
  "Video": "Video",
  "Incluir personas": "Include people",
  "Itera la idea": "Iterate the idea",
  "Aplicar al plan": "Apply to plan",
  "Replaneando…": "Replanning…",
  "Wireframe (baja fidelidad)": "Wireframe (low fidelity)",
  "Sin imagen": "No image",
  "Tipografía": "Typography",
  "Paleta y color": "Palette & color",
  "Producto y tema": "Product & theme",
  "Copy propuesto": "Proposed copy",
  "Layout": "Layout",
  "¿Por qué este plan?": "Why this plan?",
  // Generación
  "Backend conectado": "Backend connected",
  "Backend error": "Backend error",
  "¿Por qué?": "Why?",
  // Canvas
  "Ver": "View",
  "Editar": "Edit",
  "Comentar": "Comment",
  "Edición directa": "Direct edit",
  "Todo el texto": "All text",
  "Imagen": "Image",
  "POR SECCIÓN": "PER SECTION",
  "Título": "Headline",
  "Subtítulo": "Subheadline",
  "CTA": "CTA",
  "Descartar cambios": "Discard",
  "Aplicar al instante": "Apply instantly",
  "Aplicando…": "Applying…",
  "Revisa, comenta y aprueba": "Review, comment and approve",
  "Aprobaciones": "Approvals",
  "Aprobar": "Approve",
  "Cambios": "Changes",
  "Publicación y agenda": "Publishing & schedule",
  "Programar": "Schedule",
  // Performance
  "Registrar snapshot": "Record snapshot",
  "Cargando métricas del backend…": "Loading backend metrics…",
  "Sin métricas registradas para esta campaña. Usa «Registrar snapshot» o espera el sync automático del agente.":
    "No metrics recorded for this campaign yet. Use “Record snapshot” or wait for the agent's automatic sync.",
  "Sin serie de CTR todavía — sincroniza snapshots de performance.": "No CTR series yet — sync performance snapshots.",
  // Genéricos
  "Verifica que el backend (:8000) y Supabase estén arriba.": "Check that the backend (:8000) and Supabase are up.",
};

function t(es) {
  if (AIJOLOT_LANG !== "en") return es;
  return I18N_EN[es] || es;
}

// Switcher ES | EN (topbar). Cambiar idioma persiste + recarga, y desde ese
// momento TODO (UI + agente vía X-Aijolot-Lang/brief.language) va en ese idioma.
function LangSwitcher() {
  const pill = (lang, label) => (
    <button
      key={lang}
      onClick={() => AIJOLOT_LANG !== lang && setAijolotLang(lang)}
      style={{
        padding: "4px 10px", borderRadius: 9999, border: "none", cursor: "pointer",
        fontFamily: "Space Grotesk", fontSize: 11.5, fontWeight: 700,
        background: AIJOLOT_LANG === lang ? "#0891B2" : "transparent",
        color: AIJOLOT_LANG === lang ? "#fff" : "#64748B",
      }}
      title={lang === "es" ? "Español (México)" : "English"}
    >{label}</button>
  );
  return (
    <div style={{ display: "inline-flex", gap: 2, background: "rgba(248,250,252,0.9)", border: "1px solid #EEF2F6", borderRadius: 9999, padding: 3 }}>
      {pill("es", "ES")}{pill("en", "EN")}
    </div>
  );
}

Object.assign(window, { AIJOLOT_LANG, I18N_EN, t, setAijolotLang, LangSwitcher });
