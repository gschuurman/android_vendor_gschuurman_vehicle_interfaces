// out: rev0.4/audio/WIZARD.html
// Bring-up wizard data. Rebuild the page with: python3 PCB/wizard/build.py
const BOARD = {
  title: 'Audiomodule rev 0.4',
  key: 'audio-rev04',
  meta: `Ontwerp: <code>PCB/rev0.4/audio/carradio_audio_rev04.kicad_pcb</code> (gebruikt in de rev 0.6-set). Header J24 zit aan de onderkant. Pin 1 is het vierkante pad.`,
  tabs: [
  {id:'audm', name:"Multimeter (zonder voeding)", next:"Ga door met \"Eerste keer voeden\", met stroombegrenzing.", steps:[
 {t:"Voorbereiding",info:true,body:`
  <p>Audiomodule los, niets aangesloten. Header J24 zit aan de <b>onderkant</b>; pin 1 is het <b>vierkante</b> pad. GND-pinnen: 3, 4, 6, 15 en 16. Deze wizard gebruikt pin 3.</p>
  <p>Kijk eerst met de loep naar de pinnen van <b>U10</b> en <b>U11</b> (PCM5102A, TSSOP-20) en of <b>U8</b> en <b>U9</b> (LP5907) goed om zitten.</p>
  <p>Multimeter op <b>Ω</b>, pennen tegen elkaar: bijna 0 Ω.</p>`},
 {t:"GND controleren",setting:"piepstand",red:"J24 pin 3",black:"J24 pin 4",exp:"≈ 0 Ω (piept)",small:"",
  fail:"Pin 3 of 4 slecht gesoldeerd."},
 {t:"5 V-ingang naar GND",setting:"Ω",red:"J24 pin 1",black:"J24 pin 3",exp:"loopt op → hoog",small:"C18, C20 en de ingangen van U8/U9",
  fail:"Onder 100 Ω: kijk naar C18, C20 en de pinnen 1–3 van U8 en U9."},
 {t:"Pin 1 en 2 samen",setting:"piepstand",red:"J24 pin 1",black:"J24 pin 2",exp:"≈ 0 Ω (piept)",small:"",
  fail:"Pin 1 of 2 slecht gesoldeerd."},
 {t:"3,3 V analoog",setting:"Ω",red:"hete pad van C28",black:"J24 pin 3",exp:"loopt op → hoger dan ~1 kΩ",small:"uitgang U8, pinnen 1 en 8 van beide DAC's",
  pre:"C28 is de 10 µF naast U8, bovenaan.",
  fail:"Onder 100 Ω: brug bij U10/U11 pin 1 of 8, of C25, C26, C35, C36, C38."},
 {t:"3,3 V digitaal",setting:"Ω",red:"hete pad van C29",black:"J24 pin 3",exp:"loopt op → hoger dan ~1 kΩ",small:"uitgang U9, pin 20 van beide DAC's",
  fail:"Onder 100 Ω: brug bij U10/U11 pin 20, of C27, C37, C39."},
 {t:"5 V niet aan 3,3 V",setting:"Ω",red:"J24 pin 1",black:"hete pad van C28, daarna C29",exp:"hoger dan ~1 kΩ",small:"",
  fail:"Laag: brug tussen in- en uitgang bij U8 of U9, of een LDO zit gedraaid."},
 {t:"Interne 1,8 V",setting:"Ω",red:"hete pad van C24, daarna C34",black:"J24 pin 3",exp:"hoger dan ~100 Ω",small:"LDOO-pin 18 van U10 en U11",
  fail:"Laag: brug bij pin 18/19 van die DAC, of een defecte C24/C34. Op het eerste bord was C34 (U11) kortgesloten; til één kant van de condensator op om het verschil te zien. Vervanging: 1 µF 0603 (C77386)."},
 {t:"Laadpomp",setting:"Ω",red:"hete pad van C23, daarna C33",black:"J24 pin 3",exp:"niet 0 Ω",small:"VNEG, pin 5",
  fail:"0 Ω: brug bij pin 3–5 van die DAC."},
 {t:"Pompcondensatoren",setting:"Ω",red:"één pad van C22, daarna C32",black:"ander pad van dezelfde condensator",exp:"niet 0 Ω",small:"CAPP–CAPM, pin 2 en 4",
  fail:"0 Ω: brug tussen pin 2, 3 en 4 van die DAC."},
 {t:"Lijnuitgangen",setting:"Ω",red:"J24 pin 17, 18, 19 en 20 om de beurt",black:"J24 pin 3",exp:"niet 0 Ω",small:"FL, FR, RL, RR",
  fail:"0 Ω: brug bij C30, C31, C40 of C41 (2,2 nF)."},
 {t:"Serieweerstanden",setting:"Ω",red:"één pad van R48, R49, R50, R51",black:"ander pad",exp:"≈ 470 Ω elk",small:"",
  fail:"OL: weerstand slecht gesoldeerd. Veel lager: brug."},
 {t:"I2S-lijnen",setting:"Ω",red:"J24 pin 5, 7, 9 en 10 om de beurt",black:"J24 pin 3",exp:"niet 0 Ω",small:"pin 9 en 10 onderling: hoog",
  fail:"0 Ω: brug bij pin 13–16 van U10 of U11."},
 {t:"Mute-lijn",setting:"Ω",red:"J24 pin 12 (XSMT)",black:"J24 pin 3",exp:"niet 0 Ω",small:"de pull-down zit op het main board",
  fail:"0 Ω: brug bij pin 17 van U10 of U11. De DAC's blijven dan altijd gedempt."},
]},
  {id:'audp', name:"Eerste keer voeden", next:"De audiomodule is klaar.", steps:[
 {t:"Aansluiten op 5 V",info:true,body:`
  <p>Doe dit pas als alle multimetermetingen van de audiomodule kloppen. Module los, niets aangesloten.</p>
  <p>Labvoeding <b>uit</b>. Stel in op <b>5,0 V</b> en een stroomgrens van <b>100 mA</b>. Plus op <b>J24 pin 1</b>, min op <b>J24 pin 3</b>.</p>`},
 {t:"Inschakelen",setting:"display van de labvoeding",exp:"minder dan ~50 mA",small:"zonder I2S-klok staan de DAC's in rust",
  fail:"Op de stroomgrens: meteen uit, voel of U8, U9, U10 of U11 warm wordt en meld het."},
 {t:"3,3 V analoog",setting:"V DC",red:"hete pad van C28",black:"J24 pin 3",exp:"3,25 – 3,35 V",small:"U8",
  fail:"0 V: U8 (pin 3 is EN, hoort aan 5 V). Iets anders: meld de waarde."},
 {t:"3,3 V digitaal",setting:"V DC",red:"hete pad van C29",black:"J24 pin 3",exp:"3,25 – 3,35 V",small:"U9",
  fail:"0 V: U9."},
 {t:"Interne 1,8 V",setting:"V DC",red:"hete pad van C24, daarna C34",black:"J24 pin 3",exp:"≈ 1,8 V",small:"LDOO van U10 en U11",
  fail:"0 V bij één DAC: die krijgt geen 3,3 V digitaal (pin 20) of zit slecht gesoldeerd."},
 {t:"Lijnuitgangen in rust",setting:"V DC",red:"J24 pin 17, 18, 19 en 20 om de beurt",black:"J24 pin 3",exp:"≈ 0 V (binnen ±0,05 V)",small:"de uitgangen zijn rond 0 V gecentreerd",
  fail:"Een vaste spanning op een uitgang: kijk naar de pinnen 6 en 7 van die DAC en meld de waarde."},
 {t:"Op het main board",info:true,body:`
  <p>Voeding uit. Steek de module op <b>J23</b> van het main board en zet hem vast op standoff <b>H6</b>. Sluit de VIM3 aan met de lintkabel op J2, zekering in F4 en JP1 erop (service), zodat de VIM3 aan blijft.</p>
  <p>Start Android. De firmware haalt de mute eraf zodra de VHAL verbinding heeft, of 30 seconden nadat de VIM3 is opgestart.</p>`},
 {t:"Mute eraf",setting:"V DC",red:"niet-GND-kant van R47 (rechts van de hub U13)",black:"GND",exp:"≈ 3 V",small:"DAC_XSMT; 0 V = gedempt",
  fail:"0 V na een minuut: de firmware houdt de DAC's gedempt. Meld het; dan kijken we naar de VHAL-verbinding."},
 {t:"Laadpomp onder klok",setting:"V DC",red:"hete pad van C23",black:"GND",exp:"negatief, ≈ −3 V",small:"speel iets af, zodat er een I2S-klok is",
  fail:"0 V terwijl er geluid speelt: de DAC krijgt geen klok (BCLK of LRCK, J23 pin 5 en 7)."},
 {t:"Testtoon voor",setting:"V AC",red:"J8 pin 3 (FL), daarna pin 4 (FR)",black:"J8 pin 5 (LINE_GND)",exp:"≈ 0,5 – 2 V AC",small:"1 kHz-toon, volume hoog; volle schaal is 2,1 V",
  fail:"0 V: kijk welke kant ontbreekt. Beide weg: I2S-data (J23 pin 9), de audio-uitvoer in Android of de mute-stap."},
 {t:"Testtoon achter",setting:"V AC",red:"J8 pin 1 (RL), daarna pin 2 (RR)",black:"J8 pin 5",exp:"≈ 0,5 – 2 V AC",small:"alleen als Android 4 kanalen naar de tweede DAC stuurt",
  fail:"Voor werkt en achter niet: meestal software (audio-HAL stuurt DOUT1 niet). Hardware: J23 pin 10 en U11 pin 14."},
]},
  ],
};
