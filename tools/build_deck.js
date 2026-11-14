// Builds Hotspot_Harmony_Presentation.pptx (7 slides). Run from project root: node tools/build_deck.js
// Uses real app screenshots from screenshots/*.png when present; otherwise shows a labelled placeholder.
const pptxgen = require("pptxgenjs");
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, ".."), SHOT = (n) => path.join(ROOT, "screenshots", n);
const THEME = { headFontFace: "Calibri", bodyFontFace: "Calibri" };
const BG = "0B1220", CARD = "141E33", ORANGE = "FF6B2C", BLUE = "4DA3FF", TXT = "E8EEF9", MUTED = "9FB0CC";

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.title = "Hotspot Harmony";
pres.author = "Muhammad Ahmar";
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };

function base(title, notes) {
  const s = pres.addSlide();
  s.background = { color: BG };
  s.addText(title, { x: 0.5, y: 0.3, w: 9, h: 0.6, fontSize: 28, bold: true, color: TXT, margin: 0, isTextBox: true });
  s.addShape(pres.ShapeType.rect, { x: 0.5, y: 0.95, w: 0.8, h: 0.05, fill: { color: ORANGE }, line: { color: ORANGE } });
  s.addText("Hotspot Harmony · NASA Space Apps 2026", { x: 0.5, y: 5.2, w: 6, h: 0.25, fontSize: 10, color: MUTED, margin: 0, isTextBox: true });
  if (notes) s.addNotes(notes);
  return s;
}
function card(s, x, y, w, h, head, body, color) {
  s.addShape(pres.ShapeType.roundRect, { x, y, w, h, fill: { color: CARD }, line: { color: "23314F" }, rectRadius: 0.1 });
  s.addText(head, { x: x + 0.2, y: y + 0.15, w: w - 0.4, h: 0.45, fontSize: 18, bold: true, color: color || ORANGE, margin: 0, isTextBox: true });
  s.addText(body, { x: x + 0.2, y: y + 0.65, w: w - 0.4, h: h - 0.8, fontSize: 14, color: TXT, valign: "top", margin: 0, isTextBox: true });
}
function shot(s, file, x, y, w, h, label) {
  if (fs.existsSync(SHOT(file))) {
    s.addImage({ path: SHOT(file), x, y, w, h, sizing: { type: "contain", w, h } });
  } else {
    s.addShape(pres.ShapeType.rect, { x, y, w, h, fill: { color: CARD }, line: { color: ORANGE, dashType: "dash", width: 1.5 } });
    s.addText([{ text: "SCREENSHOT PLACEHOLDER", options: { bold: true, breakLine: true } },
               { text: `${label}\nRun tools/capture_screenshots.py, then node tools/build_deck.js` }],
      { x, y, w, h, align: "center", valign: "middle", fontSize: 12, color: MUTED, isTextBox: true });
  }
}

// 1 Title
let s = pres.addSlide(); s.background = { color: BG };
s.addShape(pres.ShapeType.ellipse, { x: 6.6, y: 0.9, w: 2.9, h: 2.9, fill: { color: ORANGE, transparency: 70 }, line: { color: ORANGE, width: 2 } });
s.addShape(pres.ShapeType.ellipse, { x: 7.3, y: 1.6, w: 1.5, h: 1.5, fill: { color: BLUE, transparency: 55 }, line: { color: BLUE, width: 2 } });
s.addText("HOTSPOT\nHARMONY", { x: 0.6, y: 1.0, w: 6, h: 1.8, fontSize: 54, bold: true, color: TXT, margin: 0, isTextBox: true });
s.addText("One burning-activity calendar from MODIS + VIIRS fire detections", { x: 0.6, y: 2.95, w: 5.8, h: 0.8, fontSize: 18, color: ORANGE, margin: 0, isTextBox: true });
s.addText("Team: MODIS Meets VIIRS  ·  Muhammad Ahmar\nNASA Space Apps Challenge 2026", { x: 0.6, y: 4.3, w: 7, h: 0.7, fontSize: 14, color: MUTED, margin: 0, isTextBox: true });
s.addNotes("Hotspot Harmony harmonises MODIS and VIIRS active-fire data into one interactive calendar.");

// 2 Challenge
s = base("The challenge: two sensors, two stories", "NASA challenge: Harmonization of MODIS and VIIRS Hot Spots.");
card(s, 0.5, 1.3, 4.3, 2.0, "MODIS", "1 km pixels\nFire record since 2000", BLUE);
card(s, 5.2, 1.3, 4.3, 2.0, "VIIRS", "375 m pixels\nFire record since 2012", ORANGE);
s.addText("Different resolution and coverage → counts are not directly comparable. Long-term fire patterns are hard to read.",
  { x: 0.5, y: 3.7, w: 9, h: 0.9, fontSize: 18, color: TXT, margin: 0, isTextBox: true });

// 3 Inspiration & solution
s = base("Inspiration and solution", "Inspiration: seasonal crop-residue burning around the user's home region (Punjab).");
card(s, 0.5, 1.3, 4.3, 3.4, "Inspiration", "Seasonal burning in Punjab shapes smoke and air quality every year.\n\nCommunities need to know: is this month normal?", ORANGE);
card(s, 5.2, 1.3, 4.3, 3.4, "Solution", "An interactive calendar that merges both sensors into one VIIRS-equivalent record, compares each month to its historical median, and flags unusual periods.", BLUE);

// 4 How it works
s = base("How it works", "Pipeline: FIRMS CSV -> normalise -> monthly fire-cell-days -> calibrate on overlap -> harmonise -> compare with history.");
const steps = ["FIRMS CSVs\nMODIS + VIIRS", "Normalise\nconfidence, region", "Fire-cell-days\n0.1° grid", "Calibrate\nVIIRS/MODIS ratio", "Compare\nvs monthly median"];
steps.forEach((t, i) => {
  const x = 0.5 + i * 1.84;
  s.addShape(pres.ShapeType.roundRect, { x, y: 1.25, w: 1.6, h: 0.85, fill: { color: CARD }, line: { color: i % 2 ? BLUE : ORANGE, width: 1.5 }, rectRadius: 0.08 });
  s.addText(t, { x, y: 1.25, w: 1.6, h: 0.85, fontSize: 11, color: TXT, align: "center", valign: "middle", isTextBox: true });
  if (i < 4) s.addText("›", { x: x + 1.6, y: 1.25, w: 0.24, h: 0.85, fontSize: 20, color: ORANGE, align: "center", valign: "middle", isTextBox: true });
});
shot(s, "01_calendar.png", 0.5, 2.3, 4.4, 2.75, "Calendar tab");
shot(s, "02_compare.png", 5.1, 2.3, 4.4, 2.75, "Compare to history tab");

// 5 More screens
s = base("Explore, compare, spot unusual months", "Screens captured from the running app.");
shot(s, "03_unusual.png", 0.5, 1.2, 2.9, 3.6, "Unusual periods");
shot(s, "04_map.png", 3.55, 1.2, 2.9, 3.6, "Map");
shot(s, "05_harmonisation.png", 6.6, 1.2, 2.9, 3.6, "Harmonisation");

// 6 Data & tech
s = base("NASA data and technology", "All detections come from NASA FIRMS files loaded by the user.");
card(s, 0.5, 1.3, 4.3, 3.4, "NASA data", "NASA FIRMS (LANCE / EOSDIS)\n• MODIS active fire (Terra/Aqua)\n• VIIRS 375 m active fire (S-NPP)\n\nfirms.modaps.eosdis.nasa.gov", ORANGE);
card(s, 5.2, 1.3, 4.3, 3.4, "Technology", "Python · Streamlit\nPandas · NumPy\nPlotly (charts + maps)\n\nOpen-source, runs on a laptop", BLUE);

// 7 Future
s = base("Future impact and potential", "Roadmap items are ideas, not completed work.");
card(s, 0.5, 1.3, 2.85, 3.4, "Who benefits", "Researchers, air-quality teams, agriculture and disaster planners", ORANGE);
card(s, 3.575, 1.3, 2.85, 3.4, "Next steps", "More sensors (NOAA-20/21)\nBurned-area context\nAlerts for unusual months", BLUE);
card(s, 6.65, 1.3, 2.85, 3.4, "Scale", "Any region on Earth with FIRMS coverage", ORANGE);

pres.writeFile({ fileName: path.join(ROOT, "Hotspot_Harmony_Presentation.pptx") }).then(f => console.log("wrote", f));
