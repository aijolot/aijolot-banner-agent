/* global React */
// Aijolot Banner Agent — campaign data (single source of truth for the demo)

// ---- Module 2: Brand Guidelines Engine — locked tokens ----
const BRAND = {
  palette: [
    { hex: "#0B1622", name: "Noir base" },
    { hex: "#1E3A52", name: "Steel navy" },
    { hex: "#C9A24B", name: "Boss gold" },
    { hex: "#F5F2EC", name: "Ivory" },
    { hex: "#B23A6B", name: "Rosé accent" },
  ],
  fonts: ["Space Grotesk · Display", "Inter · Texto"],
  rules: ["Logo siempre en mayúsculas", "Mínimo 1 frasco visible", "CTA en contraste AA+", "Sin degradados arcoíris"],
};

// ---- Personalization segments (Module 7) ----
// Each segment fully re-skins the banner: palette, product, copy, audience.
const SEGMENTS = {
  masculino: {
    id: "masculino", label: "Género: Masculino", tag: "gender:male", icon: "venus-and-mars",
    audience: "Hombres 25-45 · navegando ahora",
    product: { name: "Boss Bottled", sku: "" },
    eyebrow: "BOSS BOTTLED",
    headline: "Define tu\npresencia.",
    sub: "El icónico Boss Bottled. Carácter en cada nota. Solo esta semana.",
    cta: "Comprar con 10% OFF",
    palette: { bgA: "#0A1420", bgB: "#16314a", ink: "#F5F2EC", sub: "rgba(245,242,236,.72)", accent: "#28C7F0", chip: "#C9A24B", glow: "rgba(40,199,240,.32)", bottle: "linear-gradient(160deg,#1b2c43,#0b1622)", cap: "#28C7F0" },
  },
  femenino: {
    id: "femenino", label: "Género: Femenino", tag: "gender:female", icon: "flower-2",
    audience: "Mujeres 22-44 · navegando ahora",
    product: { name: "Boss Alive", sku: "" },
    eyebrow: "BOSS ALIVE",
    headline: "Tu momento,\ntu aroma.",
    sub: "Boss Alive, una celebración luminosa. Vívelo con 10% de descuento.",
    cta: "Descubrir Boss Alive",
    palette: { bgA: "#2A1130", bgB: "#5a2348", ink: "#FBEFF4", sub: "rgba(251,239,244,.78)", accent: "#F6B3CE", chip: "#E7B65C", glow: "rgba(246,179,206,.34)", bottle: "linear-gradient(160deg,#e9b25e,#c9824b)", cap: "#FBEFF4" },
  },
  vip: {
    id: "vip", label: "Cliente VIP", tag: "vip:true", icon: "crown",
    audience: "Clientes VIP · histórico > $1K",
    product: { name: "Set Parfums", sku: "" },
    eyebrow: "ACCESO ANTICIPADO",
    headline: "Exclusivo\npara ti.",
    sub: "Tu set de lujo Boss, con 10% y envío prioritario. Solo para clientes VIP.",
    cta: "Acceder a mi precio VIP",
    palette: { bgA: "#0B0B0D", bgB: "#22201a", ink: "#F3E7C8", sub: "rgba(243,231,200,.74)", accent: "#E7C76B", chip: "#E7C76B", glow: "rgba(231,199,107,.3)", bottle: "linear-gradient(160deg,#3a3320,#11100c)", cap: "#E7C76B" },
  },
};
const SEGMENT_ORDER = ["masculino", "femenino", "vip"];

// ---- Banner layout variants (Module 4 output) ----
const VARIANTS = [
  { id: "A", name: "Spotlight", desc: "Frasco centrado, halo de luz, texto sobre.", layout: "spotlight", recommended: true },
  { id: "B", name: "Split editorial", desc: "Texto a la izquierda, producto a la derecha.", layout: "split" },
  { id: "C", name: "Minimal flotante", desc: "Producto flotante, CTA en pastilla de contraste.", layout: "minimal" },
];

// ---- Generation pipeline (Modules 1-5) ----
const PIPELINE = [
  { id: "query", icon: "database", title: "Smart Querying", sub: "Consultando catálogo Shopify…", done: "5 SKUs · stock validado · precios con 10% aplicados" },
  { id: "brand", icon: "shield-check", title: "Brand Guidelines Engine", sub: "Bloqueando identidad de marca…", done: "Paleta + tipografías + reglas cargadas" },
  { id: "image", icon: "sparkles", title: "Generación Estética IA", sub: "Componiendo fondo + aislando producto…", done: "Fondo IA + frasco aislado · capas flotantes" },
  { id: "code", icon: "code-2", title: "Compilador HTML / Liquid", sub: "Escribiendo HTML5 + CSS fluido + Liquid…", done: "Banner responsivo · clamp() + grid" },
  { id: "shield", icon: "gauge", title: "Core Web Vitals Shield", sub: "Optimizando SEO, accesibilidad y peso…", done: "−82% peso · WCAG AA · texto rastreable" },
];

// code that "types out" during compile step
const CODE_LINES = [
  '<section class="hb-banner" role="banner">',
  '  <picture class="hb-bg" aria-hidden="true">',
  '    {{ \'campaign-bg.webp\' | image_url }}',
  '  </picture>',
  '  <img class="hb-bottle" loading="lazy"',
  '       alt="{{ product.title }} con 10% de descuento">',
  '  <div class="hb-copy">',
  '    <span class="hb-eyebrow">{{ promo.eyebrow }}</span>',
  '    <h2>{{ promo.headline }}</h2>',
  '    <a class="hb-cta" href="{{ collection.url }}">',
  '      {{ promo.cta_label }}</a>',
  '  </div>',
  '</section>',
];

// ---- Store template pages + placements (explicit fallback only)
// Backend hydration in PlacementStage uses StoreApi resources/placement types first.
// These STORE_PAGES are retained as labeled visual fallback when backend data is unreachable.
const STORE_PAGES = [
  {
    id: "home", label: "Inicio", url: "maison-store.myshopify.com",
    placements: [
      { id: "announce", name: "Barra de anuncios", size: "1200 × 48", icon: "megaphone" },
      { id: "hero", name: "Hero principal", size: "1440 × 420", icon: "panel-top", rec: true },
      { id: "promo_l", name: "Promo izquierda", size: "600 × 300", icon: "panel-left" },
      { id: "promo_r", name: "Promo derecha", size: "600 × 300", icon: "panel-right" },
      { id: "footer", name: "CTA de footer", size: "1200 × 260", icon: "panel-bottom" },
    ],
  },
  {
    id: "collection", label: "Colección", url: "maison-store.myshopify.com/collections/fragancias",
    placements: [
      { id: "announce", name: "Barra de anuncios", size: "1200 × 48", icon: "megaphone" },
      { id: "coll_top", name: "Cabecera de colección", size: "1440 × 320", icon: "gallery-horizontal-end", rec: true },
      { id: "coll_inline", name: "Bloque intermedio", size: "600 × 600", icon: "layout-grid" },
      { id: "footer", name: "CTA de footer", size: "1200 × 260", icon: "panel-bottom" },
    ],
  },
  {
    id: "product", label: "Producto", url: "maison-store.myshopify.com/products/boss-bottled",
    placements: [
      { id: "pdp_strip", name: "Franja de oferta", size: "520 × 90", icon: "tag", rec: true },
      { id: "pdp_cross", name: "Cross-sell", size: "1200 × 220", icon: "layers" },
      { id: "footer", name: "CTA de footer", size: "1200 × 260", icon: "panel-bottom" },
    ],
  },
  {
    id: "search", label: "Búsqueda", url: "maison-store.myshopify.com/search?q=hugo+boss",
    placements: [
      { id: "search_top", name: "Banner de resultados", size: "1200 × 200", icon: "search", rec: true },
      { id: "announce", name: "Barra de anuncios", size: "1200 × 48", icon: "megaphone" },
      { id: "footer", name: "CTA de footer", size: "1200 × 260", icon: "panel-bottom" },
    ],
  },
];

// Targeting-scope options per page type (rule-based placement)
const SCOPE_OPTS = {
  home: [
    { id: "home", icon: "house", label: "Solo Home" },
    { id: "store", icon: "globe", label: "Toda la tienda" },
  ],
  collection: [
    { id: "this", icon: "layout-grid", label: "Solo esta colección" },
    { id: "multi", icon: "list-checks", label: "Selección de colecciones", param: "collections" },
    { id: "all", icon: "globe", label: "Todas las colecciones" },
  ],
  product: [
    { id: "this", icon: "package", label: "Solo este producto" },
    { id: "brand", icon: "tag", label: "Todos los PDP de una marca", param: "brand" },
    { id: "ptag", icon: "hash", label: "Productos con etiqueta", param: "tag" },
  ],
  search: [
    { id: "query", icon: "search", label: "Resultados de una búsqueda", param: "query" },
  ],
};

// ---- Art direction local UI presets ----
// Backend persists selected hero_style_key/model_key/custom_model through
// ArtDirectionApi, but it has no list endpoints for hero styles or model bank.
// These options are therefore local presets, not backend-provided data.
const HERO_STYLES = [
  { id: "rocks", name: "Rocas húmedas", desc: "Destellos · premium", grad: "linear-gradient(135deg,#0b1622,#1f3a52)" },
  { id: "marble", name: "Mármol minimal", desc: "Limpio · editorial", grad: "linear-gradient(135deg,#2a2622,#4a443a)" },
  { id: "studio", name: "Estudio degradado", desc: "Foco al producto", grad: "linear-gradient(135deg,#241026,#5a2348)" },
];
// "usage shot" model bank — brand can also create its own (see ModelBank)
const MODELS = [
  { id: "m1", name: "Sofía", tag: "Mujer · 25-34", grad: "linear-gradient(150deg,#5a2348,#b23a6b)" },
  { id: "m2", name: "Marcus", tag: "Hombre · 30-40", grad: "linear-gradient(150deg,#16314a,#28C7F0)" },
  { id: "m3", name: "Elena", tag: "Mujer · 35-44", grad: "linear-gradient(150deg,#3a3320,#c9a24b)" },
  { id: "m4", name: "Liam", tag: "Hombre · deportivo", grad: "linear-gradient(150deg,#0b3b2e,#10B981)" },
  { id: "m5", name: "Yuki", tag: "Unisex · editorial", grad: "linear-gradient(150deg,#1e1b4b,#8B5CF6)" },
  { id: "m6", name: "Noa", tag: "Mujer · 18-24", grad: "linear-gradient(150deg,#3a1020,#F72585)" },
];
const GRID_OPTS = [
  { id: 1, name: "Único", icon: "square" },
  { id: 2, name: "2 en fila", icon: "columns-2" },
  { id: 3, name: "3 en grid", icon: "grid-3x3" },
];

// Brand adapter — producción: solo /api/v1; un backend caído es un error
// visible, nunca brands sembradas en memoria.
const API_BASE = window.API_BASE || window.AIJOLOT_API_BASE || "http://localhost:8000";

const BrandAPI = {
  online: null, // null = unknown, true = backend reachable, false = unreachable
  async list() {
    try { const d = await AijolotApi.get(AijolotApi.v1("/brands")); this.online = true; return d; }
    catch (e) { this.online = e.status ? this.online : false; throw e; }
  },
  async get(id) {
    try { const d = await AijolotApi.get(AijolotApi.v1("/brands/" + id)); this.online = true; return d; }
    catch (e) { this.online = e.status ? this.online : false; throw e; }
  },
  async put(id, brand) {
    try { const d = await AijolotApi.put(AijolotApi.v1("/brands/" + id), brand); this.online = true; return d; }
    catch (e) { this.online = e.status ? this.online : false; throw e; }
  },
  async paletteSuggestions(id, payload) {
    try {
      const d = await AijolotApi.post(AijolotApi.v1(`/brands/${id}/palette-suggestions`), payload || {});
      this.online = true; return d;
    } catch (e) {
      if (e.status) throw e; // backend validation/Gemini errors should be shown as-is
      this.online = false;
      const err = new Error("AI Palette Suggestions unavailable: backend/Gemini service is not reachable.");
      err.body = err.message;
      throw err;
    }
  },
  // Shopify brand discovery (synchronous run). NEVER faked offline: discovery is
  // real store evidence, so a network failure surfaces an explicit error instead
  // of seeds. Backend errors (404/409/422/503 with detail) are rethrown as-is.
  async startDiscovery(id, payload) {
    try {
      const d = await AijolotApi.post(AijolotApi.v1(`/brands/${id}/discovery-runs`), payload || {});
      this.online = true; return d;
    } catch (e) {
      if (e.status) throw e;
      this.online = false;
      const err = new Error("El descubrimiento requiere el backend y Shopify conectados. No se puede simular.");
      err.body = err.message;
      throw err;
    }
  },
  // Gemini color-role recommendation for a finished discovery run. Real AI only:
  // never simulated offline (backend already answers 503 when Gemini is down).
  async discoveryRecommendations(id, runId) {
    try {
      const d = await AijolotApi.post(AijolotApi.v1(`/brands/${id}/discovery-runs/${runId}/recommendations`));
      this.online = true; return d;
    } catch (e) {
      if (e.status) throw e;
      this.online = false;
      const err = new Error("Las recomendaciones IA requieren el backend y Gemini conectados. No se pueden simular.");
      err.body = err.message;
      throw err;
    }
  },
  // Font candidates (Gemini-backed when available; labeled non-AI fallback otherwise).
  // The endpoint answers 200 with ai_available=false when Gemini is down, so the
  // only offline path here is the backend itself being unreachable — never faked.
  async fontSuggestions(id, payload) {
    try {
      const d = await AijolotApi.post(AijolotApi.v1(`/brands/${id}/font-suggestions`), payload || {});
      this.online = true; return d;
    } catch (e) {
      if (e.status) throw e;
      this.online = false;
      const err = new Error("Las sugerencias de fuentes requieren el backend conectado. No se pueden simular.");
      err.body = err.message;
      throw err;
    }
  },
};

Object.assign(window, {
  BRAND, SEGMENTS, SEGMENT_ORDER, VARIANTS, PIPELINE, CODE_LINES, STORE_PAGES,
  SCOPE_OPTS, HERO_STYLES, MODELS, GRID_OPTS,
  BrandAPI, API_BASE,
});
