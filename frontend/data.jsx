/* global React */
// Aijolot Banner Agent — campaign data (single source of truth for the demo)

// ---- The campaign brief ----
const CAMPAIGN = {
  id: "CMP-0192",
  title: "Hugo Boss — Fragancias",
  promo: "10% OFF",
  promoRule: "10% de descuento en toda la línea de fragancias Hugo Boss",
  window: "2 — 9 jun 2026",
  channel: "Tienda online · Home + Colección",
  brief: "Necesito un banner para la home: 10% de descuento en perfumes Hugo Boss, del 2 al 9 de junio. Que se vea premium, elegante, y que destaque el frasco. Personalizar por género del cliente.",
};

// ---- Module 1: Smart Querying — catalog auto-pulled from Shopify ----
const CATALOG = [
  { sku: "HB-BOTTLED-100", name: "Boss Bottled EDP 100ml", seg: "masculino", price: 138, sale: 124.2, stock: 64, img: "frasco azul oscuro" },
  { sku: "HB-SCENT-100", name: "Boss The Scent EDT 100ml", seg: "masculino", price: 118, sale: 106.2, stock: 38, img: "frasco ámbar" },
  { sku: "HB-ALIVE-80", name: "Boss Alive EDP 80ml", seg: "femenino", price: 124, sale: 111.6, stock: 51, img: "frasco dorado" },
  { sku: "HB-MAVIE-75", name: "Boss Ma Vie EDP 75ml", seg: "femenino", price: 116, sale: 104.4, stock: 27, img: "frasco rosa" },
  { sku: "HB-SET-LUX", name: "Set Lujo Boss Bottled", seg: "vip", price: 210, sale: 189, stock: 12, img: "estuche premium" },
];

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
    product: CATALOG[0],
    eyebrow: "BOSS BOTTLED",
    headline: "Define tu\npresencia.",
    sub: "El icónico Boss Bottled. Carácter en cada nota. Solo esta semana.",
    cta: "Comprar con 10% OFF",
    palette: { bgA: "#0A1420", bgB: "#16314a", ink: "#F5F2EC", sub: "rgba(245,242,236,.72)", accent: "#28C7F0", chip: "#C9A24B", glow: "rgba(40,199,240,.32)", bottle: "linear-gradient(160deg,#1b2c43,#0b1622)", cap: "#28C7F0" },
  },
  femenino: {
    id: "femenino", label: "Género: Femenino", tag: "gender:female", icon: "flower-2",
    audience: "Mujeres 22-44 · navegando ahora",
    product: CATALOG[2],
    eyebrow: "BOSS ALIVE",
    headline: "Tu momento,\ntu aroma.",
    sub: "Boss Alive, una celebración luminosa. Vívelo con 10% de descuento.",
    cta: "Descubrir Boss Alive",
    palette: { bgA: "#2A1130", bgB: "#5a2348", ink: "#FBEFF4", sub: "rgba(251,239,244,.78)", accent: "#F6B3CE", chip: "#E7B65C", glow: "rgba(246,179,206,.34)", bottle: "linear-gradient(160deg,#e9b25e,#c9824b)", cap: "#FBEFF4" },
  },
  vip: {
    id: "vip", label: "Cliente VIP", tag: "vip:true", icon: "crown",
    audience: "Clientes VIP · histórico > $1K",
    product: CATALOG[4],
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

// ---- Module 6: Approval workflow ----
const APPROVERS_SEED = [
  { id: "ecom", name: "Mara Voss", role: "Gerente E-commerce", initials: "MV", grad: "linear-gradient(135deg,#F72585,#8B5CF6)", status: "approved", note: "Aprobado. Se ve premium." },
  { id: "com", name: "Diego Salas", role: "Director Comercial", initials: "DS", grad: "linear-gradient(135deg,#22D3EE,#0891B2)", status: "pending", note: "" },
  { id: "legal", name: "Paula Rincón", role: "Legal", initials: "PR", grad: "linear-gradient(135deg,#10B981,#0EA5A4)", status: "pending", note: "" },
];

// ---- Collaborative comments pinned to banner regions ----
const COMMENTS_SEED = [
  { id: "c1", x: 26, y: 30, author: "Mara Voss", initials: "MV", grad: "linear-gradient(135deg,#F72585,#8B5CF6)", text: "El titular se ve perfecto. ¿Podemos hacer el fondo un poco más brillante?", resolved: false, time: "hace 8 min" },
  { id: "c2", x: 70, y: 64, author: "Diego Salas", initials: "DS", grad: "linear-gradient(135deg,#22D3EE,#0891B2)", text: "El botón debería resaltar más, probemos tono contraste.", resolved: false, time: "hace 3 min" },
];

// ---- Module 8: Performance metrics ----
const METRICS = [
  { id: "impr", icon: "eye", label: "Impresiones", value: "128,400", delta: "+18.2%", up: true },
  { id: "load", icon: "zap", label: "Carga real (p75)", value: "0.6 s", delta: "−72% peso", up: true },
  { id: "ctr", icon: "mouse-pointer-click", label: "CTR", value: "4.8%", delta: "+1.6 pts", up: true },
  { id: "conv", icon: "shopping-bag", label: "Conversiones", value: "612", delta: "+24%", up: true },
];

// segment performance split
const SEG_PERF = [
  { seg: "Masculino", ctr: 5.2, conv: 281, color: "#28C7F0" },
  { seg: "Femenino", ctr: 4.9, conv: 246, color: "#F6B3CE" },
  { seg: "VIP", ctr: 7.1, conv: 85, color: "#E7C76B" },
];

// 14-day CTR trend (for sparkline)
const CTR_TREND = [3.1, 3.4, 3.2, 3.8, 4.0, 3.7, 4.3, 4.6, 4.4, 4.9, 5.1, 4.8, 5.3, 4.8];

// ---- Evolutionary memory (Module 8) ----
const MEMORY = [
  { tag: "Calzado · primavera", text: "Estructuras minimalistas + botón flotante en color contraste convirtieron 24% más.", lift: "+24%" },
  { tag: "Perfumes · día de la madre", text: "Frasco centrado con halo superó al layout split en mobile.", lift: "+11%" },
  { tag: "VIP · histórico", text: "Copys de exclusividad elevan CTR en segmento VIP.", lift: "+37%" },
];

// ---- Store template pages + placements (where the banner is embedded) ----
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
const BRANDS = ["Hugo Boss", "Dior", "Chanel", "Carolina Herrera"];
const COLLECTIONS = ["Fragancias", "Hombre", "Mujer", "Novedades", "Sets de regalo"];

// ---- Art direction: hero-shot styles, model bank, banner-grid options ----
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

Object.assign(window, {
  CAMPAIGN, CATALOG, BRAND, SEGMENTS, SEGMENT_ORDER, VARIANTS, PIPELINE, CODE_LINES,
  APPROVERS_SEED, COMMENTS_SEED, METRICS, SEG_PERF, CTR_TREND, MEMORY, STORE_PAGES,
  SCOPE_OPTS, BRANDS, COLLECTIONS, HERO_STYLES, MODELS, GRID_OPTS,
});
